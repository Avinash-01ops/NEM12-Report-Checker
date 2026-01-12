import json
from pathlib import Path


def write_discrepancy_csv(discrepancies_df, out_path):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    discrepancies_df.to_csv(out, index=False)
    return str(out)


def write_summary_json(summary: dict, out_path):
    out = Path(out_path)
    out.parent.mkdir(parents=True, exist_ok=True)
    # Make a shallow serializable copy (drop DataFrames)
    serializable = {k: v for k, v in summary.items() if k != 'discrepancies'}
    # If there is a DataFrame in discrepancies, include a count instead
    if 'discrepancies' in summary and hasattr(summary['discrepancies'], 'shape'):
        serializable['discrepancies_count'] = int(summary['discrepancies'].shape[0])
    with open(out, 'w', encoding='utf-8') as fh:
        json.dump(serializable, fh, indent=2, default=str)
    return str(out)


def write_report(summary: dict, out_dir: str):
    outdir = Path(out_dir)
    outdir.mkdir(parents=True, exist_ok=True)
    csv_path = outdir / 'discrepancies.csv'
    json_path = outdir / 'summary.json'
    if 'discrepancies' in summary and not summary['discrepancies'].empty:
        write_discrepancy_csv(summary['discrepancies'], csv_path)
    # If LOCF validation results are present, export them as well
    locf_path = outdir / 'locf_details.csv'
    if 'locf_details' in summary and hasattr(summary['locf_details'], 'empty') and not summary['locf_details'].empty:
        summary['locf_details'].to_csv(locf_path, index=False)

    write_summary_json(summary, json_path)
    return {
        'csv': str(csv_path) if (outdir / 'discrepancies.csv').exists() else None,
        'locf': str(locf_path) if (outdir / 'locf_details.csv').exists() else None,
        'json': str(json_path)
    }
