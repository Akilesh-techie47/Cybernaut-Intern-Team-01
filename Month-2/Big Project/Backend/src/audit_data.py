"""
src/audit_data.py

Inspects collected BTS On-Time Performance data and produces:
- reports/data_audit.md  : Human-readable audit report
- reports/data_dictionary.csv : Machine-readable data dictionary
"""

import hashlib
import json
import sys
import csv
import argparse
import pandas as pd
from pathlib import Path
from typing import Dict, List, Optional, Tuple


# ---------------------------------------------------------------------------
# Core inspection logic
# ---------------------------------------------------------------------------

def inspect_dataset(data_dir: Path = Path("data/raw")) -> Dict:
    """Inspect all collected BTS CSV files and return audit results."""
    
    audit = {
        "dataset_source": "US DOT BTS On-Time Performance - Reporting Carrier",
        "inspection_timestamp": pd.Timestamp.utcnow().isoformat(),
        "files_inspected": 0,
        "total_records": 0,
        "columns_observed": set(),
        "predictors_identified": [],
        "leakage_columns_found": [],
        "target_column": None,
        "target_distribution": {},
        "missing_value_summary": {},
        "duplicate_rows": 0,
        "usable_records": 0,
        "warnings": [],
        "errors": [],
    }
    
    # Find CSV files in data/raw
    csv_files = sorted(data_dir.glob("*.csv"))
    
    # Filter out manifest and non-BTS files
    bts_csvs = [f for f in csv_files if f.name != "manifest.json"]
    
    if not bts_csvs:
        audit["errors"].append("No CSV files found in data/raw!. Did you run collect_data.py?")
        return audit
    
    print(f"Inspecting {len(bts_csvs)} CSV file(s) from {data_dir}...\n")
    
    all_dfs = []
    
    for csv_file in bts_csvs:
        print(f"  Examining: {csv_file.name}")
        
        try:
            df = pd.read_csv(csv_file, dtype=str, low_memory=False)
            df.columns = df.columns.str.strip()
            
            # Normalize column names to title case for consistency
            df.columns = df.columns.str.title()
            
            row_count = len(df)
            audit["total_records"] += row_count
            audit["files_inspected"] += 1
            
            # Record observed columns (original names after title case)
            observed_cols = set(df.columns)
            audit["columns_observed"].update(observed_cols)
            
            # === Target column check (case-insensitive) ===
            # Check for DepDel15 or DepDelay15 case-insensitively
            # (title case may convert "DepDel15" -> "Depdel15")
            cols_lower = [c.lower() for c in observed_cols]
            actual_target_col = None
            if "depdel15" in cols_lower:
                actual_target_col = [c for c in observed_cols if c.lower() == "depdel15"][0]
                audit["target_column"] = actual_target_col
                target_dist = df[actual_target_col].value_counts(dropna=False).to_dict()
                audit["target_distribution"] = {
                    str(k): int(v) for k, v in target_dist.items()
                }
            elif "depdelay15" in cols_lower:
                actual_target_col = [c for c in observed_cols if c.lower() == "depdelay15"][0]
                audit["target_column"] = actual_target_col
                target_dist = df[actual_target_col].value_counts(dropna=False).to_dict()
                audit["target_distribution"] = {
                    str(k): int(v) for k, v in target_dist.items()
                }
            else:
                audit["warnings"].append("No DepDel15 or DepDelay15 column found in this file.")
            
            # === Leakage column identification ===
            leakage = []
            if "DepTime" in observed_cols:
                leakage.append("DEP_TIME (Actual Departure Time - post-departure)")
            if "DepDelay" in observed_cols:
                leakage.append("DEP_DELAY (Actual Departure Delay - post-departure)")
            if "ArrTime" in observed_cols:
                leakage.append("ARR_TIME (Actual Arrival Time - post-departure)")
            if "ArrDelay" in observed_cols:
                leakage.append("ARR_DELAY (Actual Arrival Delay - post-departure)")
            if "ActualElapsedTime" in observed_cols:
                leakage.append("ACTUAL_ELAPSED_TIME (post-departure)")
            if "TaxiOut" in observed_cols:
                leakage.append("TAXI_OUT (post-departure taxi duration)")
            if "WheelsOff" in observed_cols:
                leakage.append("WHEELS_OFF (wheels off time - post-departure)")
            
            if leakage:
                audit["leakage_columns_found"].extend(leakage)
                audit["warnings"].append(f"Leakage columns present in {csv_file.name}: {leakage}")
            
            # === Candidate predictors (pre-departure, leakage-safe) ===
            pre_departure_predictors = []
            if "Reporting_Airline" in observed_cols:
                pre_departure_predictors.append("Reporting_Airline")  # carrier
            if "Origin" in observed_cols:
                pre_departure_predictors.append("Origin")  # origin airport
            if "Dest" in observed_cols:
                pre_departure_predictors.append("Dest")  # destination airport
            if "DayOfWeek" in observed_cols:
                pre_departure_predictors.append("DayOfWeek")
            if "Month" in observed_cols:
                pre_departure_predictors.append("Month")
            if "CRSDepTime" in observed_cols:
                pre_departure_predictors.append("CRSDepTime")  # scheduled departure time
            if "Distance" in observed_cols:
                pre_departure_predictors.append("Distance")  # distance between airports
            if "CRSElapsedTime" in observed_cols:
                pre_departure_predictors.append("CRSElapsedTime")  # scheduled elapsed time
            if "Cancelled" in observed_cols:
                pre_departure_predictors.append("Cancelled")
            if "CancellationCode" in observed_cols:
                pre_departure_predictors.append("CancellationCode")
            if "Diverted" in observed_cols:
                pre_departure_predictors.append("Diverted")
            
            audit["predictors_identified"].extend(pre_departure_predictors)
            
            # === Missing value analysis ===
            missing_per_col = df.isna().sum().to_dict()
            missing_pct = (df.isna().sum() / len(df) * 100).to_dict() if len(df) > 0 else {}
            audit["missing_value_summary"][csv_file.name] = {
                "counts": {str(k): int(v) for k, v in missing_per_col.items()},
                "pcts": {str(k): round(v, 2) for k, v in missing_pct.items()}
            }
            
            # === Duplicate rows ===
            dup_count = df.duplicated().sum()
            audit["duplicate_rows"] += dup_count
            
            # === Numeric range checks for key columns ===
            for col in ["CRSDepTime", "Distance", "CRSElapsedTime"]:
                if col in df.columns:
                    numeric_col = pd.to_numeric(df[col], errors="coerce")
                    null_count = numeric_col.isna().sum()
                    if null_count > 0:
                        audit["warnings"].append(f"{col} has {null_count} non-numeric values in {csv_file.name}")
            
            all_dfs.append(df)
            
        except Exception as e:
            audit["errors"].append(f"Error inspecting {csv_file.name}: {e}")
            print(f"    [ERROR] {e}")
    
    # === Consolidate findings ===
    # Deduplicate predictors (preserve order, keep unique)
    seen = set()
    unique_predictors = []
    for p in audit["predictors_identified"]:
        if p not in seen:
            seen.add(p)
            unique_predictors.append(p)
    audit["predictors_identified"] = unique_predictors
    
    # Deduplicate leakage columns
    seen = set()
    unique_leakage = []
    for l in audit["leakage_columns_found"]:
        if l not in seen:
            seen.add(l)
            unique_leakage.append(l)
    audit["leakage_columns_found"] = unique_leakage
    
    # === Usable records ===
    if all_dfs:
        combined = pd.concat(all_dfs, ignore_index=True)
        # Remove rows where target is NaN
        if audit["target_column"] and audit["target_column"] in combined.columns:
            combined = combined[combined[audit["target_column"]].notna()]
        
        # Count records with at least one predictor non-null
        predictor_cols = [c for c in audit["predictors_identified"] if c in combined.columns]
        if predictor_cols:
            has_predictor = combined[predictor_cols].notna().any(axis=1)
            audit["usable_records"] = int(has_predictor.sum())
        else:
            audit["usable_records"] = len(combined)
    
    # Minimum requirements check
    if audit["usable_records"] < 500:
        audit["warnings"].append(
            f"Usable records ({audit['usable_records']}) below minimum of 500. "
            f"Consider extending the date range."
        )
    if len(audit["predictors_identified"]) < 6:
        audit["warnings"].append(
            f"Fewer than 6 predictors identified ({len(audit['predictors_identified'])}). "
            f"Consider adding more pre-departure fields."
        )
    
    return audit


