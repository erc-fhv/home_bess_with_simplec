import pandas as pd

def assert_valid_index(idx: pd.DatetimeIndex, freq: '15min', tz='UTC'):
    """Assert that a DatetimeIndex is complete and monotonic for a given frequency."""
    # check index for consistency
    assert idx.is_unique, 'Index has duplicates'
    assert idx.is_monotonic_increasing, 'Index must be sorted ascending'

    # Completeness
    expected = pd.date_range(idx.min(), idx.max(), freq=freq, tz=tz)
    missing = expected.difference(idx)
    assert missing.empty, f"Missing timestamps: {missing}"