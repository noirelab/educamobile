from alembic import context
from geoalchemy2 import alembic_helpers
from sqlalchemy import create_engine, text

import app.models  # noqa: F401
from app.config import settings
from app.db import Base


def run_migrations_online() -> None:
    engine = create_engine(settings.database_url)
    with engine.connect() as connection:
        connection.execute(text("CREATE EXTENSION IF NOT EXISTS postgis"))
        # A imagem do PostGIS põe os esquemas Tiger no search_path; as tabelas deles não são nossas.
        connection.execute(text("SET search_path TO public"))
        connection.commit()
        context.configure(
            connection=connection,
            target_metadata=Base.metadata,
            include_object=alembic_helpers.include_object,
            process_revision_directives=alembic_helpers.writer,
            render_item=alembic_helpers.render_item,
        )
        with context.begin_transaction():
            context.run_migrations()


run_migrations_online()
