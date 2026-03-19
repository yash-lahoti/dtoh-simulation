#!/usr/bin/env python3
"""
Preprocess a patient-level nested/aggregated CSV into a modeling-ready table.

Input (one row per patient, columns contain lists):
  - patient_uid
  - bp_diastolic: list[float]
  - bp_systolic:  list[float]
  - pulse:        list[float]
  - od_iop:       list[float]
  - os_iop:       list[float]
  - code:         list[str]
  - short_desc:   list[str]
  - source_severity: list[str]

Output (one row per patient-eye-diagnosis_code):
  - patient_uid, eye (OD/OS), SBP, DBP, HR, IOP
  - diagnosis_code (unique per patient), diagnosis_short_desc, diagnosis_severity

Rules:
  - If any required values are missing after computing medians, the row is dropped.
  - For multi measurements, SBP/DBP/HR/IOP are computed as the median of the list values.
  - For diagnoses, we keep unique diagnosis codes per patient.
  - Keep only mild/moderate/severe diagnosis events.
  - For each diagnosis code, we keep the highest-priority severity using:
      mild < moderate < severe
"""

from __future__ import annotations

import argparse
import ast
import math
from dataclasses import dataclass
from pathlib import Path
from typing import Any, Dict, Iterable, List, Optional, Sequence, Tuple

import numpy as np
import pandas as pd
from tqdm import tqdm


SEVERITY_PRIORITY_ORDER = [
    # Lowest -> highest priority
    "mild",
    "moderate",
    "severe",
]

# Enforce the user constraint: only these severities are allowed through.
ALLOWED_SEVERITIES = set(SEVERITY_PRIORITY_ORDER)


def _is_null(x: Any) -> bool:
    if x is None:
        return True
    try:
        # Works for NaN and pandas NA
        return bool(pd.isna(x))
    except Exception:
        return False


def parse_list_cell(cell: Any) -> List[Any]:
    """
    Parse a CSV cell that may contain:
      - an actual list (already parsed)
      - a stringified list, e.g. "['a', 'b']" or "[1, 2]"
      - a null/empty value
    """
    if _is_null(cell):
        return []

    if isinstance(cell, list):
        return cell
    if isinstance(cell, tuple):
        return list(cell)
    if isinstance(cell, np.ndarray):
        return list(cell.tolist())

    if isinstance(cell, str):
        s = cell.strip()
        if not s or s.lower() in {"nan", "none", "null"}:
            return []

        # Common pattern: JSON-ish / Python-ish list in string form
        if (s.startswith("[") and s.endswith("]")) or (s.startswith("(") and s.endswith(")")):
            try:
                parsed = ast.literal_eval(s)
                if isinstance(parsed, (list, tuple)):
                    return list(parsed)
                # If it's a single scalar, wrap it
                return [parsed]
            except Exception:
                pass

        # Fallback: split by comma (best-effort; only for simple string lists)
        if "," in s:
            parts = [p.strip() for p in s.split(",")]
            return [p for p in parts if p and p.lower() not in {"nan", "none", "null"}]

        return [s]

    # Best-effort: scalar becomes a single-item list
    return [cell]


def median_from_list(values: Sequence[Any]) -> Optional[float]:
    nums: List[float] = []
    for v in values:
        if _is_null(v):
            continue
        try:
            f = float(v)
        except Exception:
            continue
        if math.isfinite(f):
            nums.append(f)

    if not nums:
        return None
    return float(np.median(np.asarray(nums, dtype=float)))


def normalize_code(code: Any) -> Optional[str]:
    if _is_null(code):
        return None
    s = str(code).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    return s


def normalize_severity(sev: Any) -> Optional[str]:
    if _is_null(sev):
        return None
    s = str(sev).strip()
    if not s or s.lower() in {"nan", "none", "null"}:
        return None
    return s.lower()


def severity_rank(sev: Any, priority_map: Dict[str, int]) -> int:
    norm = normalize_severity(sev)
    if norm is None:
        return -1
    return priority_map.get(norm, -1)


@dataclass(frozen=True)
class Config:
    input_csv: Path
    output_csv: Path
    output_config_yaml: Path
    output_config_base_dir: Path
    patient_uid_col: str
    bp_systolic_col: str
    bp_diastolic_col: str
    pulse_col: str
    od_iop_col: str
    os_iop_col: str
    code_col: str
    short_desc_col: str
    source_severity_col: str
    n_workers: int
    checkpoint_interval: int


