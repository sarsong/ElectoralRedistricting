# Electoral Redistricting

## 1. Setup Software

Follow the instructions for setting up the necessary software [here](https://github.com/hanelee/CA_STV/tree/peter-workflow-updates?tab=readme-ov-file#software-setup).

## 2. Configure the Pipeline (`setup.py`)

- **Interactive Mode:** Run `setup.py` to be prompted for each required field.
  - Example: `python setup.py --config-out configs/run_name.json`
- **Default Mode:** Use an existing JSON file to pre-fill default values.
  - Example: `python setup.py --defaults-from configs/default.json`

## 3. Run the Full Pipeline (`run.py`)

Once you have the configuration JSON file, run `run.py` to execute the entire simulation workflow sequentially. You only need to specify the path to the config file.

Example: `python run.py --config-path configs/your_run_name.json`

The pipeline will execute the following stages in order:

| Stage | Script | Summary |
|-------|--------|---------|
| 1 | `Districts_generator.py` | Generates district plans using GerryChain by converting geographical data into a graph |
| 2 | `Settings_generator.py` | Creates VoteKit settings JSONs by aggregating population data and computing turnout-adjusted bloc proportions for subsampled district plans |
| 3 | `Profile_generator.py` | Generates voter preference profiles (simulated ballots) for each settings file under three voting behavior models (impulsive, deliberate, and Cambridge) |
| 4 | `Simulate_elections.py` | Runs the election simulation (FastSTV) on the generated voter profiles to determine and record the winners |
| 5 | `Summarize_results.py` | Post-processes the election results into a dataframe and generates histograms of seat counts for comparative analysis |
