import argparse
import json
import os

# Default parameters
DEFAULTS = {
    "chain_length": 1000,
    "num_subsamples": 5,
    "num_voters": 10000,
    "num_reps": 2,
}