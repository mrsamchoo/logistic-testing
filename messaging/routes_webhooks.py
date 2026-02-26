"""
Webhook endpoints for receiving messages from LINE, Facebook, and Instagram.
"""

import json
import threading
from flask import request, jsonify, current_app
from messaging import messaging_bp
from messaging_db import get_channel, get_messages_for_conversation, add_message, get_default_ai_provider, get_org_by_id
from messaging.services.channel_service import load_credentials
from messaging.services.message_service import handle_incoming_message
from messaging.services.ai_service import generate_suggestion
from messaging.platforms.line_adapter import LineAdapter
from messaging.platforms.facebook_adapter import FacebookAdapter
from messaging.platforms.instagram_adapter import InstagramAdapter


def _is_ai_auto_reply_enabled(org_id):
    """Check if AI auto-reply is enabled for this org."""
    org = get_org_by_id(org_id)
    if not org:
        return False
    settings = json.loads(dict(org).get("settings_json") or "{}")
    return settings.get("ai_auto_reply_enabled", True)  # Default: enabled


def _auto_save_public_url(org_id):
    """Auto-detect and save the public base URL from incoming webhook request headers."""
    from messaging_db import update_org
    try:
        # Cloudflare Tunnel / reverse proxy sets these headers
        proto = request.headers.get("X-Forwarded-Proto", "https")
        host = request.headers.get("X-Forwarded-Host") or request.headers.get("Host", "")
        if not host or "localhost" in host or "127.0.0.1" in host:
            return
        public_url = f"{proto}://{host}"
        org = get_org_by_id(org_id)
        if not org:
            return
        settings = json.loads(dict(org).get("settings_json") or "{}")
        if settings.get("public_base_url") != public_url:
            settings["public_base_url"] = public_url
            update_org(org_id, settings_json=json.dumps(settings))
            print(f"[Auto-detect] Saved public URL: {public_url}")
    except Exception as e:
        print(f"[Auto-detect URL] Error: {e}")

PLATFORM_ADAPTERS = {
    "line": LineAdapter,
    "facebook": FacebookAdapter,
    "instagram": InstagramAdapter,
}


def _get_socketio():
    """Get SocketIO instance from app."""
    return current_app.extensions.get("socketio")


def _auto_reply_with_ai(app, channel_id, conversation_id, org_id, platform_user_id):
    """Generate AI reply and send it back to the customer (runs in background thread)."""
    with app.app_context():
        try:
            # Check if org has an active AI provider
            provider = get_default_ai_provider(org_id)
            if not provider:
                return

            # Get conversation messages for context
            messages = get_messages_for_conversation(conversation_id, limit=15)
            if not messages:
                return

            # Generate AI response
            success, ai_response = generate_suggestion(org_id, messages)
            if not success:
                print(f"[AI Auto-Reply] Failed: {ai_response}")
                return

            # Get channel info and send reply
            channel = get_channel(channel_id)
            if not channel:
                return

            creds = load_credentials(channel_id)
            if not creds:
                return

            adapter_class = PLATFORM_ADAPTERS.get(channel["channel_type"])
            if not adapter_class:
                return

            adapter = adapter_class(creds)
            sent, error = adapter.send_message(
                recipient_id=platform_user_id,
                message_type="text",
                content=ai_response,
            )

            if sent:
                # Store AI message in DB
                msg_id = add_message(
                    conversation_id=conversation_id,
                    org_id=org_id,
                    sender_type="ai",
                    sender_id="auto",
                    content=ai_response,
                    message_type="text",
                )

                # Emit socket event so UI updates
                socketio = _get_socketio()
                if socketio:
                    socketio.emit("new_message", {
                        "conversation_id": conversation_id,
                        "message_id": msg_id,
                        "channel_type": channel["channel_type"],
                        "content": ai_response,
                        "sender_type": "ai",
                    }, room=f"org_{org_id}")
                print(f"[AI Auto-Reply] Sent to conversation {conversation_id}")
            else:
                print(f"[AI Auto-Reply] Send failed: {error}")

        except Exception as e:
            print(f"[AI Auto-Reply] Error: {e}")



# ============================================================
# LINE Webhook
# ============================================================


@messaging_bp.route("/webhooks/line/<int:channel_id>", methods=["POST"])
def webhook_line(channel_id):
    channel = get_channel(channel_id)
    if not channel or channel["channel_type"] != "line" or not channel["is_active"]:
        return jsonify({"error": "Invalid channel"}), 404

    creds = load_credentials(channel_id)
    if not creds:
        return jsonify({"error": "No credentials"}), 500

    adapter = LineAdapter(creds)

    # Verify signature
    if not adapter.verify_webhook(request):
        return jsonify({"error": "Invalid signature"}), 403

    # Auto-detect and save public URL from webhook request
    _auto_save_public_url(channel["org_id"])

    # Parse messages
    messages = adapter.parse_webhook(request)

    socketio = _get_socketio()

    for msg in messages:
        # Get user profile if display_name is empty
        if not msg["display_name"]:
            profile = adapter.get_user_profile(msg["platform_user_id"])
            msg["display_name"] = profile.get("display_name", "")
            msg["avatar_url"] = profile.get("avatar_url", "")

        result = handle_incoming_message(
            channel_id=channel_id,
            platform_user_id=msg["platform_user_id"],
            content=msg["content"],
            message_type=msg["message_type"],
            display_name=msg["display_name"],
            avatar_url=msg["avatar_url"],
            metadata=msg["metadata"],
            platform_message_id=msg["platform_message_id"],
        )

        if result:
            conversation_id, message_id, contact_id = result

            if socketio:
                socketio.emit("new_message", {
                    "conversation_id": conversation_id,
                    "message_id": message_id,
                    "contact_id": contact_id,
                    "channel_type": "line",
                    "content": msg["content"],
                    "display_name": msg["display_name"],
                }, room=f"org_{channel['org_id']}")

            # AI Auto-Reply (only if enabled in org settings)
            if _is_ai_auto_reply_enabled(channel["org_id"]):
                app = current_app._get_current_object()
                thread = threading.Thread(
                    target=_auto_reply_with_ai,
                    args=(app, channel_id, conversation_id, channel["org_id"], msg["platform_user_id"]),
                )
                thread.start()

    return jsonify({"status": "ok"}), 200


