"""
simulate_elections.py
- Inputs: run_name, district_configs, and voter profile CSVs in outputs/profiles/<run_name>/<model>/<district_num>/
- Outputs: winner JSONs in outputs/election_results/<run_name>_election_results/<model>/
"""

from __future__ import annotations

import argparse
import json
import os
from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

from joblib import Parallel, delayed

# Optional progress bar for joblib.
try:
    from joblib_progress import joblib_progress  # type: ignore
except Exception:  # pragma: no cover
    joblib_progress = None  # type: ignore

from votekit import RankProfile
from votekit.elections import FastSTV as STV, Plurality


# ----------------------------
# Helpers / config handling
# ----------------------------

@dataclass(frozen=True)
class DistrictConfig:
    """One district configuration: number of districts and winners per district."""
    num_districts: int
    winners: int


def _parse_district_configs(raw: Any) -> List[DistrictConfig]:
    """
    Accepts either:
      - new schema (preferred): [{"num_districts": 5, "winners": 2}, ...]
      - legacy schema from design doc table: [{80: 1}, {20: 4}, ...]
    """
    if not isinstance(raw, list):
        raise ValueError("district_configs must be a list")

    parsed: List[DistrictConfig] = []
    for item in raw:
        if isinstance(item, dict) and "num_districts" in item and "winners" in item:
            parsed.append(DistrictConfig(int(item["num_districts"]), int(item["winners"])))
        elif isinstance(item, dict) and len(item) == 1:
            (k, v), = item.items()
            parsed.append(DistrictConfig(int(k), int(v)))
        else:
            raise ValueError(
                "Each district_configs entry must be either "
                '{"num_districts": <int>, "winners": <int>} or {<int>: <int>}.'
            )
    return parsed


def _candidate_list_from_elected(elected: Iterable[set]) -> List[str]:
    """
    VoteKit elections return an iterable of singleton sets.
    Convert them into a list of candidate IDs/strings.
    """
    winners: List[str] = []
    for s in elected:
        if not s:
            continue
        winners.append(str(next(iter(s))))
    return winners


def process_profile(profile_file: str | Path, n_seats: int) -> List[str]:
    """
    Process one voter profile CSV file: load RankProfile, run election, return winner list.
    """
    profile_path = Path(profile_file)
    profile: RankProfile = RankProfile.from_csv(profile_path)

    if n_seats > 1:
        elected = STV(profile, m=n_seats, simultaneous=False).get_elected()
        return _candidate_list_from_elected(elected)
    else:
        # Single-winner election: use Plurality (mirrors run_all_experiments_parallel.py)
        elected = Plurality(profile, m=1).get_elected()
        return _candidate_list_from_elected(elected)


# def _find_profile_dirs(run_name: str, model: str) -> List[Path]:
#     """
#     Be forgiving about exact folder naming so this stage works with different pipeline layouts.

#     Preferred (design doc):
#       outputs/profiles/<run_name>/<model>/

#     Also supports:
#       outputs/profiles/<run_name>_profiles/<model>/
#       outputs/profiles/<run_name>_profiles/<model>/   (common older naming)
#       outputs/profiles/<run_name>/<model>/            (same as preferred)
#     """
#     candidates = [
#         Path("outputs") / "profiles" / run_name / model,
#         Path("outputs") / "profiles" / f"{run_name}_profiles" / model,
#         Path("outputs") / "profiles" / f"{run_name}_profile" / model,
#     ]
#     return [p for p in candidates if p.exists() and p.is_dir()]

def _find_profile_dirs(run_name: str, model: str) -> List[Path]:
    # 🔥 HARDCODED DEBUG PATH
    debug_root = Path("outputs") / "profiles"

    p = debug_root / model
    return [p] if p.exists() else []


def _list_profile_files(profile_model_root: Path, district_num: int) -> List[str]:
    """
    Returns sorted list of profile CSVs for a given district count.
    Expected layout: <profile_model_root>/<district_num>/*.csv
    """
    return sorted(glob(str(profile_model_root / str(district_num) / "*.csv")))


