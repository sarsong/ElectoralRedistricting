from glob import glob
from votekit.ballot_generator import (
    BlocSlateConfig,
    slate_pl_profile_generator,
    slate_bt_profile_generator,
    cambridge_profile_generator,
)
from joblib import Parallel, delayed
from joblib_progress import joblib_progress
import json
from pathlib import Path
import random
import numpy as np
import os
import time


generator_name_to_function = {
    "slate_pl": slate_pl_profile_generator,
    "slate_bt": slate_bt_profile_generator,
    "cambridge": cambridge_profile_generator,
}

def process_settings_file(settings_file, profile_folder, mode, duplicate_indx):
    with open(settings_file, "r") as f:
        settings = json.load(f)
    config = BlocSlateConfig(
        n_voters = settings['num_voters'],
        slate_to_candidates=settings["slate_to_candidates"],
        bloc_proportions=settings["bloc_proportions"],
        cohesion_mapping=settings["cohesion_parameters"],
    )

    config.set_dirichlet_alphas(settings["alphas"])
    setting_file_stem = Path(settings_file).stem

    output_file = (
        profile_folder
        / f"{setting_file_stem.replace('sample_settings', 'profile')}_v{duplicate_indx}.csv"
    )
    profile = generator_name_to_function[mode](config)
    profile.to_csv(output_file)

def generate_profiles(config_path):
    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    num_reps = config['num_reps']
    for duplicate_indx in range(num_reps):
        rep_start = time.perf_counter()
        print(f"[rep {duplicate_indx + 1}/{num_reps}] Start at {time.strftime('%Y-%m-%d %H:%M:%S')}")
        district_nums =  [config['district_configs'][0]['num_districts']]
        for district_num in district_nums:
            for mode in ["slate_pl", "slate_bt", "cambridge"]:
                settings_folder = Path(f"./outputs/settings/{config['run_name']}_settings/{district_num}")
                profile_folder = Path(f"./outputs/profiles/{config['run_name']}/{mode}/{district_num}")
                profile_folder.mkdir(exist_ok=True, parents=True)

                all_settings_files = glob(f"{settings_folder}/*.json")

                with joblib_progress(
                    description=f"[rep {duplicate_indx + 1:03d}/{num_reps}] Generating VK profiles for {district_num:02d} districts and voter model {mode}",
                    total=len(all_settings_files),
                ):
                    Parallel(n_jobs=-1)(
                        delayed(process_settings_file)(settings_file, profile_folder, mode, duplicate_indx)
                        for settings_file in all_settings_files
                    )
        rep_elapsed = time.perf_counter() - rep_start
        print(f"[rep {duplicate_indx + 1}/{num_reps}] Done in {rep_elapsed:.1f}s")
