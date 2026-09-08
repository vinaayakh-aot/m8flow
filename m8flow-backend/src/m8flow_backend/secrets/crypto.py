"""Host-owned at-rest encryption for the database secret provider.

Fernet key is HKDF-derived from ``M8FLOW_SECRETS_ENCRYPTION_KEY``, falling back
to ``FLASK_SESSION_SECRET_KEY``. Ciphertext is stored; plaintext is never the
on-disk form for new writes. Legacy plaintext rows (pre-encryption) still
decrypt as themselves so existing test fixtures keep working — but Fernet-shaped
tokens that fail decryption raise rather than returning ciphertext as plaintext.
"""

from __future__ import annotations

import base64
import os
import re

from cryptography.fernet import Fernet, InvalidToken
from cryptography.hazmat.primitives import hashes
from cryptography.hazmat.primitives.kdf.hkdf import HKDF

_SALT = b"m8flow-secrets-v1"
_INFO = b"secret-at-rest"
# Fernet tokens are urlsafe-base64 and commonly start with the version/timestamp
# prefix produced by cryptography (gAAAAA…). Used only to distinguish legacy
# plaintext rows from failed decrypts of real ciphertext.
_FERNET_SHAPED = re.compile(r"^gAAAAA[A-Za-z0-9_-]+={0,2}$")


class SecretsEncryptionError(RuntimeError):
    """Raised when secret crypto cannot run safely."""


def _key_material() -> str:
    material = os.environ.get("M8FLOW_SECRETS_ENCRYPTION_KEY") or os.environ.get(
        "FLASK_SESSION_SECRET_KEY"
    )
    if not material:
        raise SecretsEncryptionError(
            "M8FLOW_SECRETS_ENCRYPTION_KEY or FLASK_SESSION_SECRET_KEY must be set "
            "for secret encryption."
        )
    return material


def _fernet() -> Fernet:
    material = _key_material().encode("utf-8")
    derived = HKDF(algorithm=hashes.SHA256(), length=32, salt=_SALT, info=_INFO).derive(material)
    return Fernet(base64.urlsafe_b64encode(derived))


def encrypt_secret_value(value: str) -> str:
    return _fernet().encrypt(value.encode("utf-8")).decode("ascii")


def decrypt_secret_value(stored: str) -> str:
    try:
        return _fernet().decrypt(stored.encode("ascii")).decode("utf-8")
    except (InvalidToken, ValueError, SecretsEncryptionError):
        # Legacy plaintext rows are not Fernet-shaped; return as-is.
        # Fernet-shaped values that fail must not be returned as "plaintext".
        if _FERNET_SHAPED.fullmatch(stored.strip()):
            raise SecretsEncryptionError("Unable to decrypt secret value.") from None
        return stored
