"""
simulate_elections.py
- Inputs: run_name, district_configs, and voter profile CSVs in outputs/profiles/<run_name>/<mode>/<district_num>/
- Outputs: winner JSONs in outputs/election_results/<run_name>_election_results/<mode>/
"""

from __future__ import annotations

import json
import os
from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import Any, Iterable, List

from joblib import Parallel, delayed

# Optional progress bar for joblib.
try:
    from joblib_progress import joblib_progress 
except Exception: 
    joblib_progress = None 

from votekit import RankProfile
from votekit.elections import FastSTV as STV, Plurality



# Helpers / config handling

@dataclass(frozen=True)
class DistrictConfig:
    """One district configuration: number of districts and winners per district."""
    num_districts: int
    winners: int


def _parse_district_configs(raw: Any) -> List[DistrictConfig]:
    """
    Accepts either:
      - newer schema: [{"num_districts": 5, "winners": 2}, ...]
      - older schema: [{80: 1}, {20: 4}, ...]
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
        # Single-winner election, plurality
        # FIX need to add IRV logic
        elected = Plurality(profile, m=1).get_elected()
        return _candidate_list_from_elected(elected)


def simulate_elections(config_path) -> None:
    """
    Run election simulations for all profiles described by config.
    """
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    run_name = str(config["run_name"])
    district_configs = _parse_district_configs(config["district_configs"])

    modes = ["slate_pl", "slate_bt", "cambridge"]
    # could add n_jobs to config file
    n_jobs = -1

    out_root = Path("outputs") / "election_results" / f"{run_name}_election_results"
    out_root.mkdir(parents=True, exist_ok=True)

    for mode in modes:
        # profile path
        profile_folder = Path(f"./outputs/profiles/{config['run_name']}/{mode}/")

        output_dir = out_root / mode
        output_dir.mkdir(parents=True, exist_ok=True)

        for dc in district_configs:
            all_profile_files = glob(f"{profile_folder}/{dc.num_districts}/*.csv")

            desc = f"Running elections for {dc.num_districts} districts, {dc.winners} winner(s), mode={mode}"
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
                f"{run_name}_{dc.num_districts}_districts_{dc.winners}_winners_for_voter_mode_{mode}.json"
            )
            with open(out_path, "w", encoding="utf-8") as f:
                json.dump(
                    {
                        "run_name": run_name,
                        "voter_mode": mode,
                        "district_num": dc.num_districts,
                        "winners_per_district": dc.winners,
                        "profile_files": all_profile_files,
                        "winners": winners_list,
                    },
                    f,
                    indent=2,
                )

            print(f"[simulate_elections] Wrote: {out_path}")