"""
REST API endpoints for the messaging platform.
All endpoints prefixed with /api/messaging/
"""

import json
import os
import requests
from functools import wraps
from flask import request, session, jsonify

# Media directory: use persistent disk in production, local static/media in development
_DATA_DIR = os.environ.get("DATA_DIR", "")
if _DATA_DIR:
    MEDIA_DIR = os.path.join(_DATA_DIR, "media")
else:
    MEDIA_DIR = os.path.join(os.path.dirname(os.path.dirname(__file__)), "static", "media")
from messaging import messaging_bp
from messaging_db import (
    get_admin_org_id, get_org_by_id, update_org,
    get_channels_for_org, get_channel, create_channel, update_channel, delete_channel,
    get_ai_providers_for_org, get_ai_provider, create_ai_provider, update_ai_provider, delete_ai_provider,
    get_conversations_for_org, get_conversation, update_conversation,
    get_messages_for_conversation, mark_messages_read,
    get_contacts_for_org, get_contact, update_contact,
    get_templates_for_org, create_template, update_template, delete_template, increment_template_usage,
    get_conversation_tags, add_conversation_tag, remove_conversation_tag,
    get_notifications, mark_notification_read, mark_all_notifications_read,
    get_messaging_overview, get_org_admins,
)
from messaging.services.channel_service import (
    CHANNEL_TYPES, save_credentials, get_masked_credentials, verify_channel_connection,
)
from messaging.services.ai_service import (
    AI_PROVIDERS, test_api_key, generate_suggestion,
)
from messaging.services.message_service import send_admin_reply
from messaging.utils.encryption import encrypt_json, mask_secret


def _row_to_dict(row):
    """Convert sqlite3.Row to dict."""
    if row is None:
        return None
    return dict(row)


def _rows_to_list(rows):
    return [dict(r) for r in rows]


# ============================================================
# Auth Decorator for API
# ============================================================


def api_admin_required(f):
    @wraps(f)
    def decorated(*args, **kwargs):
        if not session.get("admin_id"):
            return jsonify({"error": "unauthorized"}), 401
        return f(*args, **kwargs)
    return decorated


def _get_org_id():
    """Get current admin's org_id from session."""
    admin_id = session.get("admin_id")
    if not admin_id:
        return None
    return get_admin_org_id(admin_id)


# ============================================================
# Organization
# ============================================================


@messaging_bp.route("/api/messaging/org")
@api_admin_required
def api_get_org():
    org_id = _get_org_id()
    org = get_org_by_id(org_id)
    if not org:
        return jsonify({"error": "Organization not found"}), 404
    return jsonify(_row_to_dict(org))


@messaging_bp.route("/api/messaging/org", methods=["PUT"])
@api_admin_required
def api_update_org():
    org_id = _get_org_id()
    data = request.get_json()
    update_org(org_id, **data)
    return jsonify({"success": True})


# ============================================================
# Channels
# ============================================================


@messaging_bp.route("/api/messaging/channels")
@api_admin_required
def api_list_channels():
    org_id = _get_org_id()
    channels = get_channels_for_org(org_id)
    result = []
    for ch in channels:
        ch_dict = _row_to_dict(ch)
        ch_dict["has_credentials"] = get_masked_credentials(ch["id"]) is not None
        ch_dict["channel_type_info"] = CHANNEL_TYPES.get(ch["channel_type"], {})
        result.append(ch_dict)
    return jsonify(result)


@messaging_bp.route("/api/messaging/channels", methods=["POST"])
@api_admin_required
def api_create_channel():
    org_id = _get_org_id()
    data = request.get_json()
    channel_type = data.get("channel_type")
    name = data.get("name")
    if not channel_type or channel_type not in CHANNEL_TYPES:
        return jsonify({"error": "Invalid channel type"}), 400
    if not name:
        return jsonify({"error": "Name is required"}), 400
    channel_id = create_channel(org_id, channel_type, name)
    return jsonify({"id": channel_id, "success": True}), 201


@messaging_bp.route("/api/messaging/channels/<int:channel_id>")
@api_admin_required
def api_get_channel(channel_id):
    channel = get_channel(channel_id)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404
    ch_dict = _row_to_dict(channel)
    ch_dict["masked_credentials"] = get_masked_credentials(channel_id)
    ch_dict["channel_type_info"] = CHANNEL_TYPES.get(channel["channel_type"], {})
    return jsonify(ch_dict)


