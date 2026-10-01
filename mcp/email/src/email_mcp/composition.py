"""Composition root for the Email MCP process."""

from functools import cached_property

from .application.service import EmailService
from .config import EmailSettings
from .domain.ports import EmailClientFactory
from .infrastructure.client_factory import DefaultEmailClientFactory


class EmailContainer:
    """Build and reuse one Email application graph per MCP process."""

    def __init__(
        self,
        settings: EmailSettings | None = None,
        client_factory: EmailClientFactory | None = None,
    ) -> None:
        self._settings = settings
        self._client_factory = client_factory

    @cached_property
    def settings(self) -> EmailSettings:
        if self._settings is not None:
            return self._settings
        return EmailSettings.from_env()

    @cached_property
    def service(self) -> EmailService:
        return EmailService(
            self.settings,
            factory=self._client_factory or DefaultEmailClientFactory(),
        )
