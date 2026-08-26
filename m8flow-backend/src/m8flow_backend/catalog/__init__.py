from __future__ import annotations

import logging
import os
import subprocess
from pathlib import Path

from typing import Any

from sqlalchemy.orm import Session

from m8flow_backend.errors import ApiError
from m8flow_backend import workflow

LOGGER = logging.getLogger(__name__)

UNSUPPORTED_CONSTRUCTS = (
    "callActivity",
    "messageEventDefinition",
    "correlationKey",
    "correlationProperty",
    "compensateEventDefinition",
    "multiInstanceLoopCharacteristics",
)


def save(session: Session, *, path: str, xml: str, tenant_id: str, user_id: int) -> None:
    _reject_unsupported_constructs(xml)
    workflow.import_definition(
        session,
        tenant_id=tenant_id,
        user_id=user_id,
        bpmn_identifier=path,
        source_bpmn_xml=xml,
        bpmn_name=Path(path).name,
    )
    disk_path = _model_file_path(tenant_id, path)
    disk_path.parent.mkdir(parents=True, exist_ok=True)
    disk_path.write_text(xml, encoding="utf-8")
    _best_effort_git_commit(disk_path, message=f"Save process model {path}")


def is_process_model_identifier(path: str, tenant_id: str | None = None) -> bool:
    from flask import g

    tenant = tenant_id or getattr(g, "m8flow_tenant_id", None) or "default"
    model_dir = _tenant_models_root(tenant) / path
    if not model_dir.is_dir():
        return False
    # list_models keys off any *.bpmn in the directory. Template-created models
    # keep the template BPMN filename (e.g. wfh-approval.bpmn), not {leaf}.bpmn.
    return any(model_dir.glob("*.bpmn"))


def is_process_group_identifier(group: str, tenant_id: str | None = None) -> bool:
    from flask import g

    tenant = tenant_id or getattr(g, "m8flow_tenant_id", None) or "default"
    return (_tenant_models_root(tenant) / group).is_dir()


def delete_process_model(*, tenant_id: str, process_model_identifier: str) -> None:
    """Remove a process model's directory from the tenant's spec dir and
    git-commit the removal. Destructive and non-reversible from the API
    (recoverable only via git history). Callers must have already checked
    permissions and that no process instances reference the model — this only
    touches the on-disk BPMN spec, not the DB.

    Path-traversal guarded: the resolved target must stay inside the tenant's
    own models root, mirroring validate_leaf_file_name's concern for the
    file-level routes.
    """
    import shutil

    root = _tenant_models_root(tenant_id).resolve()
    target = (root / process_model_identifier).resolve()
    if target == root or root not in target.parents:
        raise ApiError("invalid_process_model", "Invalid process model identifier", 400)
    if not target.is_dir():
        raise ApiError("not_found", "Process model not found", 404)

    shutil.rmtree(target)
    # Commit the removal (git rm equivalent) from the tenant root so the
    # deleted paths are staged; best-effort, same posture as save().
    try:
        subprocess.run(["git", "add", "-A", "."], cwd=root, check=False, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", f"Delete process model {process_model_identifier}"],
            cwd=root,
            check=False,
            capture_output=True,
        )
    except OSError:
        # Best-effort git commit of the deletion; the model directory is
        # already removed from disk above regardless of git's exit status.
        LOGGER.debug(
            "Failed to commit process model deletion to git (root=%s, model=%s)",
            root,
            process_model_identifier,
            exc_info=True,
        )


def add_process_model(process_model_info: Any, *, tenant_id: str | None = None) -> None:
    from flask import g

    tenant = tenant_id or getattr(g, "m8flow_tenant_id", None) or "default"
    model_id = process_model_info["id"] if isinstance(process_model_info, dict) else getattr(process_model_info, "id")
    (_tenant_models_root(tenant) / model_id).mkdir(parents=True, exist_ok=True)


def save_process_model(process_model_info: Any, *, tenant_id: str | None = None) -> None:
    add_process_model(process_model_info, tenant_id=tenant_id)


def update_file(process_model_info: Any, file_name: str, content: bytes, *, tenant_id: str | None = None) -> Path:
    from flask import g

    tenant = tenant_id or getattr(g, "m8flow_tenant_id", None) or "default"
    model_id = process_model_info["id"] if isinstance(process_model_info, dict) else getattr(process_model_info, "id")
    path = write_spec_file(tenant_id=tenant, path=model_id, file_name=file_name, content=content)
    if file_name.endswith(".bpmn"):
        from m8flow_backend.db import current_session
        from m8flow_backend.auth import require_current_user

        xml = content.decode("utf-8") if isinstance(content, bytes) else content
        user = require_current_user()
        save(current_session(), path=model_id, xml=xml, tenant_id=tenant, user_id=user.id)
    else:
        # save() (the .bpmn branch above) already git-commits via its own call.
        # Non-bpmn files (e.g. .dmn) previously wrote straight to disk with no
        # commit at all — same audit-trail guarantee for every file type now.
        _best_effort_git_commit(path, message=f"Save {file_name} in {model_id}")
    return path


