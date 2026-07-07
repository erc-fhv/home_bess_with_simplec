import os
import pickle
import hashlib
import json
import inspect
from functools import wraps
import os

def cache_result(cache_dir=None):
    """
    Decorator to cache function results based on arguments and source code.
    Temporary file path from system environment variable 'TMP' if not provided.
    """
    def decorator(func):
        @wraps(func)
        def wrapper(*args, **kwargs):
            # base directory: use provided cache_dir, otherwise use $TMP (or /tmp fallback)
            base_tmp = os.environ.get("TMP", "/tmp")
            effective_base = cache_dir or base_tmp

            # Serialize arguments
            try:
                params_bytes = json.dumps({'args': args, 'kwargs': kwargs}, sort_keys=True, default=str).encode()
            except Exception:
                params_bytes = pickle.dumps((args, kwargs))
            params_hash = hashlib.sha256(params_bytes).hexdigest()[:12]

            # Hash function source file
            actual_func = func.__func__ if isinstance(func, staticmethod) else func # handles static methods
            file_path = inspect.getfile(actual_func)
            with open(file_path, 'rb') as f:
                file_hash = hashlib.sha256(f.read()).hexdigest()[:12]

            # Build directory structure: {effective_base}/cache_manager/<function_name>/
            # Cache filename will contain both the parameters hash and the source file hash so
            # the same param set but changed source invalidates the entry.
            func_cache_dir = os.path.join(effective_base, "cache_manager", actual_func.__name__)
            os.makedirs(func_cache_dir, exist_ok=True)
            cache_path = os.path.join(func_cache_dir, f"result_{params_hash}_{file_hash}.pkl")

            # Load or create
            if os.path.exists(cache_path):
                with open(cache_path, 'rb') as f:
                    result = pickle.load(f)
                # print(f"Loaded from cache: {cache_path}")
                return result
            else:
                result = actual_func(*args, **kwargs)
                with open(cache_path, 'wb') as f:
                    pickle.dump(result, f)
                # print(f"Saved to cache: {cache_path}")
                return result
        return wrapper
    return decorator