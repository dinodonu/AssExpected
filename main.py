from __future__ import annotations

import argparse
import asyncio
import logging
import os
from collections.abc import Callable
from pathlib import Path
from typing import Any

from dotenv import load_dotenv
from telethon.errors import RPCError

load_dotenv(Path(__file__).resolve().parent / ".env")

from aebot import ChannelForwarder, ForwardingSettings, build_client

# Key arguments collected up-front for quick adjustments.
DEFAULT_API_ID = os.getenv("TELEGRAM_API_ID", "")
DEFAULT_API_HASH = os.getenv("TELEGRAM_API_HASH", "")
DEFAULT_SOURCE_CHAT = os.getenv("TELEGRAM_SOURCE_CHAT", "")
DEFAULT_TARGET_CHAT = os.getenv("TELEGRAM_TARGET_CHAT", "")
DEFAULT_TARGET_TOPIC = os.getenv("TELEGRAM_TARGET_TOPIC", "")
DEFAULT_SESSION_FILE = os.getenv("TELEGRAM_SESSION_FILE", os.path.join("aebot", "forwarder.session"))
DEFAULT_PHONE_NUMBER = os.getenv("TELEGRAM_PHONE_NUMBER", "")
DEFAULT_CONNECT_RETRY_DELAY = os.getenv("TELEGRAM_CONNECT_RETRY_DELAY", "5.0")
DEFAULT_LOG_LEVEL = os.getenv("AE_LOG_LEVEL", "INFO")

def _parse_cli_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(
        description="Forward messages from a Telegram channel to a target chat."
    )
    parser.add_argument("--api-id", type=int, default=None, help="Telegram API ID.")
    parser.add_argument("--api-hash", type=str, default=None, help="Telegram API hash.")
    parser.add_argument("--source-chat", type=str, default=None, help="Source chat username or ID.")
    parser.add_argument("--target-chat", type=str, default=None, help="Target chat username or ID.")
    parser.add_argument(
        "--target-topic",
        type=int,
        default=None,
        help="Topic (thread) ID inside the target supergroup.",
    )
    parser.add_argument(
        "--session-file", type=str, default=None, help="Path to the Telethon session file."
    )
    parser.add_argument(
        "--phone-number",
        type=str,
        default=None,
        help="Phone number for the Telegram account (needed when creating a new session).",
    )
    parser.add_argument(
        "--connect-retry-delay",
        type=float,
        default=None,
        help="Seconds to wait before attempting to reconnect after a failure.",
    )
    parser.add_argument(
        "--log-level",
        type=str,
        default=None,
        help="Logging level (e.g. INFO, DEBUG).",
    )
    return parser.parse_args()


def _coerce_int(value: str, field_name: str) -> int:
    value = value.strip()
    if not value:
        return 0
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive branch
        msg = f"Invalid integer for {field_name}: {value}"
        raise ValueError(msg) from exc


def _coerce_float(value: str, field_name: str) -> float:
    value = value.strip()
    if not value:
        return 0.0
    try:
        return float(value)
    except ValueError as exc:  # pragma: no cover - defensive branch
        msg = f"Invalid float for {field_name}: {value}"
        raise ValueError(msg) from exc


def _coerce_optional_int(value: str, field_name: str) -> int | None:
    value = value.strip()
    if not value:
        return None
    try:
        return int(value)
    except ValueError as exc:  # pragma: no cover - defensive branch
        msg = f"Invalid integer for {field_name}: {value}"
        raise ValueError(msg) from exc


def _resolve_argument(
    cli_value: Any,
    default_env_value: str,
    field_name: str,
    *,
    parser: Callable[[str, str], Any],
) -> Any:
    if cli_value is not None:
        return cli_value
    return parser(default_env_value, field_name) if parser else default_env_value


def _build_settings(args: argparse.Namespace) -> ForwardingSettings:
    api_id = _resolve_argument(args.api_id, DEFAULT_API_ID, "api_id", parser=_coerce_int)
    api_hash = args.api_hash or DEFAULT_API_HASH
    source_chat = args.source_chat or DEFAULT_SOURCE_CHAT
    target_chat = args.target_chat or DEFAULT_TARGET_CHAT
    target_topic = (
        args.target_topic
        if args.target_topic is not None
        else _coerce_optional_int(DEFAULT_TARGET_TOPIC, "target_topic_id")
    )
    session_file = args.session_file or DEFAULT_SESSION_FILE
    phone_number = (args.phone_number or DEFAULT_PHONE_NUMBER).strip() or None
    connect_retry_delay = _resolve_argument(
        args.connect_retry_delay,
        DEFAULT_CONNECT_RETRY_DELAY,
        "connect_retry_delay",
        parser=_coerce_float,
    )

    settings = ForwardingSettings(
        api_id=api_id,
        api_hash=api_hash,
        source_chat=source_chat,
        target_chat=target_chat,
        session_file=session_file,
        phone_number=phone_number,
        connect_retry_delay=connect_retry_delay if connect_retry_delay else 5.0,
        target_topic_id=target_topic,
    )
    settings.validate()
    return settings


def _configure_logging(level_name: str) -> None:
    level = getattr(logging, level_name.upper(), logging.INFO)
    logging.basicConfig(
        level=level,
        format="%(asctime)s [%(levelname)s] %(name)s: %(message)s",
    )


async def _run_forwarder(settings: ForwardingSettings) -> None:
    retry_delay = max(settings.connect_retry_delay, 1.0)
    while True:
        try:
            async with build_client(settings) as client:
                await client.start(phone=settings.phone_number)
                forwarder = ChannelForwarder(client, settings)
                forwarder.register()
                target_descriptor = (
                    f"{settings.target_chat} (topic {settings.target_topic_id})"
                    if settings.target_topic_id
                    else settings.target_chat
                )
                logging.info(
                    "Listening on %s and forwarding to %s.",
                    settings.source_chat,
                    target_descriptor,
                )
                await client.run_until_disconnected()
        except (RPCError, ConnectionError) as exc:
            logging.warning(
                "Connection issue detected (%s). Retrying in %.1f seconds.",
                exc,
                retry_delay,
            )
            await asyncio.sleep(retry_delay)
            continue
        break


def main() -> None:
    args = _parse_cli_args()
    log_level = args.log_level or DEFAULT_LOG_LEVEL
    _configure_logging(log_level)

    try:
        settings = _build_settings(args)
    except ValueError as exc:
        logging.error(exc)
        raise SystemExit(1) from exc

    try:
        asyncio.run(_run_forwarder(settings))
    except KeyboardInterrupt:
        logging.info("Forwarder interrupted by user, shutting down.")


if __name__ == "__main__":
    main()
