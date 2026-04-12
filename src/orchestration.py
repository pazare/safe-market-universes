from __future__ import annotations

import json
from pathlib import Path
from typing import Any, TypedDict

from langgraph.graph import END, START, StateGraph

from .config import OUTPUTS_DIR
from .evaluator import build_agreement_profile, run_evaluator
from .market_data import fetch_market_data
from .models import BatchSummary, DebateSummary, StockRunOutput
from .strategy_agents import run_strategy_a, run_strategy_b, run_strategy_c, run_strategy_debate


class StockTraderState(TypedDict, total=False):
    ticker: str
    run_date: str
    model: str | None
    enable_debate: bool
    market_data: dict[str, Any]
    strategy_a: dict[str, Any]
    strategy_b: dict[str, Any]
    strategy_c: dict[str, Any]
    agreement_profile: dict[str, Any]
    evaluator: dict[str, Any]
    debate_a: dict[str, Any]
    debate_b: dict[str, Any]
    debate_c: dict[str, Any]
    debate: dict[str, Any] | None
    output_record: dict[str, Any]
    output_path: str


def _write_json(path: Path, payload: dict[str, Any]) -> None:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(json.dumps(payload, indent=2), encoding="utf-8")


def _strategy_bundle(state: StockTraderState) -> dict[str, dict[str, Any]]:
    return {
        "strategy_a": state["strategy_a"],
        "strategy_b": state["strategy_b"],
        "strategy_c": state["strategy_c"],
    }


def market_data_node(state: StockTraderState) -> StockTraderState:
    return {"market_data": fetch_market_data(state["ticker"])}


def strategy_a_node(state: StockTraderState) -> StockTraderState:
    return {
        "strategy_a": run_strategy_a(
            state["ticker"],
            state["market_data"],
            model=state.get("model"),
        )
    }


def strategy_b_node(state: StockTraderState) -> StockTraderState:
    return {
        "strategy_b": run_strategy_b(
            state["ticker"],
            state["market_data"],
            model=state.get("model"),
        )
    }


def strategy_c_node(state: StockTraderState) -> StockTraderState:
    return {
        "strategy_c": run_strategy_c(
            state["ticker"],
            state["market_data"],
            model=state.get("model"),
        )
    }


def agreement_profile_node(state: StockTraderState) -> StockTraderState:
    return {"agreement_profile": build_agreement_profile(_strategy_bundle(state))}


def evaluator_route(state: StockTraderState) -> str:
    return "consensus_summary" if state["agreement_profile"]["agents_agree"] else "disagreement_analysis"


def consensus_summary_node(state: StockTraderState) -> StockTraderState:
    return {
        "evaluator": run_evaluator(
            ticker=state["ticker"],
            market_data=state["market_data"],
            strategies=_strategy_bundle(state),
            agreement_profile=state["agreement_profile"],
            model=state.get("model"),
        )
    }


def disagreement_analysis_node(state: StockTraderState) -> StockTraderState:
    return {
        "evaluator": run_evaluator(
            ticker=state["ticker"],
            market_data=state["market_data"],
            strategies=_strategy_bundle(state),
            agreement_profile=state["agreement_profile"],
            model=state.get("model"),
        )
    }


def post_evaluator_route(state: StockTraderState) -> str:
    if state["agreement_profile"]["agents_agree"] or not state.get("enable_debate", True):
        return "save_output"
    return "debate_dispatch"


def debate_dispatch_node(state: StockTraderState) -> StockTraderState:
    return {}


def debate_a_node(state: StockTraderState) -> StockTraderState:
    strategies = _strategy_bundle(state)
    peers = {key: value for key, value in strategies.items() if key != "strategy_a"}
    return {
        "debate_a": run_strategy_debate(
            "strategy_a",
            state["ticker"],
            state["market_data"],
            state["strategy_a"],
            peers,
            model=state.get("model"),
        )
    }


def debate_b_node(state: StockTraderState) -> StockTraderState:
    strategies = _strategy_bundle(state)
    peers = {key: value for key, value in strategies.items() if key != "strategy_b"}
    return {
        "debate_b": run_strategy_debate(
            "strategy_b",
            state["ticker"],
            state["market_data"],
            state["strategy_b"],
            peers,
            model=state.get("model"),
        )
    }


def debate_c_node(state: StockTraderState) -> StockTraderState:
    strategies = _strategy_bundle(state)
    peers = {key: value for key, value in strategies.items() if key != "strategy_c"}
    return {
        "debate_c": run_strategy_debate(
            "strategy_c",
            state["ticker"],
            state["market_data"],
            state["strategy_c"],
            peers,
            model=state.get("model"),
        )
    }