def build_yaml_config(
    *,
    pipeline_name: str,
    input_csv_rel: str,
    base_dir_rel: str,
    patient_id_column: str,
    n_workers: int,
    checkpoint_interval: int,
) -> str:
    # Keep this as a simple string generator to avoid YAML dependencies.
    # Important for Windows: convert backslashes to forward slashes and quote paths,
    # otherwise YAML can interpret sequences like "\t" inside "C:\...".
    input_csv_rel = input_csv_rel.replace("\\", "/")
    base_dir_rel = base_dir_rel.replace("\\", "/")
    return "\n".join(
        [
            "pipeline:",
            f"  name: {pipeline_name}",
            "  device: cpu",
            "  modules:",
            "    - name: RetinalModel",
            "      input:",
            f"        csv_path: \"{input_csv_rel}\"",
            "      output:",
            f"        base_dir: \"{base_dir_rel}\"",
            "      config:",
            "        initial_conditions_path: DT_OH/init/Initial_wIOP.csv",
            "        required_columns:",
            "          - \"SBP\"",
            "          - \"DBP\"",
            "          - \"IOP\"",
            "          - \"HR\"",
            f"        patient_id_column: \"{patient_id_column}\"",
            "        processing:",
            f"          n_workers: {n_workers}",
            f"          checkpoint_interval: {checkpoint_interval}",
            "",
        ]
    )


def process_one_patient(
    row: pd.Series,
    *,
    patient_uid_col: str,
    bp_systolic_col: str,
    bp_diastolic_col: str,
    pulse_col: str,
    od_iop_col: str,
    os_iop_col: str,
    code_col: str,
    short_desc_col: str,
    source_severity_col: str,
    priority_map: Dict[str, int],
) -> List[Dict[str, Any]]:
    patient_uid = normalize_code(row.get(patient_uid_col))

    sbp = median_from_list(parse_list_cell(row.get(bp_systolic_col)))
    dbp = median_from_list(parse_list_cell(row.get(bp_diastolic_col)))
    hr = median_from_list(parse_list_cell(row.get(pulse_col)))

    od_iop = median_from_list(parse_list_cell(row.get(od_iop_col)))
    os_iop = median_from_list(parse_list_cell(row.get(os_iop_col)))

    # If vitals are missing, we can't run the retinal model
    if sbp is None or dbp is None or hr is None:
        return []

    codes = parse_list_cell(row.get(code_col))
    short_descs = parse_list_cell(row.get(short_desc_col))
    severities = parse_list_cell(row.get(source_severity_col))

    # Align by index; lists are "ragged" but we assume parallel arrays.
    n = min(len(codes), len(short_descs), len(severities))
    if n == 0 and len(codes) > 0:
        # If some arrays are empty, still allow code-only, but severity/desc will be missing.
        # We'll treat n=0 as no aligned entries, so we build from codes only below.
        pass

    # For each diagnosis code, keep best (highest rank) severity.
    best_by_code: Dict[str, Dict[str, Any]] = {}
    if n > 0:
        for i in range(n):
            c = normalize_code(codes[i])
            if c is None:
                continue
            # Only keep mild/moderate/severe. Drop other severities entirely.
            norm_sev = normalize_severity(severities[i]) if i < len(severities) else None
            if norm_sev is None or norm_sev not in ALLOWED_SEVERITIES:
                continue

            rank = priority_map.get(norm_sev, -1)
            desc = short_descs[i] if i < len(short_descs) else None
            # Choose the highest rank; if tie, keep existing.
            if c not in best_by_code or rank > best_by_code[c]["severity_rank"]:
                best_by_code[c] = {
                    "diagnosis_code": c,
                    "diagnosis_short_desc": desc if not _is_null(desc) else None,
                    "diagnosis_severity": norm_sev if not _is_null(norm_sev) else None,
                    "severity_rank": rank,
                }
    else:
        # If we can't align severity to codes, we can't apply the mild/moderate/severe filter.
        return []

    if not best_by_code:
        # No diagnosis codes => drop (you asked to keep unique diagnosis codes)
        return []

    output_rows: List[Dict[str, Any]] = []

    eye_specs: List[Tuple[str, Optional[float]]] = [("OD", od_iop), ("OS", os_iop)]
    for eye, iop in eye_specs:
        # Drop rows missing IOP for that eye
        if iop is None:
            continue

        for c, meta in best_by_code.items():
            out = {
                patient_uid_col: patient_uid,
                "eye": eye,
                "SBP": sbp,
                "DBP": dbp,
                "HR": hr,
                "IOP": iop,
                "diagnosis_code": meta["diagnosis_code"],
                "diagnosis_short_desc": meta["diagnosis_short_desc"],
                "diagnosis_severity": meta["diagnosis_severity"],
                # Useful for debugging the ranking choice
                "diagnosis_severity_rank": meta["severity_rank"],
            }
            output_rows.append(out)

    return output_rows


