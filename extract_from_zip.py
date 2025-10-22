#!/usr/bin/env python3
"""
extract_all_zips.py

Scan a directory for .zip files and extract only accelerometer.csv and gyroscope.csv
(from any path inside each zip, case-insensitive) for every archive found.

Updated behavior (per your request):
- The script will ask (via CLI prompt) for:
    1) the folder that contains the zip files (source)
    2) the base folder where extracted files should be placed (destination)
  You can still pass --source and --dest on the command line to avoid prompts.
- For each zip found in the source (non-recursive by default), the script creates
  a per-archive destination directory under the provided destination base:
    <destination_base>/<zip_basename_without_ext>
  and extracts matching sensor CSVs there.
- Supports --recursive, --list, --overwrite, and --verbose as before.
"""
from __future__ import annotations
import argparse
import os
import sys
import zipfile
import shutil
from typing import List, Tuple

SENSOR_BASENAMES = {"accelerometer.csv", "gyroscope.csv"}


def normalize_basename(path: str) -> str:
    return os.path.basename(path).strip().lower()


def list_zip_files_in_dir(source_dir: str, recursive: bool = False) -> List[str]:
    """Return list of zip files in source_dir. If recursive, walk the tree."""
    zips: List[str] = []
    if recursive:
        for root, _, files in os.walk(source_dir):
            for f in sorted(files):
                if f.lower().endswith(".zip"):
                    zips.append(os.path.join(root, f))
    else:
        for entry in sorted(os.listdir(source_dir)):
            full = os.path.join(source_dir, entry)
            if os.path.isfile(full) and entry.lower().endswith(".zip"):
                zips.append(full)
    return zips


def find_sensor_entries_in_zip(zip_path: str) -> List[str]:
    """Return list of zip entry names that match sensor basenames (preserve entry names)."""
    matches: List[str] = []
    try:
        with zipfile.ZipFile(zip_path, "r") as z:
            for info in z.infolist():
                if info.is_dir():
                    continue
                if normalize_basename(info.filename) in SENSOR_BASENAMES:
                    matches.append(info.filename)
    except zipfile.BadZipFile:
        raise ValueError(f"Bad or unsupported zip file: {zip_path}")
    return matches


def prepare_dest_for_zip(dest_base: str, zip_path: str) -> str:
    """
    Prepare destination directory for a given zip file.
    Layout: <dest_base>/<zip_basename_without_ext>
    """
    zip_basename = os.path.splitext(os.path.basename(zip_path))[0]
    dest_dir = os.path.join(dest_base, zip_basename)
    os.makedirs(dest_dir, exist_ok=True)
    return dest_dir


def unique_target_path(dest_dir: str, basename: str, overwrite: bool) -> str:
    """
    Generate a safe target path in dest_dir for basename.
    If overwrite is False and the file exists, append _1, _2, ... before extension.
    """
    base, ext = os.path.splitext(basename)
    candidate = basename
    target = os.path.join(dest_dir, candidate)
    if overwrite:
        return target
    idx = 0
    while os.path.exists(target):
        idx += 1
        candidate = f"{base}_{idx}{ext}"
        target = os.path.join(dest_dir, candidate)
    return target


def extract_entries_from_zip(zip_path: str, entries: List[str], dest_dir: str, overwrite: bool) -> List[str]:
    """
    Extract specified entries (full names inside zip) into dest_dir.
    Returns list of extracted file paths.
    """
    extracted: List[str] = []
    with zipfile.ZipFile(zip_path, "r") as z:
        used = {}
        for entry in entries:
            orig_basename = os.path.basename(entry)
            # ensure unique target name (handles multiple identical basenames inside zip)
            target = unique_target_path(dest_dir, orig_basename, overwrite)
            # track usage
            used[orig_basename] = used.get(orig_basename, 0) + 1
            try:
                with z.open(entry) as src, open(target, "wb") as dst:
                    shutil.copyfileobj(src, dst)
                extracted.append(target)
            except Exception as e:
                raise RuntimeError(f"Failed to extract '{entry}' from '{zip_path}': {e}") from e
    return extracted


