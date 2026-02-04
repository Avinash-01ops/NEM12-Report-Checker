"""Core NEM12 comparison logic."""

import csv
from dataclasses import dataclass
from datetime import datetime
from pathlib import Path
from typing import Dict, List, Optional

QUALITY_FLAGS = {"A", "V", "E", "F", "N", "S", "R", "C", "D"}
CSV_DELIMITERS = [",", "|", ";", "\t"]


def now_hhmmss_ddmmyy() -> str:
    """Timestamp format: HHMMSS-DDMMYY."""
    return datetime.now().strftime("%H%M%S-%d%m%y")


def detect_delimiter(file_path: str) -> str:
    try:
        with open(file_path, "r", encoding="utf-8", errors="replace") as f:
            first_line = f.readline()
        best = CSV_DELIMITERS[0]
        best_count = first_line.count(best)
        for d in CSV_DELIMITERS[1:]:
            c = first_line.count(d)
            if c > best_count:
                best, best_count = d, c
        return best
    except Exception:
        return CSV_DELIMITERS[0]


def normalize_cell(value: str) -> str:
    return (value or "").strip()


def safe_get(row: List[str], idx: int) -> str:
    if 0 <= idx < len(row):
        return normalize_cell(row[idx])
    return ""


def parse_channel_from_200(row: List[str]) -> str:
    ch = safe_get(row, 4)
    if ch:
        return ch
    ch = safe_get(row, 2)
    if ch:
        return ch
    return "UNKNOWN_CHANNEL"


def parse_interval_length_from_200(row: List[str]) -> int:
    raw = safe_get(row, 8)
    try:
        return int(raw)
    except Exception:
        return 30


def find_quality_index_for_300(row: List[str]) -> Optional[int]:
    for i in range(len(row) - 4, 1, -1):
        v = normalize_cell(row[i])
        if len(v) == 1 and v in QUALITY_FLAGS:
            return i
    return None


@dataclass(frozen=True)
class IntervalKey:
    nmi: str
    channel: str
    date: str
    interval_index: int


@dataclass(frozen=True)
class IntervalCell:
    value: str
    row_number: int
    cell_number: int


@dataclass
class Issue:
    comparison_id: str
    before_file: str
    after_file: str
    issue_type: str
    nmi: str
    channel: str
    date: str
    interval_index: str
    before_row: str
    after_row: str
    before_value: str
    after_value: str
    note: str
    timestamp: str


