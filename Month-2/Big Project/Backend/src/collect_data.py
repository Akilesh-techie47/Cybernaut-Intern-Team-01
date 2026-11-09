"""
src/collect_data.py

Collects US DOT BTS On-Time Performance data for AeroDelay AI.
"""

import hashlib
import json
import sys
import zipfile
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional, Tuple

import pandas as pd
import requests


CONFIG_PATH = Path(__file__).resolve().parent.parent / "configs" / "dataset_sources.yaml"

DEFAULT_CONFIG = {
    "dataset": "bts_on_time",
    "years": list(range(2018, 2023)),
    "months": list(range(1, 13)),
    "output_dir": Path("data/raw"),
    "manifest_path": Path("data/raw/manifest.json"),
    "url_pattern": "https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month:02d}.zip",
    "selected_fields": ",".join([
        "Year", "Month", "DayOfWeek", "DayOfMonth", "Origin", "Dest",
        "CRSDepTime", "DepDel15", "Reporting_Airline",
        "Distance", "CRSElapsedTime", "Cancelled", "CancellationCode", "Diverted",
    ]),

}
def load_manifest(manifest_path: Path) -> Dict:
    if manifest_path.exists():
        try:
            with open(manifest_path, "r", encoding="utf-8") as f:
                return json.load(f)
        except (json.JSONDecodeError, IOError):
            pass
    return {"datasets": [], "total_records": 0, "created": datetime.utcnow().isoformat(), "last_updated": datetime.utcnow().isoformat()}


def save_manifest(manifest: Dict, manifest_path: Path) -> None:
    manifest_path.parent.mkdir(parents=True, exist_ok=True)
    with open(manifest_path, "w", encoding="utf-8") as f:
        json.dump(manifest, f, indent=2, ensure_ascii=False)


def add_to_manifest(manifest: Dict, entry: Dict) -> Dict:
    entry["id"] = f"{entry['filename']}_{entry['checksum_sha256'][:8]}"
    manifest["datasets"].append(entry)
    manifest["total_records"] = manifest.get("total_records", 0) + entry.get("record_count", 0)
    manifest["last_updated"] = datetime.utcnow().isoformat()
    return manifest


def compute_checksum(filepath: Path) -> str:
    sha256 = hashlib.sha256()
    try:
        with open(filepath, "rb") as f:
            for chunk in iter(lambda: f.read(8192), b""):
                sha256.update(chunk)
        return sha256.hexdigest()
    except IOError:
        return ""


def download_file(url: str, dest: Path, timeout: int = 300) -> Tuple[bool, str]:
    try:
        dest.parent.mkdir(parents=True, exist_ok=True)
        response = requests.get(url, stream=True, timeout=timeout)
        if response.status_code != 200:
            return False, f"HTTP {response.status_code} for {url}"
        with open(dest, "wb") as f:
            for chunk in response.iter_content(chunk_size=8192):
                if chunk:
                    f.write(chunk)
        actual_size = dest.stat().st_size
        return True, f"Downloaded {actual_size / 1024:.1f} KB"
    except requests.exceptions.RequestException as e:
        return False, f"Network error: {e}"
    except IOError as e:
        return False, f"File write error: {e}"


def download_bts_zip(year: int, month: int, output_dir: Path, selected_fields: str) -> Optional[Tuple[Path, str]]:
    filename = f"On_Time_Reporting_Carrier_On_Time_Performance_{year}_{month:02d}.zip"
    url = f"https://transtats.bts.gov/PREZIP/On_Time_Reporting_Carrier_On_Time_Performance_1987_present_{year}_{month:02d}.zip"
    dest = output_dir / filename
    success, msg = download_file(url, dest)
    if not success:
        return None, msg
    checksum = compute_checksum(dest)
    if not checksum:
        return None, "Could not compute checksum of downloaded file"
    try:
        with zipfile.ZipFile(dest, "r") as zf:
            csv_names = [n for n in zf.namelist() if n.endswith(".csv")]
            if not csv_names:
                return None, f"No CSV files found in {filename}"
            csv_name = csv_names[0]
            raw_csv = zf.read(csv_name)
            extracted_path = output_dir / f"{filename}_raw.csv"
            with open(extracted_path, "wb") as f:
                f.write(raw_csv)
            return extracted_path, f"Extracted {csv_name}, {len(raw_csv)} bytes"
    except zipfile.BadZipFile:
        return None, f"Bad ZIP file: {filename}"
    except Exception as e:
        return None, f"Extraction error: {e}"


