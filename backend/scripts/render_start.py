"""Safely bootstrap/upgrade Supabase before starting the Render API process.

The historical Alembic chain assumes a legacy schema. Fresh databases are
created from current ORM metadata and stamped as a baseline. An existing
unversioned database is adopted only after all mapped tables/columns exist;
unknown drift fails closed instead of silently skipping schema changes.
"""

from __future__ import annotations

import os
import sys
from pathlib import Path

from alembic import command
from alembic.config import Config
from sqlalchemy import create_engine, inspect

ROOT = Path(__file__).resolve().parents[1]
os.chdir(ROOT)
sys.path.insert(0, str(ROOT))

from app.core.config import get_settings  # noqa: E402
from app.core.database_urls import sync_database_url  # noqa: E402
from app.db.base import Base  # noqa: E402
from app import models  # noqa: E402,F401
from scripts.prepare_render_assets import prepare_features  # noqa: E402


def _alembic_config() -> Config:
    cfg = Config(str(ROOT / "alembic.ini"))
    settings = get_settings()
    url = sync_database_url(settings.DATABASE_URL, settings.DATABASE_URL_SYNC)
    cfg.set_main_option("sqlalchemy.url", url.render_as_string(hide_password=False).replace("%", "%%"))
    return cfg


def _bootstrap_unversioned_database(cfg: Config) -> None:
    settings = get_settings()
    engine = create_engine(
        sync_database_url(settings.DATABASE_URL, settings.DATABASE_URL_SYNC),
        pool_pre_ping=True,
        pool_size=1,
        max_overflow=0,
    )
    try:
        inspector = inspect(engine)
        existing_tables = set(inspector.get_table_names())
        if "alembic_version" in existing_tables:
            return

        expected_tables = set(Base.metadata.tables)
        existing_app_tables = existing_tables & expected_tables
        if not existing_app_tables:
            # The historical first revision is not a blank-database migration.
            Base.metadata.create_all(engine)
        else:
            missing_tables = expected_tables - existing_tables
            missing_columns = {}
            for table_name, table in Base.metadata.tables.items():
                if table_name not in existing_tables:
                    continue
                actual = {column["name"] for column in inspector.get_columns(table_name)}
                missing = sorted(column.name for column in table.columns if column.name not in actual)
                if missing:
                    missing_columns[table_name] = missing
            if missing_tables or missing_columns:
                raise RuntimeError(
                    "Refusing to baseline an unversioned database with schema drift. "
                    f"Missing tables: {sorted(missing_tables)}; missing columns: {missing_columns}. "
                    "Back up Supabase and reconcile the existing schema before deploying."
                )
            # Add only absent tables/indexes after existing table columns pass.
            Base.metadata.create_all(engine)

        command.stamp(cfg, "head")
    finally:
        engine.dispose()


def main() -> None:
    prepare_features()
    cfg = _alembic_config()
    _bootstrap_unversioned_database(cfg)
    command.upgrade(cfg, "head")
    port = os.environ.get("PORT", "10000")
    os.execv(
        sys.executable,
        [sys.executable, "-m", "uvicorn", "app.main:app", "--host", "0.0.0.0", "--port", port],
    )


if __name__ == "__main__":
    main()
