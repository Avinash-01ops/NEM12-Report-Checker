#!/usr/bin/env python3
"""
NEM12 Report Comparison Tool

Compares two NEM12 files (before and after production release) logically by NMI, date, and interval.
NEM12 is a structured format used for Australian Energy Market interval meter data.
"""

import csv
import sys
import os
from pathlib import Path
from typing import Dict, List, Tuple, Optional, Set
from dataclasses import dataclass

# Constants
QUALITY_FLAGS = {'A', 'V', 'E', 'F', 'N', 'S', 'R', 'C', 'D'}
CSV_DELIMITERS = [',', '|', ';', '\t']
DEFAULT_INTERVAL_LENGTH = 30  # minutes
VALUE_TOLERANCE = 0.001
INTERVALS_PER_DAY = {15: 96, 30: 48, 60: 24}  # interval_length -> intervals per day


@dataclass
class IntervalValue:
    """Represents a single interval meter reading with metadata."""
    nmi: str
    date: str  # Format: YYYYMMDD
    interval_index: int  # 0-based index within the day
    value: str
    quality: str = ""


class NEM12File:
    """Parses and stores NEM12 file data for comparison."""
    
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.nmis: Set[str] = set()
        self.intervals: Dict[Tuple[str, str, int], IntervalValue] = {}
        self.current_nmi: Optional[str] = None
        self.current_interval_length: int = DEFAULT_INTERVAL_LENGTH
        self.parse()
    
    def _detect_delimiter(self) -> str:
        """Detect CSV delimiter by analyzing the first line."""
        try:
            with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
                first_line = f.readline()
                best_delim = CSV_DELIMITERS[0]
                max_count = first_line.count(best_delim)
                
                for delim in CSV_DELIMITERS[1:]:
                    count = first_line.count(delim)
                    if count > max_count:
                        max_count = count
                        best_delim = delim
                
                return best_delim
        except Exception:
            return CSV_DELIMITERS[0]  # Default to comma
    
    def _parse_record_200(self, row: List[str]) -> None:
        """Parse record type 200: NMI (meter) details."""
        if len(row) < 2:
            return
        
        self.current_nmi = row[1].strip()
        if not self.current_nmi:
            return
        
        self.nmis.add(self.current_nmi)
        
        # Extract interval length (typically in position 8)
        if len(row) >= 9:
            try:
                self.current_interval_length = int(row[8].strip())
            except (ValueError, IndexError):
                self.current_interval_length = DEFAULT_INTERVAL_LENGTH
        else:
            self.current_interval_length = DEFAULT_INTERVAL_LENGTH
    
    def _find_quality_flag(self, row: List[str]) -> Optional[int]:
        """Find quality flag position in record 300, searching backwards from end."""
        # Quality flag is typically 3-4 positions before the end (before timestamps)
        for i in range(len(row) - 4, 1, -1):
            val = row[i].strip()
            if val and len(val) == 1 and val in QUALITY_FLAGS:
                return i
        return None
    
    def _extract_interval_values(self, row: List[str], quality_idx: Optional[int]) -> Tuple[List[str], str]:
        """Extract interval values and quality flag from record 300."""
        if quality_idx:
            # Values are from position 2 to quality_idx - 1
            interval_values = [row[i].strip() for i in range(2, quality_idx)]
            quality = row[quality_idx].strip()
        else:
            # Fallback: use expected intervals count
            expected_count = INTERVALS_PER_DAY.get(self.current_interval_length, 48)
            end_idx = min(2 + expected_count, len(row) - 3)
            interval_values = [row[i].strip() for i in range(2, end_idx)]
            quality = ""
        
        return interval_values, quality
    
    def _store_interval_values(self, date: str, interval_values: List[str], quality: str) -> None:
        """Store interval values, preserving first non-zero value if duplicates exist."""
        if not self.current_nmi:
            return
        
        for interval_idx, value in enumerate(interval_values):
            key = (self.current_nmi, date, interval_idx)
            
            # If key exists, preserve first non-zero value
            if key in self.intervals:
                existing_value = self.intervals[key].value
                if existing_value and existing_value != "0" and existing_value != "":
                    continue  # Keep existing non-zero value
            
            # Store new value
            self.intervals[key] = IntervalValue(
                nmi=self.current_nmi,
                date=date,
                interval_index=interval_idx,
                value=value if value else "",
                quality=quality
            )
    
    def _parse_record_300(self, row: List[str]) -> None:
        """Parse record type 300: Interval data (actual meter readings)."""
        if not self.current_nmi or len(row) < 3:
            return
        
        date = row[1].strip()
        quality_idx = self._find_quality_flag(row)
        interval_values, quality = self._extract_interval_values(row, quality_idx)
        self._store_interval_values(date, interval_values, quality)
    
    def parse(self) -> None:
        """Parse the NEM12 file and extract all relevant data."""
        delimiter = self._detect_delimiter()
        
        with open(self.file_path, 'r', encoding='utf-8', errors='replace') as f:
            reader = csv.reader(f, delimiter=delimiter)
            
            for row in reader:
                if not row or len(row) < 2:
                    continue
                
                record_type = row[0].strip()
                
                if record_type == '100':
                    # File header - skip metadata
                    continue
                elif record_type == '200':
                    self._parse_record_200(row)
                elif record_type == '300':
                    self._parse_record_300(row)
                # Records 400, 500, 900 are optional metadata - skip
                elif record_type in ('400', '500', '900'):
                    continue


