#!/usr/bin/env python3
"""
Fully hardcoded sequential DT_OH runner.

Edit the CONFIG section below, then run:
  python run_retinal_model_sequential_simple.py
"""

from __future__ import annotations

from pathlib import Path
from typing import Dict, List, Optional

import pandas as pd
from tqdm import tqdm

from DT_OH import RetinalModelModule


def main() -> None:
    # ============================================================
    # CONFIG (edit these)
    # ============================================================
    INPUT_CSV = Path("data/processed/processed_aggregate_data.csv")
    OUTPUT_DIR = Path("output/DT_OH/sequential_simple_run")
    INITIAL_CONDITIONS = "DT_OH/init/Initial_wIOP.csv"

    # For quick tests set MAX_ROWS to a small number; set to None for full run.
    MAX_ROWS: Optional[int] = 10

    # Module/process settings
    N_WORKERS = 1  # sequential runner, but config expects this field
    CHECKPOINT_INTERVAL = 1
    PATIENT_ID_COLUMN = "patient_uid"  # used for logging only

    # ============================================================

    OUTPUT_DIR.mkdir(parents=True, exist_ok=True)

    input_csv = INPUT_CSV.expanduser().resolve()
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv)

    required = ["SBP", "DBP", "IOP", "HR"]
    missing_required = [c for c in required if c not in df.columns]
    if missing_required:
        raise ValueError(f"Input CSV is missing required columns: {missing_required}")

    module = RetinalModelModule(
        name="RetinalModel",
        config={
            "initial_conditions_path": INITIAL_CONDITIONS,
            "required_columns": ["SBP", "DBP", "IOP", "HR"],
            "output_columns": ["P1", "P2", "P4", "P5", "Qmean", "R1", "R4", "R5"],
            "patient_id_column": PATIENT_ID_COLUMN,
            "processing": {"n_workers": N_WORKERS, "checkpoint_interval": CHECKPOINT_INTERVAL},
        },
        output_dir=OUTPUT_DIR,
    )

    # Validate inputs using module logic
    module.validate_inputs(df)

    # Add original ordering index for checkpoint bookkeeping
    df = df.reset_index(drop=False).rename(columns={"index": "__orig_index__"})

    required_cols = module.get_required_columns()
    mask_missing = df[required_cols].isna().any(axis=1)
    missing_df = df.loc[mask_missing].copy()
    if not missing_df.empty:
        module.logger.warning(f"Dropping {len(missing_df)} rows with missing required inputs.")
        module.log_missing_data(missing_df)

    data_clean = df.loc[~mask_missing].copy()

    ckpt = module.load_checkpoint()
    processed_set = set(ckpt.get("processed_indices", []))

    to_process = data_clean[~data_clean["__orig_index__"].isin(processed_set)].copy()
    if MAX_ROWS is not None:
        to_process = to_process.head(MAX_ROWS).copy()

    if to_process.empty:
        print("No rows to process (everything already processed per checkpoint).")
        return

    results_file = module.results_dir / "results.csv"
    result_cols = module.get_output_columns()

    # Ensure header exists
    if not results_file.exists():
        out_header_df = pd.concat([to_process.head(0), pd.DataFrame(columns=result_cols)], axis=1)
        out_header_df.to_csv(results_file, index=False)

    records = to_process.to_dict(orient="records")
    buffer: List[pd.DataFrame] = []
    cols_order = list(to_process.columns) + result_cols

    for rec in tqdm(records, total=len(records), desc="Processing sequentially"):
        try:
            row = pd.Series(rec)
            result_vals = module._shimpatica_func(row)
        except Exception as e:
            patient_id = rec.get(module.patient_id_column, "Unknown")
            module.logger.error(f"Error processing Patient {patient_id}: {e}")
            err_row = {k: rec.get(k, None) for k in ["__orig_index__", module.patient_id_column] + required_cols}
            err_row["error"] = str(e)
            module.log_error(err_row)
            continue

        out_row = pd.DataFrame([{**rec, **dict(zip(result_cols, result_vals))}])
        buffer.append(out_row)

        if len(buffer) >= CHECKPOINT_INTERVAL:
            batch = pd.concat(buffer, ignore_index=True)
            batch = batch[cols_order]
            module.append_results(batch)

            processed_set.update(batch["__orig_index__"].tolist())
            module.save_checkpoint(sorted(list(processed_set)))
            buffer.clear()

    if buffer:
        batch = pd.concat(buffer, ignore_index=True)
        batch = batch[cols_order]
        module.append_results(batch)
        processed_set.update(batch["__orig_index__"].tolist())
        module.save_checkpoint(sorted(list(processed_set)))

    final_df = pd.read_csv(results_file)
    module.logger.info(f"Sequential simple run complete. Total rows: {len(final_df)}")
    print(f"Done. Results: {results_file}")


if __name__ == "__main__":
    main()

