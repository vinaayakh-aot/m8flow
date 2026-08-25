from m8flow_backend.models.native import TemplateModel

class TemplateVisibility:
    private = "PRIVATE"
    tenant = "TENANT"
    public = "PUBLIC"

__all__ = ["TemplateModel", "TemplateVisibility"]