@messaging_bp.route("/api/messaging/channels/<int:channel_id>", methods=["PUT"])
@api_admin_required
def api_update_channel(channel_id):
    data = request.get_json()
    update_channel(channel_id, **data)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/channels/<int:channel_id>", methods=["DELETE"])
@api_admin_required
def api_delete_channel(channel_id):
    delete_channel(channel_id)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/channels/<int:channel_id>/credentials", methods=["POST"])
@api_admin_required
def api_set_credentials(channel_id):
    channel = get_channel(channel_id)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404
    data = request.get_json()
    credentials = data.get("credentials", {})
    save_credentials(channel_id, channel["channel_type"], credentials)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/channels/<int:channel_id>/verify", methods=["POST"])
@api_admin_required
def api_verify_channel(channel_id):
    success, message = verify_channel_connection(channel_id)
    return jsonify({"success": success, "message": message})


@messaging_bp.route("/api/messaging/channels/<int:channel_id>/webhook-url")
@api_admin_required
def api_get_webhook_url(channel_id):
    channel = get_channel(channel_id)
    if not channel:
        return jsonify({"error": "Channel not found"}), 404
    base_url = request.host_url.rstrip("/")
    webhook_url = f"{base_url}/webhooks/{channel['channel_type']}/{channel_id}"
    return jsonify({"webhook_url": webhook_url})


@messaging_bp.route("/api/messaging/channel-types")
@api_admin_required
def api_channel_types():
    return jsonify(CHANNEL_TYPES)


# ============================================================
# AI Providers
# ============================================================


@messaging_bp.route("/api/messaging/ai-providers")
@api_admin_required
def api_list_ai_providers():
    org_id = _get_org_id()
    providers = get_ai_providers_for_org(org_id)
    result = []
    for p in providers:
        p_dict = _row_to_dict(p)
        p_dict["masked_api_key"] = mask_secret(p["encrypted_api_key"][:20] if p["encrypted_api_key"] else "")
        p_dict.pop("encrypted_api_key", None)
        p_dict["provider_info"] = AI_PROVIDERS.get(p["provider_type"], {})
        result.append(p_dict)
    return jsonify(result)


@messaging_bp.route("/api/messaging/ai-providers", methods=["POST"])
@api_admin_required
def api_create_ai_provider():
    org_id = _get_org_id()
    data = request.get_json()
    provider_type = data.get("provider_type")
    name = data.get("name")
    api_key = data.get("api_key")
    if not provider_type or provider_type not in AI_PROVIDERS:
        return jsonify({"error": "Invalid provider type"}), 400
    if not name or not api_key:
        return jsonify({"error": "Name and API key are required"}), 400
    encrypted_key = encrypt_json({"api_key": api_key})
    provider_id = create_ai_provider(
        org_id, provider_type, name, encrypted_key,
        model_name=data.get("model_name", ""),
        system_prompt=data.get("system_prompt", ""),
        max_tokens=data.get("max_tokens", 500),
        temperature=data.get("temperature", 0.7),
        is_default=1 if data.get("is_default") else 0,
    )
    return jsonify({"id": provider_id, "success": True}), 201


@messaging_bp.route("/api/messaging/ai-providers/<int:provider_id>", methods=["PUT"])
@api_admin_required
def api_update_ai_provider(provider_id):
    data = request.get_json()
    update_data = {}
    for key in ["name", "provider_type", "model_name", "system_prompt", "max_tokens", "temperature", "is_default", "is_active"]:
        if key in data:
            update_data[key] = data[key]
    if "api_key" in data and data["api_key"]:
        update_data["encrypted_api_key"] = encrypt_json({"api_key": data["api_key"]})
    update_ai_provider(provider_id, **update_data)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/ai-providers/<int:provider_id>", methods=["DELETE"])
@api_admin_required
def api_delete_ai_provider(provider_id):
    delete_ai_provider(provider_id)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/ai-providers/<int:provider_id>/test", methods=["POST"])
@api_admin_required
def api_test_ai_provider(provider_id):
    from messaging.utils.encryption import decrypt_json
    provider = get_ai_provider(provider_id)
    if not provider:
        return jsonify({"error": "Provider not found"}), 404
    api_key = decrypt_json(provider["encrypted_api_key"]).get("api_key", "")
    success, message = test_api_key(provider["provider_type"], api_key)
    return jsonify({"success": success, "message": message})


