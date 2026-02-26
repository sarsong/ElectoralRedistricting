"""
summarize_results.py

Expected inputs:
- Election results:
    outputs/election_results/<run_name>_election_results/<model>/*.json
- Settings:
    outputs/settings/<run_name>_settings/<district_num>/*.json

Usage:
    python summarize_results.py --config-path configs/your_run.json
"""

from __future__ import annotations

import argparse
import json
import re
from dataclasses import dataclass
from glob import glob
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple
import geopandas as gpd

import pandas as pd
import matplotlib.pyplot as plt


# ----------------------------
# Config parsing
# ----------------------------

@dataclass(frozen=True)
class DistrictConfig:
    num_districts: int
    winners: int


def _parse_district_configs(raw: Any) -> List[DistrictConfig]:
    """Accepts either [{"num_districts": 5, "winners": 2}, ...] or legacy [{80:1}, ...]."""
    if not isinstance(raw, list):
        raise ValueError("district_configs must be a list")

    out: List[DistrictConfig] = []
    for item in raw:
        if isinstance(item, dict) and "num_districts" in item and "winners" in item:
            out.append(DistrictConfig(int(item["num_districts"]), int(item["winners"])))
        elif isinstance(item, dict) and len(item) == 1:
            (k, v), = item.items()
            out.append(DistrictConfig(int(k), int(v)))
        else:
            raise ValueError(
                "Each district_configs entry must be either "
                '{"num_districts": <int>, "winners": <int>} or {<int>: <int>}.'
            )
    return out


# ----------------------------
# Parsing helpers
# ----------------------------


def _parse_plan_district_rep_from_path(p: str | Path):
    s = str(p)

    # plan: match "district_plan_000" (preferred) OR "plan_000"
    m_plan = re.search(r"(?:district[_-]?plan[_-]?|plan[_-]?)(\d+)", s, flags=re.IGNORECASE)
    plan = int(m_plan.group(1)) if m_plan else None

    # district: collect *all* occurrences like "district_00" and take the last one
    districts = re.findall(r"district[_-]?(\d+)", s, flags=re.IGNORECASE)
    district = int(districts[-1]) if districts else None

    # replicate/version: your files use v0, v1... so parse "v0"
    m_v = re.search(r"(?:^|[_-])v(\d+)(?:\D|$)", s, flags=re.IGNORECASE)
    rep = int(m_v.group(1)) if m_v else None

    return plan, district, rep


def _is_focal_candidate(candidate: str, focal_group: str, slate_to_candidates: Dict[str, List[str]]) -> bool:
    """Candidate is focal if in slate list OR matches prefix convention (e.g., 'A1' startswith 'A')."""
    focal_list = set(map(str, slate_to_candidates.get(focal_group, [])))
    c = str(candidate)

    if c in focal_list:
        return True
    if len(focal_group) == 1 and c.startswith(focal_group):
        return True
    return False


def count_focal_winners(
    winners: Iterable[str],
    focal_group: str,
    slate_to_candidates: Dict[str, List[str]],
) -> int:
    """Count how many winners in this election are from the focal group."""
    return sum(1 for w in winners if _is_focal_candidate(str(w), focal_group, slate_to_candidates))


def _load_json(path: Path) -> Dict[str, Any]:
    with open(path, "r", encoding="utf-8") as f:
        return json.load(f)


def _find_settings_file(
    settings_dir: Path,
    *,
    plan: Optional[int],
    district: Optional[int],
) -> Optional[Path]:
    """
    Locate the settings file for (plan, district) matching the generator naming:

        sample_vk_sample_settings_district_plan_{sample_idx:03d}_district_{district:02d}.json

    We first try the exact expected filename when both plan and district are known.
    If not found, we fall back to glob-based best-effort matching.
    """
    if not settings_dir.exists():
        return None

    # 1) Exact match for the known generator format
    if plan is not None and district is not None:
        exact = settings_dir / f"sample_vk_sample_settings_district_plan_{plan:03d}_district_{district:02d}.json"
        if exact.exists():
            return exact

    # 2) Best-effort matching (tolerant of minor naming variations)
    patterns: List[str] = []
    if plan is not None and district is not None:
        patterns.extend([
            f"*district_plan_{plan:03d}*district_{district:02d}.json",
            f"*plan_{plan:03d}*district_{district:02d}.json",
            f"*plan*{plan}*district*{district:02d}*.json",
            f"*plan*{plan}*district*{district}*.json",
        ])
    elif plan is not None:
        patterns.extend([
            f"*district_plan_{plan:03d}*.json",
            f"*plan_{plan:03d}*.json",
            f"*plan*{plan}*.json",
        ])
    elif district is not None:
        patterns.extend([
            f"*district_{district:02d}.json",
            f"*district*{district:02d}*.json",
        ])

    for pat in patterns:
        hits = sorted(settings_dir.glob(pat))
        if hits:
            return hits[0]

    # 3) If there is exactly one file, return it (useful for quick debugging)
    all_files = sorted(settings_dir.glob("*.json"))
    if len(all_files) == 1:
        return all_files[0]
    return None


