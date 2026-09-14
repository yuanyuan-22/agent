import pytest
import sqlalchemy
from sqlalchemy.orm import sessionmaker

import forge.store as st


@pytest.fixture
def db(tmp_path, monkeypatch):
    engine = sqlalchemy.create_engine(
        f"sqlite:///{tmp_path / 'test.db'}",
        connect_args={"check_same_thread": False},
    )
    Session = sessionmaker(bind=engine, autoflush=False, expire_on_commit=False)
    monkeypatch.setattr(st, "engine", engine)
    monkeypatch.setattr(st, "SessionLocal", Session)
    monkeypatch.setattr(st, "_db_path", tmp_path / "test.db")
    st.Base.metadata.create_all(engine)
    return st
