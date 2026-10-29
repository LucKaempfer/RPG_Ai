"""The end-to-end smoke scripts (``m2_smoke_test.py``,
``m4_smoke_test.py``) as pytest cases.  Each runs in its own process:
they are plain scripts with module-level state and their own pygame
display."""
import pathlib
import subprocess
import sys

import pytest

HERE = pathlib.Path(__file__).resolve().parent


@pytest.mark.parametrize("script", ["m2_smoke_test.py", "m4_smoke_test.py"])
def test_smoke_script(script):
    done = subprocess.run([sys.executable, str(HERE / script)],
                          cwd=HERE.parent, capture_output=True, text=True,
                          timeout=600)
    assert done.returncode == 0, done.stdout[-2000:] + done.stderr[-2000:]
    assert " OK (" in done.stdout
