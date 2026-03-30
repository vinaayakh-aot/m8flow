from __future__ import annotations

import io
import logging
import random
import re
import string
import zipfile
import os
from datetime import datetime, timezone
from typing import Any

from flask import g
from sqlalchemy import or_
from sqlalchemy.exc import IntegrityError

from m8flow_core.db.registry import get_db
from m8flow_core.adapters import get_error_factory
from m8flow_core.models.process_model_template import ProcessModelTemplateModel
from m8flow_core.models.template import TemplateModel, TemplateVisibility
from m8flow_core.services.template_authorization_service import TemplateAuthorizationService
from m8flow_core.services.template_storage_service import (
    FilesystemTemplateStorageService,
    TemplateStorageService,
    file_type_from_filename,
)

logger = logging.getLogger(__name__)

# Zip import safety limits
MAX_ZIP_SIZE = 50 * 1024 * 1024        # 50 MB compressed
MAX_EXTRACTED_SIZE = 200 * 1024 * 1024  # 200 MB total uncompressed
MAX_ZIP_ENTRIES = 100

UNIQUE_TEMPLATE_CONSTRAINT = "uq_template_key_version_tenant"
TENANT_REQUIRED_MESSAGE = "Tenant context required"


def _err(error_code: str, message: str, status_code: int) -> Exception:
    return get_error_factory()(error_code, message, status_code)


