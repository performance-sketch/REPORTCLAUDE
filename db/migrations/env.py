from __future__ import annotations

import os
import sys
from logging.config import fileConfig
from pathlib import Path

sys.path.insert(0, str(Path(__file__).parent.parent.parent))

from alembic import context
from sqlalchemy import engine_from_config, pool

config = context.config

if config.config_file_name:
    fileConfig(config.config_file_name)

# Sobrescreve a URL com a variável de ambiente (nunca hardcode)
db_url = os.environ.get("DATABASE_SYNC_URL")
if db_url:
    config.set_main_option("sqlalchemy.url", db_url)

from apps.api.app.database import Base
from apps.api.app.models import *  # noqa: F401,F403

target_metadata = Base.metadata


def run_migrations_offline() -> None:
    url = config.get_main_option("sqlalchemy.url")
    context.configure(url=url, target_metadata=target_metadata, literal_binds=True)
    with context.begin_transaction():
        context.run_migrations()


def run_migrations_online() -> None:
    connectable = engine_from_config(
        config.get_section(config.config_ini_section, {}),
        prefix="sqlalchemy.",
        poolclass=pool.NullPool,
    )
    with connectable.connect() as connection:
        context.configure(connection=connection, target_metadata=target_metadata)
        with context.begin_transaction():
            context.run_migrations()


if context.is_offline_mode():
    run_migrations_offline()
else:
    run_migrations_online()
