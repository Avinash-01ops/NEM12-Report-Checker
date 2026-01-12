"""Compare meter cumulative readings from DB1 with NEM12 report values in DB2.

This script:
- Connects to both databases using `src.config.load_config` and `src.db.connect_db`.
- Fetches meter cumulative readings and NEM12 report intervals for a meter/report id and time range.
- Optionally applies LOCF to missing meter cumulative values, recomputes interval usage (current - previous).
- Compares computed meter usage to the report's interval values and records discrepancies.
- Exports a summary JSON, discrepancies CSV and LOCF details CSV (when applicable).

Usage example:
python scripts/compare_meter_report.py --meter-id M123 --report-id R456 --start 2025-01-01T00:00:00Z --end 2025-01-02T00:00:00Z --out reports --apply-meter-locf
"""
import argparse
import logging
from src.config import load_config
from src.db import connect_db
from src.utils import setup_logging
from src.validator import fetch_meter_intervals, fetch_nem_intervals, validate_locf_substitution, compare_intervals
from src.report import write_report

logger = logging.getLogger(__name__)


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description='Compare meter cumulative readings (DB1) with NEM12 report (DB2)')
    parser.add_argument('--config', help='Path to config.ini', default=None)
    parser.add_argument('--meter-id', required=True)
    parser.add_argument('--report-id', required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--out', default='reports')
    parser.add_argument('--apply-meter-locf', action='store_true', help='Apply LOCF to missing meter cumulative values before computing usage')
    parser.add_argument('--interval-minutes', type=int, default=30)
    args = parser.parse_args()

    config = load_config(args.config)
    meter_db = config.get('meter_db')
    report_db = config.get('report_db')

    meter_conn = None
    report_conn = None
    try:
        meter_conn = connect_db(meter_db)
        report_conn = connect_db(report_db)

        nem_df = fetch_nem_intervals(report_conn, args.report_id, args.start, args.end)
        meter_df = fetch_meter_intervals(meter_conn, args.meter_id, args.start, args.end)

        # Run LOCF validation: this will compute meter usage (diff of cumulative) and compare to NEM values
        locf_result = validate_locf_substitution(
            nem_df,
            meter_df,
            meter_is_cumulative=True,
            locf_quality_values=None,
            tolerance=1e-6,
            interval_minutes=args.interval_minutes,
            apply_locf_to_meter=args.apply_meter_locf,
        )

        # Also run general compare_intervals for full discrepancy stats
        stats = compare_intervals(nem_df, meter_df, interval_minutes=args.interval_minutes)

        # Merge locf stats into overall summary for output
        summary = stats.copy()
        summary.update({
            'locf_count': locf_result.get('count', 0),
            'locf_matches': locf_result.get('matches', 0),
            'locf_match_percentage': locf_result.get('match_percentage', 0.0),
            'locf_details': locf_result.get('locf_details')
        })

        out = write_report(summary, args.out)
        logger.info('Report written: %s', out)
    except Exception as e:
        logger.exception('Validation failed: %s', e)
        raise
    finally:
        if meter_conn:
            try:
                meter_conn.close()
            except Exception:
                pass
        if report_conn:
            try:
                report_conn.close()
            except Exception:
                pass


if __name__ == '__main__':
    main()
