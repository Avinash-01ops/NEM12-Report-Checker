# NEM12 Validator

Tool to compare NEM12 files (BEFORE vs AFTER) and find differences.

---

## Quick Start

### 1. Install Dependencies

```bash
pip install -r requirements.txt
```

### 2. Download Reports (Optional)

**Setup**: Create `.env` file with `METRIXA_EMAIL` and `METRIXA_PASSWORD`

**Edit**: `src/download_reports/config.py` (set REPORT_NAME, FROM_DATE, TO_DATE)

**Run**:
```bash
pip install playwright
playwright install chromium
python -m src.download_reports.download_nem12_reports
```

**What it does**: Downloads NEM12 reports from MetrixAI portal. Saves to `data/Before_Production/` or `data/After_Production/` based on your selection.

### 3. Compare Files (Command Line)

**Setup**: Put BEFORE files in `data/Before_Production/`, AFTER files in `data/After_Production/`

**Edit**: `config/metadata_mapping.json` (set before_file and after_file names)

**Run**:
```bash
python -m src.check_reports.check_nem12
```

**What it does**: Compares BEFORE and AFTER files line by line. Creates CSV report in `Results/` folder with all differences found.

### 4. Compare Files (Web UI - Easier!)

**Run**: Open `ui/index.html` in your browser

**What it does**: Upload files, see automatic matching, click compare. Results shown in browser with download options.

---

## Commands Reference

| Task | Command |
|------|---------|
| Download reports | `python -m src.download_reports.download_nem12_reports` |
| Compare files (CLI) | `python -m src.check_reports.check_nem12` |
| Compare files (UI) | Open `ui/index.html` |

---

## Issue Types

- **STRUCTURE**: File structure different (missing/extra records)
- **MISSING**: Data in BEFORE but not in AFTER
- **EXTRA**: Data in AFTER but not in BEFORE
- **VALUE_MISMATCH**: Same location but different values

---

## Troubleshooting

**"File not found"**: Check filenames in `config/metadata_mapping.json` match exactly (including .csv)

**Download not working**: Check `.env` file and run `playwright install chromium`

**UI not working**: Make sure `ui/app.js` exists, refresh browser (F5)

---

## Folder Structure

```
data/Before_Production/    ← Put BEFORE files here
data/After_Production/     ← Put AFTER files here
config/metadata_mapping.json  ← Edit for CLI comparison
Results/                    ← Comparison results saved here
```
