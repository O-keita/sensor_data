# Quick Start — Exact Commands & Steps

This README gives the exact, minimal sequence of commands and the specific script filenames to run for the full pipeline:
- extract sensor CSVs (Accelerometer, Gyroscope) from zip files, and
- combine sessions into per-activity combined CSVs.

Assumes you already have the project scripts in the repository root:
- extract_all_zips.py
- extract_from_zip.py
- combine_activity_sessions.py
- combine_accel_gyro.py
- (optional) combine_csv.py / combine_csv_folder.py

I’ll walk you through the step-by-step commands to run, where to put your zip files, and what to expect.

---

## 0 — Prepare environment (one-time)

Create and activate a Python virtual environment and install pandas.

Linux / macOS:
```bash
python3 -m venv venv
source venv/bin/activate
pip install --upgrade pip
pip install pandas
```

Windows (PowerShell):
```powershell
python -m venv venv
venv\Scripts\Activate.ps1
pip install --upgrade pip
pip install pandas
```

Confirm Python and pandas:
```bash
python -V
python -c "import pandas as pd; print(pd.__version__)"
```

---

## 1 — Arrange your zip files (folder naming convention)

Create an activity folder for each activity and place the zip files in a `raw/` subfolder.

Example structure (you can create these with mkdir and copy your zips in):

```
data/
  walking/
    raw/
      2025-10-22_11-11-09.zip
      2025-10-22_11-11-25.zip
      ...
  jumping/
    raw/
      ...
  still/
    raw/
      ...
```

Notes:
- The extractor looks for `.zip` files inside each activity's `raw/` folder.
- Ensure `data/<activity>/raw` exists and contains the zips before extraction.

---

## 2 — Extract sensor CSVs from ALL zips for one activity

Use `extract_all_zips.py`. This script will:
- scan the given `--source` directory for `.zip` files,
- for each zip, create a directory under the destination base and extract only sensor files named (case-insensitive) `accelerometer.csv` and `gyroscope.csv`.

Example (non-interactive; recommended):

```bash
# Example for "walking" activity
python extract_all_zips.py --source data/walking/raw --dest data/walking/extracted --verbose
```

What this does:
- For each zip `.../<zipname>.zip` found under `data/walking/raw`, creates `data/walking/extracted/<zipname>/`
- Extracts `Accelerometer.csv` and `Gyroscope.csv` (if present) into that per-zip folder.
- Prints progress if `--verbose` is used.

Interactive mode (prompts):
```bash
python extract_all_zips.py
# then when prompted:
# Source folder containing .zip files (e.g. data/walking): data/walking/raw
# Destination base folder where extracted folders will be created (e.g. data/walking/extracted): data/walking/extracted
```

If you only need to extract a single zip or copy from an already-extracted folder, use:
```bash
# Extract single zip into a destination folder
python extract_from_zip.py /path/to/one.zip data/walking/extracted

# Copy from an already-extracted session folder into destination
python extract_from_zip.py data/walking/some_session_folder data/walking/extracted
```

---

## 3 — Confirm extraction (quick checks)

List the extracted folders and check files:

```bash
# show the per-session folders created
ls -1 data/walking/extracted

# inspect one session folder
ls -l data/walking/extracted/2025-10-22_11-11-09
# should list Accelerometer.csv and Gyroscope.csv
```

Open the first few lines to ensure headers are present:
```bash
head -n 5 data/walking/extracted/2025-10-22_11-11-09/Accelerometer.csv
head -n 5 data/walking/extracted/2025-10-22_11-11-09/Gyroscope.csv
```

---

## 4 — Combine sessions into per-activity CSVs

Run `combine_activity_sessions.py` to find session subfolders under each activity's `extracted/` and merge accelerometer + gyroscope by timestamp.

Non-interactive example (recommended):

