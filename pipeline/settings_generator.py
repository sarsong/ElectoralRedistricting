import json
import geopandas as gpd
from pathlib import Path
import jsonlines as jl
from tqdm import tqdm
from gerrychain import Graph

def generate_settings(config_path):

    with open(config_path, "r", encoding="utf-8") as f:
        config = json.load(f)

    project_root = Path(__file__).resolve().parent

    # Load in population data

    path_to_data = project_root.parent / config['geodata_path']
    # FIX geopackage, use this 
    #layer = config['geo_layer']
    #population_data = gpd.read_file(path_to_data, layer = layer)

    population_data = gpd.read_file(path_to_data)

    population_data = population_data[[config['pop_of_interest_column'],config['population_column']]]

    # Subsampling parameters
    chain_length = config['chain_length']
    num_subamples = config['num_subsamples']
    subsample_interval = chain_length // num_subamples   

    district_params = ['num_voters, slate_to_candidates', 'cohesion_parameters', 'alphas']
    output_settings = {k:config[k] for k in config if k in district_params}
    turnout = config['turnout']
    focal_group = config['focal_group']
    other_group =  next(iter(turnout.keys() - {focal_group})) 
    run_name = config['run_name']


    for district_num in [config['district_configs'][0]['num_districts']]:
        settings_folder = (project_root.parent /
                           'outputs' /
                           'settings' /
                           f"{run_name}_settings" /
                           f"{district_num}")
        settings_folder.mkdir(exist_ok=True, parents=True)

        path_to_districting = (project_root.parent /
                               'outputs' /
                               'districts' /
                               f"{run_name}_chain_out" /
                               f"{run_name}_{district_num}_districts.jsonl")
       ## changed f"{run_name}_districts" to f"{run_name}_chain_out"
        ## changed from f"{district_num}.jsonl") to f"{run_name}_{district_num}_districts.jsonl")
        
        with jl.open(path_to_districting) as file:
            for sample_idx, sample in tqdm(
                enumerate(file),
                total=chain_length,
                desc=f"Generating VK settings for {district_num:02d} districts",
            ):
                if sample_idx % subsample_interval != 0:
                    continue

                # Will be in the same order as the df since the graph was built from the gpkg
                district_plan = sample["assignment"]
                population_data["district_plan"] = district_plan
                data_by_district = population_data.groupby("district_plan").sum()

                for _, row in data_by_district.iterrows():
                    district = row.name
                    prop = float(row[config['pop_of_interest_column']] / row[config['population_column']])
                    adjusted_prop = prop*turnout[focal_group] / (prop*turnout[focal_group] + (1-prop)*turnout[other_group])

                    output_settings['bloc_proportions'] = {focal_group: adjusted_prop, other_group: 1 - adjusted_prop}
                    output_settings['total_ivap'] = row[config['pop_of_interest_column']],
                    output_settings['total_vap'] = row[config['population_column']]
                    

                    with open(
                        f"{settings_folder}/{run_name}_{district_num}_sample_settings_district_plan_{sample_idx:03d}_district_{district:02d}.json",
                        "w",
                    ) as out_file:
                        json.dump(output_settings, out_file, indent=2)
