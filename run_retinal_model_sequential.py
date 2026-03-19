#!/usr/bin/env python3
"""
Run DT_OH retinal simulation sequentially (no ProcessPoolExecutor/futures).

This avoids the "stuck" area in `DT_OH/inference.py` where futures are created
for all rows at once.

Example:
  python run_retinal_model_sequential.py \
    --input data/processed/your.csv \
    --output output/DT_OH/sequential_run \
    --n-workers 1
"""

from __future__ import annotations

import argparse
from pathlib import Path
from typing import Any, Dict, List

import pandas as pd
from tqdm import tqdm

from DT_OH import RetinalModelModule


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DT_OH retinal simulation sequentially (one row at a time).")
    parser.add_argument("--input", required=True, help="Input CSV with SBP, DBP, IOP, HR.")
    parser.add_argument("--output", required=True, help="Output directory.")
    parser.add_argument("--initial-conditions", default="DT_OH/init/Initial_wIOP.csv")
    parser.add_argument("--patient-id-column", default="Patient", help="Optional patient id column (for logging).")
    parser.add_argument("--checkpoint-interval", type=int, default=1, help="Write results/checkpoint every N rows.")
    parser.add_argument("--max-rows", type=int, default=None, help="Optional limit for testing.")

    args = parser.parse_args()

    input_csv = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()
    output_dir.mkdir(parents=True, exist_ok=True)

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    df = pd.read_csv(input_csv)

    # Initialize module (uses same core ODE logic as the main pipeline)
    module = RetinalModelModule(
        name="RetinalModel",
        config={
            "initial_conditions_path": args.initial_conditions,
            "required_columns": ["SBP", "DBP", "IOP", "HR"],
            "output_columns": ["P1", "P2", "P4", "P5", "Qmean", "R1", "R4", "R5"],
            "patient_id_column": args.patient_id_column,
            # Keep consistent with module.process() behavior
            "processing": {"n_workers": 1, "checkpoint_interval": args.checkpoint_interval},
        },
        output_dir=output_dir,
    )

    required = module.get_required_columns()
    result_cols = module.get_output_columns()

    # Validate required columns exist
    module.validate_inputs(df)

    # Track original ordering like the main pipeline does
    df = df.reset_index(drop=False).rename(columns={"index": "__orig_index__"})

    # Drop missing required inputs
    mask_missing = df[required].isna().any(axis=1)
    missing_df = df.loc[mask_missing].copy()
    if not missing_df.empty:
        module.logger.warning(f"Dropping {len(missing_df)} rows with missing required inputs.")
        module.log_missing_data(missing_df)
    data_clean = df.loc[~mask_missing].copy()

    # Resume support via checkpoint.json
    ckpt = module.load_checkpoint()
    processed_set = set(ckpt.get("processed_indices", []))

    to_process = data_clean[~data_clean["__orig_index__"].isin(processed_set)].copy()
    if args.max_rows is not None:
        to_process = to_process.head(args.max_rows).copy()

    if to_process.empty:
        print("No rows to process (from checkpoint).")
        results_file = module.results_dir / "results.csv"
        if results_file.exists():
            print(f"Existing results: {results_file}")
        return

    results_file = module.results_dir / "results.csv"

    # Ensure header exists
    out_header_df = pd.concat(
        [to_process.head(0), pd.DataFrame(columns=result_cols)],
        axis=1,
    )
    if not results_file.exists():
        out_header_df.to_csv(results_file, index=False)

    buffer: List[pd.DataFrame] = []
    cols_order = list(to_process.columns) + result_cols

    records = to_process.to_dict(orient="records")
    for i, rec in enumerate(tqdm(records, total=len(records), desc="Processing sequentially")):
        try:
            row = pd.Series(rec)
            # Direct call into the core ODE function (no multiprocessing)
            result_vals = module._shimpatica_func(row)
        except Exception as e:
            patient_id = rec.get(module.patient_id_column, "Unknown")
            module.logger.error(f"Error processing Patient {patient_id}: {e}")
            err_row = {k: rec.get(k, None) for k in ["__orig_index__", module.patient_id_column] + required}
            err_row["error"] = str(e)
            module.log_error(err_row)
            continue

        out_row = pd.DataFrame([{**rec, **dict(zip(result_cols, result_vals))}])
        buffer.append(out_row)

        if len(buffer) >= args.checkpoint_interval:
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
    module.logger.info(f"Sequential processing complete. Total rows: {len(final_df)}")
    print(f"Done. Results: {results_file}")


if __name__ == "__main__":
    main()

