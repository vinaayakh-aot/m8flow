from __future__ import annotations

from sqlalchemy import JSON, Boolean, Integer, String, Text, UniqueConstraint
from sqlalchemy.orm import Mapped, mapped_column

from m8flow_backend.models.host_base import HostBase


class SecretModel(HostBase):
    __tablename__ = "secret"
    __table_args__ = (UniqueConstraint("m8f_tenant_id", "key", name="uq_host_secret_tenant_key"),)

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    value: Mapped[str] = mapped_column(Text, nullable=False)
    m8f_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class PkceCodeVerifierModel(HostBase):
    __tablename__ = "pkce_code_verifier"

    id: Mapped[int] = mapped_column(primary_key=True)
    state: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    code_verifier: Mapped[str] = mapped_column(String(255), nullable=False)
    m8f_tenant_id: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class RefreshTokenModel(HostBase):
    __tablename__ = "refresh_token"

    id: Mapped[int] = mapped_column(primary_key=True)
    user_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    token: Mapped[str] = mapped_column(Text, nullable=False)
    m8f_tenant_id: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ServiceAccountModel(HostBase):
    __tablename__ = "service_account"

    id: Mapped[int] = mapped_column(primary_key=True)
    client_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    m8f_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TaskDraftDataModel(HostBase):
    __tablename__ = "task_draft_data"
    __table_args__ = (
        UniqueConstraint("process_instance_id", "task_guid", name="uq_host_task_draft"),
    )

    id: Mapped[int] = mapped_column(primary_key=True)
    process_instance_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    task_guid: Mapped[str] = mapped_column(String(255), nullable=False)
    saved_form_data: Mapped[str | None] = mapped_column(Text)
    m8f_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TaskInstructionsForEndUserModel(HostBase):
    __tablename__ = "task_instructions_for_end_user"

    id: Mapped[int] = mapped_column(primary_key=True)
    process_instance_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    instruction: Mapped[str] = mapped_column(Text, nullable=False)
    m8f_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TypeaheadModel(HostBase):
    __tablename__ = "typeahead"

    id: Mapped[int] = mapped_column(primary_key=True)
    category: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    search_term: Mapped[str] = mapped_column(String(255), nullable=False)
    result: Mapped[str] = mapped_column(Text, nullable=False)
    m8f_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class ApiLogModel(HostBase):
    __tablename__ = "api_log"

    id: Mapped[int] = mapped_column(primary_key=True)
    path: Mapped[str] = mapped_column(String(255), nullable=False)
    method: Mapped[str] = mapped_column(String(16), nullable=False)
    m8f_tenant_id: Mapped[str | None] = mapped_column(String(255), index=True)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ConfigurationModel(HostBase):
    __tablename__ = "configuration"

    id: Mapped[int] = mapped_column(primary_key=True)
    key: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    value: Mapped[str] = mapped_column(Text, nullable=False)


class ProcessInstanceFileDataModel(HostBase):
    __tablename__ = "process_instance_file_data"

    id: Mapped[int] = mapped_column(primary_key=True)
    process_instance_id: Mapped[int] = mapped_column(Integer, nullable=False, index=True)
    mimetype: Mapped[str | None] = mapped_column(String(255))
    filename: Mapped[str | None] = mapped_column(String(255))
    contents: Mapped[str | None] = mapped_column(Text)
    m8f_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class TemplateModel(HostBase):
    __tablename__ = "m8flow_templates"

    id: Mapped[int] = mapped_column(primary_key=True)
    template_key: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    version: Mapped[str] = mapped_column(String(50), nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    description: Mapped[str | None] = mapped_column(Text)
    tags: Mapped[list | None] = mapped_column(JSON, nullable=True)
    category: Mapped[str | None] = mapped_column(String(255))
    m8f_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    visibility: Mapped[str] = mapped_column(String(20), nullable=False, default="PRIVATE")
    files: Mapped[list] = mapped_column(JSON, nullable=False, default=list)
    is_published: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    status: Mapped[str | None] = mapped_column(String(50))
    is_deleted: Mapped[bool] = mapped_column(Boolean, default=False, nullable=False)
    created_by: Mapped[str] = mapped_column(String(255), nullable=False)
    modified_by: Mapped[str] = mapped_column(String(255), nullable=False)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
    updated_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class ProcessModelTemplateModel(HostBase):
    __tablename__ = "m8flow_process_model_template"

    id: Mapped[int] = mapped_column(primary_key=True)
    process_model_identifier: Mapped[str] = mapped_column(String(255), nullable=False)
    template_id: Mapped[int] = mapped_column(Integer, nullable=False)
    m8f_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)


class M8flowTenantInvitationModel(HostBase):
    __tablename__ = "m8flow_tenant_invitation"

    id: Mapped[int] = mapped_column(primary_key=True)
    token: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    email: Mapped[str] = mapped_column(String(255), nullable=False)
    tenant_id: Mapped[str] = mapped_column(String(255), nullable=False)
    role: Mapped[str | None] = mapped_column(String(255))
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)


class M8flowNatsApiKeyModel(HostBase):
    __tablename__ = "m8flow_nats_api_key"

    id: Mapped[int] = mapped_column(primary_key=True)
    key_hash: Mapped[str] = mapped_column(String(255), unique=True, nullable=False)
    name: Mapped[str] = mapped_column(String(255), nullable=False)
    m8f_tenant_id: Mapped[str] = mapped_column(String(255), nullable=False, index=True)
    created_at_in_seconds: Mapped[int] = mapped_column(Integer, nullable=False, default=0)
