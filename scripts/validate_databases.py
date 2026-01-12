"""Validate NEM12 reports against meter tables across two Postgres DBs.

This script is a convenience test-runner that uses the provided DB
credentials (hardcoded below) to connect to two Postgres instances,
discover sensible column names in `meter`, `meter_channel`, `meter_data`
and `nem12_reports`, fetch interval rows, run LOCF validation and a
general interval comparison, then write a report into `reports/db_run`.

Usage (after installing requirements):

python scripts/validate_databases.py --meter-identifier <METER_ID> --report-id <REPORT_ID> --start <ISO> --end <ISO>

Notes:
- The script attempts to autodiscover timestamp/value/quality columns
  in the target tables; if your schema differs significantly you can
  adapt the queries here.
"""
import argparse
import logging
from datetime import datetime
from pathlib import Path

import pandas as pd

from src.db import connect_db
from src.utils import setup_logging
from src.validator import compare_intervals, validate_locf_substitution
from src.report import write_report

logger = logging.getLogger(__name__)


# --- Replace or parameterise these connection dicts as needed ---
METER_DB = {
    'host': 'ai-metrix-dev1-autoind-327e.a.timescaledb.io',
    'port': '25897',
    'database': 'mdm-dev',
    'user': 'tatva_readonly',
    'password': 'ILsNhjI5fETbkWyc'
}

REPORT_DB = {
    'host': 'ai-mdm-test-qa.postgres.database.azure.com',
    'port': '5432',
    'database': 'pgdb-reports-test-qa',
    'user': 'tatva_readonly',
    'password': '6Yopc4msdqKeoMDn'
}


def get_table_columns(conn, table_name):
    q = """
    SELECT column_name FROM information_schema.columns
    WHERE table_name = %s
    """
    cur = conn.cursor()
    try:
        cur.execute(q, (table_name,))
        rows = cur.fetchall()
        return set(r[0] for r in rows)
    finally:
        try:
            cur.close()
        except Exception:
            pass


def fetch_meter_from_schema(conn, meter_identifier, start_ts, end_ts):
    # Simplified meter query using discovered schema: `meters` and `meter_data`
    sql = """
    SELECT md.timestamp AT TIME ZONE 'UTC' as ts, md.value as value, md.status as quality_flag
    FROM meter_data md
    JOIN meters m ON md.meter_id = m.meter_id
    WHERE (m.meter_id = %s OR m.nmi = %s) AND md.timestamp >= %s AND md.timestamp < %s
    ORDER BY md.timestamp
    """
    params = (meter_identifier, meter_identifier, start_ts, end_ts)

    cur = conn.cursor()
    try:
        cur.execute(sql, params)
        rows = cur.fetchall()
        if not rows:
            return pd.DataFrame()
        cols = [desc[0] for desc in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'])
        return df
    finally:
        try:
            cur.close()
        except Exception:
            pass


def fetch_nem_from_schema(conn, report_id, start_ts, end_ts):
    # Use data_validation_report_rule_output_data joined to nem12_report_meters to fetch interval rows
    sql = """
    SELECT d.timestamp AT TIME ZONE 'UTC' as ts, NULLIF(d.value, '')::numeric as value, d.status as quality_method
    FROM data_validation_report_rule_output_data d
    JOIN nem12_report_meters m ON m.meter_id = d.meter_id
    WHERE m.nem12_report_id = %s AND d.timestamp >= %s AND d.timestamp < %s
    ORDER BY d.timestamp
    """
    cur = conn.cursor()
    try:
        cur.execute(sql, (report_id, start_ts, end_ts))
        rows = cur.fetchall()
        if not rows:
            return pd.DataFrame()
        cols = [desc[0] for desc in cur.description]
        df = pd.DataFrame(rows, columns=cols)
        if 'ts' in df.columns:
            df['ts'] = pd.to_datetime(df['ts'])
        return df
    finally:
        try:
            cur.close()
        except Exception:
            pass


def main():
    setup_logging()
    parser = argparse.ArgumentParser(description='Validate NEM12 reports against meter tables (DBs)')
    parser.add_argument('--meter-identifier', required=True)
    parser.add_argument('--report-id', required=True)
    parser.add_argument('--start', required=True)
    parser.add_argument('--end', required=True)
    parser.add_argument('--out', default='reports/db_run')
    parser.add_argument('--apply-meter-locf', action='store_true')
    args = parser.parse_args()

    meter_conn = None
    report_conn = None
    try:
        meter_conn = connect_db(METER_DB)
        report_conn = connect_db(REPORT_DB)

        nem_df = fetch_nem_from_schema(report_conn, args.report_id, args.start, args.end)
        meter_df = fetch_meter_from_schema(meter_conn, args.meter_identifier, args.start, args.end)

        # LOCF validation (assume meter cumulative)
        locf = validate_locf_substitution(
            nem_df,
            meter_df,
            meter_is_cumulative=True,
            locf_quality_values=None,
            tolerance=1e-6,
            interval_minutes=30,
            apply_locf_to_meter=args.apply_meter_locf,
        )

        stats = compare_intervals(nem_df, meter_df, interval_minutes=30)

        summary = stats.copy()
        summary.update({
            'locf_count': locf.get('count', 0),
            'locf_matches': locf.get('matches', 0),
            'locf_match_percentage': locf.get('match_percentage', 0.0),
            'locf_details': locf.get('locf_details')
        })

        out = write_report(summary, args.out)
        logger.info('Report written: %s', out)
    except Exception as e:
        logger.exception('Validation run failed: %s', e)
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
