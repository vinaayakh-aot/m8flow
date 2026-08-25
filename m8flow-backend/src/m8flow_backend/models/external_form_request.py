from m8flow_backend.models.native import ExternalFormRequestModel

class ExternalFormRequestStatus:
    pending = "pending"
    notified = "notified"
    submitted = "submitted"
    completed = "completed"
    failed = "failed"
    expired = "expired"


ACTIONABLE_STATUSES = {
    ExternalFormRequestStatus.pending,
    ExternalFormRequestStatus.notified,
}

__all__ = ["ExternalFormRequestModel", "ExternalFormRequestStatus", "ACTIONABLE_STATUSES"]
