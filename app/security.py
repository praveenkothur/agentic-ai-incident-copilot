
import hashlib
import hmac
import json
import os
import secrets
from typing import Any


# Use a configured secret when available.
# Otherwise generate an ephemeral key for the local research lab.
_configured_secret = os.getenv("ACTION_HMAC_SECRET")

_HMAC_KEY = (
    _configured_secret.encode("utf-8")
    if _configured_secret
    else secrets.token_bytes(32)
)


def action_digest(incident_id: str, action: Any) -> str:
    """
    Generate an HMAC-SHA256 digest binding an incident ID
    to its exact proposed remediation action.
    """

    canonical_payload = json.dumps(
        {
            "incident_id": incident_id,
            "action": action,
        },
        sort_keys=True,
        separators=(",", ":"),
        ensure_ascii=False,
    )

    return hmac.new(
        _HMAC_KEY,
        canonical_payload.encode("utf-8"),
        hashlib.sha256,
    ).hexdigest()


def verify_action_digest(
    incident_id: str,
    action: Any,
    expected_digest: str,
) -> bool:
    """
    Verify the incident and proposed action against
    the originally generated HMAC digest.
    """

    if not expected_digest:
        return False

    actual_digest = action_digest(incident_id, action)

    return hmac.compare_digest(
        actual_digest,
        expected_digest,
    )
