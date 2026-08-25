import pytest

from m8flow_backend.tenancy import clear_tenant_context


@pytest.fixture(autouse=True)
def _reset_tenant_context_between_tests():
    clear_tenant_context()
    yield
    clear_tenant_context()


@pytest.fixture
def db_engine(tmp_path, monkeypatch):
    db_path = tmp_path / "test.db"
    monkeypatch.setenv("M8FLOW_BACKEND_DATABASE_URI", f"sqlite:///{db_path}")
    monkeypatch.setenv("M8FLOW_BACKEND_ENV", "unit_testing")
    monkeypatch.setenv("SPIFFWORKFLOW_BACKEND_ENV", "unit_testing")
    monkeypatch.setenv("FLASK_SESSION_SECRET_KEY", "unit-test-secret-key-32bytes-min")
    monkeypatch.setenv("M8FLOW_CREATE_ALL_SCHEMA", "1")
    from m8flow_backend.db import create_all, get_engine, reset_engine

    reset_engine()
    engine = get_engine()
    create_all(engine)
    yield engine
    reset_engine()


@pytest.fixture
def db_session(db_engine):
    from m8flow_backend.db import get_session_factory

    session = get_session_factory()()
    try:
        yield session
        session.commit()
    finally:
        session.close()


@pytest.fixture
def app(db_engine):
    from m8flow_backend.app import create_app

    application = create_app()
    application.config["TESTING"] = True
    return application


@pytest.fixture
def client(app):
    return app.test_client()