def load_bts_csv(csv_path: Path, selected_fields: str) -> Optional[Tuple[pd.DataFrame, int]]:
    try:
        df = pd.read_csv(csv_path, dtype=str, low_memory=False)
    except FileNotFoundError:
        print(f"[ERROR] Source file not found: {csv_path}")
        return None
    except Exception as e:
        print(f"[ERROR] Could not read CSV {csv_path}: {e}")
        return None
    
    bts_to_standard = {
        "Year": "Year",
        "Month": "Month",
        "DayofMonth": "DayOfMonth",
        "DayOfWeek": "DayOfWeek",
        "FlightDate": "FlightDate",
        "Reporting_Airline": "Reporting_Airline",
        "Origin": "Origin",
        "OriginAirportID": "OriginAirportID",
        "OriginAirportSeqID": "OriginAirportSeqID",
        "OriginCityMarketID": "OriginCityMarketID",
        "OriginCityName": "OriginCityName",
        "OriginState": "OriginState",
        "OriginStateFips": "OriginStateFips",
        "OriginStateName": "OriginStateName",
        "OriginWac": "OriginWac",
        "Dest": "Dest",
        "DestAirportID": "DestAirportID",
        "DestAirportSeqID": "DestAirportSeqID",
        "DestCityMarketID": "DestCityMarketID",
        "DestCityName": "DestCityName",
        "DestState": "DestState",
        "DestStateFips": "DestStateFips",
        "DestStateName": "DestStateName",
        "DestWac": "DestWac",
        "CRSDepTime": "CRSDepTime",
        "DepTime": "DepTime",
        "DepDelay": "DepDelay",
        "DepDelayMinutes": "DepDelayMinutes",
        "Depdel15": "DepDel15",
        "DepDel15": "DepDel15",
        "Depdel15": "DepDel15",
        "DepartureDelayGroups": "DepartureDelayGroups",
        "DepTimeBlk": "DepTimeBlk",
        "TaxiOut": "TaxiOut",
        "WheelsOff": "WheelsOff",
        "WheelsOn": "WheelsOn",
        "TaxiIn": "TaxiIn",
        "CRSArrTime": "CRSArrTime",
        "ArrTime": "ArrTime",
        "ArrDelay": "ArrDelay",
        "ArrDelayMinutes": "ArrDelayMinutes",
        "ArrDel15": "ArrDel15",
        "ArrivalDelayGroups": "ArrivalDelayGroups",
        "ArrTimeBlk": "ArrTimeBlk",
        "Cancelled": "Cancelled",
        "CancellationCode": "CancellationCode",
        "Diverted": "Diverted",
        "CRSElapsedTime": "CRSElapsedTime",
        "ActualElapsedTime": "ActualElapsedTime",
        "AirTime": "AirTime",
        "Flights": "Flights",
        "Distance": "Distance",
        "DistanceGroup": "DistanceGroup",
        "CarrierDelay": "CarrierDelay",
        "WeatherDelay": "WeatherDelay",
        "NASDelay": "NASDelay",
        "SecurityDelay": "SecurityDelay",
        "LateAircraftDelay": "LateAircraftDelay",
        "FirstDepTime": "FirstDepTime",
        "TotalAddGTime": "TotalAddGTime",
        "LongestAddGTime": "LongestAddGTime",
        "DivAirportLandings": "DivAirportLandings",
        "DivReachedDest": "DivReachedDest",
        "DivActualElapsedTime": "DivActualElapsedTime",
        "DivArrDelay": "DivArrDelay",
        "DivDistance": "DivDistance",
        "Div1Airport": "Div1Airport",
        "Div1AirportID": "Div1AirportID",
        "Div1AirportSeqID": "Div1AirportSeqID",
        "Div1WheelsOn": "Div1WheelsOn",
        "Div1TotalGTime": "Div1TotalGTime",
        "Div1WheelsOff": "Div1WheelsOff",
        "Div1TailNum": "Div1TailNum",
        "Div2Airport": "Div2Airport",
        "Div2AirportID": "Div2AirportID",
        "Div2AirportSeqID": "Div2AirportSeqID",
        "Div2WheelsOff": "Div2WheelsOff",
        "Div2TotalGTime": "Div2TotalGTime",
        "Div2WheelsOff": "Div2WheelsOff",
        "Div2TailNum": "Div2TailNum",
        "Div3Airport": "Div3Airport",
        "Div3AirportID": "Div3AirportID",
        "Div3AirportSeqID": "Div3AirportSeqID",
        "Div3WheelsOff": "Div3WheelsOff",
        "Div3TotalGTime": "Div3TotalGTime",
        "Div3WheelsOff": "Div3WheelsOff",
        "Div3TailNum": "Div3TailNum",
        "Div4Airport": "Div4Airport",
        "Div4AirportID": "Div4AirportID",
        "Div4AirportSeqID": "Div4AirportSeqID",
        "Div4WheelsOff": "Div4WheelsOff",
        "Div4TotalGTime": "Div4TotalGTime",
        "Div4WheelsOff": "Div4WheelsOff",
        "Div4TailNum": "Div4TailNum",
        "Div5Airport": "Div5Airport",
        "Div5AirportID": "Div5AirportID",
        "Div5AirportSeqID": "Div5AirportSeqID",
        "Div5WheelsOff": "Div5WheelsOff",
        "Div5TailNum": "Div5TailNum",
        "Unnamed: 109": "Unnamed_109",
    }
    df = df.rename(columns=bts_to_standard)
    # Remove duplicate columns
    df = df.loc[:, ~df.columns.duplicated()].copy()
    # Check for DepDel15 case-insensitively (title case may convert to Depdel15)
    cols_lower = [c.lower() for c in df.columns]
    depdel_idx = None
    for i, c in enumerate(cols_lower):
        if c == "depdel15":
            depdel_idx = i
            break
    if depdel_idx is not None:
        df = df.rename(columns={df.columns[depdel_idx]: "DepDel15"})
    available_fields = [f for f in selected_fields.split(",") if f in df.columns]
    missing_fields = [f for f in selected_fields.split(",") if f not in df.columns]
    if missing_fields:
        print(f"[WARN] Requested fields not found in {csv_path}: {missing_fields}")
    if available_fields:
        df = df[available_fields].copy()
    else:
        print(f"[WARN] None of the requested fields found in {csv_path}. Using all columns.")
    numeric_cols = ["Year", "Month", "DayOfWeek", "DayOfMonth", "CRSDepTime", "DepDelay", "DepDel15",
                    "CANCELLED", "DIVERTED", "Distance", "CRSElapsedTime"]
    for col in numeric_cols:
        if col in df.columns:
            df[col] = pd.to_numeric(df[col], errors="coerce")
    record_count = len(df)
    df = df.dropna(how="all")
    return df, record_count