@messaging_bp.route("/api/messaging/ai-provider-types")
@api_admin_required
def api_ai_provider_types():
    return jsonify(AI_PROVIDERS)


@messaging_bp.route("/api/messaging/ai/suggest", methods=["POST"])
@api_admin_required
def api_ai_suggest():
    org_id = _get_org_id()
    data = request.get_json()
    conversation_id = data.get("conversation_id")
    if not conversation_id:
        return jsonify({"error": "conversation_id is required"}), 400
    messages = get_messages_for_conversation(conversation_id, limit=15)
    messages_list = _rows_to_list(messages)
    success, result = generate_suggestion(
        org_id, messages_list,
        provider_id=data.get("provider_id"),
    )
    if success:
        return jsonify({"suggestion": result})
    return jsonify({"error": result}), 400


# ============================================================
# Conversations
# ============================================================


@messaging_bp.route("/api/messaging/conversations")
@api_admin_required
def api_list_conversations():
    org_id = _get_org_id()
    status = request.args.get("status")
    channel_id = request.args.get("channel_id", type=int)
    assigned = request.args.get("assigned_admin_id", type=int)
    search = request.args.get("search")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    conversations = get_conversations_for_org(
        org_id, status=status, channel_id=channel_id,
        assigned_admin_id=assigned, search=search, limit=limit, offset=offset,
    )
    result = _rows_to_list(conversations)
    for conv in result:
        conv["tags"] = get_conversation_tags(conv["id"])
    return jsonify(result)


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>")
@api_admin_required
def api_get_conversation(conversation_id):
    conv = get_conversation(conversation_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404
    conv_dict = _row_to_dict(conv)
    conv_dict["tags"] = get_conversation_tags(conversation_id)
    return jsonify(conv_dict)


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>", methods=["PUT"])
@api_admin_required
def api_update_conversation(conversation_id):
    data = request.get_json()
    update_data = {}
    for key in ["status", "assigned_admin_id", "priority", "subject"]:
        if key in data:
            update_data[key] = data[key]
    if data.get("status") == "resolved":
        from datetime import datetime
        update_data["resolved_at"] = datetime.now().isoformat()
    update_conversation(conversation_id, **update_data)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/messages")
@api_admin_required
def api_get_messages(conversation_id):
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    messages = get_messages_for_conversation(conversation_id, limit=limit, offset=offset)
    return jsonify(_rows_to_list(messages))


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/messages", methods=["POST"])
@api_admin_required
def api_send_message(conversation_id):
    data = request.get_json()
    content = data.get("content", "").strip()
    if not content:
        return jsonify({"error": "Message content is required"}), 400
    admin_id = session["admin_id"]
    success, result = send_admin_reply(conversation_id, admin_id, content, data.get("message_type", "text"))
    if success:
        return jsonify({"message_id": result, "success": True})
    return jsonify({"error": result}), 400


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/resolve", methods=["POST"])
@api_admin_required
def api_resolve_conversation(conversation_id):
    from datetime import datetime
    update_conversation(conversation_id, status="resolved", resolved_at=datetime.now().isoformat())
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/reopen", methods=["POST"])
@api_admin_required
def api_reopen_conversation(conversation_id):
    update_conversation(conversation_id, status="open", resolved_at=None)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/read", methods=["POST"])
@api_admin_required
def api_mark_read(conversation_id):
    mark_messages_read(conversation_id)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/tags")
@api_admin_required
def api_get_tags(conversation_id):
    tags = get_conversation_tags(conversation_id)
    return jsonify(tags)


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/tags", methods=["POST"])
@api_admin_required
def api_add_tag(conversation_id):
    org_id = _get_org_id()
    data = request.get_json()
    tag = data.get("tag", "").strip()
    if not tag:
        return jsonify({"error": "Tag is required"}), 400
    add_conversation_tag(conversation_id, org_id, tag)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/tags/<tag>", methods=["DELETE"])
@api_admin_required
def api_remove_tag(conversation_id, tag):
    remove_conversation_tag(conversation_id, tag)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/pin", methods=["POST"])
@api_admin_required
def api_pin_conversation(conversation_id):
    update_conversation(conversation_id, is_pinned=1)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/unpin", methods=["POST"])
@api_admin_required
def api_unpin_conversation(conversation_id):
    update_conversation(conversation_id, is_pinned=0)
    return jsonify({"success": True})


# ============================================================
# Contacts
# ============================================================


@messaging_bp.route("/api/messaging/contacts")
@api_admin_required
def api_list_contacts():
    org_id = _get_org_id()
    search = request.args.get("search")
    limit = request.args.get("limit", 50, type=int)
    offset = request.args.get("offset", 0, type=int)
    contacts = get_contacts_for_org(org_id, search=search, limit=limit, offset=offset)
    return jsonify(_rows_to_list(contacts))


@messaging_bp.route("/api/messaging/contacts/<int:contact_id>")
@api_admin_required
def api_get_contact(contact_id):
    contact = get_contact(contact_id)
    if not contact:
        return jsonify({"error": "Contact not found"}), 404
    return jsonify(_row_to_dict(contact))


@messaging_bp.route("/api/messaging/contacts/<int:contact_id>", methods=["PUT"])
@api_admin_required
def api_update_contact(contact_id):
    data = request.get_json()
    update_contact(contact_id, **data)
    return jsonify({"success": True})


# ============================================================
# Templates
# ============================================================


@messaging_bp.route("/api/messaging/templates")
@api_admin_required
def api_list_templates():
    org_id = _get_org_id()
    category = request.args.get("category")
    templates = get_templates_for_org(org_id, category=category)
    return jsonify(_rows_to_list(templates))


@messaging_bp.route("/api/messaging/templates", methods=["POST"])
@api_admin_required
def api_create_template():
    org_id = _get_org_id()
    data = request.get_json()
    name = data.get("name", "").strip()
    content = data.get("content", "").strip()
    if not name or not content:
        return jsonify({"error": "Name and content are required"}), 400
    template_id = create_template(
        org_id, name, content,
        category=data.get("category", "general"),
        shortcut=data.get("shortcut", ""),
    )
    return jsonify({"id": template_id, "success": True}), 201


@messaging_bp.route("/api/messaging/templates/<int:template_id>", methods=["PUT"])
@api_admin_required
def api_update_template(template_id):
    data = request.get_json()
    update_template(template_id, **data)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/templates/<int:template_id>", methods=["DELETE"])
@api_admin_required
def api_delete_template(template_id):
    delete_template(template_id)
    return jsonify({"success": True})


# ============================================================
# Notifications
# ============================================================


@messaging_bp.route("/api/messaging/notifications")
@api_admin_required
def api_list_notifications():
    admin_id = session["admin_id"]
    unread_only = request.args.get("unread") == "1"
    notifications = get_notifications(admin_id, unread_only=unread_only)
    return jsonify(_rows_to_list(notifications))


@messaging_bp.route("/api/messaging/notifications/<int:notification_id>/read", methods=["POST"])
@api_admin_required
def api_mark_notification_read(notification_id):
    mark_notification_read(notification_id)
    return jsonify({"success": True})


@messaging_bp.route("/api/messaging/notifications/read-all", methods=["POST"])
@api_admin_required
def api_mark_all_notifications_read():
    admin_id = session["admin_id"]
    mark_all_notifications_read(admin_id)
    return jsonify({"success": True})


# ============================================================
# Analytics
# ============================================================


@messaging_bp.route("/api/messaging/analytics/overview")
@api_admin_required
def api_analytics_overview():
    org_id = _get_org_id()
    stats = get_messaging_overview(org_id)
    return jsonify(stats)


# ============================================================
# Team (org admins)
# ============================================================


@messaging_bp.route("/api/messaging/team")
@api_admin_required
def api_list_team():
    org_id = _get_org_id()
    admins = get_org_admins(org_id)
    return jsonify(_rows_to_list(admins))


# ============================================================
# Current admin info
# ============================================================


@messaging_bp.route("/api/messaging/me")
@api_admin_required
def api_me():
    admin_id = session["admin_id"]
    org_id = _get_org_id()
    org = get_org_by_id(org_id)
    return jsonify({
        "admin_id": admin_id,
        "username": session.get("admin_username"),
        "role": session.get("admin_role"),
        "org_id": org_id,
        "org_name": org["name"] if org else "",
    })


# ============================================================
# Media Proxy
# ============================================================


@messaging_bp.route("/api/messaging/media/line/<message_id>")
@api_admin_required
def api_line_media_proxy(message_id):
    """Proxy LINE image/video content to frontend."""
    from flask import send_file
    from messaging.services.channel_service import load_credentials

    channel_id = request.args.get("channel_id", type=int)
    if not channel_id:
        return jsonify({"error": "channel_id required"}), 400

    # Check cache first
    os.makedirs(MEDIA_DIR, exist_ok=True)
    cache_path = os.path.join(MEDIA_DIR, f"line_{message_id}")

    if os.path.exists(cache_path):
        # Guess content type from first bytes or default
        import mimetypes
        ct = mimetypes.guess_type(cache_path)[0] or "application/octet-stream"
        return send_file(cache_path, mimetype=ct)

    # Fetch from LINE Content API (works for images, videos, audio, files)
    creds = load_credentials(channel_id)
    if not creds:
        return jsonify({"error": "No credentials"}), 404

    token = creds.get("channel_access_token", "")
    resp = requests.get(
        f"https://api-data.line.me/v2/bot/message/{message_id}/content",
        headers={"Authorization": f"Bearer {token}"},
        timeout=30,
        stream=True,
    )

    if resp.status_code != 200:
        return jsonify({"error": f"LINE API error: {resp.status_code}"}), 502

    content_type = resp.headers.get("Content-Type", "application/octet-stream")

    # Determine file extension for cache
    ext = ""
    if "image" in content_type:
        ext = ".jpg"
    elif "video" in content_type:
        ext = ".mp4"
    cache_path_with_ext = cache_path + ext

    # Save to cache
    with open(cache_path_with_ext, "wb") as f:
        for chunk in resp.iter_content(chunk_size=8192):
            f.write(chunk)

    return send_file(cache_path_with_ext, mimetype=content_type)


# ============================================================
# CSV Export
# ============================================================


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/export")
@api_admin_required
def api_export_conversation(conversation_id):
    """Export a single conversation's messages as CSV."""
    import csv
    import io
    from flask import Response

    messages = get_messages_for_conversation(conversation_id, limit=10000)
    conv = get_conversation(conversation_id)
    contact_name = conv["contact_name"] if conv else "unknown"

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Date", "Time", "Sender Type", "Sender", "Message Type", "Content"])

    for msg in messages:
        m = dict(msg)
        dt = m.get("created_at") or ""
        date_part = dt[:10] if len(dt) >= 10 else dt
        time_part = dt[11:19] if len(dt) >= 19 else ""
        sender = ""
        if m.get("sender_type") == "contact":
            sender = contact_name
        elif m.get("sender_type") == "admin":
            sender = m.get("admin_username") or m.get("admin_display_name") or f"Admin #{m.get('sender_id', '')}"
        elif m.get("sender_type") == "ai":
            sender = "AI Auto-Reply"
        writer.writerow([date_part, time_part, m.get("sender_type", ""), sender, m.get("message_type", ""), m.get("content", "")])

    csv_content = output.getvalue()
    output.close()

    safe_name = "".join(c for c in contact_name if c.isalnum() or c in (' ', '_', '-')).strip() or "unknown"
    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": f"attachment; filename=conversation_{conversation_id}_{safe_name}.csv"},
    )


