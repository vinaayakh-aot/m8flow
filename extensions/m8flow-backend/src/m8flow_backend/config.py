# Redirect stub — logic lives in m8flow_core.auth.adapters.keycloak_config
from m8flow_core.auth.adapters.keycloak_config import (  # noqa: F401
    DEFAULT_KEYCLOAK_CLIENT_SECRET,
    keycloak_url,
    keycloak_public_issuer_base,
    keycloak_admin_user,
    keycloak_admin_password,
    realm_template_path,
    spoke_keystore_p12_path,
    spoke_keystore_password,
    spoke_client_id,
    spoke_client_secret,
    master_client_secret,
    template_realm_name,
    app_public_base_url,
    redirect_uri_backend_host_and_path,
    redirect_uri_frontend_host,
    nats_token_salt,
)
