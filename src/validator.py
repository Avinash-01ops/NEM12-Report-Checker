"""Core validation routines: fetch data and compare intervals.

This module uses server-side cursors for large resultsets and pandas
to align 30-minute intervals for comparison.
"""
from datetime import datetime, timedelta
import logging
import json
import numpy as np
import pandas as pd
import psycopg2.extras

logger = logging.getLogger(__name__)


def _fetch_to_dataframe(conn, query, params=None, batch_size=5000, cursor_name=None):
    """Fetch rows using a server-side cursor and return a pandas DataFrame.

    Uses a named cursor to avoid loading the entire resultset into memory
    on the server at once.
    """
    params = params or ()
    cur_name = cursor_name or "nem12_fetch_cursor"
    cur = conn.cursor(name=cur_name, cursor_factory=psycopg2.extras.RealDictCursor)
    try:
        cur.itersize = batch_size
        cur.execute(query, params)
        chunks = []
        while True:
            rows = cur.fetchmany(batch_size)
            if not rows:
                break
            chunks.append(pd.DataFrame(rows))
        if chunks:
            df = pd.concat(chunks, ignore_index=True)
        else:
            df = pd.DataFrame()
        return df
    finally:
        try:
            cur.close()
        except Exception:
            pass


def fetch_meter_intervals(conn, meter_id, start_ts, end_ts):
    """Fetch intervals from `meter_readings` table.

    Returns a dataframe with columns: `ts`, `value`, `quality_flag`.
    Timestamps are returned in UTC.
    """
    query = """
    SELECT timestamp AT TIME ZONE 'UTC' as ts, value, quality_flag
    FROM meter_readings
    WHERE meter_id = %s AND timestamp >= %s AND timestamp < %s
    ORDER BY ts
    """
    df = _fetch_to_dataframe(conn, query, (meter_id, start_ts, end_ts), cursor_name=f"meter_{meter_id}_cur")
    if not df.empty:
        df['ts'] = pd.to_datetime(df['ts'])
    return df


def fetch_nem_intervals(conn, report_id, start_ts, end_ts):
    """Fetch NEM12 record type 200 intervals from `nem12_report`.

    Assumes `nem12_report` contains fields: `report_id`, `record_type`,
    `interval_start` (timestamp), `energy` (numeric), `quality_method`.
    If your schema differs, adjust the query accordingly.
    Returns dataframe with columns: `ts`, `value`, `quality_method`.
    """
    query = """
    SELECT interval_start AT TIME ZONE 'UTC' as ts, energy as value, quality_method
    FROM nem12_report
    WHERE report_id = %s AND record_type = 200 AND interval_start >= %s AND interval_start < %s
    ORDER BY ts
    """
    df = _fetch_to_dataframe(conn, query, (report_id, start_ts, end_ts), cursor_name=f"nem_{report_id}_cur")
    if not df.empty:
        df['ts'] = pd.to_datetime(df['ts'])
    return df


DEFAULT_QUALITY_MAP = {
    # Example mapping: meter quality_flag -> NEM12 quality_method
    # Adjust as per your business rules.
    '0': '0',
    '1': '1',
    '2': '2',
}


def map_quality(meter_q, mapping=None):
    mapping = mapping or DEFAULT_QUALITY_MAP
    if pd.isna(meter_q):
        return None
    return mapping.get(str(meter_q), str(meter_q))


def _floor_to_interval_index(df, ts_col='ts', interval_minutes=30):
    if df.empty:
        return df
    df = df.copy()
    df[ts_col] = pd.to_datetime(df[ts_col], utc=True)
    df['interval_ts'] = df[ts_col].dt.floor(f"{interval_minutes}min")
    return df


