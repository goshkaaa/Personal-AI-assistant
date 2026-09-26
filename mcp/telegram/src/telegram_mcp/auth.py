"""Bearer-token authentication for the HTTP MCP transport."""

from hmac import compare_digest
from pathlib import Path

from mcp.server.auth.provider import AccessToken, TokenVerifier
from mcp.server.auth.settings import AuthSettings
from pydantic import AnyHttpUrl


class StaticTokenVerifier(TokenVerifier):
    """Verify bearer tokens against a private file on every request."""

    def __init__(self, token_file: Path, resource_url: str):
        self.token_file = token_file
        self.resource_url = resource_url

    async def verify_token(self, token: str) -> AccessToken | None:
        try:
            expected = self.token_file.read_text(encoding="utf-8").strip()
        except OSError:
            return None

        if not expected or not compare_digest(token, expected):
            return None

        return AccessToken(
            token=token,
            client_id="codex",
            scopes=["telegram"],
            resource=self.resource_url,
        )


def build_auth_settings(issuer_url: str, resource_url: str) -> AuthSettings:
    return AuthSettings(
        issuer_url=AnyHttpUrl(issuer_url),
        resource_server_url=AnyHttpUrl(resource_url),
        required_scopes=["telegram"],
        validate_token_resource=True,
    )
