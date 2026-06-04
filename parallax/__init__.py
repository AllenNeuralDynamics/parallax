"""
Init
"""

import os

__version__ = "1.16.2"

# allow multiple OpenMP instances
os.environ["KMP_DUPLICATE_LIB_OK"] = "True"
