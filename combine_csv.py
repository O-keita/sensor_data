#!/usr/bin/env python3
"""
combine_activity_sessions.py

Scan activity subfolders under a data root, find session subfolders under each
activity's extracted/ directory, merge each session's Accelerometer and Gyroscope CSVs
on their timestamp column, and produce per-activity combined CSVs.

Now supports a --name / -n argument. If provided, the sanitized name will be
prepended to the output filename, e.g. "omar_jumping_combined.csv".

Output per-activity file layout (one file per activity):
    <out_dir>/<name_><activity>_combined.csv

Columns (ordered):
    timestamp
    accel_x
    accel_y
    accel_z
    gyro_x
    gyro_y
    gyro_z

Usage:
  python combine_activity_sessions.py --source-root data --extracted-subdir extracted --out data/combined --name Omar
  python combine_activity_sessions.py  # prompts for missing values
"""
from __future__ import annotations
import argparse
import os
import re
import sys
from typing import Dict, List, Optional, Tuple

import pandas as pd

# Keywords for file detection
ACCEL_KEYWORDS = ("accelerometer", "accel")
GYRO_KEYWORDS = ("gyroscope", "gyro")

# Default order of output columns
OUTPUT_COLS = ["timestamp", "accel_x", "accel_y", "accel_z", "gyro_x", "gyro_y", "gyro_z"]


def find_activities(source_root: str) -> List[str]:
    """Return activity directories directly under source_root (directories only)."""
    items = []
    for entry in sorted(os.listdir(source_root)):
        full = os.path.join(source_root, entry)
        if os.path.isdir(full):
            items.append(full)
    return items


def find_session_dirs(activity_dir: str, extracted_subdir: str) -> List[str]:
    """Return list of session directories under activity_dir/<extracted_subdir>."""
    extracted_dir = os.path.join(activity_dir, extracted_subdir)
    if not os.path.isdir(extracted_dir):
        return []
    sessions = []
    for entry in sorted(os.listdir(extracted_dir)):
        full = os.path.join(extracted_dir, entry)
        if os.path.isdir(full):
            sessions.append(full)
    return sessions


def find_sensor_files_in_session(session_dir: str) -> Tuple[Optional[str], Optional[str]]:
    """
    Find accel and gyro CSV paths in session_dir. Matching is case-insensitive and
    looks for filenames containing 'accelerometer'/'accel' and 'gyroscope'/'gyro'.
    """
    accel = None
    gyro = None
    for f in sorted(os.listdir(session_dir)):
        p = os.path.join(session_dir, f)
        if not os.path.isfile(p):
            continue
        low = f.lower()
        if low.endswith(".csv") and any(k in low for k in ACCEL_KEYWORDS):
            accel = p
        if low.endswith(".csv") and any(k in low for k in GYRO_KEYWORDS):
            gyro = p
    return accel, gyro


def choose_timestamp_column(df: pd.DataFrame) -> str:
    """Pick most-likely timestamp column name from df (prefers names containing time/timestamp/ts/seconds)."""
    for pattern in (r"time", r"timestamp", r"ts", r"seconds", r"sec", r"elapsed"):
        for c in df.columns:
            if re.search(pattern, c, flags=re.I):
                return c
    # fallback: first column
    return df.columns[0]


def detect_xyz_columns(df: pd.DataFrame) -> Dict[str, str]:
    """
    Detect column names for x,y,z axes. Returns mapping {'x': colname, ...}.
    Raises ValueError if not all found.
    """
    mapping: Dict[str, str] = {}
    cols = list(df.columns)
    for col in cols:
        low = col.lower()
        if re.search(r"time|timestamp|sec|elapsed", col, flags=re.I):
            continue
        tokens = re.split(r"[^a-z0-9]+", low)
        tokens = [t for t in tokens if t]
        for axis in ("x", "y", "z"):
            if axis in tokens and axis not in mapping:
                mapping[axis] = col
    # try suffix match if any missing
    for axis in ("x", "y", "z"):
        if axis not in mapping:
            for col in cols:
                if col.lower().endswith(axis) and axis not in mapping:
                    mapping[axis] = col
    # final fallback: single-letter columns named 'x','y','z'
    for axis in ("x", "y", "z"):
        if axis not in mapping:
            for col in cols:
                if col.strip().lower() == axis:
                    mapping[axis] = col
    if len(mapping) != 3:
        raise ValueError(f"Couldn't detect all axes in columns: {cols}. Found: {mapping}")
    return mapping


