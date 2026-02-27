"""
Configuration helpers for the Telegram channel forwarder.
"""

from __future__ import annotations

from dataclasses import dataclass

from telethon import TelegramClient


@dataclass(slots=True)
class ForwardingSettings:
    """
    Container for the minimal configuration required to bind to Telegram and
    forward messages between chats.
    """

    api_id: int
    api_hash: str
    source_chat: str
    target_chat: str
    session_file: str = "aebot/forwarder.session"
    phone_number: str | None = None
    connect_retry_delay: float = 5.0
    target_topic_id: int | None = None

    def validate(self) -> None:
        """
        Ensure the basic credentials are present before attempting to connect.
        """
        missing = []
        if not self.api_id:
            missing.append("api_id")
        if not self.api_hash:
            missing.append("api_hash")
        if not self.source_chat:
            missing.append("source_chat")
        if not self.target_chat:
            missing.append("target_chat")
        if missing:
            missing_args = ", ".join(missing)
            msg = f"ForwardingSettings missing required field(s): {missing_args}"
            raise ValueError(msg)

        if self.target_topic_id is not None and self.target_topic_id <= 0:
            msg = "ForwardingSettings target_topic_id must be a positive integer when provided"
            raise ValueError(msg)


def build_client(settings: ForwardingSettings) -> TelegramClient:
    """
    Create a Telegram client for the current session.
    """

    return TelegramClient(settings.session_file, settings.api_id, settings.api_hash)