class TemplateService:
    """Service for CRUD, versioning, and visibility enforcement for templates."""

    storage: TemplateStorageService = FilesystemTemplateStorageService()

    @staticmethod
    def _version_key(version: str) -> tuple:
        """Return a sortable key for V-prefixed versions like 'V1', 'V2'."""
        v = (version or "").strip()
        if v and v[0] in ("V", "v") and v[1:].isdigit():
            return (1, int(v[1:]))
        return (0, v)

    @classmethod
    def _next_version(cls, template_key: str, tenant_id: str) -> str:
        """Get the next version for a template key within a specific tenant, using V-prefixed versions."""
        rows = TemplateModel.query.filter_by(
            template_key=template_key,
            m8f_tenant_id=tenant_id,
        ).all()

        if not rows:
            return "V1"

        latest = max(rows, key=lambda r: cls._version_key(r.version))
        latest_version = (latest.version or "").strip()

        if latest_version and latest_version[0] in ("V", "v") and latest_version[1:].isdigit():
            return f"V{int(latest_version[1:]) + 1}"

        return "V1"

    @classmethod
    def create_template(
        cls,
        bpmn_bytes: bytes | None,
        metadata: dict[str, Any] | None,
        user: Any | None = None,
        tenant_id: str | None = None,
    ) -> TemplateModel:
        """Create a template with a single BPMN file (backward-compat)."""
        if bpmn_bytes is None:
            raise _err("missing_fields", "bpmn_content is required", 400)
        return cls.create_template_with_files(
            metadata=metadata,
            files=[("diagram.bpmn", bpmn_bytes)],
            user=user,
            tenant_id=tenant_id,
        )

    @classmethod
    def create_template_with_files(
        cls,
        metadata: dict[str, Any],
        files: list[tuple[str, bytes]],
        user: Any | None = None,
        tenant_id: str | None = None,
    ) -> TemplateModel:
        """Create a template with multiple files. At least one must be BPMN."""
        if user is None:
            raise _err("unauthorized", "User must be authenticated to create templates", 403)

        tenant = tenant_id or getattr(g, "m8flow_tenant_id", None)
        if tenant is None:
            raise _err("tenant_required", TENANT_REQUIRED_MESSAGE, 400)

        if not metadata:
            raise _err("missing_fields", "metadata is required", 400)

        template_key = metadata.get("template_key")
        name = metadata.get("name")
        if not template_key or not name:
            raise _err("missing_fields", "template_key and name are required", 400)

        version = metadata.get("version") or cls._next_version(template_key, tenant)
        visibility = metadata.get("visibility", TemplateVisibility.private.value)
        tags = metadata.get("tags")
        category = metadata.get("category")
        description = metadata.get("description")
        status = metadata.get("status", "draft")
        is_published = bool(metadata.get("is_published", False))

        has_bpmn = any(file_type_from_filename(fname) == "bpmn" for fname, _ in files)
        if not has_bpmn:
            raise _err("missing_fields", "At least one BPMN file is required", 400)

        file_entries: list[dict] = []
        for file_name, content in files:
            ft = file_type_from_filename(file_name)
            cls.storage.store_file(tenant, template_key, version, file_name, ft, content)
            file_entries.append({"file_type": ft, "file_name": file_name})

        username = getattr(g, "user", None)
        username_str = username.username if username and hasattr(username, "username") else None
        if username_str is None:
            raise _err("unauthorized", "User username not found in request context", 403)

        db = get_db()
        template = TemplateModel(
            template_key=template_key,
            version=version,
            name=name,
            description=description,
            tags=tags,
            category=category,
            m8f_tenant_id=tenant,
            visibility=visibility,
            files=file_entries,
            is_published=is_published,
            status=status,
            created_by=username_str,
            modified_by=username_str,
        )
        try:
            db.session.add(template)
            TemplateModel.commit_with_rollback_on_exception()
            return template
        except IntegrityError as exc:
            db.session.rollback()
            message = str(getattr(exc, "orig", exc))
            if UNIQUE_TEMPLATE_CONSTRAINT in message:
                raise _err(
                    "template_conflict",
                    "A template with this key and version already exists for this tenant.",
                    409,
                ) from exc
            raise

    @classmethod
    def list_templates(
        cls,
        user: Any | None,
        tenant_id: str | None = None,
        latest_only: bool = True,
        category: str | None = None,
        tag: str | None = None,
        owner: str | None = None,
        visibility: str | None = None,
        search: str | None = None,
        template_key: str | None = None,
        published_only: bool = False,
        sort_by: str | None = None,
        order: str = "desc",
        page: int = 1,
        per_page: int = 10,
    ) -> tuple[list[TemplateModel], dict]:
        query = TemplateModel.query
        query = TemplateAuthorizationService.filter_query_by_visibility(query, user=user)
        query = query.filter(TemplateModel.is_deleted.is_(False))

        tenant = tenant_id or getattr(g, "m8flow_tenant_id", None)
        if tenant:
            query = query.filter(
                or_(
                    TemplateModel.m8f_tenant_id == tenant,
                    TemplateModel.visibility == TemplateVisibility.public.value,
                )
            )

        if category:
            query = query.filter(TemplateModel.category == category)
        if owner:
            query = query.filter(TemplateModel.created_by == owner)
        if visibility:
            query = query.filter(TemplateModel.visibility == visibility)
        if template_key:
            query = query.filter(TemplateModel.template_key == template_key)
        if published_only:
            query = query.filter(TemplateModel.is_published.is_(True))
        if search:
            search_pattern = f"%{search}%"
            query = query.filter(
                or_(
                    TemplateModel.name.ilike(search_pattern),
                    TemplateModel.description.ilike(search_pattern),
                )
            )

        results: list[TemplateModel] = query.all()

        if tag:
            tag_list = [t.strip() for t in tag.split(",") if t.strip()]
            if tag_list:
                filtered = []
                for row in results:
                    if row.tags and isinstance(row.tags, list):
                        if any(t in row.tags for t in tag_list):
                            filtered.append(row)
                    elif row.tags and isinstance(row.tags, str):
                        if any(t in str(row.tags) for t in tag_list):
                            filtered.append(row)
                results = filtered

        if latest_only:
            latest_per_tenant_key: dict[tuple[str, str], TemplateModel] = {}
            for row in results:
                key = (row.m8f_tenant_id or "", row.template_key)
                current = latest_per_tenant_key.get(key)
                if current is None or cls._version_key(row.version) > cls._version_key(current.version):
                    latest_per_tenant_key[key] = row
            results = list(latest_per_tenant_key.values())

        if sort_by in ("created", "name"):
            reverse = order.lower() == "desc"
            if sort_by == "created":
                results = sorted(results, key=lambda r: getattr(r, "created_at_in_seconds", 0) or 0, reverse=reverse)
            else:
                results = sorted(results, key=lambda r: (r.name or "").lower(), reverse=reverse)

        total = len(results)
        per_page = max(1, min(per_page, 100))
        pages = max(1, (total + per_page - 1) // per_page)
        page = max(1, min(page, pages))
        start = (page - 1) * per_page
        items = results[start: start + per_page]
        pagination = {"count": len(items), "total": total, "pages": pages}
        return items, pagination

    @classmethod
    def get_template(
        cls,
        template_key: str,
        version: str | None = None,
        latest: bool = False,
        user: Any | None = None,
        suppress_visibility: bool = False,
        tenant_id: str | None = None,
    ) -> TemplateModel | None:
        query = TemplateModel.query.filter_by(template_key=template_key)

        tenant = tenant_id or getattr(g, "m8flow_tenant_id", None)
        if tenant:
            query = query.filter(TemplateModel.m8f_tenant_id == tenant)

        query = query.filter(TemplateModel.is_deleted.is_(False))

        if not suppress_visibility:
            query = TemplateAuthorizationService.filter_query_by_visibility(query, user=user)

        if version:
            return query.filter_by(version=version).first()

        rows = query.all()
        if not rows:
            return None
        return max(rows, key=lambda r: cls._version_key(r.version))

    @classmethod
    def get_template_by_id(
        cls,
        template_id: int,
        user: Any | None = None,
    ) -> TemplateModel | None:
        template = TemplateModel.query.filter_by(id=template_id).filter(
            TemplateModel.is_deleted.is_(False)
        ).first()
        if template is None:
            return None
        if not TemplateAuthorizationService.can_view(template, user):
            return None
        return template

    @classmethod
    def update_template(
        cls,
        template_key: str,
        version: str,
        updates: dict[str, Any],
        user: Any | None,
    ) -> TemplateModel:
        template = cls.get_template(template_key, version, user=user)
        if template is None:
            raise _err("not_found", "Template version not found", 404)
        if template.is_published:
            raise _err("immutable", "Published template versions cannot be updated", 400)
        if not TemplateAuthorizationService.can_edit(template, user):
            raise _err("forbidden", "You cannot edit this template", 403)

        for field in ["name", "description", "tags", "category", "visibility", "status", "files"]:
            if field in updates:
                setattr(template, field, updates[field])

        username = getattr(g, "user", None)
        template.modified_by = username.username if username and hasattr(username, "username") else template.modified_by
        TemplateModel.commit_with_rollback_on_exception()
        return template

    @classmethod
    def _get_or_create_draft_version(
        cls,
        published_template: TemplateModel,
        user: Any | None = None,
    ) -> TemplateModel:
        tenant = published_template.m8f_tenant_id
        key = published_template.template_key

        existing_draft = (
            TemplateModel.query
            .filter_by(template_key=key, m8f_tenant_id=tenant, is_published=False, is_deleted=False)
            .order_by(TemplateModel.id.desc())
            .first()
        )
        if existing_draft:
            return existing_draft

        username = getattr(g, "user", None)
        username_str = username.username if username and hasattr(username, "username") else "unknown"
        next_version = cls._next_version(key, tenant)

        new_files: list[dict] = []
        for entry in (published_template.files or []):
            fname = entry.get("file_name")
            if not fname:
                continue
            try:
                content = cls.storage.get_file(tenant, key, published_template.version, fname)
                ft = entry.get("file_type", file_type_from_filename(fname))
                cls.storage.store_file(tenant, key, next_version, fname, ft, content)
                new_files.append({"file_type": ft, "file_name": fname})
            except Exception as e:
                logger.warning("Failed to copy file %s for new version %s: %s", fname, next_version, e)

        if not new_files:
            raise _err("storage_error", "Failed to copy any files for the new template version", 500)

        db = get_db()
        new_template = TemplateModel(
            template_key=key,
            version=next_version,
            name=published_template.name,
            description=published_template.description,
            tags=published_template.tags,
            category=published_template.category,
            m8f_tenant_id=tenant,
            visibility=published_template.visibility,
            files=new_files,
            is_published=False,
            status="draft",
            created_by=username_str,
            modified_by=username_str,
        )

        db.session.add(new_template)
        TemplateModel.commit_with_rollback_on_exception()
        return new_template

    @classmethod
    def update_template_by_id(
        cls,
        template_id: int,
        updates: dict[str, Any],
        bpmn_bytes: bytes | None = None,
        bpmn_file_name: str | None = None,
        user: Any | None = None,
    ) -> TemplateModel:
        existing_template = cls.get_template_by_id(template_id, user=user)
        if existing_template is None:
            raise _err("not_found", "Template not found", 404)
        if not TemplateAuthorizationService.can_edit(existing_template, user):
            raise _err("forbidden", "You cannot edit this template", 403)

        username = getattr(g, "user", None)
        username_str = username.username if username and hasattr(username, "username") else None
        if username_str is None:
            raise _err("unauthorized", "User username not found in request context", 403)

        tenant = existing_template.m8f_tenant_id
        key = existing_template.template_key
        version = existing_template.version
        files_list = list(existing_template.files or [])

        if bpmn_bytes is not None:
            bpmn_name = bpmn_file_name or "diagram.bpmn"
            ft = "bpmn"
            if not existing_template.is_published:
                if bpmn_file_name:
                    cls.storage.store_file(tenant, key, version, bpmn_file_name, ft, bpmn_bytes)
                    if not any(e.get("file_name") == bpmn_file_name for e in files_list):
                        files_list.append({"file_type": ft, "file_name": bpmn_file_name})
                else:
                    for entry in files_list:
                        if entry.get("file_type") == "bpmn":
                            bpmn_name = entry.get("file_name", bpmn_name)
                            cls.storage.store_file(tenant, key, version, bpmn_name, ft, bpmn_bytes)
                            break
                    else:
                        cls.storage.store_file(tenant, key, version, bpmn_name, ft, bpmn_bytes)
                        files_list.append({"file_type": ft, "file_name": bpmn_name})

        allowed_fields = ["name", "description", "tags", "category", "visibility", "status"]

        if not existing_template.is_published:
            if updates.get("is_published") is True:
                existing_template.is_published = True
                existing_template.status = "published"
            for field in allowed_fields:
                if field in updates:
                    setattr(existing_template, field, updates[field])
            if files_list:
                existing_template.files = files_list
            existing_template.modified_by = username_str
            TemplateModel.commit_with_rollback_on_exception()
            return existing_template

        target_template = cls._get_or_create_draft_version(existing_template, user)

        if bpmn_bytes is not None:
            bpmn_name = bpmn_file_name or "diagram.bpmn"
            ft = "bpmn"
            target_files = list(target_template.files or [])
            if bpmn_file_name:
                cls.storage.store_file(
                    target_template.m8f_tenant_id, target_template.template_key,
                    target_template.version, bpmn_file_name, ft, bpmn_bytes,
                )
                if not any(e.get("file_name") == bpmn_file_name for e in target_files):
                    target_files.append({"file_type": ft, "file_name": bpmn_file_name})
                    target_template.files = target_files
            else:
                replaced = False
                for entry in target_files:
                    if entry.get("file_type") == "bpmn":
                        bpmn_name = entry.get("file_name", bpmn_name)
                        cls.storage.store_file(
                            target_template.m8f_tenant_id, target_template.template_key,
                            target_template.version, bpmn_name, ft, bpmn_bytes,
                        )
                        replaced = True
                        break
                if not replaced:
                    cls.storage.store_file(
                        target_template.m8f_tenant_id, target_template.template_key,
                        target_template.version, bpmn_name, ft, bpmn_bytes,
                    )
                    target_files.append({"file_type": ft, "file_name": bpmn_name})
                    target_template.files = target_files

        for field in allowed_fields:
            if field == "status":
                continue
            if field in updates:
                setattr(target_template, field, updates[field])

        db = get_db()
        try:
            target_template.modified_by = username_str
            TemplateModel.commit_with_rollback_on_exception()
        except IntegrityError:
            db.session.rollback()
            raise _err(
                "template_conflict",
                "A template with this key and version already exists for this tenant.",
                409,
            )
        return target_template

    @classmethod
    def delete_template_by_id(cls, template_id: int, user: Any | None) -> None:
        """Soft delete template by ID (mark as deleted without removing row)."""
        template = cls.get_template_by_id(template_id, user=user)
        if template is None:
            raise _err("not_found", "Template not found", 404)
        if template.is_published:
            raise _err("immutable", "Published template versions cannot be deleted", 400)
        if not TemplateAuthorizationService.can_edit(template, user):
            raise _err("forbidden", "You cannot delete this template", 403)

        template.is_deleted = True
        TemplateModel.commit_with_rollback_on_exception()

    @classmethod
    def get_file_content(cls, template: TemplateModel, file_name: str) -> bytes:
        return cls.storage.get_file(
            template.m8f_tenant_id,
            template.template_key,
            template.version,
            file_name,
        )

    @classmethod
    def get_first_bpmn_content(cls, template: TemplateModel) -> bytes | None:
        for entry in template.files or []:
            if entry.get("file_type") == "bpmn":
                fname = entry.get("file_name")
                if fname:
                    try:
                        return cls.get_file_content(template, fname)
                    except Exception:
                        continue
        return None

    @classmethod
    def update_file_content(
        cls,
        template: TemplateModel,
        file_name: str,
        content: bytes,
        user: Any | None = None,
    ) -> TemplateModel:
        found = None
        for e in template.files or []:
            if e.get("file_name") == file_name:
                found = e
                break

        if not found:
            raise _err("not_found", f"File not found: {file_name}", 404)

        if not template.is_published:
            ft = found.get("file_type") or file_type_from_filename(file_name)
            cls.storage.store_file(
                template.m8f_tenant_id, template.template_key, template.version, file_name, ft, content,
            )
            return template

        target_template = cls._get_or_create_draft_version(template, user)
        ft = found.get("file_type") or file_type_from_filename(file_name)
        cls.storage.store_file(
            target_template.m8f_tenant_id, target_template.template_key,
            target_template.version, file_name, ft, content,
        )
        return target_template

    @classmethod
    def delete_file_from_template(
        cls,
        template: TemplateModel,
        file_name: str,
        user: Any | None = None,
    ) -> TemplateModel:
        files_list = list(template.files or [])
        if not files_list:
            raise _err("not_found", "Template has no files", 404)

        if not any(e.get("file_name") == file_name for e in files_list):
            raise _err("not_found", f"File not found: {file_name}", 404)

        remaining = [e for e in files_list if e.get("file_name") != file_name]
        if not remaining:
            raise _err("forbidden", "Cannot delete the last file from a template", 403)
        if not any(e.get("file_type") == "bpmn" for e in remaining):
            raise _err("forbidden", "Template must have at least one BPMN file", 403)

        if template.is_published:
            target_template = cls._get_or_create_draft_version(template, user)
            target_files = list(target_template.files or [])
            remaining = [e for e in target_files if e.get("file_name") != file_name]
        else:
            target_template = template

        target_template.files = remaining
        if user and hasattr(user, "username"):
            target_template.modified_by = user.username
        TemplateModel.commit_with_rollback_on_exception()

        try:
            cls.storage.delete_file(
                target_template.m8f_tenant_id,
                target_template.template_key,
                target_template.version,
                file_name,
            )
        except Exception:
            pass

        return target_template

    @classmethod
    def export_template_zip(cls, template_id: int, user: Any | None = None) -> tuple[bytes, str]:
        template = cls.get_template_by_id(template_id, user=user)
        if template is None:
            raise _err("not_found", "Template not found", 404)
        entries = template.files or []
        if not entries:
            raise _err("not_found", "Template has no files to export", 404)
        zip_bytes = cls.storage.stream_zip(
            template.m8f_tenant_id, template.template_key, template.version, entries,
        )
        filename = f"template-{template.template_key}-{template.version}.zip"
        return zip_bytes, filename

    @classmethod
    def import_template_from_zip(
        cls,
        zip_bytes: bytes,
        metadata: dict[str, Any],
        user: Any | None = None,
        tenant_id: str | None = None,
    ) -> TemplateModel:
        if user is None:
            raise _err("unauthorized", "User must be authenticated", 403)
        tenant = tenant_id or getattr(g, "m8flow_tenant_id", None)
        if tenant is None:
            raise _err("tenant_required", TENANT_REQUIRED_MESSAGE, 400)
        template_key = metadata.get("template_key")
        name = metadata.get("name")
        if not template_key or not name:
            raise _err("missing_fields", "template_key and name are required", 400)

        if len(zip_bytes) > MAX_ZIP_SIZE:
            raise _err(
                "payload_too_large",
                f"Zip file exceeds maximum allowed size of {MAX_ZIP_SIZE // (1024 * 1024)} MB",
                400,
            )

        version = metadata.get("version") or cls._next_version(template_key, tenant)
        files_to_add: list[tuple[str, bytes]] = []
        has_bpmn = False
        total_extracted = 0
        try:
            with zipfile.ZipFile(io.BytesIO(zip_bytes), "r") as zf:
                entries = [n for n in zf.namelist() if not n.endswith("/")]
                if len(entries) > MAX_ZIP_ENTRIES:
                    raise _err(
                        "payload_too_large",
                        f"Zip contains too many entries (max {MAX_ZIP_ENTRIES})",
                        400,
                    )
                for name_in_zip in entries:
                    base_name = os.path.basename(name_in_zip)
                    if not base_name or base_name.startswith("."):
                        continue
                    content = zf.read(name_in_zip)
                    total_extracted += len(content)
                    if total_extracted > MAX_EXTRACTED_SIZE:
                        raise _err(
                            "payload_too_large",
                            f"Extracted content exceeds maximum allowed size of {MAX_EXTRACTED_SIZE // (1024 * 1024)} MB",
                            400,
                        )
                    ft = file_type_from_filename(base_name)
                    if ft == "bpmn":
                        has_bpmn = True
                    files_to_add.append((base_name, content))
        except zipfile.BadZipFile as e:
            raise _err("invalid_content", f"Invalid zip file: {e}", 400)

        if not has_bpmn:
            raise _err("missing_fields", "Zip must contain at least one .bpmn file", 400)

        metadata["version"] = version
        return cls.create_template_with_files(
            metadata=metadata,
            files=files_to_add,
            user=user,
            tenant_id=tenant,
        )

    @classmethod
    def get_process_model_template_info(
        cls,
        process_model_identifier: str,
        tenant_id: str | None = None,
    ):
        """Get the template provenance info for a process model."""
        from m8flow_core.models.process_model_template import ProcessModelTemplateModel
        tenant = tenant_id or getattr(g, "m8flow_tenant_id", None)
        query = ProcessModelTemplateModel.query.filter_by(
            process_model_identifier=process_model_identifier
        )
        if tenant:
            query = query.filter_by(m8f_tenant_id=tenant)
        return query.first()

    @classmethod
    def _transform_bpmn_content(
        cls,
        content: bytes,
        process_model_id: str,
        decision_id_map: dict[str, str] | None = None,
    ) -> tuple[bytes, str | None]:
        """Transform BPMN content by replacing process IDs with unique ones."""
        try:
            content_str = content.decode("utf-8")
        except UnicodeDecodeError:
            return content, None

        fuzz = "".join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for _ in range(7))
        underscored_id = process_model_id.replace("-", "_")
        process_id_pattern = re.compile(r'(<bpmn:process[^>]*\s+id=")([^"]+)(")')  # NOSONAR

        new_primary_process_id = None
        process_counter = 0
        process_id_map: dict[str, str] = {}

        def replace_process_id(match: re.Match) -> str:
            nonlocal new_primary_process_id, process_counter
            prefix = match.group(1)
            old_id = match.group(2)
            suffix = match.group(3)
            if process_counter == 0:
                new_id = f"Process_{underscored_id}_{fuzz}"
            else:
                new_id = f"Process_{underscored_id}_{fuzz}_{process_counter}"
            process_counter += 1
            process_id_map[old_id] = new_id
            if new_primary_process_id is None:
                new_primary_process_id = new_id
            return f"{prefix}{new_id}{suffix}"

        content_str = process_id_pattern.sub(replace_process_id, content_str)

        for old_id, new_id in process_id_map.items():
            content_str = content_str.replace(f'processRef="{old_id}"', f'processRef="{new_id}"')

        if decision_id_map:
            for old_id, new_id in decision_id_map.items():
                content_str = content_str.replace(
                    f"<spiffworkflow:calledDecisionId>{old_id}</spiffworkflow:calledDecisionId>",
                    f"<spiffworkflow:calledDecisionId>{new_id}</spiffworkflow:calledDecisionId>",
                )

        return content_str.encode("utf-8"), new_primary_process_id

    @classmethod
    def _transform_dmn_content(
        cls,
        content: bytes,
        process_model_id: str,
    ) -> tuple[bytes, dict[str, str]]:
        """Transform DMN content by replacing decision IDs with unique ones."""
        decision_id_map: dict[str, str] = {}
        try:
            content_str = content.decode("utf-8")
        except UnicodeDecodeError:
            return content, decision_id_map

        fuzz = "".join(random.SystemRandom().choice(string.ascii_lowercase + string.digits) for _ in range(7))
        underscored_id = process_model_id.replace("-", "_")
        decision_id_pattern = re.compile(r'(<decision\s[^>]*id=")([^"]+)(")')  # NOSONAR
        decision_counter = 0

        def replace_decision_id(match: re.Match) -> str:
            nonlocal decision_counter
            prefix = match.group(1)
            old_id = match.group(2)
            suffix = match.group(3)
            if decision_counter == 0:
                new_id = f"Decision_{underscored_id}_{fuzz}"
            else:
                new_id = f"Decision_{underscored_id}_{fuzz}_{decision_counter}"
            decision_counter += 1
            decision_id_map[old_id] = new_id
            return f"{prefix}{new_id}{suffix}"

        content_str = decision_id_pattern.sub(replace_decision_id, content_str)

        for old_id, new_id in decision_id_map.items():
            content_str = content_str.replace(f'dmnElementRef="{old_id}"', f'dmnElementRef="{new_id}"')

        return content_str.encode("utf-8"), decision_id_map
