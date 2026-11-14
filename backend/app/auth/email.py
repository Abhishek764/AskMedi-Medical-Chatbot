"""Outgoing email. No provider key yet, so dev/test keep messages in an outbox and log them.

Swap in a Resend/Postmark sender later behind the same `EmailSender` protocol.
"""

from __future__ import annotations

import logging
from dataclasses import dataclass, field
from typing import Protocol

logger = logging.getLogger("askmedi.email")


@dataclass
class OutgoingEmail:
    to: str
    subject: str
    body: str


class EmailSender(Protocol):
    async def send(self, email: OutgoingEmail) -> None: ...


@dataclass
class OutboxEmailSender:
    """Keeps sent mail in memory (tests read it) and logs the subject only."""

    outbox: list[OutgoingEmail] = field(default_factory=list)
    echo_body: bool = False  # dev only: prints the link so you can click it locally

    async def send(self, email: OutgoingEmail) -> None:
        self.outbox.append(email)
        logger.info("email queued: %s", email.subject)
        if self.echo_body:
            logger.info("DEV EMAIL BODY: %s", email.body)