def validate_leaf_file_name(file_name: str) -> str:
    """A model file name must be a single path segment inside its own model
    directory — reject path traversal / absolute paths / empty names.

    pathlib silently discards the left operand of `/` when the right side is
    absolute (`Path("/a/b") / "/etc/passwd" == Path("/etc/passwd")`), so an
    unvalidated file_name could otherwise escape the tenant's model root.
    Public (not `_`-prefixed): also called from the file-content routes in
    processes_controller.py before either reading or writing.
    """
    if not file_name or file_name in {".", ".."} or "/" in file_name or "\\" in file_name:
        raise ApiError("invalid_file_name", "Invalid file name", 400)
    return file_name


def read_model_file(*, tenant_id: str, process_model_identifier: str, file_name: str) -> bytes | None:
    """Raw bytes of one named file inside an existing process model directory.

    Returns None (not an error) when the file doesn't exist — callers decide
    the 404. Does not check model_exists(); callers that need a distinct
    "model not found" vs "file not found" response should check that first.
    """
    validate_leaf_file_name(file_name)
    path = _tenant_models_root(tenant_id) / process_model_identifier / file_name
    if not path.is_file():
        return None
    return path.read_bytes()


def write_spec_file(*, tenant_id: str, path: str, file_name: str, content: bytes) -> Path:
    target = _tenant_models_root(tenant_id) / path / file_name
    target.parent.mkdir(parents=True, exist_ok=True)
    target.write_bytes(content)
    return target


def list_models(group: str | None = None, *, tenant_id: str) -> list[str]:
    root = _tenant_models_root(tenant_id)
    if not root.exists():
        return []
    search_root = root / group if group else root
    if not search_root.exists():
        return []
    models: list[str] = []
    for bpmn_file in search_root.rglob("*.bpmn"):
        relative = bpmn_file.parent.relative_to(root).as_posix()
        models.append(relative)
    return sorted(set(models))


def read_json_file(path: Path) -> dict[str, Any]:
    if not path.is_file():
        return {}
    try:
        import json

        data = json.loads(path.read_text(encoding="utf-8"))
    except (OSError, ValueError):
        return {}
    return data if isinstance(data, dict) else {}


def process_model_display_name(*, tenant_id: str, process_model_identifier: str) -> str:
    """Prefer process_model.json display_name; fall back to the leaf path segment."""
    meta = read_json_file(_tenant_models_root(tenant_id) / process_model_identifier / "process_model.json")
    display = meta.get("display_name")
    if isinstance(display, str) and display.strip():
        return display.strip()
    return process_model_identifier.rstrip("/").split("/")[-1]


def process_group_id_for_model(process_model_identifier: str) -> str:
    """Parent path of a model id; empty string when the model sits at the tenant root."""
    if "/" not in process_model_identifier:
        return ""
    return process_model_identifier.rsplit("/", 1)[0]


def process_group_display_name(*, tenant_id: str, group_id: str) -> str:
    if not group_id:
        return ""
    meta = read_json_file(_tenant_models_root(tenant_id) / group_id / "process_group.json")
    display = meta.get("display_name")
    if isinstance(display, str) and display.strip():
        return display.strip()
    return group_id.rstrip("/").split("/")[-1]


def list_model_rows(*, tenant_id: str, group: str | None = None) -> list[dict[str, Any]]:
    """Disk-backed model rows for the designer Processes list (no instance stats)."""
    rows: list[dict[str, Any]] = []
    for model_id in list_models(group, tenant_id=tenant_id):
        group_id = process_group_id_for_model(model_id)
        rows.append(
            {
                "id": model_id,
                "display_name": process_model_display_name(
                    tenant_id=tenant_id, process_model_identifier=model_id
                ),
                "group_id": group_id,
                "group_display_name": process_group_display_name(
                    tenant_id=tenant_id, group_id=group_id
                ),
            }
        )
    return rows


def list_group_ids(*, tenant_id: str) -> list[str]:
    """Unique process-group paths: model parents ∪ dirs with process_group.json.

    Skips the empty (tenant-root) group id — root-level models still appear
    under All groups on the models list.
    """
    root = _tenant_models_root(tenant_id)
    ids: set[str] = set()
    for model_id in list_models(tenant_id=tenant_id):
        group_id = process_group_id_for_model(model_id)
        if group_id:
            ids.add(group_id)
    if root.exists():
        for meta_path in root.rglob("process_group.json"):
            rel = meta_path.parent.relative_to(root).as_posix()
            if rel and rel != ".":
                ids.add(rel)
    return sorted(ids)


