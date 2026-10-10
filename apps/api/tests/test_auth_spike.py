import base64
import hashlib
from urllib.parse import parse_qs, urlsplit

from authlib.integrations.httpx_client import OAuth2Client


def test_authlib_builds_pkce_and_independent_state_without_network():
    verifier = "synthetic-verifier-" + "a" * 48
    with OAuth2Client(
        client_id="synthetic-client",
        redirect_uri="https://example.invalid/callback",
        scope="openid profile",
        code_challenge_method="S256",
    ) as client:
        url, state = client.create_authorization_url(
            "https://example.invalid/authorize", code_verifier=verifier
        )
        _, second_state = client.create_authorization_url(
            "https://example.invalid/authorize", code_verifier=verifier
        )
    query = parse_qs(urlsplit(url).query)
    challenge = (
        base64.urlsafe_b64encode(hashlib.sha256(verifier.encode()).digest()).rstrip(b"=").decode()
    )
    assert state and state != second_state
    assert query["state"] == [state]
    assert query["code_challenge_method"] == ["S256"]
    assert query["code_challenge"] == [challenge]
    assert query["redirect_uri"] == ["https://example.invalid/callback"]
    assert verifier not in url
