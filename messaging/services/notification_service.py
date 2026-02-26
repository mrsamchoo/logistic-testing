"""
Notification service - creates and pushes notifications to admins.
"""

from messaging_db import (
    create_notification, get_conversation, get_org_admins,
)


def notify_new_message(conversation_id, contact_name, message_preview, socketio=None):
    """Create notifications for new incoming messages."""
    conv = get_conversation(conversation_id)
    if not conv:
        return

    org_id = conv["org_id"]
    title = f"New message from {contact_name}"
    body = message_preview[:100] if message_preview else ""

    if conv["assigned_admin_id"]:
        # Notify assigned admin only
        create_notification(
            org_id, conv["assigned_admin_id"], "new_message",
            title, body, "conversation", conversation_id,
        )
        if socketio:
            socketio.emit("notification", {
                "type": "new_message",
                "title": title,
                "body": body,
                "conversation_id": conversation_id,
            }, room=f"admin_{conv['assigned_admin_id']}")
    else:
        # Notify all admins in org
        admins = get_org_admins(org_id)
        for admin in admins:
            create_notification(
                org_id, admin["id"], "new_message",
                title, body, "conversation", conversation_id,
            )
        if socketio:
            socketio.emit("notification", {
                "type": "new_message",
                "title": title,
                "body": body,
                "conversation_id": conversation_id,
            }, room=f"org_{org_id}")


def notify_assignment(conversation_id, admin_id, assigner_name, socketio=None):
    """Notify admin when a conversation is assigned to them."""
    conv = get_conversation(conversation_id)
    if not conv:
        return

    title = f"Conversation assigned by {assigner_name}"
    body = f"Chat with {conv['contact_name']}"

    create_notification(
        conv["org_id"], admin_id, "assigned",
        title, body, "conversation", conversation_id,
    )

    if socketio:
        socketio.emit("notification", {
            "type": "assigned",
            "title": title,
            "body": body,
            "conversation_id": conversation_id,
        }, room=f"admin_{admin_id}")
