"""
Core messaging service - handles sending/receiving messages across platforms.
"""

import json
from messaging_db import (
    find_or_create_contact, find_or_create_conversation,
    add_message, get_channel, get_conversation,
    update_conversation, mark_messages_read,
)
from messaging.services.channel_service import load_credentials
from messaging.platforms.line_adapter import LineAdapter
from messaging.platforms.facebook_adapter import FacebookAdapter
from messaging.platforms.instagram_adapter import InstagramAdapter


PLATFORM_ADAPTERS = {
    "line": LineAdapter,
    "facebook": FacebookAdapter,
    "instagram": InstagramAdapter,
}


def handle_incoming_message(channel_id, platform_user_id, content, message_type="text",
                             display_name="", avatar_url="", metadata=None, platform_message_id=""):
    """Process an incoming message from any platform.

    Returns (conversation_id, message_id, contact_id) or None on error.
    """
    channel = get_channel(channel_id)
    if not channel or not channel["is_active"]:
        return None

    org_id = channel["org_id"]

    # Find or create contact
    contact_id = find_or_create_contact(
        org_id, channel_id, platform_user_id,
        display_name=display_name, avatar_url=avatar_url,
    )

    # Find or create conversation
    conversation_id = find_or_create_conversation(org_id, channel_id, contact_id)

    # Store message
    message_id = add_message(
        conversation_id=conversation_id,
        org_id=org_id,
        sender_type="contact",
        sender_id=platform_user_id,
        content=content,
        message_type=message_type,
        metadata_json=json.dumps(metadata or {}),
        platform_message_id=platform_message_id,
    )

    return conversation_id, message_id, contact_id


def send_admin_reply(conversation_id, admin_id, content, message_type="text"):
    """Send a reply from admin to customer via the appropriate platform.

    Returns (success, message_id_or_error)
    """
    conv = get_conversation(conversation_id)
    if not conv:
        return False, "Conversation not found"

    channel = get_channel(conv["channel_id"])
    if not channel:
        return False, "Channel not found"

    creds = load_credentials(channel["id"])
    if not creds:
        return False, "Channel credentials not configured"

    # Get platform adapter
    adapter_class = PLATFORM_ADAPTERS.get(channel["channel_type"])
    if not adapter_class:
        return False, f"Unsupported platform: {channel['channel_type']}"

    adapter = adapter_class(creds)

    # Send via platform
    success, platform_msg_id = adapter.send_message(
        recipient_id=conv["platform_user_id"],
        message_type=message_type,
        content=content,
    )

    if not success:
        return False, f"Failed to send: {platform_msg_id}"

    # Store in DB
    message_id = add_message(
        conversation_id=conversation_id,
        org_id=conv["org_id"],
        sender_type="admin",
        sender_id=str(admin_id),
        content=content,
        message_type=message_type,
        platform_message_id=platform_msg_id or "",
    )

    return True, message_id