def debate_summary_node(state: StockTraderState) -> StockTraderState:
    participants = {
        "strategy_a": state["debate_a"],
        "strategy_b": state["debate_b"],
        "strategy_c": state["debate_c"],
    }
    post_debate_results = {
        key: {
            "name": value["name"],
            "decision": value["updated_decision"],
            "confidence": value["updated_confidence"],
            "justification": value["response_to_peers"],
        }
        for key, value in participants.items()
    }
    debate = DebateSummary(
        triggered=True,
        any_position_changed=any(participant["changed_position"] for participant in participants.values()),
        any_confidence_changed=any(participant["confidence_changed"] for participant in participants.values()),
        changed_strategies=[
            participant["name"] for participant in participants.values() if participant["changed_position"]
        ],
        post_debate_agreement_profile=build_agreement_profile(post_debate_results),
        participants=participants,
    ).model_dump()
    return {"debate": debate}


def save_output_node(state: StockTraderState) -> StockTraderState:
    record = StockRunOutput(
        ticker=state["ticker"],
        run_date=state["run_date"],
        market_data_summary=state["market_data"],
        strategy_a=state["strategy_a"],
        strategy_b=state["strategy_b"],
        strategy_c=state["strategy_c"],
        evaluator=state["evaluator"],
        debate=state.get("debate"),
    ).model_dump()

    output_path = OUTPUTS_DIR / f"{state['ticker']}.json"
    _write_json(output_path, record)
    return {"output_record": record, "output_path": str(output_path)}


def build_graph():
    graph = StateGraph(StockTraderState)
    graph.add_node("market_data", market_data_node)
    graph.add_node("strategy_a", strategy_a_node)
    graph.add_node("strategy_b", strategy_b_node)
    graph.add_node("strategy_c", strategy_c_node)
    graph.add_node("agreement_profile", agreement_profile_node)
    graph.add_node("consensus_summary", consensus_summary_node)
    graph.add_node("disagreement_analysis", disagreement_analysis_node)
    graph.add_node("debate_dispatch", debate_dispatch_node)
    graph.add_node("debate_a", debate_a_node)
    graph.add_node("debate_b", debate_b_node)
    graph.add_node("debate_c", debate_c_node)
    graph.add_node("debate_summary", debate_summary_node)
    graph.add_node("save_output", save_output_node)

    graph.add_edge(START, "market_data")
    graph.add_edge("market_data", "strategy_a")
    graph.add_edge("market_data", "strategy_b")
    graph.add_edge("market_data", "strategy_c")
    graph.add_edge(["strategy_a", "strategy_b", "strategy_c"], "agreement_profile")
    graph.add_conditional_edges(
        "agreement_profile",
        evaluator_route,
        {
            "consensus_summary": "consensus_summary",
            "disagreement_analysis": "disagreement_analysis",
        },
    )
    graph.add_conditional_edges(
        "consensus_summary",
        post_evaluator_route,
        {
            "save_output": "save_output",
            "debate_dispatch": "debate_dispatch",
        },
    )
    graph.add_conditional_edges(
        "disagreement_analysis",
        post_evaluator_route,
        {
            "save_output": "save_output",
            "debate_dispatch": "debate_dispatch",
        },
    )
    graph.add_edge("debate_dispatch", "debate_a")
    graph.add_edge("debate_dispatch", "debate_b")
    graph.add_edge("debate_dispatch", "debate_c")
    graph.add_edge(["debate_a", "debate_b", "debate_c"], "debate_summary")
    graph.add_edge("debate_summary", "save_output")
    graph.add_edge("save_output", END)

    return graph.compile()


def write_summary(records: list[dict[str, Any]]) -> Path:
    summary = BatchSummary(
        strategies=["Momentum Trader", "Value Contrarian", "Volatility Averse"],
        stocks_analyzed=[record["ticker"] for record in records],
        total_agreements=sum(1 for record in records if record["evaluator"]["agents_agree"]),
        total_disagreements=sum(1 for record in records if not record["evaluator"]["agents_agree"]),
        two_vs_one_splits=sum(
            1
            for record in records
            if record["evaluator"]["agreement_profile"]["disagreement_type"] == "two_vs_one_split"
        ),
        three_way_splits=sum(
            1
            for record in records
            if record["evaluator"]["agreement_profile"]["disagreement_type"] == "three_way_split"
        ),
        debates_triggered=sum(1 for record in records if record.get("debate")),
        debates_with_position_change=sum(
            1 for record in records if record.get("debate") and record["debate"]["any_position_changed"]
        ),
        results=[
            {
                "ticker": record["ticker"],
                "a_decision": record["strategy_a"]["decision"],
                "b_decision": record["strategy_b"]["decision"],
                "c_decision": record["strategy_c"]["decision"],
                "agree": record["evaluator"]["agents_agree"],
                "disagreement_type": record["evaluator"]["agreement_profile"]["disagreement_type"],
                "debate_changed_any_position": (record.get("debate") or {}).get("any_position_changed", False),
            }
            for record in records
        ],
    ).model_dump()
    output_path = OUTPUTS_DIR / "summary.json"
    _write_json(output_path, summary)
    return output_path


def export_graph_mermaid(compiled_graph, destination: Path) -> Path | None:
    """
    Best-effort graph export for the report. If the local LangGraph version
    does not expose Mermaid rendering helpers, the workflow still runs.
    """
    try:
        mermaid = compiled_graph.get_graph().draw_mermaid()
    except Exception:
        return None
    destination.write_text(mermaid, encoding="utf-8")
    return destination
