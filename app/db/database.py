from sqlalchemy import create_engine, inspect, text
from sqlalchemy.orm import sessionmaker
from app.core.config import settings
from app.db.models import Base

engine = create_engine(
    settings.database_url,
    connect_args=(
        {"check_same_thread": False}
        if settings.database_url.startswith("sqlite")
        else {}
    ),
)
SessionLocal = sessionmaker(bind=engine, autocommit=False, autoflush=False)


def init_db():
    Base.metadata.create_all(engine)
    if engine.dialect.name == "sqlite":
        columns = {c["name"] for c in inspect(engine).get_columns("messages")}
        with engine.begin() as conn:
            if "tool_calls" not in columns:
                conn.execute(text("ALTER TABLE messages ADD COLUMN tool_calls TEXT"))