@messaging_bp.route("/api/messaging/conversations/export-all")
@api_admin_required
def api_export_all_conversations():
    """Export ALL conversations as CSV."""
    import csv
    import io
    from flask import Response

    org_id = _get_org_id()
    conversations = get_conversations_for_org(org_id, limit=10000)

    output = io.StringIO()
    writer = csv.writer(output)
    writer.writerow(["Conversation ID", "Contact", "Channel", "Status", "Priority", "Date", "Time", "Sender Type", "Sender", "Message Type", "Content"])

    for conv in conversations:
        conv_dict = dict(conv)
        messages = get_messages_for_conversation(conv_dict["id"], limit=10000)
        for msg in messages:
            m = dict(msg)
            dt = m.get("created_at") or ""
            date_part = dt[:10] if len(dt) >= 10 else dt
            time_part = dt[11:19] if len(dt) >= 19 else ""
            sender = ""
            if m.get("sender_type") == "contact":
                sender = conv_dict.get("contact_name", "")
            elif m.get("sender_type") == "admin":
                sender = m.get("admin_username") or m.get("admin_display_name") or f"Admin #{m.get('sender_id', '')}"
            elif m.get("sender_type") == "ai":
                sender = "AI Auto-Reply"
            writer.writerow([
                conv_dict["id"], conv_dict.get("contact_name", ""), conv_dict.get("channel_type", ""),
                conv_dict.get("status", ""), conv_dict.get("priority", "normal"),
                date_part, time_part, m.get("sender_type", ""), sender, m.get("message_type", ""), m.get("content", ""),
            ])

    csv_content = output.getvalue()
    output.close()

    return Response(
        csv_content,
        mimetype="text/csv",
        headers={"Content-Disposition": "attachment; filename=all_conversations_export.csv"},
    )


