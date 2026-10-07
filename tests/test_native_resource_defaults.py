"""Cold app/NumPy startup preserves math and explicit operator thread settings."""
import json
import os
from pathlib import Path
import subprocess
import sys

import pytest

ROOT = Path(__file__).resolve().parents[1]


@pytest.mark.parametrize("operator_threads", [None, "2"])
def test_cold_start_has_bounded_default_and_honors_operator_override(operator_threads):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("BB_") and key not in ("PYTHONPATH", "PYTHONHOME", "PYTHONPYCACHEPREFIX",
                                                        "OPENBLAS_NUM_THREADS")}
    if operator_threads is not None:
        env["OPENBLAS_NUM_THREADS"] = operator_threads
    code = (
        "import json,os; import app; import numpy as np; "
        "a=np.ones((64,64)); result=a@a; "
        "print(json.dumps({'version':app.__version__,'threads':os.environ.get('OPENBLAS_NUM_THREADS'),"
        "'checksum':float(result.sum())}))"
    )
    child = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
    actual = json.loads(child.stdout)
    assert actual == {"version": "3.0.0", "threads": operator_threads or "1", "checksum": 262144.0}


@pytest.mark.parametrize("operator_threads", [None, "3"])
def test_cold_start_opencv_default_and_explicit_override(operator_threads):
    env = {key: value for key, value in os.environ.items()
           if not key.startswith("BB_") and key not in ("PYTHONPATH", "PYTHONHOME", "PYTHONPYCACHEPREFIX",
                                                        "OPENCV_FOR_THREADS_NUM")}
    if operator_threads is not None:
        env["OPENCV_FOR_THREADS_NUM"] = operator_threads
    code = (
        "import json,os; import app; import app.barcode; import cv2; import numpy as np; "
        "image=np.full((256,256),255,dtype=np.uint8); "
        "result=cv2.fastNlMeansDenoising(image,h=10); "
        "print(json.dumps({'version':app.__version__,'threads':cv2.getNumThreads(),"
        "'preserved':bool(np.array_equal(image,result))}))"
    )
    child = subprocess.run([sys.executable, "-B", "-c", code], cwd=ROOT, env=env,
                           capture_output=True, text=True, timeout=30)
    assert child.returncode == 0, child.stderr
    actual = json.loads(child.stdout)
    assert actual == {"version": "3.0.0", "threads": int(operator_threads or "2"), "preserved": True}
