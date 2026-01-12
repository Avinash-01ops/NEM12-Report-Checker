import pandas as pd
from src.validator import compare_intervals


def test_compare_intervals_basic():
    # Build sample NEM12 dataframe (30-min intervals)
    nem = pd.DataFrame([
        {'ts': '2025-01-01T00:00:00Z', 'value': 1.0, 'quality_method': '0'},
        {'ts': '2025-01-01T00:30:00Z', 'value': 2.0, 'quality_method': '0'},
        {'ts': '2025-01-01T01:00:00Z', 'value': 3.0, 'quality_method': '0'},
    ])

    # Meter readings: one mismatch and one missing
    meter = pd.DataFrame([
        {'ts': '2025-01-01T00:00:00Z', 'value': 1.0, 'quality_flag': 0},
        {'ts': '2025-01-01T00:30:00Z', 'value': 9.0, 'quality_flag': 0},
        # missing 01:00
    ])

    stats = compare_intervals(nem, meter, interval_minutes=30)
    assert stats['total_intervals'] == 3
    assert stats['matches'] == 1
    assert stats['missing_meter'] == 1
    assert stats['missing_nem'] == 0
    assert 'discrepancies' in stats
    assert len(stats['discrepancies']) == 3


def test_validate_locf_substitution():
    # Meter cumulative readings
    meter = pd.DataFrame([
        {'ts': '2025-01-01T00:00:00Z', 'value': 100.0},
        {'ts': '2025-01-01T00:30:00Z', 'value': 101.0},
        {'ts': '2025-01-01T01:00:00Z', 'value': 103.0},
    ])

    # NEM report intervals: interval usage values. The 00:30 value was substituted via LOCF (repeated 1.0)
    nem = pd.DataFrame([
        {'ts': '2025-01-01T00:00:00Z', 'value': 1.0, 'quality_method': 'OK'},
        {'ts': '2025-01-01T00:30:00Z', 'value': 1.0, 'quality_method': 'LOCF'},
        {'ts': '2025-01-01T01:00:00Z', 'value': 2.0, 'quality_method': 'OK'},
    ])

    from src.validator import validate_locf_substitution

    res = validate_locf_substitution(nem, meter, meter_is_cumulative=True, locf_quality_values=['LOCF'], interval_minutes=30)
    assert res['count'] == 1
    assert res['matches'] == 1
    assert res['match_percentage'] == 100.0
