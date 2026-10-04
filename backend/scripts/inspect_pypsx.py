import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import os
import glob
print("Files in site-packages/pypsx_toolkit:")
for p in glob.glob("/usr/local/lib/python3.11/site-packages/pypsx_toolkit/**/*", recursive=True):
    print(p)
"""

run_remote_python(code)
