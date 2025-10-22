# Sensor Data Extraction & Combining — Full Pipeline Guide

This README explains the end-to-end workflow to extract Accelerometer/Gyroscope CSVs from zip archives and produce combined per-activity CSVs merged by timestamp. It covers repository layout and folder naming, virtualenv and dependencies, the full extract→combine pipeline, and troubleshooting notes.

Goal: Given a tree of activity folders where each activity has a `raw/` folder with zip files, extract only the sensor CSVs (Accelerometer, Gyroscope) and merge session pairs into per-activity combined CSVs with columns:

- timestamp
- accel_x
- accel_y
- accel_z
- gyro_x
- gyro_y
- gyro_z

---

## Requirements

- Python 3.8+ (3.10+ recommended)
- pandas

We recommend using a virtual environment. Typical steps:
- create and activate a venv (e.g., `python3 -m venv venv` and `source venv/bin/activate`)
- install pandas in the virtual environment

---

## Expected folder naming / layout

Set up activity folders under a `data/` root. Example structure:

data/
- walking/
  - raw/                (put all .zip files for walking here)
- jumping/
  - raw/
- still/
  - raw/

After extraction you will get:

data/
- walking/
  - raw/
    - 2025-10-22_11-11-09.zip
    - ...
  - extracted/
    - 2025-10-22_11-11-09/
      - Accelerometer.csv
      - Gyroscope.csv
    - ...
- jumping/
  - extracted/
    - ...

Combined outputs will be written to an output directory (default `data/combined/`), for example:
- `omar_walking_combined.csv`
- `omar_jumping_combined.csv`

Notes:
- Filenames inside zips can be `Accelerometer.csv`, `accelerometer.csv`, etc. Matching is case-insensitive and looks for basenames `accelerometer.csv` and `gyroscope.csv`.
- Session folders are created per-zip using the zip basename (e.g., `2025-10-22_11-11-09.zip` → extracted folder `2025-10-22_11-11-09/`).

---

## Scripts overview

The repository contains several small CLI scripts:

- `extract_all_zips.py` — scan a folder containing `.zip` files and extract only `accelerometer.csv` and `gyroscope.csv` into per-zip folders under a destination base.
- `extract_from_zip.py` — extract or copy sensors from a single zip or a single folder (useful for one-off operations).
- `combine_activity_sessions.py` — locate session folders under `activity/extracted/`, merge accelerometer + gyroscope by timestamp across sessions, and write per-activity combined CSVs. Supports optional `--name` to prepend a sanitized name to the output filenames (e.g., `omar_walking_combined.csv`).
- `combine_accel_gyro.py` — helper to merge a single session folder (useful for testing).
- `combine_csv.py` / `combine_csv_folder.py` — generic CSV concatenation helpers.

---

## Full pipeline (step-by-step)

1. Prepare activity folders and place zips under each activity's `raw/` folder.
   - Example: create `data/walking/raw` and copy walking zips there.

2. Extract zips for an activity:
   - Run `extract_all_zips.py` and provide the source folder (the folder that contains `.zip` files, e.g. `data/walking/raw`) and the destination base (e.g. `data/walking/extracted`).
   - The script creates per-zip subfolders under the destination base and extracts `Accelerometer.csv` and `Gyroscope.csv` from each zip.

   Alternatively, for a single zip or already-extracted folder, use `extract_from_zip.py` to extract or copy the two sensor files into a chosen destination.

3. Combine sessions into per-activity CSVs:
   - Run `combine_activity_sessions.py` and provide:
     - source root (the folder containing activity subfolders, e.g. `data`)
     - extracted subdir name (default `extracted`)
     - output base (default `data/combined`)
     - optional `--name` to prepend a sanitized name (e.g., `Omar`) to output filenames
     - optional `--add-session` to include a `session` column in aggregated outputs
   - The script finds each session folder under `<activity>/extracted/`, merges each session's `Accelerometer.csv` and `Gyroscope.csv` on timestamp (inner join), concatenates session merges for each activity, and writes one combined CSV per activity.

4. Verify outputs
   - Check the files created under the output directory (default `data/combined`), and inspect a few rows to confirm column ordering and content.

---

## Examples (high level)

- Extract all zips for activity `walking` by pointing `extract_all_zips.py` at `data/walking/raw` and choosing `data/walking/extracted` as the destination base.
- Combine sessions across activities by running `combine_activity_sessions.py` with the appropriate `--source-root` and `--extracted-subdir`, and use `--name` to prepend a username to output filenames.

(Commands are run from the project root with a Python virtual environment activated.)

---

## Notes on merging and matching timestamps

- The scripts detect the timestamp column heuristically by looking for column names containing `time`, `timestamp`, `seconds`, `elapsed`, etc. If no such name is found, the first column is used as a fallback.
- Merging is an inner join on exact timestamp equality. If accelerometer and gyroscope timestamps are slightly different (no exact equality), the join drops non-matching rows. If sensors are not synchronized, consider requesting a nearest-neighbor merge option that matches rows within a tolerance.
- Axis detection handles common naming patterns (`x`, `X`, `accel_x`, `z`, etc.) but if your headers differ significantly you may need to rename them or update the scripts.

---

## Filename sanitization & outputs

- The `--name` passed to `combine_activity_sessions.py` is sanitized (lowercased and non-alphanumeric characters replaced) and prepended to output filenames. Example: `--name Omar` → `omar_walking_combined.csv`.
- Output columns order:
  - `timestamp, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z`
- Combined files are written to the directory specified by `--out` (default `data/combined`).

---

## Troubleshooting

- "No zip files found" — ensure the `--source` path points to a folder containing `.zip` files (e.g. `data/walking/raw`).
- "No sensor CSVs in '<zip>'" — check zip contents; the extractor looks for basenames `accelerometer.csv` and `gyroscope.csv` (case-insensitive).
- "Missing accel or gyro" during combine — ensure each session folder contains both `Accelerometer.csv` and `Gyroscope.csv`.
- "No merged rows" — timestamps don't match exactly. Consider requesting nearest-neighbor merging within a tolerance.
- Memory: scripts load CSVs into pandas DataFrames. For very large files, consider chunked or streaming processing.

---

## Next steps / Extensions

Possible improvements:
- Add nearest-neighbor timestamp matching with a user-specified tolerance.
- Produce per-session combined CSVs in addition to per-activity aggregates.
- Add tests and a small example dataset.
- Make the pipeline more memory-efficient for very large CSV files.

---

## Contact / usage tip

- Activate the virtual environment before running scripts: use your project's `venv` activation command (for example, `source venv/bin/activate` on Linux/macOS).
- Run the extractor first to create the `extracted/` session folders, then run the combine script to produce per-activity combined files.

If you want, I can now:
- update the combine script to perform nearest-neighbor timestamp matching,
- add per-session outputs,
- or produce a minimal example run using one activity from your tree. Tell me which and I'll implement it.