def main() -> None:
    parser = argparse.ArgumentParser(
        description="Preprocess nested patient-level aggregate CSV into eye-level rows + ranked diagnoses."
    )
    parser.add_argument("--input-csv", required=True, help="Path to aggregate_data CSV")
    parser.add_argument(
        "--output-csv",
        default="data/processed/processed_aggregate_data.csv",
        help="Where to write the processed CSV",
    )
    parser.add_argument(
        "--output-config-yaml",
        default="config/processed_retinal_model.yaml",
        help="Where to write the YAML config pointing to the processed CSV",
    )
    parser.add_argument("--output-config-base-dir", default="output/DT_OH/processed")
    parser.add_argument("--patient-uid-col", default="patient_uid")

    # Column names in your aggregate_data sheet
    parser.add_argument("--bp-systolic-col", default="bp_systolic")
    parser.add_argument("--bp-diastolic-col", default="bp_diastolic")
    parser.add_argument("--pulse-col", default="pulse")
    parser.add_argument("--od-iop-col", default="od_iop")
    parser.add_argument("--os-iop-col", default="os_iop")
    parser.add_argument("--code-col", default="code")
    parser.add_argument("--short-desc-col", default="short_desc")
    parser.add_argument("--source-severity-col", default="source_severity")

    parser.add_argument("--n-workers", type=int, default=1, help="Workers for the simulation (default: 1)")
    parser.add_argument("--checkpoint-interval", type=int, default=1)
    parser.add_argument(
        "--pipeline-name",
        default="processed_retinal_model",
        help="Name to use inside the YAML config",
    )

    args = parser.parse_args()

    input_csv = Path(args.input_csv).expanduser().resolve()
    if not input_csv.exists():
        raise FileNotFoundError(f"Input CSV not found: {input_csv}")

    output_csv = Path(args.output_csv).expanduser().resolve()
    output_csv.parent.mkdir(parents=True, exist_ok=True)

    output_config_yaml = Path(args.output_config_yaml).expanduser().resolve()
    output_config_yaml.parent.mkdir(parents=True, exist_ok=True)

    output_config_base_dir = Path(args.output_config_base_dir).expanduser().resolve()
    output_config_base_dir.mkdir(parents=True, exist_ok=True)

    priority_map: Dict[str, int] = {s: i for i, s in enumerate(SEVERITY_PRIORITY_ORDER)}

    cfg = Config(
        input_csv=input_csv,
        output_csv=output_csv,
        output_config_yaml=output_config_yaml,
        output_config_base_dir=output_config_base_dir,
        patient_uid_col=args.patient_uid_col,
        bp_systolic_col=args.bp_systolic_col,
        bp_diastolic_col=args.bp_diastolic_col,
        pulse_col=args.pulse_col,
        od_iop_col=args.od_iop_col,
        os_iop_col=args.os_iop_col,
        code_col=args.code_col,
        short_desc_col=args.short_desc_col,
        source_severity_col=args.source_severity_col,
        n_workers=args.n_workers,
        checkpoint_interval=args.checkpoint_interval,
    )

    df = pd.read_csv(cfg.input_csv)
    required_cols = [
        cfg.patient_uid_col,
        cfg.bp_systolic_col,
        cfg.bp_diastolic_col,
        cfg.pulse_col,
        cfg.od_iop_col,
        cfg.os_iop_col,
        cfg.code_col,
        cfg.short_desc_col,
        cfg.source_severity_col,
    ]
    missing = [c for c in required_cols if c not in df.columns]
    if missing:
        raise ValueError(f"Missing required columns in input CSV: {missing}")

    out_rows: List[Dict[str, Any]] = []
    for _, row in tqdm(df.iterrows(), total=len(df), desc="Processing patients"):
        out_rows.extend(
            process_one_patient(
                row,
                patient_uid_col=cfg.patient_uid_col,
                bp_systolic_col=cfg.bp_systolic_col,
                bp_diastolic_col=cfg.bp_diastolic_col,
                pulse_col=cfg.pulse_col,
                od_iop_col=cfg.od_iop_col,
                os_iop_col=cfg.os_iop_col,
                code_col=cfg.code_col,
                short_desc_col=cfg.short_desc_col,
                source_severity_col=cfg.source_severity_col,
                priority_map=priority_map,
            )
        )

    processed = pd.DataFrame(out_rows)

    # Drop rows with missing required simulation inputs (SBP/DBP/HR/IOP)
    processed = processed.dropna(
        subset=["SBP", "DBP", "HR", "IOP", "diagnosis_code", "diagnosis_severity"]
    )

    # Drop helper severity rank if you don't want it later; leaving it is useful.
    processed = processed.reset_index(drop=True)

    processed.to_csv(cfg.output_csv, index=False)

    # Generate YAML config referencing the output CSV with relative paths.
    # Resolve relative paths to the repo root (script location).
    repo_root = Path(__file__).resolve().parent
    try:
        input_rel = cfg.output_csv.relative_to(repo_root)
        base_dir_rel = cfg.output_config_base_dir.relative_to(repo_root)
    except Exception:
        # If user runs from a different layout, still provide absolute paths.
        input_rel = cfg.output_csv
        base_dir_rel = cfg.output_config_base_dir

    yaml_text = build_yaml_config(
        pipeline_name=args.pipeline_name,
        input_csv_rel=str(input_rel),
        base_dir_rel=str(base_dir_rel),
        patient_id_column=cfg.patient_uid_col,
        n_workers=cfg.n_workers,
        checkpoint_interval=cfg.checkpoint_interval,
    )

    cfg.output_config_yaml.write_text(yaml_text, encoding="utf-8")

    print(f"Wrote processed CSV: {cfg.output_csv}")
    print(f"Wrote config YAML: {cfg.output_config_yaml}")
    print(f"Processed rows: {len(processed):,}")


if __name__ == "__main__":
    main()

