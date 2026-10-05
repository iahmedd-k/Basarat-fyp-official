import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
from app.db.base import get_sync_session_factory
from app.models.user import User

with get_sync_session_factory()() as s:
    users = s.query(User).all()
    print("Users in DB count:", len(users))
    for u in users:
        print(f"ID={u.id}, email={u.email}, username={u.username}, is_active={u.is_active}, role={getattr(u, 'role', 'user')}")
"""

run_remote_python(code)