def list_group_rows(*, tenant_id: str) -> list[dict[str, Any]]:
    """Disk-backed group rows for the designer groups picker (no instance stats)."""
    rows: list[dict[str, Any]] = []
    for group_id in list_group_ids(tenant_id=tenant_id):
        meta = read_json_file(_tenant_models_root(tenant_id) / group_id / "process_group.json")
        description = meta.get("description")
        if not isinstance(description, str):
            description = ""
        else:
            description = description.strip()
        rows.append(
            {
                "id": group_id,
                "display_name": process_group_display_name(tenant_id=tenant_id, group_id=group_id),
                "description": description,
                "model_count": len(list_models(group_id, tenant_id=tenant_id)),
            }
        )
    return rows


def model_exists(*, tenant_id: str, process_model_identifier: str) -> bool:
    return is_process_model_identifier(process_model_identifier, tenant_id=tenant_id)


def process_model_description(*, tenant_id: str, process_model_identifier: str) -> str:
    meta = read_json_file(_tenant_models_root(tenant_id) / process_model_identifier / "process_model.json")
    description = meta.get("description")
    if isinstance(description, str):
        return description.strip()
    return ""


def list_model_files(*, tenant_id: str, process_model_identifier: str) -> list[dict[str, Any]]:
    """Files in the model directory (not recursive). Marks primary via process_model.json."""
    model_dir = _tenant_models_root(tenant_id) / process_model_identifier
    if not model_dir.is_dir():
        return []
    meta = read_json_file(model_dir / "process_model.json")
    primary = meta.get("primary_file_name")
    primary_name = primary.strip() if isinstance(primary, str) else ""
    files: list[dict[str, Any]] = []
    for path in sorted(model_dir.iterdir(), key=lambda p: p.name.lower()):
        if not path.is_file():
            continue
        if path.name in {"process_model.json"}:
            continue
        try:
            stat = path.stat()
        except OSError:
            # File removed/renamed between iterdir() and stat(); skip it
            # rather than fail the whole listing for a benign race.
            LOGGER.debug("Skipping unstat-able file %s while listing process model files", path, exc_info=True)
            continue
        files.append(
            {
                "name": path.name,
                "size_bytes": int(stat.st_size),
                "updated_at_in_seconds": int(stat.st_mtime),
                "primary": bool(primary_name) and path.name == primary_name,
            }
        )
    return files


def get_model_identity(*, tenant_id: str, process_model_identifier: str) -> dict[str, Any] | None:
    """Identity + group + description for one model, or None if missing."""
    if not model_exists(tenant_id=tenant_id, process_model_identifier=process_model_identifier):
        return None
    group_id = process_group_id_for_model(process_model_identifier)
    return {
        "id": process_model_identifier,
        "display_name": process_model_display_name(
            tenant_id=tenant_id, process_model_identifier=process_model_identifier
        ),
        "description": process_model_description(
            tenant_id=tenant_id, process_model_identifier=process_model_identifier
        ),
        "group_id": group_id,
        "group_display_name": process_group_display_name(tenant_id=tenant_id, group_id=group_id),
    }


def _reject_unsupported_constructs(xml: str) -> None:
    lowered = xml
    # Regular subProcess elements are allowed; only event subprocesses are
    # unsupported, detected here via triggeredByEvent="true" rather than via
    # UNSUPPORTED_CONSTRUCTS below.
    if "triggeredByEvent=\"true\"" in xml or "triggeredByEvent='true'" in xml:
        raise ApiError("unsupported_bpmn", "Event subprocess is not supported", 400)
    for construct in UNSUPPORTED_CONSTRUCTS:
        if f"<{construct}" in lowered or f":{construct}" in lowered:
            raise ApiError("unsupported_bpmn", f"Unsupported BPMN construct: {construct}", 400)


def _tenant_models_root(tenant_id: str) -> Path:
    base = os.environ.get("M8FLOW_BACKEND_BPMN_SPEC_ABSOLUTE_DIR") or os.environ.get(
        "SPIFFWORKFLOW_BACKEND_BPMN_SPEC_ABSOLUTE_DIR"
    ) or "/tmp/m8flow-process-models"
    return Path(base) / tenant_id


def _model_file_path(tenant_id: str, path: str) -> Path:
    name = path.rstrip("/").split("/")[-1]
    return _tenant_models_root(tenant_id) / path / f"{name}.bpmn"


def _best_effort_git_commit(file_path: Path, *, message: str) -> None:
    repo = file_path.parent
    try:
        subprocess.run(["git", "add", str(file_path)], cwd=repo, check=False, capture_output=True)
        subprocess.run(
            ["git", "commit", "-m", message],
            cwd=repo,
            check=False,
            capture_output=True,
        )
    except OSError:
        return