def safe_read_csv(path: str) -> pd.DataFrame:
    """Read CSV with pandas using python engine (more permissive)."""
    return pd.read_csv(path, engine="python")


def merge_session(accel_path: str, gyro_path: str, verbose: bool = False) -> pd.DataFrame:
    """
    Merge one session's accelerometer and gyroscope CSVs on timestamp.
    Returns DataFrame with columns: timestamp, accel_x/y/z, gyro_x/y/z (where available).
    """
    a = safe_read_csv(accel_path)
    g = safe_read_csv(gyro_path)

    ts_a = choose_timestamp_column(a)
    ts_g = choose_timestamp_column(g)

    if verbose:
        print(f" Session: accel_ts='{ts_a}', gyro_ts='{ts_g}'")

    # unify timestamp column name for merging
    common_ts = ts_a if ts_a == ts_g else "timestamp"
    if common_ts != ts_a:
        a = a.rename(columns={ts_a: common_ts})
    if common_ts != ts_g:
        g = g.rename(columns={ts_g: common_ts})

    # detect axis columns
    am = detect_xyz_columns(a)
    gm = detect_xyz_columns(g)

    if verbose:
        print(f"  accel cols -> {am}")
        print(f"  gyro cols  -> {gm}")

    a_sel = a[[common_ts, am["x"], am["y"], am["z"]]].copy()
    a_sel = a_sel.rename(columns={am["x"]: "accel_x", am["y"]: "accel_y", am["z"]: "accel_z"})
    g_sel = g[[common_ts, gm["x"], gm["y"], gm["z"]]].copy()
    g_sel = g_sel.rename(columns={gm["x"]: "gyro_x", gm["y"]: "gyro_y", gm["z"]: "gyro_z"})

    # try to convert timestamp to numeric to help merging/sorting
    try:
        a_sel[common_ts] = pd.to_numeric(a_sel[common_ts], errors="coerce")
        g_sel[common_ts] = pd.to_numeric(g_sel[common_ts], errors="coerce")
    except Exception:
        pass

    # inner join on timestamp (only matching timestamps retained)
    merged = pd.merge(a_sel, g_sel, on=common_ts, how="inner", sort=True)
    merged = merged.reset_index(drop=True)

    # rename timestamp column to standard 'timestamp'
    if common_ts != "timestamp":
        merged = merged.rename(columns={common_ts: "timestamp"})

    # ensure column ordering; if any missing keep what's present
    cols_present = [c for c in OUTPUT_COLS if c in merged.columns]
    merged = merged[cols_present]
    return merged


def make_unique_path(path: str, overwrite: bool) -> str:
    if overwrite or not os.path.exists(path):
        return path
    base, ext = os.path.splitext(path)
    idx = 1
    candidate = f"{base}_{idx}{ext}"
    while os.path.exists(candidate):
        idx += 1
        candidate = f"{base}_{idx}{ext}"
    return candidate


def sanitize_name(name: str) -> str:
    """Sanitize provided name to safe lowercase token (letters, digits, underscore, dash)."""
    if not name:
        return ""
    s = name.strip().lower()
    # replace non-alnum/_/- with underscore
    s = re.sub(r"[^a-z0-9_-]+", "_", s)
    # collapse multiple underscores
    s = re.sub(r"_+", "_", s)
    s = s.strip("_")
    return s


def parse_args() -> argparse.Namespace:
    p = argparse.ArgumentParser(description="Combine accelerometer+gyroscope CSVs across extracted session folders per activity.")
    p.add_argument("--source-root", "-s", help="Root folder that contains activity subfolders (default: data)", default="data")
    p.add_argument("--extracted-subdir", "-e", help="Name of extracted subfolder under each activity (default: extracted)", default="extracted")
    p.add_argument("--activity", "-a", help="Specific activity folder to process (e.g. walking). If omitted, all activities under source-root are processed")
    p.add_argument("--out", "-o", help="Output directory for combined files (default: data/combined)", default=os.path.join("data", "combined"))
    p.add_argument("--name", "-n", help="Optional name to prepend to output filenames (e.g. Omar -> omar_activity_combined.csv)")
    p.add_argument("--add-session", action="store_true", help="Add 'session' column to aggregated per-activity output identifying the session folder")
    p.add_argument("--overwrite", action="store_true", help="Overwrite existing output files")
    p.add_argument("--recursive", "-r", action="store_true", help="Search for session folders recursively under extracted subdir")
    p.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    return p.parse_args()


