import sys
from pathlib import Path
sys.path.insert(0, str(Path(__file__).resolve().parent.parent))
from scripts.remote_exec import run_remote_python

code = """
import json
import urllib.request
from datetime import timedelta
from app.core.security import create_access_token
from app.db.base import get_sync_session_factory
from app.models.user import User

# 1. Get or create a seeded admin test user
token = None
with get_sync_session_factory()() as s:
    u = s.query(User).filter(User.email == "admin@basarat.pk").first()
    if not u:
        u = s.query(User).first()
    if u:
        token = create_access_token(
            data={"sub": str(u.id), "email": u.email, "role": getattr(u, "role", "admin")},
            expires_delta=timedelta(days=7)
        )
        print("Generated Token for user:", u.email, "ID:", u.id)

print("TOKEN_READY:", bool(token))
"""

run_remote_python(code)