def compare_intervals(nem_df: pd.DataFrame, meter_df: pd.DataFrame, interval_minutes=30, quality_map=None):
    """Compare NEM12 intervals and meter readings on 30-minute boundaries.

    Returns a dict with summary stats and a `discrepancies` DataFrame.
    """
    # Prepare dataframes
    nem = _floor_to_interval_index(nem_df, 'ts', interval_minutes)
    meter = _floor_to_interval_index(meter_df, 'ts', interval_minutes)

    # Rename columns for clarity
    if 'value' in nem.columns:
        nem = nem.rename(columns={'value': 'value_nem', 'quality_method': 'quality_nem'})
    if 'value' in meter.columns:
        meter = meter.rename(columns={'value': 'value_meter', 'quality_flag': 'quality_meter'})

    # Set index and reindex to full interval range between min/max
    # Determine start/end from inputs
    all_timestamps = []
    if not nem.empty:
        all_timestamps.append(nem['interval_ts'].min())
        all_timestamps.append(nem['interval_ts'].max())
    if not meter.empty:
        all_timestamps.append(meter['interval_ts'].min())
        all_timestamps.append(meter['interval_ts'].max())

    if not all_timestamps:
        # Nothing to compare
        return {
            'total_intervals': 0,
            'matches': 0,
            'match_percentage': 0.0,
            'missing_nem': 0,
            'missing_meter': 0,
            'discrepancies': pd.DataFrame(),
        }

    start = min(all_timestamps)
    end = max(all_timestamps) + pd.Timedelta(minutes=interval_minutes)
    full_index = pd.date_range(start=start, end=end - pd.Timedelta(minutes=interval_minutes), freq=f"{interval_minutes}min", tz='UTC')

    nem_idx = nem.set_index('interval_ts')
    meter_idx = meter.set_index('interval_ts')

    nem_re = nem_idx.reindex(full_index)
    meter_re = meter_idx.reindex(full_index)

    merged = pd.concat([nem_re[['value_nem','quality_nem']], meter_re[['value_meter','quality_meter']]], axis=1)
    merged.index.name = 'interval_ts'
    merged = merged.reset_index()

    # Map quality flags
    merged['mapped_quality_meter'] = merged['quality_meter'].apply(lambda q: map_quality(q, quality_map))

    # Determine matches
    # Use numeric tolerance for float comparisons to avoid false mismatches
    def _values_equal(a, b, tol=1e-9):
        if pd.isna(a) or pd.isna(b):
            return False
        try:
            return bool(np.isclose(float(a), float(b), atol=tol, rtol=0))
        except Exception:
            return False

    merged['value_match'] = merged.apply(lambda r: _values_equal(r.get('value_nem'), r.get('value_meter')), axis=1)
    total = len(merged)
    matches = int(merged['value_match'].sum())
    missing_nem = int(merged['value_nem'].isna().sum())
    missing_meter = int(merged['value_meter'].isna().sum())

    # Build discrepancies DataFrame with reasons
    def reason_row(row):
        if pd.isna(row['value_nem']):
            return 'missing_nem'
        if pd.isna(row['value_meter']):
            return 'missing_meter'
        if not _values_equal(row['value_nem'], row['value_meter']):
            return 'value_mismatch'
        if row['mapped_quality_meter'] != row.get('quality_nem') and pd.notna(row.get('quality_nem')):
            return 'quality_mismatch'
        return 'match'

    merged['reason'] = merged.apply(reason_row, axis=1)
    discrepancies = merged[merged['reason'] != 'match'].copy()

    stats = {
        'total_intervals': int(total),
        'matches': int(matches),
        'match_percentage': float(matches) / total * 100 if total else 0.0,
        'missing_nem': int(missing_nem),
        'missing_meter': int(missing_meter),
        'discrepancies': discrepancies,
    }
    return stats