# ============================================================
# File Upload (Admin send image/video)
# ============================================================


@messaging_bp.route("/api/messaging/conversations/<int:conversation_id>/upload", methods=["POST"])
@api_admin_required
def api_upload_media(conversation_id):
    """Upload an image or video and send it to the customer."""
    from messaging.services.message_service import send_admin_reply
    from messaging_db import add_message

    if "file" not in request.files:
        return jsonify({"error": "No file provided"}), 400

    file = request.files["file"]
    if not file.filename:
        return jsonify({"error": "No file selected"}), 400

    # Determine message type
    content_type = file.content_type or ""
    if content_type.startswith("image/"):
        msg_type = "image"
    elif content_type.startswith("video/"):
        msg_type = "video"
    else:
        return jsonify({"error": "Only image and video files are supported"}), 400

    # Save file locally (persistent disk in production)
    import uuid
    os.makedirs(MEDIA_DIR, exist_ok=True)
    ext = os.path.splitext(file.filename)[1] or (".jpg" if msg_type == "image" else ".mp4")
    filename = f"upload_{uuid.uuid4().hex}{ext}"
    filepath = os.path.join(MEDIA_DIR, filename)
    file.save(filepath)

    # Get conversation info
    conv = get_conversation(conversation_id)
    if not conv:
        return jsonify({"error": "Conversation not found"}), 404

    channel = get_channel(conv["channel_id"])
    if not channel:
        return jsonify({"error": "Channel not found"}), 404

    # Build public media URL (LINE requires HTTPS publicly accessible URL)
    org = get_org_by_id(conv["org_id"])
    org_settings = json.loads(dict(org).get("settings_json") or "{}") if org else {}
    public_base = org_settings.get("public_base_url", "").rstrip("/")
    if not public_base:
        # Fallback: try to detect from request headers
        fwd_proto = request.headers.get("X-Forwarded-Proto", "")
        fwd_host = request.headers.get("X-Forwarded-Host", "")
        if fwd_host and "localhost" not in fwd_host:
            public_base = f"{fwd_proto or 'https'}://{fwd_host}"
        else:
            public_base = request.host_url.rstrip("/")

    media_url = f"{public_base}/static/media/{filename}"

    creds = load_credentials(channel["id"])
    if not creds:
        return jsonify({"error": "Channel credentials not configured"}), 400

    # Send via platform adapter
    from messaging.platforms.line_adapter import LineAdapter
    from messaging.platforms.facebook_adapter import FacebookAdapter
    from messaging.platforms.instagram_adapter import InstagramAdapter

    adapters = {"line": LineAdapter, "facebook": FacebookAdapter, "instagram": InstagramAdapter}
    adapter_class = adapters.get(channel["channel_type"])
    if not adapter_class:
        return jsonify({"error": "Unsupported platform"}), 400

    adapter = adapter_class(creds)
    success, error = adapter.send_message(
        recipient_id=conv["platform_user_id"],
        message_type=msg_type,
        content=f"[{msg_type.title()}]",
        media_url=media_url,
    )

    # Store message in DB regardless (so admin sees it in chat)
    import json
    admin_id = session["admin_id"]
    metadata = {"filename": filename, "media_url": f"/static/media/{filename}", "content_type": content_type}
    message_id = add_message(
        conversation_id=conversation_id,
        org_id=conv["org_id"],
        sender_type="admin",
        sender_id=str(admin_id),
        content=f"[{msg_type.title()}]",
        message_type=msg_type,
        metadata_json=json.dumps(metadata),
    )

    if success:
        return jsonify({"success": True, "message_id": message_id, "media_url": f"/static/media/{filename}"})
    else:
        return jsonify({"success": True, "message_id": message_id, "media_url": f"/static/media/{filename}", "warning": f"Saved but LINE delivery failed: {error}"})


