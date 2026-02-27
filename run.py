import json
import geopandas as gpd
from pathlib import Path
import jsonlines as jl
from tqdm import tqdm
from gerrychain import Graph
from pipeline.settings_generator import generate_settings
from pipeline.profile_generator import generate_profiles

config_path = "configs/sample.json"

generate_settings(config_path)

generate_profiles(config_path)
