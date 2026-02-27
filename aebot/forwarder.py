"""
Forwarding logic for relaying messages from one Telegram chat to another.
"""

from __future__ import annotations

import asyncio
import logging
from typing import Awaitable, Callable

from telethon import TelegramClient, events
from telethon.errors import FloodWaitError, RPCError
from telethon.events.newmessage import NewMessage
from telethon.tl.patched import Message
from telethon.tl import functions

from .config import ForwardingSettings


class ChannelForwarder:
    """
    Subscribe to a source chat and forward each new message to a target chat.
    """

    def __init__(
        self,
        client: TelegramClient,
        settings: ForwardingSettings,
        *,
        on_forward: Callable[[Message], Awaitable[None]] | None = None,
    ) -> None:
        self._client = client
        self._settings = settings
        self._on_forward = on_forward
        self._target_reference = self._coerce_peer_reference(settings.target_chat)

    def register(self) -> None:
        """
        Attach the handler to the Telethon client so it starts forwarding.
        """

        @self._client.on(events.NewMessage(chats=self._settings.source_chat))
        async def _relay(event: NewMessage.Event) -> None:
            await self._handle_event(event)

    async def _handle_event(self, event: NewMessage.Event) -> None:
        """
        Process individual new message events and forward them downstream.
        """

        message = event.message
        if not message:
            return

        # Skip service notifications (user joined, pinned message, etc.).
        if message.action is not None:
            logging.debug("Skipping service message %s", message.id)
            return

        try:
            forwarded_messages = await self._forward_message(message, event)
        except FloodWaitError as wait_error:
            wait_seconds = wait_error.seconds + 1
            logging.warning(
                "Flood wait triggered (%ss). Sleeping before retry.", wait_error.seconds
            )
            await asyncio.sleep(wait_seconds)
            forwarded_messages = await self._retry_forward(message, event)
        except RPCError as rpc_error:
            logging.error(
                "Failed to forward message %s due to RPC error: %s",
                message.id,
                rpc_error,
            )
            return

        if not forwarded_messages:
            return

        await self._post_forward(message, forwarded_messages)

    async def _retry_forward(
        self,
        message: Message,
        event: NewMessage.Event,
    ) -> list[Message]:
        """
        Retry forwarding the message once after a flood wait.
        """

        try:
            return await self._forward_message(message, event)
        except FloodWaitError as wait_error:
            logging.error(
                "Second flood wait encountered for message %s (%ss). Giving up.",
                message.id,
                wait_error.seconds,
            )
        except RPCError as rpc_error:
            logging.error(
                "Retry failed for message %s: %s",
                message.id,
                rpc_error,
            )
        return []

    async def _forward_message(
        self,
        message: Message,
        event: NewMessage.Event,
    ) -> list[Message]:
        """
        Forward a single message, respecting optional topic configuration.
        """

        if self._settings.target_topic_id is None:
            forwarded = await self._client.forward_messages(
                entity=self._target_reference,
                messages=message,
                from_peer=event.chat_id,
            )
            if not forwarded:
                return []
            if isinstance(forwarded, list):
                return [msg for msg in forwarded if msg]
            return [forwarded]

        target_entity = await self._client.get_input_entity(self._target_reference)
        source_entity = await event.get_input_chat()

        request = functions.messages.ForwardMessagesRequest(
            from_peer=source_entity,
            id=[message.id],
            to_peer=target_entity,
            top_msg_id=self._settings.target_topic_id,
        )
        result = await self._client(request)
        forwarded_messages = self._client._get_response_message(request, result, target_entity)
        return [msg for msg in forwarded_messages if msg]

    async def _post_forward(self, original: Message, forwarded_messages: list[Message]) -> None:
        """
        Log forwarding success and trigger optional callback.
        """

        target_descriptor = (
            f"{self._target_reference} (topic {self._settings.target_topic_id})"
            if self._settings.target_topic_id
            else self._target_reference
        )
        logging.info(
            "Forwarded message %s from %s to %s",
            original.id,
            self._settings.source_chat,
            target_descriptor,
        )

        if self._on_forward and forwarded_messages:
            await self._on_forward(forwarded_messages[0])

    @staticmethod
    def _coerce_peer_reference(peer: str | int) -> str | int:
        """
        Convert stringified numeric IDs into integers for Telethon lookups.
        """

        if isinstance(peer, str):
            cleaned = peer.strip()
            if cleaned.startswith("-") and cleaned[1:].isdigit():
                return int(cleaned)
            if cleaned.isdigit():
                return int(cleaned)
            return cleaned
        return peer
