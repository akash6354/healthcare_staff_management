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
        if get_settings().app_env in ("development", "demo"):  # never in production
            print(
                f"\n--- email to {message.to}: {message.subject}\n{message.body}\n---", flush=True
            )


class SesEmailAdapter:
    """AWS SES v2 in ap-south-1 (decision G1). Credentials come from the instance role, never code."""

    async def send(self, message: EmailMessage) -> None:  # pragma: no cover - needs AWS
        import asyncio

        import boto3

        settings = get_settings()
        client = boto3.client("sesv2", region_name=settings.aws_ses_region)
        await asyncio.to_thread(
            client.send_email,
            FromEmailAddress=settings.email_from,
            Destination={"ToAddresses": [message.to]},
            Content={
                "Simple": {
                    "Subject": {"Data": message.subject, "Charset": "UTF-8"},
                    "Body": {"Text": {"Data": message.body, "Charset": "UTF-8"}},
                }
            },
        )


def email_adapter() -> EmailAdapter:
    provider = get_settings().email_provider
    if provider == "console":
        if get_settings().is_production:
            raise RuntimeError("console email provider is not allowed in production")
        return ConsoleEmailAdapter()
    if provider == "ses":
        return SesEmailAdapter()
    raise RuntimeError(f"unknown EMAIL_PROVIDER {provider}")
