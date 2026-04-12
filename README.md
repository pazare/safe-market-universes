# StockTrader: Signals, Strategies, Disagreement, and Bonus Extensions

This project implements the assignment as a LangGraph workflow grounded in real Yahoo Finance market data. The base system compares two distinct LLM-powered strategies on the same stock snapshot and routes their outputs through an evaluator. The bonus implementation extends that core with:

- a third strategy agent
- disagreement-triggered debate mode
- a historical backtest scorecard in `outputs/backtest.json`

## Strategy lineup

Core assignment pair:

- Strategy A: `Momentum Trader`
- Strategy B: `Value Contrarian`

Bonus third strategy:

- Strategy C: `Volatility Averse`

Why this set works:

- `Momentum Trader` emphasizes short-term vs long-term moving-average structure, recent returns, and volume confirmation.
- `Value Contrarian` emphasizes trailing P/E, RSI, drawdown, and distance from the 52-week range.
- `Volatility Averse` emphasizes realized volatility, ATR, and drawdown risk.

This gives the project a strong analytical contrast:

- trend continuation
- valuation / mean reversion
- risk avoidance

## LLM provider

- Provider: OpenAI
- Default model: `gpt-5.4-mini`

The model is configurable through `OPENAI_MODEL`.

## Framework and toolset

- Orchestration: LangGraph
- Market data: `yfinance`
- LLM SDK: `openai`
- Data wrangling: `pandas`, `numpy`
- Validation: `pydantic`
- Env loading: `python-dotenv`

## Setup

1. Create and activate a virtual environment.

```bash
python3 -m venv .venv
source .venv/bin/activate
```

2. Install dependencies.

```bash
pip install -r requirements.txt
```

3. Add your OpenAI key.

```bash
cp .env.example .env
```

Then edit `.env`:

```bash
OPENAI_API_KEY=your_real_key_here
OPENAI_MODEL=gpt-5.4-mini
```

Important:

- `yfinance` does **not** require a Yahoo Finance API key.
- There is no separate Yahoo credential to submit for this implementation.

## Verify setup

Before the full run:

```bash
python -m src.main --verify-setup
```

This command performs:

- one real Yahoo Finance fetch
- one real OpenAI call

## Run the full workflow

Run the default five-stock batch with all bonus features enabled:

```bash
python -m src.main
```

Current default basket:

- `COST` for a steady, established large-cap case
- `HIMS` for a volatile recent momentum case
- `SMCI` for a sharp decline / drawdown case
- `JNJ` for a sideways or lower-conviction case
- `TSLA` for a disagreement-rich speculative mega-cap case

Run a custom stock list:

```bash
python -m src.main NVDA TSLA JNJ KO
```

Inspect live market data only:

```bash
python -m src.main --market-only NVDA
```

Skip the debate extension:

```bash
python -m src.main --skip-debate
```

Skip the historical backtest:

```bash
python -m src.main --skip-backtest
```

Tune backtest settings:

```bash
python -m src.main --backtest-checkpoints 4 --backtest-forward-days 20 --backtest-hold-band 3.0
```

## Output files

The workflow writes:

- one JSON file per stock in `outputs/`
- one aggregated `outputs/summary.json`
- one historical scorecard in `outputs/backtest.json`

Current canonical output set:

- `outputs/COST.json`
- `outputs/HIMS.json`
- `outputs/SMCI.json`
- `outputs/JNJ.json`
- `outputs/TSLA.json`
- `outputs/summary.json`
- `outputs/backtest.json`

The per-stock JSON files now include:

- Strategy A result
- Strategy B result
- Strategy C result
- evaluator analysis
- debate output when disagreement triggers a second round

These pre-generated outputs are intended to be committed so grading does not require your API key.

## Idempotence and GitHub safety

This project is organized so reruns stay clean:

- rerunning `python -m src.main` overwrites the same per-stock JSON files for the requested tickers
- rerunning the batch also rewrites `outputs/summary.json` and `outputs/backtest.json`
- the workflow does not append duplicate rows or create timestamped output sprawl by default

What is written to disk:

- source files, prompts, reports, and JSON outputs in this workspace
- your local `.env` file if you create it

What is **not** automatically pushed anywhere:

- there is no Git repository until you run `git init`
- nothing is uploaded to GitHub unless you explicitly stage, commit, and push it
- the Codex app's local conversation mode is not a file inside this repository by default

Secret-handling rule:

- `.env` is ignored by [`.gitignore`](/Users/pablo/Desktop/Agentic%20AI/Trading%20Simulation/.gitignore), so your OpenAI key should stay local
- after `git init`, verify that `.env` is still ignored before your first commit

## Backtest methodology

The backtest extension uses recent historical checkpoints per stock and evaluates each strategy’s recommendation against realized forward returns.

Current default methodology:

- `3` checkpoints per stock
- `20` forward trading days
- `3.0%` hold band

Outcome mapping:

- forward return `> +3%` => realized outcome `BUY`
- forward return `< -3%` => realized outcome `SELL`
- otherwise => realized outcome `HOLD`

Important rigor note:

- historical snapshots intentionally omit `trailing_pe` to avoid lookahead bias
- `yfinance.info` exposes live metadata, not historical valuation snapshots
- the Value Contrarian prompt is already designed to lower confidence and rely more on RSI / range signals when valuation is missing

## Report workflow

Pre-filled report assets are already prepared:

- main report draft: `report/report.md`
- AI use appendix draft: `report/ai_use_appendix.md`
- post-run checklist: `report/post_run_fill_guide.md`

Before the OpenAI run, these files already contain:

- architecture explanation
- stock-selection rationale
- documentation-backed design logic
- actual first full-run results
- backtest analysis
- a documented failure / surprise case

The remaining manual step is to export the Markdown drafts to PDF:

- `report/report.md` -> `report/report.pdf`
- `report/ai_use_appendix.md` -> `report/ai_use_appendix.pdf`

## Repository layout

```text
.
├── README.md
├── requirements.txt
├── prompts/
│   ├── debate.txt
│   ├── evaluator.txt
│   ├── strategy_a.txt
│   ├── strategy_b.txt
│   └── strategy_c.txt
├── outputs/
├── report/
│   ├── ai_use_appendix.md
│   ├── langgraph_workflow.mmd
│   ├── post_run_fill_guide.md
│   └── report.md
└── src/
    ├── __init__.py
    ├── backtest.py
    ├── config.py
    ├── evaluator.py
    ├── llm.py
    ├── main.py
    ├── market_data.py
    ├── models.py
    ├── orchestration.py
    └── strategy_agents.py
```

## Documentation references used in implementation

- OpenAI Structured Outputs guide: [Structured outputs](https://platform.openai.com/docs/guides/structured-outputs?api-mode=responses&lang=python)
- OpenAI Responses API reference: [Responses API](https://platform.openai.com/docs/api-reference/responses)
- OpenAI models reference: [Models](https://platform.openai.com/docs/models)
- LangGraph overview: [LangGraph overview](https://docs.langchain.com/oss/python/langgraph)
- LangGraph Graph API guide: [Use the graph API](https://docs.langchain.com/oss/python/langgraph/use-graph-api)
- yfinance README: [yfinance README](https://github.com/ranaroussi/yfinance)