```bash
python combine_activity_sessions.py \
  --source-root data \
  --extracted-subdir extracted \
  --out data/combined \
  --name Omar \
  --add-session \
  --verbose
```

Meaning of flags:
- `--source-root data` — root folder that contains activity folders (walking, jumping, etc.)
- `--extracted-subdir extracted` — subfolder name under each activity containing session folders
- `--out data/combined` — where combined per-activity CSVs will be written
- `--name Omar` — optional; sanitized and prepended to output filenames (`omar_walking_combined.csv`)
- `--add-session` — include a `session` column in aggregated outputs identifying which session folder each row came from
- `--verbose` — prints extra info while processing

Interactive prompts (if you omit args):
```bash
python combine_activity_sessions.py
# then follow prompts:
# Source root (folder that contains activity subfolders) [default: data]: data
# Name (optional): Omar
# Name of extracted subfolder under each activity [default: extracted]: extracted
# Output base folder for combined CSVs [default: data/combined]: data/combined
```

What to expect:
- For each activity (e.g., `walking`) the script concatenates merged rows from all sessions and writes:
  - `data/combined/omar_walking_combined.csv` (if `--name Omar` provided)
  - or `data/combined/walking_combined.csv` (if no name provided)
- Output columns (ordered): `timestamp, accel_x, accel_y, accel_z, gyro_x, gyro_y, gyro_z`
- If `--add-session` is used, the `session` column appears first.

---

## 5 — Verify combined outputs

List and inspect:

```bash
ls -l data/combined
head -n 5 data/combined/omar_walking_combined.csv
```

Check counts:
```bash
wc -l data/combined/omar_walking_combined.csv
# or open in pandas for further checks
python - <<'PY'
import pandas as pd
df=pd.read_csv("data/combined/omar_walking_combined.csv")
print(df.columns)
print(df.head())
PY
```

---

## Optional / Helpful commands

- Combine a single session folder (test) using `combine_accel_gyro.py`:
```bash
python combine_accel_gyro.py --source data/walking/extracted/2025-10-22_11-11-09 --out data/combined --verbose
```

- Combine raw CSV files in a single folder (generic concatenation):
```bash
python combine_csv_folder.py data/some_folder_with_csvs -o data/combined/merged.csv --add-source
```

- Re-run extraction with `--overwrite` to replace files:
```bash
python extract_all_zips.py --source data/walking/raw --dest data/walking/extracted --overwrite
```

---

## Important behaviors & troubleshooting reminders

- Extraction looks for basenames exactly matching `accelerometer.csv` and `gyroscope.csv` (case-insensitive). If your sensor files use different names, rename them or adjust the extractor.
- Combining merges on exact timestamp equality (inner join). If accel and gyro timestamps are not exactly aligned, the merge may drop rows. If you need fuzzy/nearest matching, ask to add a tolerance-based matching option.
- Activate the venv before running scripts so pandas from your env is used: `source venv/bin/activate`.
- If a session is missing either Accelerometer or Gyroscope, it will be skipped during combine (the script prints warnings in `--verbose` mode).
- For very large CSVs, the scripts load files into pandas and may use a lot of memory—if that is an issue, we can add streaming or chunked processing.

---

## Quick example: single actionable run

1. Activate venv:
```bash
source venv/bin/activate
```

2. Extract all walking zips:
```bash
python extract_all_zips.py --source data/walking/raw --dest data/walking/extracted --verbose
```

3. Combine all activities into per-activity CSVs with your name:
```bash
python combine_activity_sessions.py --source-root data --extracted-subdir extracted --out data/combined --name Omar --add-session --verbose
```

4. Inspect output:
```bash
ls -l data/combined
head -n 5 data/combined/omar_walking_combined.csv
```

---

If you'd like, I can:
- add a short block with the exact results you should expect for one session (sample `head` output), or
- add a `--tolerance` nearest-neighbor merge option to handle unsynchronized timestamps — tell me which and I will update the combine script and the README accordingly.