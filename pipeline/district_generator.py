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
    population_column = config["population_column"]
    chain_length = config["chain_length"]
    district_configs = config["district_configs"]

    # load cached graph if it exists, otherwise build from geodata and save
    graph_path = geodata_path.parent / (geodata_path.stem + "_graph.json")
    if graph_path.exists():
        graph = Graph.from_json(str(graph_path))
    else:
        graph = Graph.from_file(str(geodata_path))
        graph.to_json(str(graph_path))

    total_population = sum(graph.nodes[n][population_column] for n in graph.nodes)

    output_dir = Path(f"outputs/districts/{run_name}_chain_out")
    output_dir.mkdir(parents=True, exist_ok=True)

    # run a separate markov chain for each district count in the config
    for d_config in district_configs:
        num_districts = d_config["num_districts"]
        ideal_pop = total_population / num_districts  # target population per district

        # seed a valid starting partition using random spanning trees
        initial_assignment = recursive_tree_part(
            graph,
            range(num_districts),
            ideal_pop,
            population_column,
            0.05,  # allow 5% population deviation
        )

        partition = Partition(
            graph,
            assignment=initial_assignment,
            updaters={"population": Tally(population_column)},
        )

        # recom proposal: merges two adjacent districts and repartitions
        proposal = partial(
            recom,
            pop_col=population_column,
            pop_target=ideal_pop,
            epsilon=0.05,
            node_repeats=2,
        )

        chain = MarkovChain(
            proposal=proposal,
            constraints=[contiguous],  # reject disconnected districts
            accept=always_accept,
            initial_state=partition,
            total_steps=chain_length,
        )

        # write each step as a jsonl record: {"assignment": [...], "sample:": n}
        output_path = output_dir / f"{run_name}_{num_districts}_districts.jsonl"
        with jl.open(str(output_path), mode="w") as writer:
            for sample_num, step in enumerate(tqdm(chain, total=chain_length, desc=f"Generating {num_districts}-district plans"), start=1):
                # assignment as list ordered by node index (matches sample_chain.jsonl format)
                assignment = [int(step.assignment[n]) for n in range(len(step.assignment))]
                writer.write({"assignment": assignment, "sample:": sample_num})


if __name__ == "__main__":
    generate_districts("configs/sample.json")