def validate_locf_substitution(nem_df: pd.DataFrame,
                               meter_df: pd.DataFrame,
                               meter_is_cumulative: bool = True,
                               locf_quality_values=None,
                               tolerance: float = 1e-6,
                               interval_minutes=30,
                               apply_locf_to_meter: bool = False):
    """Validate LOCF-substituted NEM12 intervals against meter readings.

    - `nem_df` expected to contain `ts`, `value` (interval energy) and optionally `quality_method`.
    - `meter_df` expected to contain `ts` and `value` which is either cumulative reading
      (if `meter_is_cumulative=True`) or interval usage (if False).
    - `locf_quality_values` (optional): iterable of values in `quality_method` that indicate LOCF substitution.
      If not provided, LOCF candidates are detected where the NEM `value` equals the previous interval's value.

    Returns a dict with:
      - `locf_details`: DataFrame of LOCF rows with `meter_usage`, `nem_value`, `diff`, `match`
      - `count`, `matches`, `match_percentage`
    """
    nem = _floor_to_interval_index(nem_df, 'ts', interval_minutes)
    meter = _floor_to_interval_index(meter_df, 'ts', interval_minutes)

    # Normalize column names
    if 'value' in nem.columns:
        nem = nem.rename(columns={'value': 'value_nem', 'quality_method': 'quality_nem'})
    if 'value' in meter.columns:
        meter = meter.rename(columns={'value': 'value_meter'})

    # Build full index from overlapping range
    all_timestamps = []
    if not nem.empty:
        all_timestamps.append(nem['interval_ts'].min())
        all_timestamps.append(nem['interval_ts'].max())
    if not meter.empty:
        all_timestamps.append(meter['interval_ts'].min())
        all_timestamps.append(meter['interval_ts'].max())

    if not all_timestamps:
        return {'locf_details': pd.DataFrame(), 'count': 0, 'matches': 0, 'match_percentage': 0.0}

    start = min(all_timestamps)
    end = max(all_timestamps) + pd.Timedelta(minutes=interval_minutes)
    full_index = pd.date_range(start=start, end=end - pd.Timedelta(minutes=interval_minutes), freq=f"{interval_minutes}min", tz='UTC')

    nem_idx = nem.set_index('interval_ts').reindex(full_index)
    meter_idx = meter.set_index('interval_ts').reindex(full_index)

    # Compute meter usage
    if meter_is_cumulative:
        # diff of cumulative readings gives interval usage
        meter_idx = meter_idx.sort_index()
        meter_usage = meter_idx['value_meter'].astype(float).diff()
    else:
        meter_usage = meter_idx['value_meter'].astype(float)

    out = pd.DataFrame({'interval_ts': full_index})
    out = out.set_index('interval_ts')
    out['nem_value'] = nem_idx.get('value_nem')
    out['quality_nem'] = nem_idx.get('quality_nem')
    out['meter_usage'] = meter_usage.values

    # Optionally apply LOCF substitution to meter cumulative values before usage calculation
    # If apply_locf_to_meter is True, we mark where meter cumulative values were NaN and filled
    out['meter_substituted'] = False
    if apply_locf_to_meter and meter_is_cumulative:
        # We need original cumulative series to detect substitutions
        orig_cum = meter_idx['value_meter'].copy()
        filled = orig_cum.ffill()
        substituted_mask = orig_cum.isna() & filled.notna()
        # Recompute usage from filled cumulative series
        filled_usage = filled.astype(float).diff()
        out['meter_usage'] = filled_usage.values
        # Mark substituted intervals where the cumulative reading was filled
        # Note: substituted_mask aligns with interval index
        # Create a Series for mask aligned to full_index
        mask_series = pd.Series(substituted_mask.values, index=full_index)
        out['meter_substituted'] = mask_series.values

    # Identify LOCF candidates
    if locf_quality_values is not None:
        out['is_locf'] = out['quality_nem'].isin(set(locf_quality_values))
    else:
        # Heuristic: LOCF when nem_value equals previous nem_value and nem_value not null
        out['is_locf'] = (out['nem_value'] == out['nem_value'].shift(1)) & out['nem_value'].notna()

    # Compare expected usage vs reported nem interval value
    # For LOCF rows, the reported interval in some schemas is stored as the interval usage
    # Here we compare `nem_value` to `meter_usage`.
    def compare_row(row):
        if pd.isna(row['nem_value']) or pd.isna(row['meter_usage']):
            return None
        try:
            diff = float(row['nem_value']) - float(row['meter_usage'])
        except Exception:
            return None
        return diff

    out['diff'] = out.apply(compare_row, axis=1)
    out['match'] = out['diff'].apply(lambda d: True if d is not None and abs(d) <= tolerance else False)

    locf_details = out[out['is_locf']].reset_index()
    count = int(len(locf_details))
    matches = int(locf_details['match'].sum()) if count else 0
    match_percentage = float(matches) / count * 100.0 if count else 0.0

    return {'locf_details': locf_details, 'count': count, 'matches': matches, 'match_percentage': match_percentage}
