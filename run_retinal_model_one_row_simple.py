#!/usr/bin/env python3
"""
Fully hardcoded single-row test for DT_OH retinal simulation.

Edit the variables in the "CONFIG" section below, then run:
  python run_retinal_model_one_row_simple.py
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
    OUTPUT_DIR = Path("output/DT_OH/one_row_test")
    INITIAL_CONDITIONS = "DT_OH/init/Initial_wIOP.csv"

    # Choose ONE selection method:
    ROW_INDEX: Optional[int] = 0  # uses pandas iloc index
    PATIENT_UID: Optional[str] = None  # set to a value if you want filter-by-patient
    EYE: Optional[str] = None  # "OD" or "OS" (optional if using PATIENT_UID)

    N_WORKERS = 1
    CHECKPOINT_INTERVAL = 1
    PATIENT_ID_COLUMN = "patient_uid"  # only used for logging

    # ============================================================

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    if not INPUT_CSV.exists():
        raise FileNotFoundError(f"Input CSV not found: {INPUT_CSV.resolve()}")

    df = pd.read_csv(INPUT_CSV)

    required = ["SBP", "DBP", "IOP", "HR"]
    missing_required = [c for c in required if c not in df.columns]
    if missing_required:
        raise ValueError(f"Input CSV missing required columns: {missing_required}")

    if ROW_INDEX is not None:
        if ROW_INDEX < 0 or ROW_INDEX >= len(df):
            raise IndexError(f"ROW_INDEX out of range: {ROW_INDEX} (csv rows={len(df)})")
        one = df.iloc[[ROW_INDEX]].copy()
    else:
        if PATIENT_UID is None:
            raise ValueError("Either set ROW_INDEX or set PATIENT_UID (and optionally EYE).")
        if "patient_uid" not in df.columns:
            raise ValueError("CSV does not contain `patient_uid`, but you set PATIENT_UID.")

        mask = df["patient_uid"].astype(str) == str(PATIENT_UID)
        if EYE is not None:
            if "eye" not in df.columns:
                raise ValueError("CSV does not contain `eye`, but you set EYE.")
            mask &= df["eye"].astype(str).str.upper() == str(EYE).upper()

        filtered = df.loc[mask]
        if len(filtered) == 0:
            raise ValueError("Selection matched 0 rows. Check PATIENT_UID/EYE.")
        one = filtered.iloc[[0]].copy()

    # Save the selected row for transparency/debugging
    one_csv_path = OUTPUT_DIR / "one_row.csv"
    one.to_csv(one_csv_path, index=False)

    print("Selected one row (required columns):")
    print(one[required].to_string(index=False))
    print(f"Running model on: {one_csv_path}")

    module_def = {
        "name": "RetinalModel",
        "input": {"csv_path": str(one_csv_path)},
        "output": {"base_dir": str(OUTPUT_DIR)},
        "config": {
            "initial_conditions_path": INITIAL_CONDITIONS,
            "required_columns": ["SBP", "DBP", "IOP", "HR"],
            "patient_id_column": PATIENT_ID_COLUMN,
            "processing": {
                "n_workers": N_WORKERS,
                "checkpoint_interval": CHECKPOINT_INTERVAL,
            },
        },
    }

    wrapper = RetinalModelModuleWrapper(module_def=module_def)
    wrapper.run()
    print(f"Done. Results: {OUTPUT_DIR / 'results.csv'}")


if __name__ == "__main__":
    main()

