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

    name = input("Use existing config file? (y/n): ")

    if name == "y":
        print("Setup complete!")
    
    else:
    # testing

        out = "configs/test.json"
        result = prompt_dict_of_floats("A", [1,2,3,4])

        with open(out, "w") as f:
            json.dump(result, f, indent=2)

        print(f"\nConfig saved to {out}")