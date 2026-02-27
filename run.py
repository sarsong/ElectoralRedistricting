import json
import geopandas as gpd
from pathlib import Path
import jsonlines as jl
from tqdm import tqdm
from gerrychain import Graph
from pipeline.settings_generator import generate_settings

generate_settings("configs/sample.json")