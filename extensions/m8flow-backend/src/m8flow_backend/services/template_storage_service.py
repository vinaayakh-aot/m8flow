# Redirect stub — logic lives in m8flow_core.services.template_storage_service
from m8flow_core.services.template_storage_service import (  # noqa: F401
    FILE_EXT_TO_TYPE,
    file_type_from_filename,
    TemplateStorageService,
    NoopTemplateStorageService,
    FilesystemTemplateStorageService,
)
