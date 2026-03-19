# dtoh-simulation (DT_OH retinal hemodynamics)

This repo contains a Python implementation of the DT_OH (retinal hemodynamics) simulation pipeline.

## What you need

1. Python 3.9+
2. A CSV file placed in `data/` with the required columns:
   - `SBP` (systolic blood pressure)
   - `DBP` (diastolic blood pressure)
   - `IOP` (intraocular pressure)
   - `HR` (heart rate)
3. Optional: `Patient` column (patient identifier used for logging)

The simulation uses the lookup table `DT_OH/init/Initial_wIOP.csv`. The `IOP` value is rounded to the nearest integer before matching against that table.

## Install dependencies

From the repo root:

```bash
python -m pip install --upgrade pip
pip install -r requirements.txt
```

## Run the simulation

Example:

```bash
python run_retinal_model.py \
  --input data/your_input.csv \
  --output output/DT_OH/your_run
```

This writes:
- `output/DT_OH/your_run/results.csv` (the full input + computed columns)
- `output/DT_OH/your_run/logs/processing.log`
- `output/DT_OH/your_run/checkpoints/checkpoint.json` (progress for re-runs)

### Minimal CSV format

Your input CSV must have at least these headers:

```csv
SBP,DBP,IOP,HR,Patient
```

`Patient` is optional; if omitted, you can still run.

## Preprocess nested patient-level CSVs

If your input is a *patient-level aggregated* CSV where many columns are stored as lists/arrays (and there are no timestamps), you can preprocess it into an eye-level dataset (one row per `patient_uid` + `eye` + unique diagnosis code) using:

### One-click (recommended)

Edit paths inside `preprocess_and_generate_config_simple.py`, then run:

```bash
python preprocess_and_generate_config_simple.py
```

This produces:
- `data/processed/processed_aggregate_data.csv`
- `config/processed_retinal_model.yaml`

### CLI (more flexible)

```bash
python preprocess_aggregate_data.py \
  --input-csv data/aggregate_data.csv \
  --output-csv data/processed/processed_aggregate_data.csv \
  --output-config-yaml config/processed_retinal_model.yaml
```

The script:
- computes medians for `SBP`, `DBP`, `HR`, and per-eye `IOP`
- drops rows missing required values
- keeps unique diagnosis codes per patient and selects the highest-priority severity

## Notes / troubleshooting

- If you get an error related to missing `IOP` matches in `Initial_wIOP.csv`, try using an `IOP` value whose rounded integer exists in the lookup table.
- The default runner uses `--n-workers 1` to avoid multiprocessing issues on some systems. You can increase it with `--n-workers`.

