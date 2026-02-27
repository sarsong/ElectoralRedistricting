import json
from pathlib import Path

import jsonlines as jl
from tqdm import tqdm
from gerrychain import Graph, Partition, MarkovChain
from gerrychain.proposals import recom
from gerrychain.accept import always_accept
from gerrychain.constraints import contiguous
from gerrychain.updaters import Tally
from gerrychain.tree import recursive_tree_part
from functools import partial


def generate_districts(config_path):

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    run_name = config["run_name"]
    geodata_path = Path(config["geodata_path"])
    geo_layer = config.get("geo_layer", None)
    population_column = config["population_column"]
    chain_length = config["chain_length"]
    district_configs = config["district_configs"]

    # Load or build graph
    graph_path = geodata_path.parent / (geodata_path.stem + "_graph.json")
    if graph_path.exists():
        graph = Graph.from_json(str(graph_path))
    else:
        if geo_layer:
            graph = Graph.from_file(str(geodata_path), layer=geo_layer)
        else:
            graph = Graph.from_file(str(geodata_path))
        graph.to_json(str(graph_path))




if __name__ == "__main__":
    generate_districts("configs/sample.json")
