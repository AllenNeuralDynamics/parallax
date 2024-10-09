"""
Init
"""

import os

__version__ = "1.0.0"

# allow multiple OpenMP instances
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
