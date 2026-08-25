from m8flow_backend.models.native import M8flowTenantInvitationModel

class TenantInvitationStatus:
    PENDING = "PENDING"
    ACCEPTED = "ACCEPTED"
    REVOKED = "REVOKED"
    EXPIRED = "EXPIRED"

__all__ = ["M8flowTenantInvitationModel", "TenantInvitationStatus"]
