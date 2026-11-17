"""
Init
"""

import os
from importlib.metadata import PackageNotFoundError, version

try:
    __version__ = version("parallax-app")  # single source: version in pyproject.toml
except PackageNotFoundError:  # running from a source tree that is not installed
    __version__ = "unknown"

# allow multiple OpenMP instances
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