# ----------------------------
# Core summarization
# ----------------------------

def summarize_results(
    config: Dict[str, Any],
    *,
    models: Optional[Sequence[str]] = None,
    election_results_root: Path = Path("outputs") / "election_results",
    settings_root: Path = Path("outputs") / "settings",
    out_root: Path = Path("outputs") / "summaries",
) -> Path:
    """
    Produce a CSV + histogram PNGs. Returns path to the summary folder.
    """
    run_name = str(config["run_name"])
    district_configs = _parse_district_configs(config["district_configs"])
    focal_group = str(config["focal_group"])
    slate_to_candidates = config.get("slate_to_candidates", {}) or {}

    geodata_path = Path(config["geodata_path"])
    gdf = gpd.read_file(geodata_path)
    vap = sum(gdf[config["population_column"]])
    ivap = sum(gdf[config["pop_of_interest_column"]])
    iprop = ivap/vap

    turnout = config["turnout"]
    cohesion_parameters = config["cohesion_parameters"]
    if len(turnout) != 2:
        raise ValueError("Turnout does not have exactly two keys")
    non_focal_group = next(k for k in turnout if k != focal_group)
    iprop_turnout = iprop*turnout[focal_group] / (iprop*turnout[focal_group] + (1-iprop)*turnout[non_focal_group])

    # Compute combined support
    focal_group_cohesion = cohesion_parameters[focal_group]
    non_focal_group_cohesion = cohesion_parameters[non_focal_group]
    i_cs_turnout = iprop_turnout*focal_group_cohesion[focal_group] + (1-iprop_turnout)*non_focal_group_cohesion[focal_group]

    if models is None:
        models = ["slate_pl", "slate_bt", "cambridge"]

    # Input roots
    results_dir = election_results_root / f"{run_name}_election_results"
    if not results_dir.exists():
        raise FileNotFoundError(f"Could not find election results directory: {results_dir}")

    # Output roots
    summary_dir = out_root / f"{run_name}_summary"
    summary_dir.mkdir(parents=True, exist_ok=True)
    figs_dir = summary_dir / "figures"
    figs_dir.mkdir(parents=True, exist_ok=True)

    rows: List[Dict[str, Any]] = []

    for dc in district_configs:
        # Settings directory is grouped by district_num per design doc
        settings_dir = settings_root / str(dc.num_districts)  # CHECK if matches settings_generator naming

        for model in models:
            # Find results files for this model & district config.
            model_dir = results_dir / model
            if not model_dir.exists():
                continue

            for rf in sorted(model_dir.glob("*.json")):
                data = _load_json(rf)
                
               
                district_num = int(data.get("district_num", dc.num_districts))
                winners_per_district = int(data.get("winners_per_district", dc.winners))
                voter_model = str(data.get("voter_model", model))
                if district_num != dc.num_districts or winners_per_district != dc.winners or voter_model != model:
                    continue

                winners_all: List[List[str]] = data.get("winners", [])
                profile_files: Optional[List[str]] = data.get("profile_files")  

                # Build per-simulation rows
                for idx, winners in enumerate(winners_all):
                    plan = district = rep = None
                    plan, district, rep = _parse_plan_district_rep_from_path(profile_files[idx])

                    settings_path = _find_settings_file(settings_dir, plan=plan, district=district)
                    settings_data = _load_json(settings_path) if settings_path else {}
                    # FIX names -- should be column names specified in config
                    total_vap = settings_data.get("total_vap", None)
                    total_ivap = settings_data.get("total_hvap", None)
                    # partisan has p_prop_census -- add?

                    focal_seats = count_focal_winners(winners, focal_group, slate_to_candidates)

                    rows.append({
                        "run_name": run_name,
                        "plan": plan,
                        "num_districts": district_num,
                        "seats_per_district": winners_per_district,
                        "election_method": "STV", # FIX
                        "mode": model,
                        "district_id": district,
                        "rep": rep,
                        "simulation_index": idx,
                        "focal_group": focal_group,
                        "focal_seats": focal_seats,
                        config["population_column"]: total_vap,
                        config["pop_of_interest_column"]: total_ivap,
                        "combined_support": i_cs_turnout,
                    })

    df = pd.DataFrame(rows)

    # Save dataframe
    csv_path = summary_dir / f"{run_name}_summary.csv"
    df.to_csv(csv_path, index=False)

   # Plan-level totals across districts
    df_plan = (
        df.groupby(
            ["plan", "num_districts", "seats_per_district", "mode", "election_method", "rep"],
            as_index=False
        )
        .agg({"focal_seats": "sum"})
    )

    mode_colors = {
        "cambridge": "#E32636",
        "slate_bt": "#FFBF00",
        "slate_pl": "#8DB600",
    }

    legend_mapping = {
        "slate_bt": "Deliberative",
        "slate_pl": "Impulsive",
        "cambridge": "Cambridge",
    }
    desired_order = ["slate_pl", "slate_bt", "cambridge"]

    for (num_dist, seats_per_district, elm), group_distn in df_plan.groupby(["num_districts", "seats_per_district", "election_method"]):
        fig, ax = plt.subplots(figsize=(6, 4))

        # Plot histogram for each mode
        for mode, group_mode in group_distn.groupby("mode"):
            if group_mode["focal_seats"].empty:
                continue
            ax.hist(
                group_mode["focal_seats"],
                bins=range(int(group_mode["focal_seats"].min()), int(group_mode["focal_seats"].max()) + 2),
                align="left",
                edgecolor="gray",
                linewidth=0.5,
                color=mode_colors.get(mode, "xkcd:light gray"),
                alpha=0.5,
                label=mode,
            )

        # styling
        for spine in ax.spines.values():
            spine.set_linewidth(0.5)

        total_seats = config["total_seats"]
        #FIX
        ylim = 12

        ax.set_xlim(-1, total_seats + 1)
        ax.set_ylim(0, ylim)
        ax.set_xticks(range(0, total_seats + 1, 10))
        ax.set_xlabel(f"Seats")
        ax.set_title(f"Representation for {focal_group}-preferred candidates, {num_dist} x {seats_per_district} {elm}")
        ax.tick_params(axis="both", which="major", labelsize=8)

        # legend (modes only, renamed + ordered)
        handles, labels = ax.get_legend_handles_labels()
        handle_map = {label: handle for handle, label in zip(handles, labels) if label in legend_mapping}

        ordered_handles, ordered_labels = [], []
        for mode_key in desired_order:
            if mode_key in handle_map:
                ordered_handles.append(handle_map[mode_key])
                ordered_labels.append(legend_mapping[mode_key])

        ax.legend(ordered_handles, ordered_labels, title="Mode", fontsize=8)

        # ---- vertical lines ----
        color_cs = "xkcd:brownish grey"
        color_iprop = "xkcd:purplish brown"

        i_cs_share = i_cs_turnout * total_seats
        ax.axvline(i_cs_share, color=color_cs, linewidth=1)

        ax.text(
            i_cs_share - 0.5,
            ylim * 0.90,
            f"Combined support\n{i_cs_turnout*100:.2f}%\n({i_cs_share:.2f} seats)",
            va="center",
            ha="right",
            fontsize=8,
            color=color_cs,
        )

        i_share = iprop * total_seats
        ax.axvline(i_share, color=color_iprop, linestyle=":", linewidth=1)

        ax.text(
            i_share + 0.5,
            ylim * 0.90,
            f"Focal group VAP\n{iprop*100:.2f}%\n({i_share:.2f} seats)",
            va="center",
            ha="left",
            fontsize=8,
            color=color_iprop,
        )

        fig_path = figs_dir / f"{run_name}_{num_dist}x{seats_per_district}_{elm}_bymode.png"
        fig.savefig(fig_path, dpi=300, bbox_inches="tight")
        plt.close(fig)

    print(f"[summarize_results] Wrote CSV: {csv_path}")
    print(f"[summarize_results] Figures in: {figs_dir}")
    return summary_dir


# ----------------------------
# CLI
# ----------------------------

def _parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Summarize election results into a dataframe + histograms.")
    p.add_argument("--config-path", required=True, help="Path to pipeline config JSON.")
    p.add_argument(
        "--models",
        nargs="*",
        default=None,
        help="Optional list of voter model folder names to include (default: slate_pl slate_bt cambridge).",
    )
    p.add_argument(
        "--election-results-root",
        default="outputs/election_results",
        help="Root containing <run_name>_election_results/.",
    )
    p.add_argument(
        "--settings-root",
        default="outputs/settings",
        help="Root containing <run_name>_settings/<district_num>/.",
    )
    p.add_argument(
        "--out-root",
        default="outputs/summaries",
        help="Where to write <run_name>_summary/.",
    )
    return p.parse_args()


def main() -> None:
    args = _parse_args()
    config_path = Path(args.config_path)
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    summarize_results(
        config,
        models=args.models,
        election_results_root=Path(args.election_results_root),
        settings_root=Path(args.settings_root),
        out_root=Path(args.out_root),
    )


if __name__ == "__main__":
    main()