# ---------------------------------------------------------------------------
# Report generation
# ---------------------------------------------------------------------------

def write_audit_report(audit: Dict, output_path: Path = Path("reports/data_audit.md")) -> None:
    """Write the human-readable audit report."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    leakage_str = "\n".join(audit["leakage_columns_found"]) if audit["leakage_columns_found"] else "None observed."
    
    # Build missing-value summary lines
    mv_lines = []
    for fname, msum in audit["missing_value_summary"].items():
        for col, count in msum["counts"].items():
            if count > 0:
                pct = msum["pcts"].get(col, 0)
                mv_lines.append(f"- **{col}**: {count} total missing ({pct}%)")
    
    report = f"""# AeroDelay AI Dataset Audit Report

**Source:** {audit['dataset_source']}  
**Inspection Date:** {audit['inspection_timestamp']}  
**Files Inspected:** {audit['files_inspected']}  

## Minimum Requirements Check

- **Usable Records:** {audit['usable_records']:,} (minimum required: 500)
  - {'✅ PASS' if audit['usable_records'] >= 500 else '❌ FAIL'}  
- **Meaningful Predictors:** {len(audit['predictors_identified'])} (minimum required: 6)
  - {'✅ PASS' if len(audit['predictors_identified']) >= 6 else '❌ FAIL'}  

## Target Distribution

{chr(10).join([f"- **{k}**: {v}" for k, v in audit['target_distribution'].items()])}

## Identified Predictors ({len(audit['predictors_identified'])})

