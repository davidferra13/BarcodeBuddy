"""BarcodeBuddy application package."""

import os

# Web and ingestion run separately; avoid multiplying BLAS startup allocations.
# An operator's explicit thread count remains authoritative.
os.environ.setdefault("OPENBLAS_NUM_THREADS", "1")

__version__ = "3.1.0"
