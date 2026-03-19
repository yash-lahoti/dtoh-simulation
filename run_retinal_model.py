#!/usr/bin/env python3
"""
Convenience runner for the DT_OH retinal hemodynamics simulation.

Usage:
  python run_retinal_model.py --input data/my.csv --output output/DT_OH/my_run
"""

import argparse
from pathlib import Path

from DT_OH import RetinalModelModuleWrapper


def main() -> None:
    parser = argparse.ArgumentParser(description="Run DT_OH retinal simulation on an input CSV.")
    parser.add_argument(
        "--input",
        required=True,
        help="Path to input CSV (must include columns: SBP, DBP, IOP, HR; optional Patient).",
    )
    parser.add_argument(
        "--output",
        required=True,
        help="Output directory. Results will be written to <output>/results.csv.",
    )
    parser.add_argument(
        "--initial-conditions",
        default="DT_OH/init/Initial_wIOP.csv",
        help="Path to Initial_wIOP.csv (defaults to the one shipped with this repo).",
    )
    parser.add_argument(
        "--patient-id-column",
        default="Patient",
        help="Column name used for logging patient identifiers (optional).",
    )
    parser.add_argument(
        "--n-workers",
        type=int,
        default=1,
        help="Number of parallel workers (default: 1).",
    )
    parser.add_argument(
        "--checkpoint-interval",
        type=int,
        default=1,
        help="How often to write checkpoint updates (default: 1 row).",
    )

    args = parser.parse_args()

    input_csv = Path(args.input).expanduser().resolve()
    output_dir = Path(args.output).expanduser().resolve()

    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    module_def = {
        "name": "RetinalModel",
        "input": {"csv_path": str(input_csv)},
        "output": {"base_dir": str(output_dir)},
        "config": {
            "initial_conditions_path": args.initial_conditions,
            # The core ODE code expects these exact column names.
            "required_columns": ["SBP", "DBP", "IOP", "HR"],
            "patient_id_column": args.patient_id_column,
            "processing": {
                "n_workers": args.n_workers,
                "checkpoint_interval": args.checkpoint_interval,
            },
        },
    }

    wrapper = RetinalModelModuleWrapper(module_def=module_def)
    wrapper.run()


if __name__ == "__main__":
    main()

