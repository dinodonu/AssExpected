"""
Core package for the AE Telegram forwarding bot.
"""

from .config import ForwardingSettings, build_client
from .forwarder import ChannelForwarder

__all__ = ["ForwardingSettings", "build_client", "ChannelForwarder"]
