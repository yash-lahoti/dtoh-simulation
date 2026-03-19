#!/usr/bin/env python3
"""
Simple hardcoded preprocessing for aggregate_data.

This script:
1) Reads a patient-level nested aggregate CSV
2) Keeps only diagnosis severities: mild/moderate/severe
3) Computes medians for vitals and IOP
4) Creates one row per patient-eye-diagnosis_code
5) Drops rows missing required retinal-model inputs
6) Writes processed CSV + YAML config

Run:
  python preprocess_aggregate_data_simple_mmds.py
"""

from __future__ import annotations

from pathlib import Path

import pandas as pd
from tqdm import tqdm

import preprocess_aggregate_data as core


def main() -> None:
    # ============================================================
    # CONFIG (edit these)
    # ============================================================
    INPUT_CSV = Path("data/aggregate_data.csv")
    OUTPUT_CSV = Path("data/processed/processed_aggregate_data_mmds.csv")
    OUTPUT_YAML = Path("config/processed_retinal_model_mmds.yaml")
    OUTPUT_BASE_DIR = Path("output/DT_OH/processed_mmds")

    PIPELINE_NAME = "processed_retinal_model_mmds"
    PATIENT_UID_COL = "patient_uid"
    BP_SYSTOLIC_COL = "bp_systolic"
    BP_DIASTOLIC_COL = "bp_diastolic"
    PULSE_COL = "pulse"
    OD_IOP_COL = "od_iop"
    OS_IOP_COL = "os_iop"
    CODE_COL = "code"
    SHORT_DESC_COL = "short_desc"
    SOURCE_SEVERITY_COL = "source_severity"

    N_WORKERS = 1
    CHECKPOINT_INTERVAL = 1
    # ============================================================

    repo_root = Path(__file__).resolve().parent
    input_csv = (repo_root / INPUT_CSV).resolve()
    output_csv = (repo_root / OUTPUT_CSV).resolve()
    output_yaml = (repo_root / OUTPUT_YAML).resolve()
    output_base_dir = (repo_root / OUTPUT_BASE_DIR).resolve()

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    output_csv.parent.mkdir(parents=True, exist_ok=True)
    output_yaml.parent.mkdir(parents=True, exist_ok=True)
    output_base_dir.mkdir(parents=True, exist_ok=True)

    df = pd.read_csv(input_csv)

    required_cols = [
        PATIENT_UID_COL,
        BP_SYSTOLIC_COL,
        BP_DIASTOLIC_COL,
        PULSE_COL,
        OD_IOP_COL,
        OS_IOP_COL,
        CODE_COL,
        SHORT_DESC_COL,
        SOURCE_SEVERITY_COL,
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in input CSV: {missing}")

    priority_map = {s: i for i, s in enumerate(core.SEVERITY_PRIORITY_ORDER)}

    out_rows = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Processing patients"):
        out_rows.extend(
            core.process_one_patient(
                row,
                patient_uid_col=PATIENT_UID_COL,
                bp_systolic_col=BP_SYSTOLIC_COL,
                bp_diastolic_col=BP_DIASTOLIC_COL,
                pulse_col=PULSE_COL,
                od_iop_col=OD_IOP_COL,
                os_iop_col=OS_IOP_COL,
                code_col=CODE_COL,
                short_desc_col=SHORT_DESC_COL,
                source_severity_col=SOURCE_SEVERITY_COL,
                priority_map=priority_map,
            )
        )

    processed = pd.DataFrame(out_rows)
    processed = processed.dropna(
        subset=["SBP", "DBP", "HR", "IOP", "diagnosis_code", "diagnosis_severity"]
    ).reset_index(drop=True)
    processed.to_csv(output_csv, index=False)

    try:
        input_rel = output_csv.relative_to(repo_root)
        base_dir_rel = output_base_dir.relative_to(repo_root)
    except Exception:
        input_rel = output_csv
        base_dir_rel = output_base_dir

    yaml_text = core.build_yaml_config(
        pipeline_name=PIPELINE_NAME,
        input_csv_rel=str(input_rel),
        base_dir_rel=str(base_dir_rel),
        patient_id_column=PATIENT_UID_COL,
        n_workers=N_WORKERS,
        checkpoint_interval=CHECKPOINT_INTERVAL,
    )
    output_yaml.write_text(yaml_text, encoding="utf-8")

    print(f"Wrote processed CSV: {output_csv}")
    print(f"Wrote config YAML: {output_yaml}")
    print(f"Processed rows: {len(processed):,}")


if __name__ == "__main__":
    main()