# ============================================================
# AI Auto-Reply Toggle
# ============================================================


@messaging_bp.route("/api/messaging/settings/ai-toggle")
@api_admin_required
def api_get_ai_toggle():
    """Get AI auto-reply setting."""
    org_id = _get_org_id()
    org = get_org_by_id(org_id)
    if not org:
        return jsonify({"error": "Org not found"}), 404
    settings = json.loads(dict(org).get("settings_json") or "{}")
    return jsonify({"ai_auto_reply_enabled": settings.get("ai_auto_reply_enabled", True)})


@messaging_bp.route("/api/messaging/settings/ai-toggle", methods=["PUT"])
@api_admin_required
def api_set_ai_toggle():
    """Toggle AI auto-reply on/off."""
    org_id = _get_org_id()
    org = get_org_by_id(org_id)
    if not org:
        return jsonify({"error": "Org not found"}), 404
    data = request.get_json()
    enabled = data.get("ai_auto_reply_enabled", True)
    settings = json.loads(dict(org).get("settings_json") or "{}")
    settings["ai_auto_reply_enabled"] = bool(enabled)
    update_org(org_id, settings_json=json.dumps(settings))
    return jsonify({"success": True, "ai_auto_reply_enabled": bool(enabled)})


# ============================================================
# Public URL Setting (for media sharing via LINE)
# ============================================================


