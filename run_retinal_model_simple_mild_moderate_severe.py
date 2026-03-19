#!/usr/bin/env python3
"""
Simple hardcoded DT_OH run that ONLY keeps mild/moderate/severe rows
based on `diagnosis_severity` in the processed CSV.

Edit CONFIG values below, then run:
  python run_retinal_model_simple_mild_moderate_severe.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional, Set

import pandas as pd

from DT_OH import RetinalModelModuleWrapper


def main() -> None:
    # ============================================================
    # CONFIG (edit these)
    # ============================================================
    INPUT_CSV = Path("data/processed/processed_aggregate_data.csv")
    OUTPUT_DIR = Path("output/DT_OH/processed_mmds_simple_run")
    INITIAL_CONDITIONS = "DT_OH/init/Initial_wIOP.csv"

    # For quick testing; set to None to process all filtered rows.
    MAX_ROWS: Optional[int] = 50

    # Column in processed CSV that contains severity labels.
    SEVERITY_COL = "diagnosis_severity"
    ALLOWED_SEVERITIES: Set[str] = {"mild", "moderate", "severe"}

    # Logging / patient id column in processed CSV.
    PATIENT_ID_COLUMN = "patient_uid"

    CHECKPOINT_INTERVAL = 1
    # ============================================================

    repo_root = Path(__file__).resolve().parent
    input_csv = (repo_root / INPUT_CSV).resolve()
    output_dir = (repo_root / OUTPUT_DIR).resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv)

    if SEVERITY_COL not in df.columns:
        raise ValueError(
            f"Expected `{SEVERITY_COL}` column in input CSV, but found columns: {list(df.columns)}"
        )

    # Normalize severity labels and filter.
    df[SEVERITY_COL] = df[SEVERITY_COL].astype(str).str.strip().str.lower()
    df = df[df[SEVERITY_COL].isin({s.lower() for s in ALLOWED_SEVERITIES})].copy()

    if df.empty:
        raise ValueError("No rows left after filtering to mild/moderate/severe.")

    if MAX_ROWS is not None:
        df = df.head(MAX_ROWS).copy()

    # Wrapper reads from disk, so write the filtered data to a temp CSV.
    temp_csv = output_dir / "filtered_input_one_batch.csv"
    df.to_csv(temp_csv, index=False)

    module_def = {
        "name": "RetinalModel",
        "input": {"csv_path": str(temp_csv)},
        "output": {"base_dir": str(output_dir)},
        "config": {
            "initial_conditions_path": INITIAL_CONDITIONS,
            # Core simulation requires these columns.
            "required_columns": ["SBP", "DBP", "IOP", "HR"],
            "patient_id_column": PATIENT_ID_COLUMN,
            "processing": {
                "checkpoint_interval": CHECKPOINT_INTERVAL,
                # Leave n_workers unset so inference picks an available default.
            },
        },
    }

    wrapper = RetinalModelModuleWrapper(module_def=module_def)
    wrapper.run()

    print(f"Done. Results: {output_dir / 'results.csv'}")


if __name__ == "__main__":
    main()

