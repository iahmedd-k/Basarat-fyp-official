import subprocess
import sys
from pathlib import Path

script = Path(sys.argv[1])
try:
    completed = subprocess.run(
        [sys.executable, str(script)],
        cwd=script.parent.parent,
        capture_output=True,
        text=True,
        timeout=90,
    )
    print(completed.stdout)
    if completed.stderr:
        print("STDERR:\n" + completed.stderr)
    raise SystemExit(completed.returncode)
except subprocess.TimeoutExpired as exc:
    print(f"PROBE_TIMEOUT after 90s: {script.name}")
    if exc.stdout:
        print(exc.stdout.decode(errors="replace") if isinstance(exc.stdout, bytes) else exc.stdout)
    raise SystemExit(124)