def process_all_zips(source_dir: str, dest_base: str, recursive: bool, list_only: bool, overwrite: bool, verbose: bool) -> Tuple[int, int]:
    """
    Process all zip files found. Returns tuple (zip_count_processed, total_files_extracted)
    """
    zip_files = list_zip_files_in_dir(source_dir, recursive=recursive)
    if not zip_files:
        if verbose:
            print(f"No zip files found in '{source_dir}'.")
        return 0, 0

    total_extracted = 0
    processed = 0
    for zf in zip_files:
        processed += 1
        try:
            matches = find_sensor_entries_in_zip(zf)
        except ValueError as e:
            print(f"Skipping '{zf}': {e}", file=sys.stderr)
            continue

        if not matches:
            if verbose:
                print(f"No sensor CSVs in '{zf}'.")
            continue

        dest_dir = prepare_dest_for_zip(dest_base, zf)
        if list_only:
            print(f"Zip: {zf}")
            for m in matches:
                print(f"  {m}")
            continue

        if verbose:
            print(f"Extracting from '{zf}' -> '{dest_dir}' ...")
        try:
            extracted = extract_entries_from_zip(zf, matches, dest_dir, overwrite=overwrite)
            total_extracted += len(extracted)
            if verbose:
                for p in extracted:
                    print("   -", p)
        except Exception as e:
            print(f"Error extracting from '{zf}': {e}", file=sys.stderr)
            continue

    return processed, total_extracted


def parse_args():
    parser = argparse.ArgumentParser(description="Extract accelerometer.csv and gyroscope.csv from all .zip files in a directory.")
    parser.add_argument("--source", "-s", help="Directory containing .zip files (if omitted the CLI will prompt)")
    parser.add_argument("--dest", "-d", help="Base destination folder where each zip's contents will be extracted (if omitted the CLI will prompt)")
    parser.add_argument("--recursive", "-r", action="store_true", help="Find .zip files recursively under source")
    parser.add_argument("--list", action="store_true", help="Only list matching entries inside each zip (no extraction)")
    parser.add_argument("--overwrite", action="store_true", help="Overwrite existing files in destination")
    parser.add_argument("--verbose", "-v", action="store_true", help="Verbose output")
    return parser.parse_args()


def prompt_if_missing(value: str, prompt_text: str) -> str:
    if value:
        return value
    try:
        return input(prompt_text).strip()
    except EOFError:
        return ""


def main():
    args = parse_args()

    # Ask for source and destination if not provided on CLI
    source_dir = prompt_if_missing(args.source, "Source folder containing .zip files (e.g. data/walking): ")
    dest_base = prompt_if_missing(args.dest, "Destination base folder where extracted folders will be created (e.g. data/extracted): ")

    if not source_dir:
        print("Error: source folder is required.", file=sys.stderr)
        sys.exit(2)
    if not dest_base:
        print("Error: destination base folder is required.", file=sys.stderr)
        sys.exit(2)

    if not os.path.isdir(source_dir):
        print(f"Error: source directory not found: {source_dir}", file=sys.stderr)
        sys.exit(1)

    # ensure destination base exists
    try:
        os.makedirs(dest_base, exist_ok=True)
    except Exception as e:
        print(f"Error creating destination base folder '{dest_base}': {e}", file=sys.stderr)
        sys.exit(2)

    processed, extracted = process_all_zips(
        source_dir,
        dest_base,
        recursive=args.recursive,
        list_only=args.list,
        overwrite=args.overwrite,
        verbose=args.verbose,
    )

    if args.list:
        # listing is informational only
        sys.exit(0)

    if processed == 0:
        print("No zip files processed.", file=sys.stderr)
        sys.exit(2)

    print(f"Processed {processed} zip file(s). Extracted {extracted} sensor file(s).")
    sys.exit(0)


if __name__ == "__main__":
    main()