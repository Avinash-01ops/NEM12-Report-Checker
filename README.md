# NEM12 Report Comparison Tool

Compares Australian Energy Market NEM12 reports before and after production release. Compares files logically by NMI, date, and interval index.

## Usage

1. Place CSV files in the `csv_input` folder
2. Run:
   ```bash
   python compare_csv.py
   ```
3. Select files when prompted (BEFORE and AFTER production release)

Or specify files directly:
```bash
python compare_csv.py before.csv after.csv
```

## What It Compares

- Missing/extra NMIs
- Missing/extra dates per NMI
- Interval value mismatches (tolerance: 0.001)
- Ignores metadata (timestamps, headers, record order)

## Output

- `[OK]` = Files identical, no changes detected
- `[X]` = Discrepancies found with detailed location (NMI, Date, Interval Index)

## Exit Codes

- `0` = Identical files
- `1` = Discrepancies found