# ============================================================
# Facebook Webhook
# ============================================================


@messaging_bp.route("/webhooks/facebook/<int:channel_id>", methods=["GET"])
def webhook_facebook_verify(channel_id):
    channel = get_channel(channel_id)
    if not channel or channel["channel_type"] != "facebook":
        return "Invalid channel", 404

    creds = load_credentials(channel_id)
    if not creds:
        return "No credentials", 500

    adapter = FacebookAdapter(creds)
    challenge = adapter.verify_webhook_challenge(request)
    if challenge:
        return challenge, 200
    return "Verification failed", 403


@messaging_bp.route("/webhooks/facebook/<int:channel_id>", methods=["POST"])
def webhook_facebook(channel_id):
    channel = get_channel(channel_id)
    if not channel or channel["channel_type"] != "facebook" or not channel["is_active"]:
        return jsonify({"error": "Invalid channel"}), 404

    creds = load_credentials(channel_id)
    if not creds:
        return jsonify({"error": "No credentials"}), 500

    adapter = FacebookAdapter(creds)

    if not adapter.verify_webhook(request):
        return jsonify({"error": "Invalid signature"}), 403

    messages = adapter.parse_webhook(request)
    socketio = _get_socketio()

    # Filter out messages from the page itself
    page_id = creds.get("page_id", "")
    messages = [m for m in messages if m["platform_user_id"] != page_id]

    for msg in messages:
        result = handle_incoming_message(
            channel_id=channel_id,
            platform_user_id=msg["platform_user_id"],
            content=msg["content"],
            message_type=msg["message_type"],
            display_name=msg["display_name"],
            avatar_url=msg["avatar_url"],
            metadata=msg["metadata"],
            platform_message_id=msg["platform_message_id"],
        )

        if result and socketio:
            conversation_id, message_id, contact_id = result
            socketio.emit("new_message", {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "contact_id": contact_id,
                "channel_type": "facebook",
                "content": msg["content"],
                "display_name": msg["display_name"],
            }, room=f"org_{channel['org_id']}")

    return jsonify({"status": "ok"}), 200


# ============================================================
# Instagram Webhook
# ============================================================


@messaging_bp.route("/webhooks/instagram/<int:channel_id>", methods=["GET"])
def webhook_instagram_verify(channel_id):
    channel = get_channel(channel_id)
    if not channel or channel["channel_type"] != "instagram":
        return "Invalid channel", 404

    creds = load_credentials(channel_id)
    if not creds:
        return "No credentials", 500

    adapter = InstagramAdapter(creds)
    challenge = adapter.verify_webhook_challenge(request)
    if challenge:
        return challenge, 200
    return "Verification failed", 403


@messaging_bp.route("/webhooks/instagram/<int:channel_id>", methods=["POST"])
def webhook_instagram(channel_id):
    channel = get_channel(channel_id)
    if not channel or channel["channel_type"] != "instagram" or not channel["is_active"]:
        return jsonify({"error": "Invalid channel"}), 404

    creds = load_credentials(channel_id)
    if not creds:
        return jsonify({"error": "No credentials"}), 500

    adapter = InstagramAdapter(creds)

    if not adapter.verify_webhook(request):
        return jsonify({"error": "Invalid signature"}), 403

    messages = adapter.parse_webhook(request)
    socketio = _get_socketio()

    ig_id = creds.get("instagram_account_id", "")
    messages = [m for m in messages if m["platform_user_id"] != ig_id]

    for msg in messages:
        result = handle_incoming_message(
            channel_id=channel_id,
            platform_user_id=msg["platform_user_id"],
            content=msg["content"],
            message_type=msg["message_type"],
            display_name=msg["display_name"],
            avatar_url=msg["avatar_url"],
            metadata=msg["metadata"],
            platform_message_id=msg["platform_message_id"],
        )

        if result and socketio:
            conversation_id, message_id, contact_id = result
            socketio.emit("new_message", {
                "conversation_id": conversation_id,
                "message_id": message_id,
                "contact_id": contact_id,
                "channel_type": "instagram",
                "content": msg["content"],
                "display_name": msg["display_name"],
            }, room=f"org_{channel['org_id']}")

    return jsonify({"status": "ok"}), 200
