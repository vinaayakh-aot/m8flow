"""M8flowEnum — a portable enum base replicating SpiffEnum's .list() helper."""
from __future__ import annotations

import enum


class M8flowEnum(str, enum.Enum):
    """Base enum providing a .list() classmethod for retrieving all values.

    Drop-in replacement for SpiffEnum from spiffworkflow_backend.
    """

    @classmethod
    def list(cls) -> list[str]:
        return [e.value for e in cls]
