"""
Channel management service - handles CRUD and credential verification.
"""

import requests
from messaging.utils.encryption import encrypt_json, decrypt_json, mask_secret
from messaging_db import (
    create_channel, get_channel, get_channels_for_org, update_channel,
    delete_channel, set_channel_credentials, get_channel_credentials,
    update_channel_verified,
)

CHANNEL_TYPES = {
    "line": {
        "label": "LINE",
        "credential_fields": [
            {"key": "channel_access_token", "label": "Channel Access Token", "type": "password"},
            {"key": "channel_secret", "label": "Channel Secret", "type": "password"},
        ],
    },
    "facebook": {
        "label": "Facebook Messenger",
        "credential_fields": [
            {"key": "page_access_token", "label": "Page Access Token", "type": "password"},
            {"key": "app_secret", "label": "App Secret", "type": "password"},
            {"key": "page_id", "label": "Page ID", "type": "text"},
            {"key": "verify_token", "label": "Verify Token (for webhook)", "type": "text"},
        ],
    },
    "instagram": {
        "label": "Instagram",
        "credential_fields": [
            {"key": "access_token", "label": "Access Token", "type": "password"},
            {"key": "app_secret", "label": "App Secret", "type": "password"},
            {"key": "instagram_account_id", "label": "Instagram Account ID", "type": "text"},
        ],
    },
}


def save_credentials(channel_id, channel_type, credentials: dict):
    """Encrypt and store channel credentials."""
    encrypted = encrypt_json(credentials)
    credential_type = f"{channel_type}_api"
    set_channel_credentials(channel_id, encrypted, credential_type)


def load_credentials(channel_id) -> dict | None:
    """Load and decrypt channel credentials."""
    cred = get_channel_credentials(channel_id)
    if not cred:
        return None
    return decrypt_json(cred["encrypted_credentials"])


def get_masked_credentials(channel_id) -> dict | None:
    """Get credentials with values masked for display."""
    creds = load_credentials(channel_id)
    if not creds:
        return None
    masked = {}
    for key, value in creds.items():
        if "token" in key.lower() or "secret" in key.lower() or "key" in key.lower():
            masked[key] = mask_secret(value)
        else:
            masked[key] = value
    return masked


def verify_channel_connection(channel_id) -> tuple[bool, str]:
    """Test if channel credentials are valid by making a lightweight API call."""
    channel = get_channel(channel_id)
    if not channel:
        return False, "Channel not found"

    creds = load_credentials(channel_id)
    if not creds:
        return False, "No credentials configured"

    try:
        if channel["channel_type"] == "line":
            return _verify_line(channel_id, creds)
        elif channel["channel_type"] == "facebook":
            return _verify_facebook(creds)
        elif channel["channel_type"] == "instagram":
            return _verify_instagram(creds)
        else:
            return False, f"Unknown channel type: {channel['channel_type']}"
    except Exception as e:
        return False, f"Connection error: {str(e)}"


def _verify_line(channel_id, creds):
    token = creds.get("channel_access_token", "")
    resp = requests.get(
        "https://api.line.me/v2/bot/info",
        headers={"Authorization": f"Bearer {token}"},
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        update_channel_verified(channel_id)
        return True, f"Connected to LINE Bot: {data.get('displayName', 'Unknown')}"
    return False, f"LINE API error: {resp.status_code} - {resp.text}"


def _verify_facebook(creds):
    token = creds.get("page_access_token", "")
    page_id = creds.get("page_id", "me")
    resp = requests.get(
        f"https://graph.facebook.com/v18.0/{page_id}",
        params={"access_token": token, "fields": "name,id"},
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        return True, f"Connected to Facebook Page: {data.get('name', 'Unknown')}"
    return False, f"Facebook API error: {resp.status_code} - {resp.text}"


def _verify_instagram(creds):
    token = creds.get("access_token", "")
    ig_id = creds.get("instagram_account_id", "me")
    resp = requests.get(
        f"https://graph.facebook.com/v18.0/{ig_id}",
        params={"access_token": token, "fields": "name,username"},
        timeout=10,
    )
    if resp.status_code == 200:
        data = resp.json()
        return True, f"Connected to Instagram: @{data.get('username', 'Unknown')}"
    return False, f"Instagram API error: {resp.status_code} - {resp.text}"
