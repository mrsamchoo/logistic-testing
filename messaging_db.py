"""
Database layer for the messaging platform.
All messaging-related tables and queries live here.
"""

import json
from datetime import datetime
from database import get_db


# ============================================================
# Schema Initialization
# ============================================================


def init_messaging_db():
    """Create all messaging tables and run migrations."""
    conn = get_db()

    conn.execute("""
        CREATE TABLE IF NOT EXISTS organizations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            name TEXT NOT NULL,
            slug TEXT UNIQUE NOT NULL,
            plan TEXT NOT NULL DEFAULT 'free',
            max_channels INTEGER DEFAULT 3,
            max_admins INTEGER DEFAULT 5,
            settings_json TEXT DEFAULT '{}',
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS channels (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            channel_type TEXT NOT NULL,
            name TEXT NOT NULL,
            is_active INTEGER DEFAULT 1,
            config_json TEXT DEFAULT '{}',
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS channel_credentials (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            channel_id INTEGER NOT NULL UNIQUE,
            encrypted_credentials TEXT NOT NULL,
            credential_type TEXT NOT NULL,
            last_verified_at TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (channel_id) REFERENCES channels(id) ON DELETE CASCADE
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS ai_providers (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            provider_type TEXT NOT NULL,
            name TEXT NOT NULL,
            encrypted_api_key TEXT NOT NULL,
            model_name TEXT DEFAULT '',
            is_default INTEGER DEFAULT 0,
            system_prompt TEXT DEFAULT '',
            max_tokens INTEGER DEFAULT 500,
            temperature REAL DEFAULT 0.7,
            is_active INTEGER DEFAULT 1,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS contacts (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            platform_user_id TEXT NOT NULL,
            display_name TEXT DEFAULT '',
            avatar_url TEXT DEFAULT '',
            email TEXT DEFAULT '',
            phone TEXT DEFAULT '',
            customer_code TEXT DEFAULT '',
            tags_json TEXT DEFAULT '[]',
            notes TEXT DEFAULT '',
            custom_fields_json TEXT DEFAULT '{}',
            first_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            last_seen_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            UNIQUE(channel_id, platform_user_id),
            FOREIGN KEY (org_id) REFERENCES organizations(id),
            FOREIGN KEY (channel_id) REFERENCES channels(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversations (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            channel_id INTEGER NOT NULL,
            contact_id INTEGER NOT NULL,
            status TEXT NOT NULL DEFAULT 'open',
            assigned_admin_id INTEGER DEFAULT NULL,
            priority TEXT DEFAULT 'normal',
            subject TEXT DEFAULT '',
            last_message_at TIMESTAMP DEFAULT NULL,
            last_message_preview TEXT DEFAULT '',
            unread_count INTEGER DEFAULT 0,
            resolved_at TIMESTAMP DEFAULT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            updated_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id),
            FOREIGN KEY (channel_id) REFERENCES channels(id),
            FOREIGN KEY (contact_id) REFERENCES contacts(id),
            FOREIGN KEY (assigned_admin_id) REFERENCES admins(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messages (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            conversation_id INTEGER NOT NULL,
            org_id INTEGER NOT NULL,
            sender_type TEXT NOT NULL,
            sender_id TEXT DEFAULT '',
            message_type TEXT NOT NULL DEFAULT 'text',
            content TEXT NOT NULL DEFAULT '',
            metadata_json TEXT DEFAULT '{}',
            platform_message_id TEXT DEFAULT '',
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id),
            FOREIGN KEY (org_id) REFERENCES organizations(id)
        )
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_conversation
        ON messages(conversation_id, created_at)
    """)

    conn.execute("""
        CREATE INDEX IF NOT EXISTS idx_messages_platform_id
        ON messages(platform_message_id)
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS message_templates (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            name TEXT NOT NULL,
            category TEXT DEFAULT 'general',
            content TEXT NOT NULL,
            shortcut TEXT DEFAULT '',
            is_active INTEGER DEFAULT 1,
            usage_count INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS conversation_tags (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            conversation_id INTEGER NOT NULL,
            tag TEXT NOT NULL,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (conversation_id) REFERENCES conversations(id),
            UNIQUE(conversation_id, tag)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS admin_notifications (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            admin_id INTEGER NOT NULL,
            notification_type TEXT NOT NULL,
            title TEXT NOT NULL,
            body TEXT DEFAULT '',
            reference_type TEXT DEFAULT '',
            reference_id INTEGER DEFAULT NULL,
            is_read INTEGER DEFAULT 0,
            created_at TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
            FOREIGN KEY (org_id) REFERENCES organizations(id),
            FOREIGN KEY (admin_id) REFERENCES admins(id)
        )
    """)

    conn.execute("""
        CREATE TABLE IF NOT EXISTS messaging_analytics (
            id INTEGER PRIMARY KEY AUTOINCREMENT,
            org_id INTEGER NOT NULL,
            channel_id INTEGER DEFAULT NULL,
            date TEXT NOT NULL,
            messages_received INTEGER DEFAULT 0,
            messages_sent INTEGER DEFAULT 0,
            new_conversations INTEGER DEFAULT 0,
            resolved_conversations INTEGER DEFAULT 0,
            avg_response_time_seconds REAL DEFAULT 0,
            active_contacts INTEGER DEFAULT 0,
            UNIQUE(org_id, channel_id, date),
            FOREIGN KEY (org_id) REFERENCES organizations(id)
        )
    """)

    # --- Migrations for admins table ---
    admin_columns = [row[1] for row in conn.execute("PRAGMA table_info(admins)").fetchall()]
    if "org_id" not in admin_columns:
        conn.execute("ALTER TABLE admins ADD COLUMN org_id INTEGER DEFAULT NULL")
    if "display_name" not in admin_columns:
        conn.execute("ALTER TABLE admins ADD COLUMN display_name TEXT DEFAULT ''")
    if "avatar_url" not in admin_columns:
        conn.execute("ALTER TABLE admins ADD COLUMN avatar_url TEXT DEFAULT ''")

    # --- Create default organization and assign existing admins ---
    default_org = conn.execute("SELECT id FROM organizations WHERE slug = 'default'").fetchone()
    if not default_org:
        conn.execute(
            "INSERT INTO organizations (name, slug, plan) VALUES (?, ?, ?)",
            ("Default Organization", "default", "pro"),
        )
        default_org_id = conn.execute("SELECT last_insert_rowid()").fetchone()[0]
        conn.execute("UPDATE admins SET org_id = ? WHERE org_id IS NULL", (default_org_id,))
    else:
        default_org_id = default_org[0]
        conn.execute("UPDATE admins SET org_id = ? WHERE org_id IS NULL", (default_org_id,))

    # --- Migration for conversations table ---
    conv_columns = [row[1] for row in conn.execute("PRAGMA table_info(conversations)").fetchall()]
    if "is_pinned" not in conv_columns:
        conn.execute("ALTER TABLE conversations ADD COLUMN is_pinned INTEGER DEFAULT 0")

    conn.commit()
    conn.close()