def prompt_if_missing(val: Optional[str], prompt_text: str, default: Optional[str] = None) -> str:
    if val:
        return val
    try:
        raw = input(prompt_text).strip()
    except EOFError:
        raw = ""
    if raw:
        return raw
    if default is not None:
        return default
    raise ValueError("Required value not provided")


def main():
    args = parse_args()
    source_root = prompt_if_missing(args.source_root, "Source root (folder that contains activity subfolders) [default: data]: ", default="data")
    extracted_subdir = prompt_if_missing(args.extracted_subdir, "Name of extracted subfolder under each activity [default: extracted]: ", default="extracted")
    out_base = prompt_if_missing(args.out, "Output base folder for combined CSVs [default: data/combined]: ", default=os.path.join("data", "combined"))
    name_raw = prompt_if_missing(args.name, "Optional name to prepend to filenames (press Enter to skip): ", default="")

    name_token = sanitize_name(name_raw)

    if args.activity:
        activities = [os.path.join(source_root, args.activity)]
    else:
        activities = find_activities(source_root)

    if not activities:
        print(f"No activity folders found under {source_root}", file=sys.stderr)
        sys.exit(1)

    os.makedirs(out_base, exist_ok=True)
    total_processed_activities = 0

    for activity_dir in activities:
        activity_name = os.path.basename(os.path.normpath(activity_dir))
        if not os.path.isdir(activity_dir):
            if args.verbose:
                print(f"Skipping (not dir): {activity_dir}")
            continue
        sessions = find_session_dirs(activity_dir, extracted_subdir) if not args.recursive else []
        if args.recursive:
            # collect any folder under activity_dir that contains accel/gyro files
            for root, dirs, files in os.walk(os.path.join(activity_dir, extracted_subdir) if os.path.isdir(os.path.join(activity_dir, extracted_subdir)) else activity_dir):
                accel, gyro = find_sensor_files_in_session(root)
                if accel or gyro:
                    sessions.append(root)
        if not sessions:
            if args.verbose:
                print(f"No sessions found for activity '{activity_name}' under {os.path.join(activity_dir, extracted_subdir)}")
            continue

        if args.verbose:
            print(f"Processing activity '{activity_name}' with {len(sessions)} session(s)...")

        per_activity_rows = []
        processed_sessions = 0

        for sess in sessions:
            sess_name = os.path.basename(os.path.normpath(sess))
            accel_path, gyro_path = find_sensor_files_in_session(sess)
            if not accel_path or not gyro_path:
                if args.verbose:
                    print(f" Skipping session '{sess_name}' (missing accel or gyro)")
                continue
            try:
                merged = merge_session(accel_path, gyro_path, verbose=args.verbose)
            except Exception as e:
                print(f" Failed to merge session '{sess}': {e}", file=sys.stderr)
                continue
            if merged.empty:
                if args.verbose:
                    print(f"  Session '{sess_name}' produced no merged rows (no matching timestamps)")
                continue

            if args.add_session:
                merged = merged.copy()
                merged.insert(0, "session", sess_name)

            per_activity_rows.append(merged)
            processed_sessions += 1
            if args.verbose:
                print(f"  Merged session '{sess_name}' -> {merged.shape[0]} rows")

        if not per_activity_rows:
            if args.verbose:
                print(f"No merged data produced for activity '{activity_name}'")
            continue

        # concat all sessions for this activity
        activity_df = pd.concat(per_activity_rows, ignore_index=True, sort=False)

        # sort by timestamp if present
        if "timestamp" in activity_df.columns:
            try:
                activity_df = activity_df.sort_values(by="timestamp").reset_index(drop=True)
            except Exception:
                pass

        # construct output filename with optional name prefix
        if name_token:
            out_name = f"{name_token}_{activity_name}_combined.csv"
        else:
            out_name = f"{activity_name}_combined.csv"

        out_path = os.path.join(out_base, out_name)
        out_path = make_unique_path(out_path, args.overwrite)

        # ensure column order: if add_session put it first
        if args.add_session and "session" in activity_df.columns:
            cols = ["session"] + [c for c in OUTPUT_COLS if c in activity_df.columns]
        else:
            cols = [c for c in OUTPUT_COLS if c in activity_df.columns]
        activity_df.to_csv(out_path, index=False, columns=cols)
        print(f"Wrote activity combined file: {out_path} ({activity_df.shape[0]} rows across {processed_sessions} session(s))")
        total_processed_activities += 1

    if total_processed_activities == 0:
        print("No activities were processed successfully.", file=sys.stderr)
        sys.exit(2)

    print(f"Done. Combined files are under: {out_base}")
    sys.exit(0)


if __name__ == "__main__":
    main()