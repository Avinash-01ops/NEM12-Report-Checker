#!/usr/bin/env python3
"""NEM12 Comparator - Compare BEFORE and AFTER NEM12 reports sequentially."""

import json
import sys
from pathlib import Path
from datetime import datetime
from typing import List, Dict, Any

from src.check_reports.report_checker_engine import compare, write_issues_csv, Issue


def _project_root() -> Path:
    """Project root (directory containing 'src' and 'config')."""
    return Path(__file__).resolve().parent.parent.parent


def load_config(path: str = "config/metadata_mapping.json") -> dict:
    """Load configuration from JSON file with error handling."""
    try:
        with open(path, "r", encoding="utf-8") as f:
            return json.load(f)
    except FileNotFoundError:
        print(f"ERROR: Configuration file not found: {path}")
        sys.exit(1)
    except json.JSONDecodeError as e:
        print(f"ERROR: Invalid JSON in configuration file: {e}")
        sys.exit(1)
    except Exception as e:
        print(f"ERROR: Failed to load configuration: {e}")
        sys.exit(1)


def validate_file_path(file_path: Path, file_type: str) -> bool:
    """Validate that a file exists and is readable."""
    if not file_path.exists():
        print(f"ERROR: {file_type} file not found: {file_path}")
        return False
    if not file_path.is_file():
        print(f"ERROR: {file_type} path is not a file: {file_path}")
        return False
    if not file_path.stat().st_size > 0:
        print(f"WARNING: {file_type} file is empty: {file_path}")
    return True


def compare_pair_safely(
    before_path: Path,
    after_path: Path,
    comparison_id: str,
    pair_index: int,
    total_pairs: int
) -> tuple[List[Issue], bool]:
    """
    Compare a single pair with comprehensive error handling.
    Returns (issues_list, success_flag).
    """
    try:
        # Validate files exist
        if not validate_file_path(before_path, "BEFORE"):
            return [], False
        if not validate_file_path(after_path, "AFTER"):
            return [], False

        print(f"[{pair_index}/{total_pairs}] Comparing: {before_path.name} vs {after_path.name}")
        
        # Perform comparison
        issues = compare(str(before_path), str(after_path), comparison_id)
        
        issue_count = len(issues)
        print(f"[{pair_index}/{total_pairs}] Completed: {issue_count} issue(s) found")
        
        return issues, True
        
    except FileNotFoundError as e:
        print(f"ERROR [{pair_index}/{total_pairs}]: File not found - {e}")
        return [], False
    except PermissionError as e:
        print(f"ERROR [{pair_index}/{total_pairs}]: Permission denied - {e}")
        return [], False
    except UnicodeDecodeError as e:
        print(f"ERROR [{pair_index}/{total_pairs}]: File encoding error - {e}")
        return [], False
    except Exception as e:
        print(f"ERROR [{pair_index}/{total_pairs}]: Unexpected error during comparison: {e}")
        print(f"  Error type: {type(e).__name__}")
        import traceback
        print(f"  Traceback: {traceback.format_exc()}")
        return [], False


def main() -> None:
    """Main function with sequential comparison and error handling."""
    root = _project_root()

    try:
        config_path = root / "config" / "metadata_mapping.json"
        config = load_config(str(config_path))
    except SystemExit:
        raise
    except Exception as e:
        print(f"ERROR: Failed to initialize: {e}")
        sys.exit(1)

    pairs = config.get("comparison_pairs", [])
    if not pairs:
        print("ERROR: No comparison_pairs configured in config/metadata_mapping.json")
        sys.exit(1)

    # Paths relative to project root (must match where download_nem12_reports.py saves files)
    before_dir = root / "Data" / "Before_Production"
    after_dir = root / "Data" / "After_Production"
    out_dir = root / "Results"
    
    try:
        before_dir.mkdir(parents=True, exist_ok=True)
        after_dir.mkdir(parents=True, exist_ok=True)
        out_dir.mkdir(parents=True, exist_ok=True)
    except Exception as e:
        print(f"ERROR: Failed to create directories: {e}")
        sys.exit(1)

    all_issues: List[Issue] = []
    successful_comparisons = 0
    failed_comparisons = 0
    skipped_pairs = 0
    last_before_name = ""
    last_after_name = ""

    total_pairs = len(pairs)
    print(f"\nStarting comparison of {total_pairs} file pair(s)...\n")

    # Process each pair sequentially
    for idx, pair in enumerate(pairs, start=1):
        before_file = pair.get("before_file")
        after_file = pair.get("after_file")
        
        if not before_file or not after_file:
            print(f"[{idx}/{total_pairs}] SKIPPED: Missing file names in pair configuration")
            skipped_pairs += 1
            continue

        before_path = before_dir / before_file
        after_path = after_dir / after_file
        comparison_id = f"RUN_{idx:03d}"
        last_before_name = before_file
        last_after_name = after_file

        # Compare pair with error handling
        issues, success = compare_pair_safely(
            before_path,
            after_path,
            comparison_id,
            idx,
            total_pairs
        )

        if success:
            all_issues.extend(issues)
            successful_comparisons += 1
        else:
            failed_comparisons += 1
            # Continue with next pair even if this one failed

    # Generate output file
    try:
        out_name = f"comparison_results_{datetime.now().strftime('%Y%m%d_%H%M%S')}.csv"
        out_path = out_dir / out_name
        csv_path = write_issues_csv(
            all_issues,
            str(out_path),
            before_file_name=last_before_name,
            after_file_name=last_after_name,
        )
    except Exception as e:
        print(f"ERROR: Failed to write results CSV: {e}")
        sys.exit(1)

    # Summary
    total_issues = len(all_issues)
    print("\n" + "="*60)
    print("COMPARISON SUMMARY")
    print("="*60)
    print(f"Total pairs processed: {total_pairs}")
    print(f"Successful: {successful_comparisons}")
    print(f"Failed: {failed_comparisons}")
    print(f"Skipped: {skipped_pairs}")
    print(f"Total issues found: {total_issues}")
    print(f"Results CSV: {csv_path}")
    print("="*60)

    # Exit with error code if any comparisons failed
    if failed_comparisons > 0:
        print(f"\nWARNING: {failed_comparisons} comparison(s) failed. Check errors above.")
        sys.exit(1)
    else:
        print("\nStatus: All comparisons completed successfully")
        sys.exit(0)


if __name__ == "__main__":
    main()
