"""Exercise every documented HTTP operation against the in-process FastAPI app.

Uses a unique temporary admin fixture, synthetic resource IDs, and safe invalid
payloads for actions that could send email, call paid AI, or alter global data.
"""
import json
import re
import sys
import asyncio
from pathlib import Path
from uuid import uuid4

import httpx
from collections import defaultdict, deque
from sqlalchemy import delete, or_, select

BACKEND_DIR = Path(__file__).resolve().parents[1]
sys.path.insert(0, str(BACKEND_DIR))

from app.core.security import create_access_token, hash_password
from app.db.base import Base, async_session_factory, engine
from app.main import app
from app.models.user import User

UUID_SENTINEL = "00000000-0000-4000-8000-000000000000"


def resolve_schema(schema, components):
    if "$ref" in schema:
        name = schema["$ref"].split("/")[-1]
        return resolve_schema(components.get(name, {}), components)
    if "allOf" in schema:
        result = {}
        for part in schema["allOf"]:
            result.update(resolve_schema(part, components))
        return result
    return schema


def sample_value(name, schema, components, depth=0):
    schema = resolve_schema(schema, components)
    if "enum" in schema:
        return schema["enum"][0]
    if "default" in schema:
        return schema["default"]
    typ = schema.get("type", "string")
    fmt = schema.get("format")
    n = name.lower()
    if typ == "object":
        return sample_object(schema, components, depth + 1)
    if typ == "array":
        return [sample_value(name, schema.get("items", {}), components, depth + 1)]
    if typ == "integer":
        return schema.get("minimum", 1)
    if typ == "number":
        return schema.get("minimum", 1.0)
    if typ == "boolean":
        return True
    if fmt == "email" or "email" in n:
        return "api-audit@example.invalid"
    if "password" in n:
        return "Audit-Test-Password-2026!"
    if "symbol" in n or n in {"ticker", "stock"}:
        return "SYS"
    if "token" in n or "secret" in n:
        return "invalid-audit-token"
    if "name" in n:
        return "API audit fixture"
    if "message" in n or "content" in n or "text" in n:
        return "Local API endpoint audit"
    if "code" in n or "otp" in n:
        return "000000"
    if "id" in n:
        return UUID_SENTINEL
    return "audit"


def sample_object(schema, components, depth=0):
    if depth > 5:
        return {}
    schema = resolve_schema(schema, components)
    props = schema.get("properties", {})
    required = schema.get("required", list(props))
    return {key: sample_value(key, props[key], components, depth + 1)
            for key in required if key in props}


def make_path(path):
    path = re.sub(r"\{[^}]*symbol[^}]*\}", "SYS", path, flags=re.I)
    path = re.sub(r"\{[^}]*name[^}]*\}", "API-audit-fixture", path, flags=re.I)
    path = re.sub(r"\{[^}]*\}", UUID_SENTINEL, path)
    return path


def useful_data(payload):
    if payload is None:
        return False
    if isinstance(payload, str):
        return bool(payload.strip())
    if isinstance(payload, (int, float, bool)):
        return True
    if isinstance(payload, list):
        return bool(payload) and any(useful_data(x) for x in payload)
    if isinstance(payload, dict):
        return any(useful_data(v) for v in payload.values())
    return False


async def purge_fixture(user_id):
    """Delete only the audit user and records reachable through its foreign keys."""
    scopes = defaultdict(list)
    users = Base.metadata.tables["users"]
    seed_scope = select(users.c.id).where(users.c.id == user_id)
    scopes[users].append(seed_scope)
    queue = deque([(users, seed_scope, frozenset({users.name}))])
    while queue:
        parent, parent_keys, path = queue.popleft()
        for child in Base.metadata.tables.values():
            if child.name in path:
                continue
            for fk in child.foreign_keys:
                if fk.column.table is parent:
                    child_pk = list(child.primary_key.columns)[0]
                    child_scope = select(child_pk).where(fk.parent.in_(parent_keys))
                    scopes[child].append(child_scope)
                    queue.append((child, child_scope, path | {child.name}))

    async with async_session_factory() as session:
        async with session.begin():
            for table in reversed(Base.metadata.sorted_tables):
                if table not in scopes:
                    continue
                pk = list(table.primary_key.columns)[0]
                await session.execute(delete(table).where(or_(*(pk.in_(scope) for scope in scopes[table]))))


