#!/usr/bin/env python3
"""
Simple hardcoded run for the processed aggregate dataset.

Edit CONFIG values below, then run:
  python run_retinal_model_simple_from_processed.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Optional

import pandas as pd

from DT_OH import RetinalModelModuleWrapper


def main() -> None:
    # ============================================================
    # CONFIG (edit these)
    # ============================================================
    INPUT_CSV = Path("data/processed/processed_aggregate_data.csv")
    OUTPUT_DIR = Path("output/DT_OH/processed_simple_run")
    INITIAL_CONDITIONS = "DT_OH/init/Initial_wIOP.csv"

    # For quick testing. Set to None to process everything.
    MAX_ROWS: Optional[int] = 50

    # Logging: processed CSV uses `patient_uid`
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
    if MAX_ROWS is not None:
        df = df.head(MAX_ROWS).copy()

    # Write temp CSV because the wrapper reads from disk.
    temp_csv = output_dir / "input_one_batch.csv"
    df.to_csv(temp_csv, index=False)

    module_def = {
        "name": "RetinalModel",
        "input": {"csv_path": str(temp_csv)},
        "output": {"base_dir": str(output_dir)},
        "config": {
            "initial_conditions_path": INITIAL_CONDITIONS,
            "required_columns": ["SBP", "DBP", "IOP", "HR"],
            "patient_id_column": PATIENT_ID_COLUMN,
            # Leave n_workers unset so DT_OH can auto-pick based on CPU cores.
            "processing": {
                "checkpoint_interval": CHECKPOINT_INTERVAL,
            },
        },
    }

    wrapper = RetinalModelModuleWrapper(module_def=module_def)
    wrapper.run()

    print(f"Done. Results: {output_dir / 'results.csv'}")


if __name__ == "__main__":
    main()

