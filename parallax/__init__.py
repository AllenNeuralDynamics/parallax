"""
Init
"""

import os

__version__ = "1.5.1"

# allow multiple OpenMP instances
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
