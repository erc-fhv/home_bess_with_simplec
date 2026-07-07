import pytest
import os
import shutil
import pandas as pd
from util.cache_manager import cache_result

@pytest.fixture(scope="function")
def cache_dir(tmp_path):
    # Use a temporary directory for cache
    return tmp_path

def test_cache_decorator_saves_and_loads(cache_dir):
    call_counter = {'count': 0}

    @cache_result(cache_dir=str(cache_dir))
    def dummy_func(x):
        call_counter['count'] += 1
        return pd.DataFrame({'a': [x, x+1, x+2]})

    # First call: should compute and save
    df1 = dummy_func(1)
    assert call_counter['count'] == 1
    assert (df1['a'] == [1,2,3]).all()

    # Second call: should load from cache
    df2 = dummy_func(1)
    assert call_counter['count'] == 1  # No increment, loaded from cache
    assert (df2['a'] == [1,2,3]).all()

def test_cache_decorator_invalidation_on_args_change(cache_dir):
    call_counter = {'count': 0}

    @cache_result(cache_dir=str(cache_dir))
    def dummy_func(x):
        call_counter['count'] += 1
        return pd.DataFrame({'a': [x, x+1, x+2]})

    df1 = dummy_func(1)
    df2 = dummy_func(2)
    assert call_counter['count'] == 2
    assert not df1.equals(df2)

def test_cache_decorator_invalidation_on_code_change(cache_dir):
    call_counter1 = {'count': 0}
    call_counter2 = {'count': 0}

    @cache_result(cache_dir=str(cache_dir))
    def dummy_func(x):
        call_counter1['count'] += 1
        return pd.DataFrame({'a': [x, x+1, x+2]})

    @cache_result(cache_dir=str(cache_dir))
    def dummy_func_modified(x):
        call_counter2['count'] += 1
        return pd.DataFrame({'a': [x+10, x+11, x+12]})

    df1 = dummy_func(1)
    df2 = dummy_func_modified(1)
    assert call_counter1['count'] == 1
    assert call_counter2['count'] == 1
    assert not df1.equals(df2)

def test_cache_file_created(cache_dir):
    @cache_result(cache_dir=str(cache_dir))
    def dummy_func(x):
        return pd.DataFrame({'a': [x, x+1, x+2]})

    dummy_func(1)
    # Check that a cache file exists in the function-specific cache folder
    expected_dir = os.path.join(str(cache_dir), "cache_manager", "dummy_func")
    assert os.path.isdir(expected_dir), f"Expected cache directory not found: {expected_dir}"
    files = os.listdir(expected_dir)
    assert any(f.startswith("result_") and f.endswith(".pkl") for f in files), f"No cache file named result_*.pkl found in {expected_dir}"