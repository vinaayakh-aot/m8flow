from __future__ import annotations

import importlib.util
from pathlib import Path
from types import SimpleNamespace

from alembic.migration import MigrationContext
from alembic.operations import Operations
import sqlalchemy as sa


MIGRATION_PATH = (
    Path(__file__).resolve().parents[3]
    / "migrations"
    / "versions"
    / "s3d4e5f6a7b8_enable_rls_on_scheduler_job.py"
)


def _load_migration_module():
    spec = importlib.util.spec_from_file_location("scheduler_job_rls_migration", MIGRATION_PATH)
    assert spec is not None
    assert spec.loader is not None
    module = importlib.util.module_from_spec(spec)
    spec.loader.exec_module(module)
    return module


def _bind_operations(module, connection: sa.Connection) -> None:
    context = MigrationContext.configure(connection)
    module.op = Operations(context)


def _sql_text(stmt) -> str:
    return getattr(stmt, "text", str(stmt))


class _FakeInspector:
    def __init__(self, tables: list[str], columns: list[str]) -> None:
        self._tables = tables
        self._columns = columns

    def get_table_names(self) -> list[str]:
        return list(self._tables)

    def get_columns(self, _table: str) -> list[dict[str, str]]:
        return [{"name": name} for name in self._columns]


class _RecordingOp:
    def __init__(self, dialect_name: str, inspector: _FakeInspector) -> None:
        self.statements: list[str] = []
        self._bind = SimpleNamespace(dialect=SimpleNamespace(name=dialect_name))
        self._inspector = inspector

    def get_bind(self):
        return self._bind

    def execute(self, stmt) -> None:
        self.statements.append(_sql_text(stmt))


def test_upgrade_is_noop_on_sqlite(tmp_path):
    module = _load_migration_module()
    engine = sa.create_engine(f"sqlite:///{tmp_path / 'rls.db'}")
    with engine.begin() as connection:
        connection.execute(
            sa.text(
                "CREATE TABLE scheduler_job ("
                "id INTEGER PRIMARY KEY, "
                "m8f_tenant_id VARCHAR(255) NOT NULL"
                ")"
            )
        )
        _bind_operations(module, connection)
        module.upgrade()
        module.downgrade()
        assert "scheduler_job" in sa.inspect(connection).get_table_names()


def test_upgrade_skips_when_scheduler_job_is_missing(monkeypatch):
    module = _load_migration_module()
    recorder = _RecordingOp("postgresql", _FakeInspector([], []))
    monkeypatch.setattr(module, "op", recorder)
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: recorder._inspector)

    module.upgrade()
    module.downgrade()
    assert recorder.statements == []


def test_upgrade_applies_tenant_and_bypass_policies_on_postgres(monkeypatch):
    module = _load_migration_module()
    recorder = _RecordingOp(
        "postgresql",
        _FakeInspector(["scheduler_job"], ["id", "m8f_tenant_id"]),
    )
    monkeypatch.setattr(module, "op", recorder)
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: recorder._inspector)

    module.upgrade()

    joined = "\n".join(recorder.statements)
    assert "ALTER TABLE scheduler_job ENABLE ROW LEVEL SECURITY" in joined
    assert "CREATE POLICY scheduler_job_tenant_isolation ON scheduler_job" in joined
    assert "FOR ALL USING (m8f_tenant_id = current_setting('app.current_tenant', true))" in joined
    assert "WITH CHECK (m8f_tenant_id = current_setting('app.current_tenant', true))" in joined
    assert "CREATE POLICY scheduler_job_super_admin_select ON scheduler_job" in joined
    assert "FOR SELECT USING (current_setting('app.bypass_rls', true) = 'on')" in joined


def test_downgrade_drops_policies_and_disables_rls_on_postgres(monkeypatch):
    module = _load_migration_module()
    recorder = _RecordingOp(
        "postgresql",
        _FakeInspector(["scheduler_job"], ["id", "m8f_tenant_id"]),
    )
    monkeypatch.setattr(module, "op", recorder)
    monkeypatch.setattr(module.sa, "inspect", lambda _bind: recorder._inspector)

    module.downgrade()

    assert recorder.statements == [
        "DROP POLICY IF EXISTS scheduler_job_super_admin_select ON scheduler_job",
        "DROP POLICY IF EXISTS scheduler_job_tenant_isolation ON scheduler_job",
        "ALTER TABLE scheduler_job DISABLE ROW LEVEL SECURITY",
    ]
