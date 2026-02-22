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


## can decide how much we really want to prompt user
def build_config():

    # dict inits
    slate_to_candidates = {}
    cohesion_parameters = {}
    alphas = {}

    # get defaults
    chain_length = DEFAULTS["chain_length"]
    num_subsamples = DEFAULTS["num_subsamples"]
    num_voters = DEFAULTS["num_voters"]
    num_reps = DEFAULTS["num_reps"]

    # collect basic user input
    run_name = prompt("run_name")
    geodata_path = prompt("geodata_path")
    population_column = prompt("population_column")
    pop_of_interest_col = prompt("pop_of_interest_column")

    num_districts = int(prompt("num_districts"))
    winners       = int(prompt("winners"))
    total_seats   = num_districts * winners

    # collect group names
    groups_raw = prompt("Group names (comma-separated, e.g. A,B)")
    groups = [g.strip() for g in groups_raw.split(",")]

    # collect per-group info
    for g in groups:
        cands_raw = prompt(f"  Candidate names for group {g} (comma-separated)")
        slate_to_candidates[g] = [c.strip() for c in cands_raw.split(",")]

    for g in groups:
        cohesion_parameters[g] = prompt_dict_of_floats(f"Cohesion parameters for group {g}:", groups)

    for g in groups:
        alphas[g] = prompt_dict_of_floats(f"Alpha parameters for group {g}:", groups)

    turnout = prompt_dict_of_floats("Turnout per group:", groups)

    focal_group = groups[0] # could also prompt this

    # can more of these be derived
    return {
        "run_name":                run_name,
        "geodata_path":            geodata_path,
        "gerrychain_output_dir":   f"outputs/districts/{run_name}",
        "population_column":       population_column,
        "pop_of_interest_column":  pop_of_interest_col,
        "total_seats":             total_seats,
        "district_configs":        [{"num_districts": num_districts, "winners": winners}], # may need to build this out more
        "chain_length":            chain_length,
        "num_subsamples":          num_subsamples,
        "num_reps":                num_reps,
        "num_voters":              num_voters,
        "slate_to_candidates":     slate_to_candidates,
        "turnout":                 turnout,
        "focal_group":             focal_group,
        "cohesion_parameters":     cohesion_parameters,
        "alphas":                  alphas,
      
    }

if __name__ == "__main__":

    name = input("Use existing config file? (y/n): ")

    if name == "y": # make more robust later
        print("Setup complete!")
    
    else:

        
        result = build_config()
        out = f"configs/{result["run_name"]}.json"

        with open(out, "w") as f:
            json.dump(result, f, indent=2)

        print(f"\nConfig saved to {out}")