"""Email adapter interface (decision 20 / G1). `console` in development, `ses` in production.

The console adapter writes to an in-memory outbox (read by tests and the dev endpoint) and to stdout
only in development. It never writes through the logger, so OTP codes never reach log storage.
"""

from collections import deque
from dataclasses import dataclass
from typing import ClassVar, Protocol

from app.core.config import get_settings


@dataclass(frozen=True)
class EmailMessage:
    to: str
    subject: str
    body: str


class EmailAdapter(Protocol):
    async def send(self, message: EmailMessage) -> None: ...


class ConsoleEmailAdapter:
    outbox: ClassVar[deque[EmailMessage]] = deque(maxlen=50)

    async def send(self, message: EmailMessage) -> None:
        self.outbox.append(message)
        if get_settings().app_env == "development":
            print(
                f"\n--- email to {message.to}: {message.subject}\n{message.body}\n---", flush=True
            )


class SesEmailAdapter:
    async def send(self, message: EmailMessage) -> None:  # pragma: no cover - Phase 6
        raise NotImplementedError("SES adapter is configured at deployment (decision G1)")


def email_adapter() -> EmailAdapter:
    provider = get_settings().email_provider
    if provider == "console":
        if get_settings().is_production:
            raise RuntimeError("console email provider is not allowed in production")
        return ConsoleEmailAdapter()
    if provider == "ses":
        return SesEmailAdapter()
    raise RuntimeError(f"unknown EMAIL_PROVIDER {provider}")