@messaging_bp.route("/api/messaging/settings/public-url")
@api_admin_required
def api_get_public_url():
    """Get the public base URL setting."""
    org_id = _get_org_id()
    org = get_org_by_id(org_id)
    if not org:
        return jsonify({"error": "Org not found"}), 404
    settings = json.loads(dict(org).get("settings_json") or "{}")
    return jsonify({"public_base_url": settings.get("public_base_url", "")})


@messaging_bp.route("/api/messaging/settings/public-url", methods=["PUT"])
@api_admin_required
def api_set_public_url():
    """Set the public base URL (Cloudflare Tunnel, ngrok, etc.)."""
    org_id = _get_org_id()
    org = get_org_by_id(org_id)
    if not org:
        return jsonify({"error": "Org not found"}), 404
    data = request.get_json()
    url = (data.get("public_base_url") or "").strip().rstrip("/")
    settings = json.loads(dict(org).get("settings_json") or "{}")
    settings["public_base_url"] = url
    update_org(org_id, settings_json=json.dumps(settings))
    return jsonify({"success": True, "public_base_url": url})


# ============================================================
# Customer Behavior Analytics
# ============================================================


@messaging_bp.route("/api/messaging/analytics/customer-behavior")
@api_admin_required
def api_customer_behavior():
    """Get customer behavior analytics: message times, frequency, product categories."""
    from database import get_db

    org_id = _get_org_id()
    conn = get_db()

    # 1) Message count by hour of day (when do customers message?)
    hourly = conn.execute("""
        SELECT CAST(strftime('%%H', m.created_at) AS INTEGER) AS hour, COUNT(*) AS count
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.id
        WHERE m.org_id = ? AND m.sender_type = 'contact'
        GROUP BY hour ORDER BY hour
    """, (org_id,)).fetchall()
    hourly_data = {h["hour"]: h["count"] for h in hourly}

    # 2) Message count by day of week (0=Sunday, 6=Saturday)
    daily = conn.execute("""
        SELECT CAST(strftime('%%w', m.created_at) AS INTEGER) AS dow, COUNT(*) AS count
        FROM messages m
        JOIN conversations c ON m.conversation_id = c.id
        WHERE m.org_id = ? AND m.sender_type = 'contact'
        GROUP BY dow ORDER BY dow
    """, (org_id,)).fetchall()
    day_names = ["อาทิตย์", "จันทร์", "อังคาร", "พุธ", "พฤหัสบดี", "ศุกร์", "เสาร์"]
    daily_data = [{"day": day_names[d["dow"]], "dow": d["dow"], "count": d["count"]} for d in daily]

    # 3) Top active contacts (message count, last seen, first seen)
    top_contacts = conn.execute("""
        SELECT ct.id, ct.display_name, ct.platform_user_id, ct.first_seen_at, ct.last_seen_at,
               ct.customer_code, ct.tags_json, ct.notes,
               COUNT(m.id) AS message_count,
               MAX(m.created_at) AS last_message_at
        FROM contacts ct
        JOIN conversations cv ON cv.contact_id = ct.id
        JOIN messages m ON m.conversation_id = cv.id AND m.sender_type = 'contact'
        WHERE ct.org_id = ?
        GROUP BY ct.id
        ORDER BY message_count DESC
        LIMIT 20
    """, (org_id,)).fetchall()
    top_contacts_data = [dict(c) for c in top_contacts]

    # 4) Product category keywords — scan recent messages for common product-related keywords
    keyword_categories = {
        "อิเล็กทรอนิกส์": ["โทรศัพท์", "มือถือ", "คอม", "โน๊ตบุ๊ค", "laptop", "phone", "tablet", "ipad", "iphone", "กล้อง", "camera", "หูฟัง"],
        "แฟชั่น/เสื้อผ้า": ["เสื้อ", "กางเกง", "รองเท้า", "กระเป๋า", "เครื่องประดับ", "นาฬิกา", "แว่น", "shoes", "bag", "watch", "clothes"],
        "อาหาร/เครื่องดื่ม": ["อาหาร", "ขนม", "เครื่องดื่ม", "กาแฟ", "ชา", "food", "snack", "coffee", "supplement", "วิตามิน"],
        "สุขภาพ/ความงาม": ["ครีม", "เซรั่ม", "สกินแคร์", "skincare", "อาหารเสริม", "ยา", "cosmetic", "เครื่องสำอาง", "beauty"],
        "ของใช้ในบ้าน": ["เฟอร์นิเจอร์", "furniture", "โซฟา", "เตียง", "ตู้", "โต๊ะ", "ของตกแต่ง", "home"],
        "ชิ้นส่วน/อะไหล่": ["อะไหล่", "parts", "spare", "ชิ้นส่วน", "เครื่องจักร", "machine"],
    }

    recent_messages = conn.execute("""
        SELECT m.content FROM messages m
        WHERE m.org_id = ? AND m.sender_type = 'contact' AND m.message_type = 'text'
        ORDER BY m.created_at DESC LIMIT 500
    """, (org_id,)).fetchall()

    category_counts = {}
    for cat, keywords in keyword_categories.items():
        count = 0
        for msg_row in recent_messages:
            text = (msg_row["content"] or "").lower()
            if any(kw.lower() in text for kw in keywords):
                count += 1
        if count > 0:
            category_counts[cat] = count

    # 5) Monthly message trend
    monthly = conn.execute("""
        SELECT strftime('%%Y-%%m', m.created_at) AS month, COUNT(*) AS count
        FROM messages m
        WHERE m.org_id = ? AND m.sender_type = 'contact'
        GROUP BY month ORDER BY month DESC LIMIT 12
    """, (org_id,)).fetchall()
    monthly_data = [{"month": m["month"], "count": m["count"]} for m in monthly]
    monthly_data.reverse()

    # 6) Average response time (admin reply after contact message)
    avg_resp = conn.execute("""
        SELECT AVG(
            CAST((julianday(admin_msg.created_at) - julianday(contact_msg.created_at)) * 86400 AS REAL)
        ) AS avg_seconds
        FROM messages contact_msg
        JOIN messages admin_msg ON admin_msg.conversation_id = contact_msg.conversation_id
            AND admin_msg.sender_type IN ('admin', 'ai')
            AND admin_msg.created_at > contact_msg.created_at
            AND admin_msg.id = (
                SELECT MIN(am2.id) FROM messages am2
                WHERE am2.conversation_id = contact_msg.conversation_id
                AND am2.sender_type IN ('admin', 'ai')
                AND am2.created_at > contact_msg.created_at
            )
        WHERE contact_msg.org_id = ? AND contact_msg.sender_type = 'contact'
    """, (org_id,)).fetchone()
    avg_response_seconds = avg_resp["avg_seconds"] if avg_resp and avg_resp["avg_seconds"] else 0

    conn.close()

    return jsonify({
        "hourly_activity": {str(h): hourly_data.get(h, 0) for h in range(24)},
        "daily_activity": daily_data,
        "top_contacts": top_contacts_data,
        "product_categories": category_counts,
        "monthly_trend": monthly_data,
        "avg_response_time_seconds": round(avg_response_seconds, 1),
    })
