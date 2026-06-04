from __future__ import annotations

import argparse
import json
import sys
from datetime import datetime, timezone
from pathlib import Path
from typing import Any

sys.path.insert(0, str(Path(__file__).resolve().parents[1]))

from src.benchmark.artifact_paths import portable_path
from src.benchmark.spec import (
    CANONICAL_EPISODES,
    CANONICAL_HORIZON,
    CANONICAL_JUDGE_SAMPLE_SIZE,
    CANONICAL_SEED,
    CANONICAL_TICKERS,
    OVERSIGHT_BUDGETS,
)
from src.config import OUTPUTS_DIR, ROOT_DIR, load_environment


DEFAULT_SEEDS = [CANONICAL_SEED, CANONICAL_SEED + 1, CANONICAL_SEED + 2]
DEFAULT_MODEL_REGISTRY_PATH = ROOT_DIR / "benchmark_models.json"


def _parse_int_list(raw: str) -> list[int]:
    return [int(item.strip()) for item in raw.split(",") if item.strip()]


def _load_model_registry_offline(path: Path | str | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else DEFAULT_MODEL_REGISTRY_PATH
    payload = json.loads(registry_path.read_text(encoding="utf-8"))
    models = payload.get("default_models", [])
    if not isinstance(models, list) or len(models) != 3:
        raise ValueError("benchmark_models.json must define exactly three default_models.")
    return payload


def _configured_model_names_offline(path: Path | str | None = None) -> list[str]:
    registry = _load_model_registry_offline(path)
    return [item["model"] for item in registry["default_models"]]


def _offline_preflight_report(path: Path | str | None = None) -> dict[str, Any]:
    registry_path = Path(path) if path else DEFAULT_MODEL_REGISTRY_PATH
    registry = _load_model_registry_offline(registry_path)
    return {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "registry_path": portable_path(registry_path),
        "policy": registry.get("policy", {}),
        "live_response_check": False,
        "offline_status_only": True,
        "results": [
            {
                "alias": item["alias"],
                "model": item["model"],
                "role": item.get("role"),
                "status": "not_checked_status_only",
                "available": None,
                "reason": "Skipped live model preflight for offline status/dry-run mode.",
                "live_response_check": False,
            }
            for item in registry["default_models"]
        ],
    }


def _planned_runs(
    *,
    models: list[str],
    seeds: list[int],
    budgets: list[int],
    corruption_settings: list[bool],
    episode_count: int,
    horizon: int,
    judge_sample_size: int,
) -> list[dict]:
    runs = []
    for model in models:
        model_slug = model.replace(".", "_").replace("-", "_")
        for seed in seeds:
            for budget in budgets:
                for corruption_enabled in corruption_settings:
                    corruption_label = "corrupt_on" if corruption_enabled else "corrupt_off"
                    runs.append(
                        {
                            "run_id": f"publication_{model_slug}_seed{seed}_budget{budget}_{corruption_label}",
                            "model": model,
                            "seed": seed,
                            "budget": budget,
                            "corruption_enabled": corruption_enabled,
                            "episode_count": episode_count,
                            "horizon": horizon,
                            "judge_sample_size": judge_sample_size,
                            "ablations": [
                                "committee_only",
                                "committee_plus_abstention",
                                "committee_plus_abstention_plus_overseer",
                                "technical_rule_baseline",
                                "overseer_budget_0",
                                "overseer_budget_1",
                                "overseer_budget_2",
                            ],
                        }
                    )
    return runs


def _run_status(run: dict, outputs_root: Path) -> dict:
    run_dir = outputs_root / run["run_id"]
    summary_path = run_dir / "summary.json"
    progress_path = run_dir / "progress.json"
    status = "missing"
    detail = "No summary or progress file found."

    if summary_path.exists():
        try:
            summary = json.loads(summary_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            status = "summary_unreadable"
            detail = f"summary.json is not valid JSON: {exc}"
        else:
            validation_status = summary.get("artifact_validation", {}).get("status")
            if validation_status == "pass":
                status = "complete"
                detail = "summary.json exists and artifact_validation.status=pass."
            elif validation_status:
                status = "summary_validation_failed"
                detail = f"summary.json exists but artifact_validation.status={validation_status}."
            else:
                status = "summary_unvalidated"
                detail = "summary.json exists but has no artifact_validation.status."
    elif progress_path.exists():
        try:
            progress = json.loads(progress_path.read_text(encoding="utf-8"))
        except json.JSONDecodeError as exc:
            status = "progress_unreadable"
            detail = f"progress.json is not valid JSON: {exc}"
        else:
            status = str(progress.get("status", "progress_present"))
            detail = progress.get("error") or f"progress.json status={status}."

    return {
        **run,
        "status": status,
        "status_detail": detail,
        "run_dir": portable_path(run_dir),
        "summary_path": portable_path(summary_path),
        "progress_path": portable_path(progress_path),
    }


def _annotate_run_statuses(runs: list[dict], outputs_root: Path | str) -> list[dict]:
    root = Path(outputs_root)
    return [_run_status(run, root) for run in runs]


def _select_runs_for_execution(
    runs: list[dict],
    *,
    outputs_root: Path | str,
    resume: bool,
    max_runs: int | None,
    requested_run_ids: list[str],
) -> tuple[list[dict], list[dict]]:
    requested = set(requested_run_ids)
    annotated = _annotate_run_statuses(runs, outputs_root)
    if requested:
        annotated = [run for run in annotated if run["run_id"] in requested]

    skipped: list[dict] = []
    selected: list[dict] = []
    for run in annotated:
        if resume and run["status"] == "complete":
            skipped.append(run)
            continue
        selected.append(run)

    if max_runs is not None:
        selected = selected[:max_runs]
    return selected, skipped


def _refresh_manifest_status(
    *,
    manifest: dict,
    manifest_path: Path,
    runs: list[dict],
    selectable_runs: list[dict],
    outputs_root: Path,
    resume: bool,
    max_runs: int | None,
    requested_run_ids: list[str],
) -> None:
    runs_with_status = _annotate_run_statuses(runs, outputs_root)
    selected_runs, skipped_runs = _select_runs_for_execution(
        selectable_runs,
        outputs_root=outputs_root,
        resume=resume,
        max_runs=max_runs,
        requested_run_ids=requested_run_ids,
    )
    manifest.update(
        {
            "last_status_refresh_at": datetime.now(timezone.utc).isoformat(),
            "runs": runs_with_status,
            "selected_runs": selected_runs,
            "skipped_runs": skipped_runs,
            "selected_run_count": len(selected_runs),
            "skipped_run_count": len(skipped_runs),
            "completed_run_count": sum(1 for row in runs_with_status if row["status"] == "complete"),
        }
    )
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")


def main() -> None:
    load_environment()
    parser = argparse.ArgumentParser(description="Run or preview the Safe MarketUniverses publication matrix.")
    parser.add_argument("--models-config", help="Path to benchmark_models.json.")
    parser.add_argument("--seeds", default=",".join(str(seed) for seed in DEFAULT_SEEDS))
    parser.add_argument("--budgets", default=",".join(str(budget) for budget in OVERSIGHT_BUDGETS))
    parser.add_argument("--episode-count", type=int, default=CANONICAL_EPISODES)
    parser.add_argument("--horizon", type=int, default=CANONICAL_HORIZON)
    parser.add_argument("--judge-sample-size", type=int, default=CANONICAL_JUDGE_SAMPLE_SIZE)
    parser.add_argument("--dry-run", action="store_true", help="Write the planned matrix without running it.")
    parser.add_argument("--resume", action="store_true", help="Skip runs whose summary already validates as complete.")
    parser.add_argument("--max-runs", type=int, help="Run at most this many selected runs in this invocation.")
    parser.add_argument(
        "--run-id",
        action="append",
        default=[],
        help="Run only the requested run_id. Can be passed more than once.",
    )
    parser.add_argument(
        "--status-only",
        action="store_true",
        help="Write the manifest with current run statuses but do not execute runs.",
    )
    parser.add_argument(
        "--outputs-root",
        default=str(OUTPUTS_DIR / "benchmark"),
        help="Directory containing publication run output folders.",
    )
    parser.add_argument(
        "--manifest",
        default=str(OUTPUTS_DIR / "benchmark" / "publication_suite_manifest.json"),
        help="Path to write the publication-suite manifest.",
    )
    parser.add_argument(
        "--live-response-check",
        action="store_true",
        help="Make one minimal Responses API call per configured model before selecting runs.",
    )
    args = parser.parse_args()

    registry_path = Path(args.models_config) if args.models_config else None
    if args.status_only or args.dry_run:
        preflight = _offline_preflight_report(registry_path)
    else:
        from src.benchmark.model_registry import preflight_models

        preflight = preflight_models(
            registry_path=registry_path,
            live_response_check=args.live_response_check,
        )
    available_models = [
        row["model"]
        for row in preflight["results"]
        if row["status"] == "available"
    ]
    models = _configured_model_names_offline(registry_path)

    runs = _planned_runs(
        models=models,
        seeds=_parse_int_list(args.seeds),
        budgets=_parse_int_list(args.budgets),
        corruption_settings=[False, True],
        episode_count=args.episode_count,
        horizon=args.horizon,
        judge_sample_size=args.judge_sample_size,
    )
    selectable_runs = (
        runs
        if args.dry_run or args.status_only
        else [row for row in runs if row["model"] in set(available_models)]
    )
    outputs_root = Path(args.outputs_root)
    runs_with_status = _annotate_run_statuses(runs, outputs_root)
    selected_runs, skipped_runs = _select_runs_for_execution(
        selectable_runs,
        outputs_root=outputs_root,
        resume=args.resume,
        max_runs=args.max_runs,
        requested_run_ids=args.run_id,
    )
    manifest = {
        "generated_at": datetime.now(timezone.utc).isoformat(),
        "dry_run": args.dry_run,
        "status_only": args.status_only,
        "resume": args.resume,
        "max_runs": args.max_runs,
        "requested_run_ids": args.run_id,
        "outputs_root": portable_path(outputs_root),
        "preflight": preflight,
        "planned_run_count": len(runs),
        "selected_run_count": len(selected_runs),
        "skipped_run_count": len(skipped_runs),
        "runs": runs_with_status,
        "selected_runs": selected_runs,
        "skipped_runs": skipped_runs,
        "unavailable_models": [] if args.status_only or args.dry_run else [
            row for row in preflight["results"] if row["status"] != "available"
        ],
    }
    manifest_path = Path(args.manifest)
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    manifest_path.write_text(json.dumps(manifest, indent=2), encoding="utf-8")
    print(f"Wrote publication suite manifest to {manifest_path}")

    if args.dry_run or args.status_only:
        for row in selected_runs if (args.resume or args.max_runs or args.run_id) else runs_with_status:
            print(
                "DRY RUN "
                f"{row['run_id']} model={row['model']} seed={row['seed']} "
                f"budget={row['budget']} corruption={row['corruption_enabled']} "
                f"status={row['status']}"
            )
        return

    if not available_models:
        raise RuntimeError("No configured benchmark models are available. See the preflight report in the manifest.")

    for row in selected_runs:
        print(f"Running {row['run_id']}")
        try:
            from src.benchmark.runtime import run_safe_market_universes

            run_safe_market_universes(
                tickers=CANONICAL_TICKERS,
                episode_count=row["episode_count"],
                horizon=row["horizon"],
                oversight_budget=row["budget"],
                seed=row["seed"],
                model=row["model"],
                enable_corruption=row["corruption_enabled"],
                judge_sample_size=row["judge_sample_size"],
                run_id=row["run_id"],
                ensure_ticker_coverage=True,
                resume=args.resume,
            )
        finally:
            _refresh_manifest_status(
                manifest=manifest,
                manifest_path=manifest_path,
                runs=runs,
                selectable_runs=selectable_runs,
                outputs_root=outputs_root,
                resume=args.resume,
                max_runs=args.max_runs,
                requested_run_ids=args.run_id,
            )


if __name__ == "__main__":
    main()
