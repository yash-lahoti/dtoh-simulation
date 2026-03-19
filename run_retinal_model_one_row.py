#!/usr/bin/env python3
"""
Run DT_OH retinal simulation on exactly one row from a CSV.

Examples:
  python run_retinal_model_one_row.py --input data/processed/processed_aggregate_data.csv --row-index 0 --output output/DT_OH/one_row
  python run_retinal_model_one_row.py --input data/processed/processed_aggregate_data.csv --patient-uid 123 --eye OD --output output/DT_OH/one_row
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Optional

import pandas as pd

from DT_OH import RetinalModelModuleWrapper


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DT_OH retinal simulation on a single CSV row.")
    parser.add_argument("--input", required=True, help="Input CSV with columns: SBP, DBP, IOP, HR.")
    parser.add_argument("--output", required=True, help="Output directory.")

    # Selection
    parser.add_argument("--row-index", type=int, default=None, help="Row index (pandas iloc index).")
    parser.add_argument("--patient-uid", default=None, help="Optional: filter by patient_uid.")
    parser.add_argument("--eye", default=None, help="Optional: filter by eye (OD/OS).")

    # Logging only (not required for computation)
    parser.add_argument("--patient-id-column", default="patient_uid", help="Column used only for logging (optional).")

    # Solver/process tuning
    parser.add_argument("--initial-conditions", default="DT_OH/init/Initial_wIOP.csv")
    parser.add_argument("--n-workers", type=int, default=1)
    parser.add_argument("--checkpoint-interval", type=int, default=1)

    args = parser.parse_args()

    input_csv = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv)

    if args.row_index is not None:
        if args.row_index < 0 or args.row_index >= len(df):
            raise IndexError(f"--row-index out of range. Got {args.row_index} but CSV has {len(df)} rows.")
        one = df.iloc[[args.row_index]].copy()
    else:
        mask = pd.Series([True] * len(df))
        if args.patient_uid is not None:
            if "patient_uid" not in df.columns:
                raise ValueError("Your CSV does not contain `patient_uid`, but you passed --patient-uid.")
            mask &= df["patient_uid"].astype(str) == str(args.patient_uid)
        if args.eye is not None:
            if "eye" not in df.columns:
                raise ValueError("Your CSV does not contain `eye`, but you passed --eye.")
            mask &= df["eye"].astype(str).str.upper() == str(args.eye).upper()

        filtered = df.loc[mask]
        if len(filtered) == 0:
            raise ValueError("Filter matched 0 rows. Adjust --patient-uid/--eye or use --row-index.")
        one = filtered.iloc[[0]].copy()

    # Basic sanity display
    required = ["SBP", "DBP", "IOP", "HR"]
    missing = [c for c in required if c not in one.columns]
    if missing:
        raise ValueError(f"Missing required columns in input CSV: {missing}")

    # If patient-id-column isn't present, fall back to "Patient" (RetinalModelModuleWrapper only uses it for logs)
    patient_id_column = args.patient_id_column
    if patient_id_column not in one.columns and "Patient" in one.columns:
        patient_id_column = "Patient"

    # Write a 1-row temp CSV for transparency/debugging
    one_csv_path = output_dir / "one_row.csv"
    one.to_csv(one_csv_path, index=False)

    module_def = {
        "name": "RetinalModel",
        "input": {"csv_path": str(one_csv_path)},
        "output": {"base_dir": str(output_dir)},
        "config": {
            "initial_conditions_path": args.initial_conditions,
            "required_columns": ["SBP", "DBP", "IOP", "HR"],
            "patient_id_column": patient_id_column,
            "processing": {
                "n_workers": args.n_workers,
                "checkpoint_interval": args.checkpoint_interval,
            },
        },
    }

    wrapper = RetinalModelModuleWrapper(module_def=module_def)
    print("Selected one row:")
    print(one[required].to_string(index=False))
    wrapper.run()

    print(f"Done. Results: {output_dir / 'results.csv'}")


if __name__ == "__main__":
    main()

