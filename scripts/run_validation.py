import argparse
import logging
from src.config import load_config
from src.db import connect_db
from src.utils import setup_logging
from src.validator import fetch_meter_intervals, fetch_nem_intervals, compare_intervals
from src.report import write_report

logger = logging.getLogger(__name__)


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description='Validate NEM12 report against meter readings')
    parser.add_argument('--config', help='Path to config.ini', default=None)
    parser.add_argument('--meter-id', help='Meter ID to validate', required=True)
    parser.add_argument('--report-id', help='NEM12 report id to validate', required=True)
    parser.add_argument('--start', help='Start timestamp (ISO)', required=True)
    parser.add_argument('--end', help='End timestamp (ISO)', required=True)
    parser.add_argument('--out', help='Output directory for reports', default='reports')
    args = parser.parse_args()

    config = load_config(args.config)
    meter_db = config.get('meter_db')
    report_db = config.get('report_db')

    meter_conn = connect_db(meter_db)
    report_conn = connect_db(report_db)

    try:
        nem_df = fetch_nem_intervals(report_conn, args.report_id, args.start, args.end)
        meter_df = fetch_meter_intervals(meter_conn, args.meter_id, args.start, args.end)

        stats = compare_intervals(nem_df, meter_df, interval_minutes=30)

        out = write_report(stats, args.out)
        logger.info('Report written: %s', out)
    finally:
        try:
            meter_conn.close()
        except Exception:
            pass
        try:
            report_conn.close()
        except Exception:
            pass


if __name__ == '__main__':
    main()