def compare_nem12_files(file1_path: str, file2_path: str) -> Tuple[bool, List[str]]:
    """
    Compare two NEM12 files logically by NMI, date, and interval index.
    
    Returns:
        Tuple of (is_identical, list_of_discrepancies)
    """
    discrepancies = []
    is_identical = True
    
    try:
        # Parse both files
        print("\nReading files...")
        file1 = NEM12File(file1_path)
        file2 = NEM12File(file2_path)
        
        print(f"File 1: {len(file1.nmis)} NMIs, {len(file1.intervals):,} intervals")
        print(f"File 2: {len(file2.nmis)} NMIs, {len(file2.intervals):,} intervals")
        print("\nComparing files...\n")
        
        # Step 1: Check for missing or extra NMIs
        nmis_only_in_file1 = file1.nmis - file2.nmis
        nmis_only_in_file2 = file2.nmis - file1.nmis
        
        for nmi in sorted(nmis_only_in_file1):
            msg = f"Missing NMI: {nmi} (in File 1, not in File 2)"
            discrepancies.append(msg)
            print(f"[X] {msg}")
            is_identical = False
        
        for nmi in sorted(nmis_only_in_file2):
            msg = f"Extra NMI: {nmi} (in File 2, not in File 1)"
            discrepancies.append(msg)
            print(f"[X] {msg}")
            is_identical = False
        
        # Step 2: Check for missing or extra dates per NMI
        common_nmis = file1.nmis & file2.nmis
        
        for nmi in sorted(common_nmis):
            dates_file1 = {date for (n, date, idx) in file1.intervals.keys() if n == nmi}
            dates_file2 = {date for (n, date, idx) in file2.intervals.keys() if n == nmi}
            
            for date in sorted(dates_file1 - dates_file2):
                msg = f"Missing date: NMI {nmi}, Date {date} (in File 1, not in File 2)"
                discrepancies.append(msg)
                print(f"[X] {msg}")
                is_identical = False
            
            for date in sorted(dates_file2 - dates_file1):
                msg = f"Extra date: NMI {nmi}, Date {date} (in File 2, not in File 1)"
                discrepancies.append(msg)
                print(f"[X] {msg}")
                is_identical = False
        
        # Step 3: Compare interval values
        all_keys_file1 = set(file1.intervals.keys())
        all_keys_file2 = set(file2.intervals.keys())
        common_keys = all_keys_file1 & all_keys_file2
        keys_only_in_file1 = all_keys_file1 - all_keys_file2
        keys_only_in_file2 = all_keys_file2 - all_keys_file1
        
        # Report missing/extra intervals
        for key in sorted(keys_only_in_file1):
            nmi, date, idx = key
            msg = f"Missing interval: NMI {nmi}, Date {date}, Index {idx} (File 1 value: {file1.intervals[key].value})"
            discrepancies.append(msg)
            print(f"[X] {msg}")
            is_identical = False
        
        for key in sorted(keys_only_in_file2):
            nmi, date, idx = key
            msg = f"Extra interval: NMI {nmi}, Date {date}, Index {idx} (File 2 value: {file2.intervals[key].value})"
            discrepancies.append(msg)
            print(f"[X] {msg}")
            is_identical = False
        
        # Compare values for common intervals
        value_mismatches = 0
        for key in sorted(common_keys):
            val1 = file1.intervals[key]
            val2 = file2.intervals[key]
            
            # Try numeric comparison with tolerance
            try:
                num1 = float(val1.value)
                num2 = float(val2.value)
                if abs(num1 - num2) > VALUE_TOLERANCE:
                    msg = (
                        f"Value mismatch: NMI {val1.nmi}, Date {val1.date}, "
                        f"Index {val1.interval_index} | "
                        f"File 1: {val1.value} | File 2: {val2.value}"
                    )
                    discrepancies.append(msg)
                    print(f"[X] {msg}")
                    is_identical = False
                    value_mismatches += 1
                    
                    # Progress indicator for large comparisons
                    if value_mismatches % 100 == 0:
                        print(f"  ... Found {value_mismatches} mismatches so far ...")
            except ValueError:
                # Fallback to string comparison for non-numeric values
                if val1.value != val2.value:
                    msg = (
                        f"Value mismatch: NMI {val1.nmi}, Date {val1.date}, "
                        f"Index {val1.interval_index} | "
                        f"File 1: '{val1.value}' | File 2: '{val2.value}'"
                    )
                    discrepancies.append(msg)
                    print(f"[X] {msg}")
                    is_identical = False
                    value_mismatches += 1
        
        # Print summary
        print(f"\n{'='*60}")
        print("SUMMARY")
        print(f"{'='*60}")
        print(f"Intervals compared: {len(common_keys):,}")
        print(f"Value mismatches: {value_mismatches:,}")
        print(f"Missing/Extra intervals: {len(keys_only_in_file1) + len(keys_only_in_file2)}")
        print(f"Missing/Extra NMIs: {len(nmis_only_in_file1) + len(nmis_only_in_file2)}")
        print(f"Total issues found: {len(discrepancies):,}")
        
        if is_identical:
            print(f"\n[OK] Files are identical - No changes detected.")
        else:
            print(f"\n[X] Files differ - {len(discrepancies):,} issue(s) found.")
        
        print(f"{'='*60}\n")
        
    except FileNotFoundError as e:
        error_msg = f"File not found: {str(e)}"
        discrepancies.append(error_msg)
        print(f"[X] {error_msg}")
        is_identical = False
    except Exception as e:
        error_msg = f"Error: {str(e)}"
        discrepancies.append(error_msg)
        print(f"[X] {error_msg}")
        is_identical = False
    
    return is_identical, discrepancies


