"""EU-specific configuration for the Narwal Cloud EU build."""

from __future__ import annotations

API_BASE_URL = "https://eu-app.narwaltech.com"
COUNTRY_CODE = "DK"
BROKER_DISCOVERY_COUNTRY = "DK"


def build_login_payload(email: str, password: str) -> dict[str, str]:
    """Build the payload accepted by Narwal's EU login endpoint.

    The payload is transported inside verified HTTPS. The EU endpoint expects
    the password field itself rather than the RSA-wrapped fields used by the
    Korean endpoint in the upstream integration.
    """
    return {"email": email, "password": password}