def simulate_elections(
    config: Dict[str, Any],
    *,
    models: Optional[Sequence[str]] = None,
    n_jobs: int = -1,
) -> None:
    """
    Run election simulations for all profiles described by config.

    Parameters
    ----------
    config:
      Loaded JSON config. Must include:
        - run_name (str)
        - district_configs (list)
      Models default to ["slate_pl", "slate_bt", "cambridge"] if not provided.
    models:
      Which voter models to process.
    n_jobs:
      joblib parallelism; -1 uses all cores.
    """
    run_name = str(config["run_name"])
    district_configs = _parse_district_configs(config["district_configs"])

    if models is None:
        models = ["slate_pl", "slate_bt", "cambridge"]

    out_root = Path("outputs") / "election_results" / f"{run_name}_election_results"
    out_root.mkdir(parents=True, exist_ok=True)

    for model in models:
        # Locate model profile root(s)
        profile_roots = _find_profile_dirs(run_name, model)
        if not profile_roots:
            # Still create output dir so downstream can see the model was attempted.
            (out_root / model).mkdir(parents=True, exist_ok=True)
            print(
                f"[simulate_elections] No profile directory found for model '{model}'. "
                "Looked for: "
                f"outputs/profiles/{run_name}/{model}/ and outputs/profiles/{run_name}_profiles/{model}/"
            )
            continue

        output_dir = out_root / model
        output_dir.mkdir(parents=True, exist_ok=True)

        for dc in district_configs:
            # Merge profile files found under any compatible root
            all_profile_files: List[str] = []
            for root in profile_roots:
                all_profile_files.extend(_list_profile_files(root, dc.num_districts))

            all_profile_files = sorted(set(all_profile_files))
            if not all_profile_files:
                print(
                    f"[simulate_elections] No profiles found for model='{model}', "
                    f"district_num={dc.num_districts} under {', '.join(map(str, profile_roots))}"
                )
                continue

            desc = f"Running elections for {dc.num_districts} districts, {dc.winners} winner(s), model={model}"
            if joblib_progress is not None:
                ctx = joblib_progress(description=desc, total=len(all_profile_files))
            else:
                ctx = None

            if ctx is not None:
                with ctx:
                    winners_list = Parallel(n_jobs=n_jobs)(
                        delayed(process_profile)(pf, dc.winners) for pf in all_profile_files
                    )
            else:
                print(f"[simulate_elections] {desc} (no joblib_progress installed)")
                winners_list = Parallel(n_jobs=n_jobs)(
                    delayed(process_profile)(pf, dc.winners) for pf in all_profile_files
                )

            out_path = output_dir / (
                f"{run_name}_{dc.num_districts}_districts_{dc.winners}_winners_for_voter_model_{model}.json"
            )
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "run_name": run_name,
                        "voter_model": model,
                        "district_num": dc.num_districts,
                        "winners_per_district": dc.winners,
                        "winners": winners_list,
                    },
                    f,
                    indent=2,
                )

            print(f"[simulate_elections] Wrote: {out_path}")


# ----------------------------
# CLI
# ----------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Run FastSTV/Plurality on generated VoteKit profiles.")
    p.add_argument(
        "--config-path",
        required=True,
        help="Path to pipeline config JSON (e.g., configs/your_run.json).",
    )
    p.add_argument(
        "--models",
        nargs="*",
        default=None,
        help=(
            "Optional list of voter model folder names to process. "
            "If omitted, defaults to: impulsive deliberate cambridge"
        ),
    )
    p.add_argument(
        "--n-jobs",
        type=int,
        default=-1,
        help="joblib parallel workers; -1 uses all available cores.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    config_path = Path(args.config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    simulate_elections(config, models=args.models, n_jobs=args.n_jobs)


if __name__ == "__main__":
    main()