def create_dep_delay15_target(df: pd.DataFrame) -> pd.DataFrame:
    """Create the DepDelay15 binary target column.
    
    Target: 1 if departure delay >= 15 minutes, 0 otherwise.
    Uses DEP_DEL15 if available; otherwise derives from DEP_DELAY.
    """
    # Check for DepDel15 case-insensitively
    cols_lower = [c.lower() for c in df.columns]
    depdel_idx = None
    for i, c in enumerate(cols_lower):
        if c == "depdel15":
            depdel_idx = i
            break
    
    if depdel_idx is not None:
        # Use the pre-computed target; convert to binary, handling NaN
        df["DepDelay15"] = df[df.columns[depdel_idx]].fillna(0).astype(int)
    elif "DepDelay" in df.columns:
        # Derive from DEP_DELAY: 1 if delay >= 15, 0 otherwise
        dep_delay_num = pd.to_numeric(df["DepDelay"], errors="coerce")
        df["DepDelay15"] = (dep_delay_num >= 15).astype(int)
    else:
        raise ValueError("Neither DepDel15 nor DepDelay column found; cannot create DepDelay15 target.")
    
    # Ensure binary (clip to 0/1 in case of unexpected values)
    df["DepDelay15"] = df["DepDelay15"].clip(0, 1)
    
    return df


