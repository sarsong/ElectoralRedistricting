import argparse
import json
import os

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

if __name__ == "__main__":
    
    # testing
    result = prompt_dict_of_floats(["A", "B"], [1,2,3,4])
    print(result)