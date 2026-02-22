import argparse
import json
import os

# setting these as constant for now
DEFAULTS = {
    "chain_length": 1000,
    "num_subsamples": 5,
    "num_voters": 10000,
    "num_reps": 2,
}

#helpers
def prompt(label):
    return input(f"{label}: ").strip()

def prompt_dict_of_floats(label, keys):
    result = {}
    print(f"{label}")
    for k in keys:
        result[k] = float(prompt(f"  {k}"))
    return result


def build_config():

    # collect user input
    run_name = prompt("run_name")
    geodata_path = prompt("geodata_path")
    population_column = prompt("population_column")
    pop_of_interest_col = prompt("pop_of_interest_column")

    num_districts = int(prompt("num_districts"))
    winners       = int(prompt("winners"))
    total_seats   = num_districts * winners

    return {
        "run_name":                run_name,
        "geodata_path":            geodata_path,
        "gerrychain_output_dir":   f"outputs/districts/{run_name}",
        "population_column":       population_column,
        "pop_of_interest_column":  pop_of_interest_col,
        "chain_length":            chain_length,
        "num_subsamples":          num_subsamples,
        "total_seats":             total_seats,
        "district_configs":        [{"num_districts": num_districts, "winners": winners}],
        "turnout":                 turnout,
        "num_voters":              num_voters,
        "slate_to_candidates":     slate_to_candidates,
        "focal_group":             focal_group,
        "cohesion_parameters":     cohesion_parameters,
        "alphas":                  alphas,
        "num_reps":                num_reps,
    }

if __name__ == "__main__":

    name = input("Use existing config file? (y/n): ")

    if name == "y": # make more robust later
        print("Setup complete!")
    
    else:

        out = "configs/test.json"
        result = prompt_dict_of_floats("A", [1,2,3,4])

        with open(out, "w") as f:
            json.dump(result, f, indent=2)

        print(f"\nConfig saved to {out}")