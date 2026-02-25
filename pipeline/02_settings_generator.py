import json
import geopandas as gpd
from pathlib import Path
import jsonlines as jl
from tqdm import tqdm
from gerrychain import Graph

def settings_generator(config):

    # Load in population data

    path_to_data = Path(f'{config['geodata_path']}')

    if 'geo_layer' in config.keys():
        layer = config['geo_layer']
        population_data = gpd.read_file(path_to_data, layer = layer)
    else: 
        population_data = gpd.read_file(path_to_data)

    population_data = population_data[[config['pop_of_interest_column'],config['population_column']]]

    # Subsampling parameters
    chain_length = config['chain_length']
    num_subamples = config['num_subsamples']
    subsample_interval = chain_length // num_subamples   

    district_params = ['num_voters', 'slate_to_candidates', 'cohesion_parameters', 'alphas']
    output_settings = {k:config[k] for k in config if k in district_params}
    turnout = config['turnout']
    focal_group = config['focal_group']
    other_group =  (set(turnout) - set(focal_group)).pop()
    run_name = config['run_name']
    


    for district_num in [d_config['num_districts'] for d_config in config['district_configs']]:
        settings_folder = Path(f'outputs/settings/{run_name}_settings/{district_num}')
        settings_folder.mkdir(exist_ok=True, parents=True)

        path_to_districting = Path(f'outputs/districts/{run_name}_districts/{district_num}.jsonl')
        
        with jl.open(path_to_districting) as file:
            for sample_idx, sample in tqdm(
                enumerate(file),
                total=chain_length,
                desc=f"Generating VK settings for {district_num:02d} districts",
            ):
                if sample_idx % subsample_interval != 0:
                    continue

                district_plan = sample["assignment"]
                population_data["district_plan"] = district_plan
                data_by_district = population_data.groupby("district_plan").sum()

                for _, row in data_by_district.iterrows():
                    district = row.name
                    prop = float(row[config['pop_of_interest_column']] / row[config['population_column']])
                    adjusted_prop = prop*turnout[focal_group] / (prop*turnout[focal_group] + (1-prop)*turnout[other_group])

                    output_settings['bloc_proportions'] = {focal_group: adjusted_prop, other_group: 1 - adjusted_prop}
                    output_settings['total_ivap'] = row[config['pop_of_interest_column']]
                    output_settings['total_vap'] = row[config['population_column']]
                    
                    with open(
                        f"{settings_folder}/{run_name}_{district_num}_sample_settings_district_plan_{sample_idx:03d}_district_{district:02d}.json",
                        "w",
                    ) as out_file:
                        json.dump(output_settings, out_file, indent=2)