class Nem12Parsed:
    def __init__(self, file_path: str):
        self.file_path = file_path
        self.file_name = Path(file_path).name
        self.delimiter = detect_delimiter(file_path)
        self.has_100 = False
        self.has_200 = False
        self.has_900 = False
        self.first_record_type: Optional[str] = None
        self.interval_map: Dict[IntervalKey, IntervalCell] = {}
        self._current_nmi: Optional[str] = None
        self._current_channel: Optional[str] = None
        self._current_interval_len: int = 30
        self._parse()

    def _parse(self) -> None:
        with open(self.file_path, "r", encoding="utf-8", errors="replace") as f:
            reader = csv.reader(f, delimiter=self.delimiter)
            for row_num, row in enumerate(reader, start=1):
                if not row:
                    continue
                rec = normalize_cell(row[0])
                if self.first_record_type is None:
                    self.first_record_type = rec

                if rec == "100":
                    self.has_100 = True
                    continue
                if rec == "200":
                    self.has_200 = True
                    self._current_nmi = safe_get(row, 1)
                    self._current_channel = parse_channel_from_200(row)
                    self._current_interval_len = parse_interval_length_from_200(row)
                    continue
                if rec == "900":
                    self.has_900 = True
                    continue

                if rec != "300":
                    continue

                if not self._current_nmi or not self._current_channel:
                    continue

                date = safe_get(row, 1)
                q_idx = find_quality_index_for_300(row)
                if q_idx is not None and q_idx > 2:
                    values = [normalize_cell(c) for c in row[2:q_idx]]
                else:
                    expected = 48 if self._current_interval_len == 30 else max(1, (24 * 60) // max(1, self._current_interval_len))
                    values = [normalize_cell(c) for c in row[2 : 2 + expected]]

                for idx, v in enumerate(values):
                    key = IntervalKey(self._current_nmi, self._current_channel, date, idx)
                    cell_number = 2 + idx + 1
                    if key in self.interval_map and self.interval_map[key].value:
                        continue
                    self.interval_map[key] = IntervalCell(value=v, row_number=row_num, cell_number=cell_number)


def compare(before_path: str, after_path: str, comparison_id: str) -> List[Issue]:
    before = Nem12Parsed(before_path)
    after = Nem12Parsed(after_path)
    ts = now_hhmmss_ddmmyy()
    issues: List[Issue] = []

    # Test 1: Verify structure (100/200/900)
    if before.first_record_type != "100":
        issues.append(Issue(comparison_id, before.file_name, after.file_name, "STRUCTURE", "", "", "", "", "", "", "", "", f"BEFORE first record is {before.first_record_type}", ts))
    if after.first_record_type != "100":
        issues.append(Issue(comparison_id, before.file_name, after.file_name, "STRUCTURE", "", "", "", "", "", "", "", "", f"AFTER first record is {after.first_record_type}", ts))
    if not before.has_200:
        issues.append(Issue(comparison_id, before.file_name, after.file_name, "STRUCTURE", "", "", "", "", "", "", "", "", "BEFORE missing any 200 record", ts))
    if not after.has_200:
        issues.append(Issue(comparison_id, before.file_name, after.file_name, "STRUCTURE", "", "", "", "", "", "", "", "", "AFTER missing any 200 record", ts))
    if not before.has_900:
        issues.append(Issue(comparison_id, before.file_name, after.file_name, "STRUCTURE", "", "", "", "", "", "", "", "", "BEFORE missing 900 record", ts))
    if not after.has_900:
        issues.append(Issue(comparison_id, before.file_name, after.file_name, "STRUCTURE", "", "", "", "", "", "", "", "", "AFTER missing 900 record", ts))

    # Test 3: Missing/extra chunks
    before_keys = set(before.interval_map.keys())
    after_keys = set(after.interval_map.keys())
    missing_in_after = before_keys - after_keys
    extra_in_after = after_keys - before_keys

    for k in sorted(missing_in_after, key=lambda x: (x.nmi, x.channel, x.date, x.interval_index)):
        bcell = before.interval_map[k]
        issues.append(Issue(comparison_id, before.file_name, after.file_name, "MISSING", k.nmi, k.channel, k.date, str(k.interval_index), str(bcell.row_number), "", bcell.value, "", "", ts))

    for k in sorted(extra_in_after, key=lambda x: (x.nmi, x.channel, x.date, x.interval_index)):
        acell = after.interval_map[k]
        issues.append(Issue(comparison_id, before.file_name, after.file_name, "EXTRA", k.nmi, k.channel, k.date, str(k.interval_index), "", str(acell.row_number), "", acell.value, "", ts))

    # Test 4: Value mismatches
    common = before_keys & after_keys
    for k in sorted(common, key=lambda x: (x.nmi, x.channel, x.date, x.interval_index)):
        b = before.interval_map[k]
        a = after.interval_map[k]
        if b.value != a.value:
            issues.append(Issue(comparison_id, before.file_name, after.file_name, "VALUE_MISMATCH", k.nmi, k.channel, k.date, str(k.interval_index), str(b.row_number), str(a.row_number), b.value, a.value, "", ts))

    return issues


def write_issues_csv(
    issues: List[Issue],
    out_path: str,
    before_file_name: str = "",
    after_file_name: str = "",
) -> str:
    """Write issues in the simplified report format used by the tool.

    CSV layout:
    - Metadata header:
        Report_Name,NEM12 Before vs After Comparison
        Report_Date,YYYY-MM-DD
        Report_Time,HH:MM:SS
        Before_Report,<before file name>
        After_Report,<after file name>
    - Blank row
    - Detail header:
        Sr,issue_type,nmi,record_type,channel,date,
        field_name,after_cell_location,before_value,after_value,details
    """

    # Basic metadata
    now = datetime.now()
    report_date = now.strftime("%Y-%m-%d")
    report_time = now.strftime("%H:%M:%S")

    if issues:
        before_name = issues[0].before_file
        after_name = issues[0].after_file
    else:
        before_name = before_file_name
        after_name = after_file_name

    def classify(i: Issue) -> tuple[str, str, str, str, str]:
        """Map internal Issue to (issue_type, level, record_type, field_name, excel_cell)."""
        t = i.issue_type.upper()
        # Defaults
        level = "ROW"
        record_type = ""
        field_name = ""
        excel_cell = ""

        if t == "VALUE_MISMATCH":
            level = "CELL"
            record_type = "300"
            field_name = "IntervalValue"
        elif t in {"MISSING", "EXTRA"}:
            level = "ROW"
            record_type = "300"
        elif t == "STRUCTURE":
            level = "METADATA"
            record_type = ""
            field_name = ""

        return t, level, record_type, field_name, excel_cell

    with open(out_path, "w", newline="", encoding="utf-8") as f:
        w = csv.writer(f)

        # Metadata header
        w.writerow(["Report_Name", "NEM12 Before vs After Comparison"])
        w.writerow(["Report_Date", report_date])
        w.writerow(["Report_Time", report_time])
        w.writerow(["Before_Report", before_name])
        w.writerow(["After_Report", after_name])
        w.writerow([])  # blank separator row

        # Detail header
        w.writerow(
            [
                "Sr",
                "issue_type",
                "nmi",
                "record_type",
                "channel",
                "date",
                "field_name",
                f"after_cell_location ({after_name})",
                "before_value",
                "after_value",
                "details",
            ]
        )

        # Detail rows
        for idx, i in enumerate(issues, start=1):
            issue_type, level, record_type, field_name, excel_cell = classify(i)
            # Cell location (primarily AFTER file)
            cell_parts: List[str] = []
            if i.after_row:
                cell_parts.append(f"row {i.after_row}")
            elif i.before_row:
                cell_parts.append(f"row {i.before_row}")
            if i.interval_index:
                cell_parts.append(f"interval {i.interval_index}")
            cell_loc = ", ".join(cell_parts)

            # Human‑friendly details
            if issue_type == "VALUE_MISMATCH":
                details = (
                    f"Value mismatch between BEFORE and AFTER files "
                    f"({i.before_file}={i.before_value} vs {i.after_file}={i.after_value})."
                )
            elif issue_type == "MISSING":
                details = (
                    "Interval present in BEFORE file but missing in AFTER file "
                    f"for NMI {i.nmi}, channel {i.channel}, date {i.date}, interval {i.interval_index}."
                )
            elif issue_type == "EXTRA":
                details = (
                    "Extra interval present only in AFTER file (not in BEFORE file) "
                    f"for NMI {i.nmi}, channel {i.channel}, date {i.date}, interval {i.interval_index}."
                )
            else:  # STRUCTURE or other
                details = i.note or ""

            w.writerow(
                [
                    idx,
                    issue_type,
                    i.nmi,
                    record_type,
                    i.channel,
                    i.date,
                    field_name,
                    cell_loc,
                    i.before_value,
                    i.after_value,
                    details,
                ]
            )

    return str(Path(out_path).absolute())
