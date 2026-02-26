"""
SocketIO event handlers for real-time messaging.
"""

from flask import session
from messaging_db import get_admin_org_id, mark_messages_read


def register_socketio_events(socketio):
    """Register all SocketIO event handlers."""

    @socketio.on("connect")
    def handle_connect():
        admin_id = session.get("admin_id")
        if not admin_id:
            return False  # Reject connection
        org_id = get_admin_org_id(admin_id)
        if org_id:
            from flask_socketio import join_room
            join_room(f"org_{org_id}")
            join_room(f"admin_{admin_id}")
            socketio.emit("admin_online", {
                "admin_id": admin_id,
                "username": session.get("admin_username", ""),
            }, room=f"org_{org_id}")

    @socketio.on("disconnect")
    def handle_disconnect():
        admin_id = session.get("admin_id")
        if admin_id:
            org_id = get_admin_org_id(admin_id)
            if org_id:
                socketio.emit("admin_offline", {
                    "admin_id": admin_id,
                }, room=f"org_{org_id}")

    @socketio.on("join_conversation")
    def handle_join_conversation(data):
        conversation_id = data.get("conversation_id")
        if conversation_id:
            from flask_socketio import join_room
            join_room(f"conversation_{conversation_id}")

    @socketio.on("leave_conversation")
    def handle_leave_conversation(data):
        conversation_id = data.get("conversation_id")
        if conversation_id:
            from flask_socketio import leave_room
            leave_room(f"conversation_{conversation_id}")

    @socketio.on("mark_read")
    def handle_mark_read(data):
        conversation_id = data.get("conversation_id")
        if conversation_id:
            mark_messages_read(conversation_id)

    @socketio.on("admin_typing")
    def handle_admin_typing(data):
        conversation_id = data.get("conversation_id")
        admin_id = session.get("admin_id")
        if conversation_id and admin_id:
            socketio.emit("admin_typing", {
                "conversation_id": conversation_id,
                "admin_id": admin_id,
                "username": session.get("admin_username", ""),
            }, room=f"conversation_{conversation_id}", include_self=False)