{chr(10).join([f"{i+1}. **{p}**" for i, p in enumerate(audit['predictors_identified'])])}

## Potential Leakage Columns ({len(audit['leakage_columns_found'])})

{leakage_str}

## Missing-Value Summary

{chr(10).join(mv_lines) if mv_lines else "- No missing values observed."}

## Duplicate Rows

- **Total duplicate rows:** {audit['duplicate_rows']}

## Warnings

{chr(10).join([f"- {w}" for w in audit['warnings']]) if audit['warnings'] else "- No warnings."}

## Errors

{chr(10).join([f"- {e}" for e in audit['errors']]) if audit['errors'] else "- No errors."}
"""
    
    with open(output_path, "w", encoding="utf-8") as f:
        f.write(report)
    
    print(f"Audit report written to: {output_path}")


def write_data_dictionary(audit: Dict, output_path: Path = Path("reports/data_dictionary.csv")) -> None:
    """Write the data dictionary CSV."""
    output_path.parent.mkdir(parents=True, exist_ok=True)
    
    # Build rows from observed columns and audit findings
    rows = []
    
    # Add predictor columns
    for i, predictor in enumerate(audit["predictors_identified"]):
        rows.append({
            "field_name": predictor,
            "field_type": "categorical" if predictor in ["Reporting_Airline", "Origin", "Dest", "DayOfWeek"] else "numeric",
            "description": f"Predictor {i+1}: {predictor}",
            "source": "BTS On-Time Performance",
            "leakage_risk": "safe" if predictor not in audit["leakage_columns_found"] else "high",
        })
    
    # Add target column
    target = audit.get("target_column", "DepDelay15")
    rows.append({
        "field_name": target,
        "field_type": "binary",
        "description": "Target: 1 = departure >= 15 min late, 0 = otherwise",
        "source": "BTS On-Time Performance (DepDel15 or derived from DEP_DELAY)",
        "leakage_risk": "safe",
    })
    
    # Add leakage columns as warnings
    for leakage in audit["leakage_columns_found"]:
        rows.append({
            "field_name": leakage,
            "field_type": "observed",
            "description": f"LEAKAGE COLUMN: {leakage} - MUST NOT be used as predictor",
            "source": "BTS On-Time Performance",
            "leakage_risk": "high - post-departure information",
        })
    
    # Add missing-value info for key columns
    for fname, msum in audit["missing_value_summary"].items():
        for col, count in msum["counts"].items():
            if count > 0:
                pct = msum["pcts"].get(col, 0)
                rows.append({
                    "field_name": col,
                    "field_type": "numeric/missing",
                    "description": f"Missing values: {count} rows ({pct}%)",
                    "source": fname,
                    "leakage_risk": "safe",
                })
    
    with open(output_path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=["field_name", "field_type", "description", "source", "leakage_risk"])
        writer.writeheader()
        writer.writerows(rows)
    
    print(f"Data dictionary written to: {output_path}")


# ---------------------------------------------------------------------------
# CLI entry point
# ---------------------------------------------------------------------------

def main():
    parser = argparse.ArgumentParser(description="AeroDelay AI: Dataset inspection and audit")
    parser.add_argument("--data-dir", type=str, default="data/raw",
                        help="Directory containing collected CSV files")
    parser.add_argument("--report", type=str, default="reports/data_audit.md",
                        help="Output path for audit markdown report")
    parser.add_argument("--dictionary", type=str, default="reports/data_dictionary.csv",
                        help="Output path for data dictionary CSV")
    parser.add_argument("--compact", action="store_true",
                        help="Produce compact output summary only")
    
    args = parser.parse_args()
    
    data_dir = Path(args.data_dir)
    
    if not data_dir.exists():
        print(f"[ERROR] Data directory does not exist: {data_dir}")
        print("Run collect_data.py first to download and extract the dataset.")
        sys.exit(1)
    
    # Run inspection
    audit = inspect_dataset(data_dir)
    
    # Write reports
    write_audit_report(audit, Path(args.report))
    write_data_dictionary(audit, Path(args.dictionary))
    
    # Print summary
    print(f"\n=== Audit Summary ===")
    print(f"Files inspected: {audit['files_inspected']}")
    print(f"Total records: {audit['total_records']:,}")
    print(f"Usable records: {audit['usable_records']:,}")
    print(f"Predictors identified: {len(audit['predictors_identified'])}")
    print(f"Leakage columns: {len(audit['leakage_columns_found'])}")
    print(f"\nReports written:")
    print(f"  - {args.report}")
    print(f"  - {args.dictionary}")
    
    # Exit with error code if requirements not met
    if audit["usable_records"] < 500:
        print(f"\n⚠ WARNING: Usable records below 500 minimum. Consider expanding the date range.")
        sys.exit(2)
    if len(audit["predictors_identified"]) < 6:
        print(f"\n⚠ WARNING: Fewer than 6 predictors. Consider adding more pre-departure fields.")
        sys.exit(3)


if __name__ == "__main__":
    main()