async def main():
    spec = app.openapi()
    components = spec.get("components", {}).get("schemas", {})
    async with async_session_factory() as session:
        regular = (await session.execute(select(User).where(User.username.like("swagger_audit_%")))).scalars().first()
        if regular is None:
            audit_id = uuid4().hex
            regular = User(id=audit_id, email=f"swagger-audit-{audit_id}@example.invalid",
                           username=f"swagger_audit_{audit_id[:16]}",
                           hashed_password=hash_password("Audit-Only-Password-2026!"),
                           full_name="Temporary Swagger Audit", is_active=True,
                           is_verified=True, is_admin=True)
            session.add(regular)
            await session.commit()
        audit_id = regular.id
    tokens = {regular.id: create_access_token({"sub": regular.id})}
    transport = httpx.ASGITransport(app=app, raise_app_exceptions=False)
    results = []
    async with httpx.AsyncClient(transport=transport, base_url="http://local", timeout=60) as client:
        for path, path_item in spec["paths"].items():
            for method, op in path_item.items():
                if method not in {"get", "post", "put", "patch", "delete"}:
                    continue
                target = make_path(path)
                params = {}
                for p in path_item.get("parameters", []) + op.get("parameters", []):
                    if p.get("in") == "query" and p.get("required"):
                        params[p["name"]] = sample_value(p["name"], p.get("schema", {}), components)
                headers = {"User-Agent": "Basarat-Local-Swagger-Audit/1.0"}
                security = op.get("security", spec.get("security", []))
                if security:
                    headers["Authorization"] = f"Bearer {tokens[regular.id]}"
                kwargs = {"headers": headers, "params": params}
                print(f"[{len(results) + 1}/{sum(1 for pi in spec['paths'].values() for m in pi if m in {'get','post','put','patch','delete'})}] {method.upper()} {path}", flush=True)
                body = op.get("requestBody", {}).get("content", {})
                if body:
                    media, descriptor = next(iter(body.items()))
                    schema = descriptor.get("schema", {})
                    value = sample_object(schema, components)
                    # Avoid triggering non-local or broad side effects; these routes
                    # are still invoked with schema-invalid data to check validation.
                    if (path in {"/api/v1/news/refresh",
                                 "/api/v1/assistant/chat", "/api/v1/assistant/chat/stream"}
                            or path.startswith("/api/v1/auth/") and path.rsplit("/", 1)[-1] in {
                                "signup", "resend-verification", "forgot-password"}):
                        value = {}
                    if "json" in media:
                        kwargs["json"] = value
                    elif "form" in media or "urlencoded" in media:
                        kwargs["data"] = value
                try:
                    response = await asyncio.wait_for(client.request(method.upper(), target, **kwargs), timeout=30)
                    try:
                        payload = response.json()
                    except Exception:
                        payload = response.text
                    success = 200 <= response.status_code < 300
                    quality = "ok" if success and (response.status_code == 204 or useful_data(payload)) else ("empty/null payload" if success else "")
                    results.append({"method": method.upper(), "path": path, "status": response.status_code,
                                    "success": success, "quality": quality,
                                    "snippet": str(payload)[:240] if not success or quality else ""})
                except Exception as exc:
                    results.append({"method": method.upper(), "path": path, "status": 0,
                                    "success": False, "quality": "runtime error",
                                    "snippet": f"{type(exc).__name__}: {exc!r}"[:240]})
    report = {"operation_count": len(results), "success_count": sum(r["success"] for r in results),
              "useful_success_count": sum(r["success"] and r["quality"] == "ok" for r in results),
              "temporary_fixture_user_id": audit_id,
              "failures": [r for r in results if not r["success"] or r["quality"] != "ok"],
              "results": results}
    await purge_fixture(audit_id)
    report["temporary_fixture_cleaned"] = True
    out = BACKEND_DIR / "reports" / "local_swagger_audit_2026-09-30.json"
    out.parent.mkdir(exist_ok=True)
    out.write_text(json.dumps(report, indent=2, default=str), encoding="utf-8")
    print(f"Operations: {report['operation_count']}; HTTP 2xx: {report['success_count']}; useful 2xx payloads: {report['useful_success_count']}")
    print(f"Full report: {out}")
    for item in report["failures"]:
        print(f"{item['status']:>3} {item['method']:<6} {item['path']} [{item['quality']}] {item['snippet'][:160]}")
    await engine.dispose()


if __name__ == "__main__":
    asyncio.run(main())
