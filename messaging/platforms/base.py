"""
Base class for platform adapters.
"""

from abc import ABC, abstractmethod


class BasePlatformAdapter(ABC):
    """Abstract base for messaging platform adapters."""

    def __init__(self, credentials: dict):
        self.credentials = credentials

    @abstractmethod
    def send_message(self, recipient_id: str, message_type: str, content: str) -> tuple[bool, str]:
        """Send a message to a user.

        Returns (success, platform_message_id_or_error)
        """
        pass

    @abstractmethod
    def verify_webhook(self, request) -> bool:
        """Verify webhook signature."""
        pass

    @abstractmethod
    def parse_webhook(self, request) -> list[dict]:
        """Parse webhook payload into normalized message dicts.

        Each dict should have:
        - platform_user_id: str
        - display_name: str (if available)
        - avatar_url: str (if available)
        - message_type: str (text, image, sticker, file, location)
        - content: str
        - metadata: dict
        - platform_message_id: str
        """
        pass