# ============================================================
# Organization Operations
# ============================================================


def get_org_by_id(org_id):
    conn = get_db()
    org = conn.execute("SELECT * FROM organizations WHERE id = ?", (org_id,)).fetchone()
    conn.close()
    return org


def get_admin_org_id(admin_id):
    """Get the org_id for an admin."""
    conn = get_db()
    admin = conn.execute("SELECT org_id FROM admins WHERE id = ?", (admin_id,)).fetchone()
    conn.close()
    return admin["org_id"] if admin else None


def update_org(org_id, **fields):
    allowed = {"name", "plan", "max_channels", "max_admins", "settings_json"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [org_id]
    conn = get_db()
    conn.execute(f"UPDATE organizations SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
    conn.commit()
    conn.close()


# ============================================================
# Channel Operations
# ============================================================


def create_channel(org_id, channel_type, name):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO channels (org_id, channel_type, name) VALUES (?, ?, ?)",
        (org_id, channel_type, name),
    )
    channel_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return channel_id


def get_channel(channel_id):
    conn = get_db()
    channel = conn.execute("SELECT * FROM channels WHERE id = ?", (channel_id,)).fetchone()
    conn.close()
    return channel


def get_channels_for_org(org_id):
    conn = get_db()
    channels = conn.execute(
        "SELECT * FROM channels WHERE org_id = ? ORDER BY created_at DESC",
        (org_id,),
    ).fetchall()
    conn.close()
    return channels


def update_channel(channel_id, **fields):
    allowed = {"name", "channel_type", "is_active", "config_json"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [channel_id]
    conn = get_db()
    conn.execute(f"UPDATE channels SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_channel(channel_id):
    conn = get_db()
    conn.execute("DELETE FROM channel_credentials WHERE channel_id = ?", (channel_id,))
    conn.execute("DELETE FROM channels WHERE id = ?", (channel_id,))
    conn.commit()
    conn.close()


def set_channel_credentials(channel_id, encrypted_creds, credential_type):
    conn = get_db()
    existing = conn.execute("SELECT id FROM channel_credentials WHERE channel_id = ?", (channel_id,)).fetchone()
    if existing:
        conn.execute(
            "UPDATE channel_credentials SET encrypted_credentials = ?, credential_type = ?, updated_at = CURRENT_TIMESTAMP WHERE channel_id = ?",
            (encrypted_creds, credential_type, channel_id),
        )
    else:
        conn.execute(
            "INSERT INTO channel_credentials (channel_id, encrypted_credentials, credential_type) VALUES (?, ?, ?)",
            (channel_id, encrypted_creds, credential_type),
        )
    conn.commit()
    conn.close()


def get_channel_credentials(channel_id):
    conn = get_db()
    cred = conn.execute("SELECT * FROM channel_credentials WHERE channel_id = ?", (channel_id,)).fetchone()
    conn.close()
    return cred


def update_channel_verified(channel_id):
    conn = get_db()
    conn.execute(
        "UPDATE channel_credentials SET last_verified_at = CURRENT_TIMESTAMP WHERE channel_id = ?",
        (channel_id,),
    )
    conn.commit()
    conn.close()


# ============================================================
# AI Provider Operations
# ============================================================


def create_ai_provider(org_id, provider_type, name, encrypted_api_key, model_name="",
                       system_prompt="", max_tokens=500, temperature=0.7, is_default=0):
    conn = get_db()
    if is_default:
        conn.execute("UPDATE ai_providers SET is_default = 0 WHERE org_id = ?", (org_id,))
    cursor = conn.execute(
        """INSERT INTO ai_providers
           (org_id, provider_type, name, encrypted_api_key, model_name,
            system_prompt, max_tokens, temperature, is_default)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)""",
        (org_id, provider_type, name, encrypted_api_key, model_name,
         system_prompt, max_tokens, temperature, is_default),
    )
    provider_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return provider_id


def get_ai_providers_for_org(org_id):
    conn = get_db()
    providers = conn.execute(
        "SELECT * FROM ai_providers WHERE org_id = ? ORDER BY is_default DESC, created_at DESC",
        (org_id,),
    ).fetchall()
    conn.close()
    return providers


def get_ai_provider(provider_id):
    conn = get_db()
    provider = conn.execute("SELECT * FROM ai_providers WHERE id = ?", (provider_id,)).fetchone()
    conn.close()
    return provider


def get_default_ai_provider(org_id):
    conn = get_db()
    provider = conn.execute(
        "SELECT * FROM ai_providers WHERE org_id = ? AND is_default = 1 AND is_active = 1",
        (org_id,),
    ).fetchone()
    if not provider:
        provider = conn.execute(
            "SELECT * FROM ai_providers WHERE org_id = ? AND is_active = 1 ORDER BY created_at LIMIT 1",
            (org_id,),
        ).fetchone()
    conn.close()
    return provider


def update_ai_provider(provider_id, **fields):
    allowed = {"name", "provider_type", "encrypted_api_key", "model_name",
               "system_prompt", "max_tokens", "temperature", "is_default", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    conn = get_db()
    if updates.get("is_default"):
        provider = conn.execute("SELECT org_id FROM ai_providers WHERE id = ?", (provider_id,)).fetchone()
        if provider:
            conn.execute("UPDATE ai_providers SET is_default = 0 WHERE org_id = ?", (provider["org_id"],))
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [provider_id]
    conn.execute(f"UPDATE ai_providers SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_ai_provider(provider_id):
    conn = get_db()
    conn.execute("DELETE FROM ai_providers WHERE id = ?", (provider_id,))
    conn.commit()
    conn.close()


# ============================================================
# Contact Operations
# ============================================================


def find_or_create_contact(org_id, channel_id, platform_user_id, display_name="", avatar_url=""):
    conn = get_db()
    contact = conn.execute(
        "SELECT * FROM contacts WHERE channel_id = ? AND platform_user_id = ?",
        (channel_id, platform_user_id),
    ).fetchone()
    if contact:
        conn.execute(
            "UPDATE contacts SET last_seen_at = CURRENT_TIMESTAMP, display_name = COALESCE(NULLIF(?, ''), display_name), avatar_url = COALESCE(NULLIF(?, ''), avatar_url) WHERE id = ?",
            (display_name, avatar_url, contact["id"]),
        )
        conn.commit()
        contact_id = contact["id"]
    else:
        cursor = conn.execute(
            "INSERT INTO contacts (org_id, channel_id, platform_user_id, display_name, avatar_url) VALUES (?, ?, ?, ?, ?)",
            (org_id, channel_id, platform_user_id, display_name, avatar_url),
        )
        contact_id = cursor.lastrowid
        conn.commit()
    conn.close()
    return contact_id


def get_contact(contact_id):
    conn = get_db()
    contact = conn.execute("SELECT * FROM contacts WHERE id = ?", (contact_id,)).fetchone()
    conn.close()
    return contact


def get_contacts_for_org(org_id, search=None, limit=50, offset=0):
    conn = get_db()
    query = "SELECT * FROM contacts WHERE org_id = ?"
    params = [org_id]
    if search:
        query += " AND (display_name LIKE ? OR platform_user_id LIKE ? OR customer_code LIKE ? OR email LIKE ?)"
        term = f"%{search}%"
        params.extend([term, term, term, term])
    query += " ORDER BY last_seen_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    contacts = conn.execute(query, params).fetchall()
    conn.close()
    return contacts


def update_contact(contact_id, **fields):
    allowed = {"display_name", "email", "phone", "customer_code", "tags_json", "notes", "custom_fields_json"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [contact_id]
    conn = get_db()
    conn.execute(f"UPDATE contacts SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


# ============================================================
# Conversation Operations
# ============================================================


def find_or_create_conversation(org_id, channel_id, contact_id):
    conn = get_db()
    conv = conn.execute(
        "SELECT * FROM conversations WHERE contact_id = ? AND status IN ('open', 'assigned') ORDER BY created_at DESC LIMIT 1",
        (contact_id,),
    ).fetchone()
    if conv:
        conv_id = conv["id"]
    else:
        cursor = conn.execute(
            "INSERT INTO conversations (org_id, channel_id, contact_id) VALUES (?, ?, ?)",
            (org_id, channel_id, contact_id),
        )
        conv_id = cursor.lastrowid
        conn.commit()
    conn.close()
    return conv_id


def get_conversation(conversation_id):
    conn = get_db()
    conv = conn.execute(
        """SELECT c.*, ct.display_name AS contact_name, ct.avatar_url AS contact_avatar,
                  ct.platform_user_id, ch.channel_type, ch.name AS channel_name
           FROM conversations c
           JOIN contacts ct ON c.contact_id = ct.id
           JOIN channels ch ON c.channel_id = ch.id
           WHERE c.id = ?""",
        (conversation_id,),
    ).fetchone()
    conn.close()
    return conv


def get_conversations_for_org(org_id, status=None, channel_id=None, assigned_admin_id=None,
                               search=None, limit=50, offset=0):
    conn = get_db()
    query = """SELECT c.*, ct.display_name AS contact_name, ct.avatar_url AS contact_avatar,
                      ct.platform_user_id, ch.channel_type, ch.name AS channel_name,
                      a.username AS assigned_admin_name
               FROM conversations c
               JOIN contacts ct ON c.contact_id = ct.id
               JOIN channels ch ON c.channel_id = ch.id
               LEFT JOIN admins a ON c.assigned_admin_id = a.id
               WHERE c.org_id = ?"""
    params = [org_id]
    if status and status != "all":
        query += " AND c.status = ?"
        params.append(status)
    if channel_id:
        query += " AND c.channel_id = ?"
        params.append(channel_id)
    if assigned_admin_id:
        query += " AND c.assigned_admin_id = ?"
        params.append(assigned_admin_id)
    if search:
        term = f"%{search}%"
        query += " AND (ct.display_name LIKE ? OR c.last_message_preview LIKE ? OR ct.platform_user_id LIKE ?)"
        params.extend([term, term, term])
    query += " ORDER BY c.is_pinned DESC, CASE c.priority WHEN 'urgent' THEN 0 WHEN 'high' THEN 1 ELSE 2 END, c.last_message_at DESC NULLS LAST, c.created_at DESC LIMIT ? OFFSET ?"
    params.extend([limit, offset])
    conversations = conn.execute(query, params).fetchall()
    conn.close()
    return conversations


def update_conversation(conversation_id, **fields):
    allowed = {"status", "assigned_admin_id", "priority", "subject", "last_message_at",
               "last_message_preview", "unread_count", "resolved_at", "is_pinned"}
    updates = {k: v for k, v in fields.items() if k in allowed}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [conversation_id]
    conn = get_db()
    conn.execute(f"UPDATE conversations SET {set_clause}, updated_at = CURRENT_TIMESTAMP WHERE id = ?", values)
    conn.commit()
    conn.close()


# ============================================================
# Message Operations
# ============================================================


def add_message(conversation_id, org_id, sender_type, content, sender_id="",
                message_type="text", metadata_json="{}", platform_message_id=""):
    conn = get_db()
    # Check for duplicate platform message
    if platform_message_id:
        existing = conn.execute(
            "SELECT id FROM messages WHERE platform_message_id = ? AND conversation_id = ?",
            (platform_message_id, conversation_id),
        ).fetchone()
        if existing:
            conn.close()
            return existing["id"]
    cursor = conn.execute(
        """INSERT INTO messages
           (conversation_id, org_id, sender_type, sender_id, message_type, content, metadata_json, platform_message_id)
           VALUES (?, ?, ?, ?, ?, ?, ?, ?)""",
        (conversation_id, org_id, sender_type, sender_id, message_type, content, metadata_json, platform_message_id),
    )
    message_id = cursor.lastrowid
    # Update conversation
    preview = content[:100] if content else ""
    conn.execute(
        """UPDATE conversations SET last_message_at = CURRENT_TIMESTAMP, last_message_preview = ?,
           unread_count = CASE WHEN ? = 'contact' THEN unread_count + 1 ELSE unread_count END,
           updated_at = CURRENT_TIMESTAMP WHERE id = ?""",
        (preview, sender_type, conversation_id),
    )
    conn.commit()
    conn.close()
    return message_id


def get_messages_for_conversation(conversation_id, limit=50, offset=0, before_id=None):
    conn = get_db()
    if before_id:
        # Cursor-based: get messages older than before_id, return in ASC order
        messages = conn.execute(
            """SELECT * FROM (
                 SELECT m.*, a.username AS admin_username, a.display_name AS admin_display_name
                 FROM messages m
                 LEFT JOIN admins a ON m.sender_type = 'admin' AND CAST(m.sender_id AS INTEGER) = a.id
                 WHERE m.conversation_id = ? AND m.id < ?
                 ORDER BY m.created_at DESC
                 LIMIT ?
               ) sub ORDER BY sub.created_at ASC""",
            (conversation_id, before_id, limit),
        ).fetchall()
    else:
        # Default: get the NEWEST N messages, returned in ASC order for display
        messages = conn.execute(
            """SELECT * FROM (
                 SELECT m.*, a.username AS admin_username, a.display_name AS admin_display_name
                 FROM messages m
                 LEFT JOIN admins a ON m.sender_type = 'admin' AND CAST(m.sender_id AS INTEGER) = a.id
                 WHERE m.conversation_id = ?
                 ORDER BY m.created_at DESC
                 LIMIT ? OFFSET ?
               ) sub ORDER BY sub.created_at ASC""",
            (conversation_id, limit, offset),
        ).fetchall()
    conn.close()
    return messages


def get_message_count(conversation_id):
    """Get total message count for a conversation."""
    conn = get_db()
    count = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE conversation_id = ?",
        (conversation_id,),
    ).fetchone()[0]
    conn.close()
    return count


def mark_messages_read(conversation_id):
    conn = get_db()
    conn.execute(
        "UPDATE messages SET is_read = 1 WHERE conversation_id = ? AND is_read = 0",
        (conversation_id,),
    )
    conn.execute(
        "UPDATE conversations SET unread_count = 0 WHERE id = ?",
        (conversation_id,),
    )
    conn.commit()
    conn.close()


# ============================================================
# Template Operations
# ============================================================


def create_template(org_id, name, content, category="general", shortcut=""):
    conn = get_db()
    cursor = conn.execute(
        "INSERT INTO message_templates (org_id, name, content, category, shortcut) VALUES (?, ?, ?, ?, ?)",
        (org_id, name, content, category, shortcut),
    )
    template_id = cursor.lastrowid
    conn.commit()
    conn.close()
    return template_id


def get_templates_for_org(org_id, category=None):
    conn = get_db()
    if category:
        templates = conn.execute(
            "SELECT * FROM message_templates WHERE org_id = ? AND category = ? AND is_active = 1 ORDER BY usage_count DESC",
            (org_id, category),
        ).fetchall()
    else:
        templates = conn.execute(
            "SELECT * FROM message_templates WHERE org_id = ? AND is_active = 1 ORDER BY usage_count DESC",
            (org_id,),
        ).fetchall()
    conn.close()
    return templates


def update_template(template_id, **fields):
    allowed = {"name", "content", "category", "shortcut", "is_active"}
    updates = {k: v for k, v in fields.items() if k in allowed and v is not None}
    if not updates:
        return
    set_clause = ", ".join(f"{k} = ?" for k in updates)
    values = list(updates.values()) + [template_id]
    conn = get_db()
    conn.execute(f"UPDATE message_templates SET {set_clause} WHERE id = ?", values)
    conn.commit()
    conn.close()


def delete_template(template_id):
    conn = get_db()
    conn.execute("DELETE FROM message_templates WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()


def increment_template_usage(template_id):
    conn = get_db()
    conn.execute("UPDATE message_templates SET usage_count = usage_count + 1 WHERE id = ?", (template_id,))
    conn.commit()
    conn.close()


# ============================================================
# Tag Operations
# ============================================================


def add_conversation_tag(conversation_id, org_id, tag):
    conn = get_db()
    try:
        conn.execute(
            "INSERT INTO conversation_tags (conversation_id, org_id, tag) VALUES (?, ?, ?)",
            (conversation_id, org_id, tag),
        )
        conn.commit()
    except Exception:
        pass  # Duplicate tag
    conn.close()


def remove_conversation_tag(conversation_id, tag):
    conn = get_db()
    conn.execute(
        "DELETE FROM conversation_tags WHERE conversation_id = ? AND tag = ?",
        (conversation_id, tag),
    )
    conn.commit()
    conn.close()


def get_conversation_tags(conversation_id):
    conn = get_db()
    tags = conn.execute(
        "SELECT tag FROM conversation_tags WHERE conversation_id = ? ORDER BY tag",
        (conversation_id,),
    ).fetchall()
    conn.close()
    return [t["tag"] for t in tags]


# ============================================================
# Notification Operations
# ============================================================


def create_notification(org_id, admin_id, notification_type, title, body="",
                        reference_type="", reference_id=None):
    conn = get_db()
    conn.execute(
        """INSERT INTO admin_notifications
           (org_id, admin_id, notification_type, title, body, reference_type, reference_id)
           VALUES (?, ?, ?, ?, ?, ?, ?)""",
        (org_id, admin_id, notification_type, title, body, reference_type, reference_id),
    )
    conn.commit()
    conn.close()


def get_notifications(admin_id, unread_only=False, limit=20):
    conn = get_db()
    query = "SELECT * FROM admin_notifications WHERE admin_id = ?"
    params = [admin_id]
    if unread_only:
        query += " AND is_read = 0"
    query += " ORDER BY created_at DESC LIMIT ?"
    params.append(limit)
    notifications = conn.execute(query, params).fetchall()
    conn.close()
    return notifications


def mark_notification_read(notification_id):
    conn = get_db()
    conn.execute("UPDATE admin_notifications SET is_read = 1 WHERE id = ?", (notification_id,))
    conn.commit()
    conn.close()


def mark_all_notifications_read(admin_id):
    conn = get_db()
    conn.execute("UPDATE admin_notifications SET is_read = 1 WHERE admin_id = ? AND is_read = 0", (admin_id,))
    conn.commit()
    conn.close()


# ============================================================
# Analytics Operations
# ============================================================


def get_messaging_overview(org_id, days=30):
    conn = get_db()
    stats = {}
    stats["total_conversations"] = conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE org_id = ?", (org_id,)
    ).fetchone()[0]
    stats["open_conversations"] = conn.execute(
        "SELECT COUNT(*) FROM conversations WHERE org_id = ? AND status IN ('open', 'assigned')", (org_id,)
    ).fetchone()[0]
    stats["total_messages"] = conn.execute(
        "SELECT COUNT(*) FROM messages WHERE org_id = ?", (org_id,)
    ).fetchone()[0]
    stats["total_contacts"] = conn.execute(
        "SELECT COUNT(*) FROM contacts WHERE org_id = ?", (org_id,)
    ).fetchone()[0]
    stats["channels"] = conn.execute(
        "SELECT COUNT(*) FROM channels WHERE org_id = ? AND is_active = 1", (org_id,)
    ).fetchone()[0]
    stats["unread_messages"] = conn.execute(
        "SELECT SUM(unread_count) FROM conversations WHERE org_id = ?", (org_id,)
    ).fetchone()[0] or 0
    conn.close()
    return stats


def get_org_admins(org_id):
    conn = get_db()
    admins = conn.execute(
        "SELECT id, username, role, display_name, avatar_url, created_at FROM admins WHERE org_id = ? ORDER BY created_at",
        (org_id,),
    ).fetchall()
    conn.close()
    return admins