def collect_dataset(config: Dict = None) -> Dict:
    if config is None:
        config = DEFAULT_CONFIG
    config = {**DEFAULT_CONFIG, **config}
    output_dir: Path = config["output_dir"]
    manifest_path: Path = config["manifest_path"]
    years: List[int] = config["years"]
    months: List[int] = config["months"]
    selected_fields: str = config["selected_fields"]
    output_dir.mkdir(parents=True, exist_ok=True)
    Path("reports").mkdir(parents=True, exist_ok=True)
    manifest = load_manifest(manifest_path)
    stats = {"files_downloaded": 0, "files_extracted": 0, "records_total": 0, "errors": []}
    print(f"=== AeroDelay AI Data Collection ===")
    print(f"Dataset: BTS On-Time Performance (Reporting Carrier)")
    print(f"Period: {min(years)}-{max(years)}, months {min(months)}-{max(months)}")
    print(f"Output: {output_dir}")
    print()
    for year in years:
        for month in months:
            print(f"[Processing] YEAR={year}, MONTH={month:02d}...")
            result = download_bts_zip(year, month, output_dir, selected_fields)
            if result[0] is None:
                error_msg = result[1]
                print(f"  [SKIP] {error_msg}")
                stats["errors"].append(f"Y{year}M{month:02d}: {error_msg}")
                continue
            csv_path, extraction_msg = result
            print(f"  {extraction_msg}")
            df_result = load_bts_csv(csv_path, selected_fields)
            if df_result is None:
                stats["errors"].append(f"Y{year}M{month:02d}: Failed to load CSV {csv_path}")
                continue
            df, record_count = df_result
            try:
                df = create_dep_delay15_target(df)
            except ValueError as e:
                stats["errors"].append(f"Y{year}M{month:02d}: {e}")
                continue
            entry = {
                "source_url": config["url_pattern"].format(year=year, month=month),
                "retrieval_timestamp": datetime.utcnow().isoformat(),
                "filename": csv_path.name,
                "file_size_bytes": csv_path.stat().st_size if csv_path.exists() else 0,
                "checksum_sha256": compute_checksum(csv_path) if csv_path.exists() else "",
                "year": year,
                "month": month,
                "record_count": record_count,
                "selected_fields": selected_fields.split(","),
                "target_column": "DepDelay15",
                "dataset_name": config["dataset"],
            }
            manifest = add_to_manifest(manifest, entry)
            stats["files_downloaded"] += 1
            stats["files_extracted"] += 1
            stats["records_total"] += record_count
            print(f"  Records: {record_count:,}")
            print(f"  DepDelay15 distribution: {df['DepDelay15'].value_counts().to_dict()}")
    save_manifest(manifest, manifest_path)
    print()
    print(f"=== Collection Complete ===")
    print(f"Files processed: {stats['files_downloaded']}")
    print(f"Total records: {stats['records_total']:,}")
    if stats["errors"]:
        print(f"Errors: {len(stats['errors'])}")
        for e in stats["errors"][:5]:
            print(f"  - {e}")
    return manifest


def main():
    import argparse
    parser = argparse.ArgumentParser(description="AeroDelay AI: Collect BTS On-Time Performance data")
    parser.add_argument("--years", nargs="+", type=int, default=None, help="List of years to download")
    parser.add_argument("--months", nargs="+", type=int, default=None, help="List of months to download (1-12)")
    parser.add_argument("--output", type=str, default=None, help="Output directory for raw data")
    parser.add_argument("--list-urls", action="store_true", help="List available BTS URLs without downloading")
    args = parser.parse_args()
    config = DEFAULT_CONFIG.copy()
    if args.years:
        config["years"] = args.years
    if args.months:
        config["months"] = args.months
    if args.output:
        config["output_dir"] = Path(args.output)
    config["manifest_path"] = config["output_dir"] / "manifest.json"
    config["manifest_path"].parent.mkdir(parents=True, exist_ok=True)
    if args.list_urls:
        for year in config["years"]:
            for month in config["months"]:
                url = config["url_pattern"].format(year=year, month=month)
                print(f"Y{year}M{month:02d}: {url}")
        return
    manifest = collect_dataset(config)
    print(f"\nManifest saved to: {config['manifest_path']}")
    print(f"Dataset entries: {len(manifest.get('datasets', []))}")


if __name__ == "__main__":
    main()