def list_csv_files(directory: str) -> List[str]:
    """List all CSV files in the specified directory."""
    csv_dir = Path(directory)
    if not csv_dir.exists():
        return []
    return sorted([f.name for f in csv_dir.glob("*.csv")])


def prompt_file_selection(directory: str, prompt_text: str) -> Optional[str]:
    """Prompt user to interactively select a CSV file from the directory."""
    files = list_csv_files(directory)
    
    if not files:
        print(f"[X] No CSV files found in '{directory}' directory.")
        return None
    
    # Show file list compactly
    print(f"\n{prompt_text}")
    for idx, filename in enumerate(files, 1):
        print(f"  {idx}. {filename}")
    
    while True:
        try:
            choice = input(f"\nSelect file (1-{len(files)}): ").strip()
            
            # Try as number
            if choice.isdigit():
                file_num = int(choice)
                if 1 <= file_num <= len(files):
                    selected = files[file_num - 1]
                    print(f"Selected: {selected}")
                    return str(Path(directory) / selected)
                print(f"Invalid. Enter 1-{len(files)}.")
                continue
            
            # Try as filename
            if choice in files:
                print(f"Selected: {choice}")
                return str(Path(directory) / choice)
            
            # Try as full path
            if os.path.exists(choice):
                return choice
            
            print(f"Invalid. Enter 1-{len(files)} or filename.")
        
        except (KeyboardInterrupt, EOFError):
            print("\nCancelled.")
            return None
        except Exception as e:
            print(f"Error: {e}")


def main():
    """Main entry point for the NEM12 comparison tool."""
    print("NEM12 Report Comparison Tool")
    print("="*60)
    
    # Get file paths from command line or prompt user
    if len(sys.argv) >= 3:
        file1 = sys.argv[1]
        file2 = sys.argv[2]
    else:
        csv_input_dir = "csv_input"
        
        file1 = prompt_file_selection(csv_input_dir, "BEFORE production release file:")
        if not file1:
            print("[X] No file selected for BEFORE file.")
            sys.exit(1)
        
        file2 = prompt_file_selection(csv_input_dir, "AFTER production release file:")
        if not file2:
            print("[X] No file selected for AFTER file.")
            sys.exit(1)
    
    # Verify files exist
    if not os.path.exists(file1):
        print(f"[X] File not found: {file1}")
        sys.exit(1)
    
    if not os.path.exists(file2):
        print(f"[X] File not found: {file2}")
        sys.exit(1)
    
    # Perform comparison
    is_identical, discrepancies = compare_nem12_files(file1, file2)
    
    # Exit with appropriate code (0 = success, 1 = discrepancies found)
    sys.exit(0 if is_identical else 1)


if __name__ == "__main__":
    main()
