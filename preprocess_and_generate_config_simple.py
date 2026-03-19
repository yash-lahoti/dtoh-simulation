#!/usr/bin/env python3
"""
One-click wrapper around `preprocess_aggregate_data.py`.

Edit the paths/column names below, then run:
  python preprocess_and_generate_config_simple.py
"""

from __future__ import annotations

import subprocess
import sys
from pathlib import Path


def main() -> None:
    repo_root = Path(__file__).resolve().parent

    # -----------------------------
    # Edit these paths/columns
    # -----------------------------
    INPUT_CSV = repo_root / "data/aggregate_data.csv"
    OUTPUT_CSV = repo_root / "data/processed/processed_aggregate_data.csv"
    OUTPUT_YAML = repo_root / "config/processed_retinal_model.yaml"
    OUTPUT_CONFIG_BASE_DIR = repo_root / "output/DT_OH/processed"

    # Column names inside your `aggregate_data.csv`
    PATIENT_UID_COL = "patient_uid"
    BP_SYSTOLIC_COL = "bp_systolic"
    BP_DIASTOLIC_COL = "bp_diastolic"
    PULSE_COL = "pulse"
    OD_IOP_COL = "od_iop"
    OS_IOP_COL = "os_iop"
    CODE_COL = "code"
    SHORT_DESC_COL = "short_desc"
    SOURCE_SEVERITY_COL = "source_severity"

    # Simulation pipeline settings (written into the YAML)
    N_WORKERS = 1
    CHECKPOINT_INTERVAL = 1
    PIPELINE_NAME = "processed_retinal_model"

    cmd = [
        sys.executable,
        str(repo_root / "preprocess_aggregate_data.py"),
        "--input-csv",
        str(INPUT_CSV),
        "--output-csv",
        str(OUTPUT_CSV),
        "--output-config-yaml",
        str(OUTPUT_YAML),
        "--output-config-base-dir",
        str(OUTPUT_CONFIG_BASE_DIR),
        "--patient-uid-col",
        PATIENT_UID_COL,
        "--bp-systolic-col",
        BP_SYSTOLIC_COL,
        "--bp-diastolic-col",
        BP_DIASTOLIC_COL,
        "--pulse-col",
        PULSE_COL,
        "--od-iop-col",
        OD_IOP_COL,
        "--os-iop-col",
        OS_IOP_COL,
        "--code-col",
        CODE_COL,
        "--short-desc-col",
        SHORT_DESC_COL,
        "--source-severity-col",
        SOURCE_SEVERITY_COL,
        "--n-workers",
        str(N_WORKERS),
        "--checkpoint-interval",
        str(CHECKPOINT_INTERVAL),
        "--pipeline-name",
        PIPELINE_NAME,
    ]

    subprocess.run(cmd, check=True)

    print("Preprocessing + YAML config generation complete.")
    print(f"Processed CSV: {OUTPUT_CSV}")
    print(f"Config YAML:    {OUTPUT_YAML}")


if __name__ == "__main__":
    main()

