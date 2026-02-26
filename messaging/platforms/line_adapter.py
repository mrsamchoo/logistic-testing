"""
LINE Messaging API adapter.
"""

import hashlib
import hmac
import base64
import json
import requests
from messaging.platforms.base import BasePlatformAdapter


class LineAdapter(BasePlatformAdapter):

    def send_message(self, recipient_id, message_type="text", content="", media_url=""):
        token = self.credentials.get("channel_access_token", "")

        if message_type == "image" and media_url:
            payload = {
                "to": recipient_id,
                "messages": [{"type": "image", "originalContentUrl": media_url, "previewImageUrl": media_url}],
            }
        elif message_type == "video" and media_url:
            # Video requires a preview image — use a placeholder or thumbnail
            payload = {
                "to": recipient_id,
                "messages": [{"type": "video", "originalContentUrl": media_url, "previewImageUrl": media_url.replace('.mp4', '.jpg') if '.mp4' in media_url else media_url}],
            }
        else:
            payload = {
                "to": recipient_id,
                "messages": [{"type": "text", "text": content}],
            }

        resp = requests.post(
            "https://api.line.me/v2/bot/message/push",
            headers={
                "Authorization": f"Bearer {token}",
                "Content-Type": "application/json",
            },
            json=payload,
            timeout=10,
        )

        if resp.status_code == 200:
            return True, ""
        return False, f"LINE error: {resp.status_code} - {resp.text}"

    def verify_webhook(self, request):
        channel_secret = self.credentials.get("channel_secret", "")
        signature = request.headers.get("X-Line-Signature", "")
        body = request.get_data(as_text=True)

        hash_val = hmac.new(
            channel_secret.encode("utf-8"),
            body.encode("utf-8"),
            hashlib.sha256,
        ).digest()
        expected = base64.b64encode(hash_val).decode("utf-8")

        return hmac.compare_digest(signature, expected)

    def parse_webhook(self, request):
        body = request.get_json()
        messages = []

        for event in body.get("events", []):
            if event.get("type") != "message":
                continue

            msg = event.get("message", {})
            source = event.get("source", {})
            user_id = source.get("userId", "")

            message_type = msg.get("type", "text")
            content = ""
            metadata = {}

            if message_type == "text":
                content = msg.get("text", "")
            elif message_type == "image":
                content = "[Image]"
                metadata["message_id"] = msg.get("id", "")
            elif message_type == "video":
                content = "[Video]"
                metadata["message_id"] = msg.get("id", "")
                metadata["duration"] = msg.get("duration", 0)
            elif message_type == "sticker":
                content = "[Sticker]"
                metadata["sticker_id"] = msg.get("stickerId", "")
                metadata["package_id"] = msg.get("packageId", "")
            elif message_type == "location":
                content = f"[Location] {msg.get('title', '')} ({msg.get('latitude')}, {msg.get('longitude')})"
                metadata["latitude"] = msg.get("latitude")
                metadata["longitude"] = msg.get("longitude")
            elif message_type == "file":
                content = f"[File] {msg.get('fileName', '')}"
                metadata["file_name"] = msg.get("fileName", "")
                metadata["file_size"] = msg.get("fileSize", 0)
            else:
                content = f"[{message_type}]"

            messages.append({
                "platform_user_id": user_id,
                "display_name": "",  # Need profile API call to get name
                "avatar_url": "",
                "message_type": message_type if message_type in ("text", "image", "video", "sticker", "location", "file") else "text",
                "content": content,
                "metadata": metadata,
                "platform_message_id": msg.get("id", ""),
            })

        return messages

    def get_user_profile(self, user_id):
        """Fetch LINE user profile."""
        token = self.credentials.get("channel_access_token", "")
        resp = requests.get(
            f"https://api.line.me/v2/bot/profile/{user_id}",
            headers={"Authorization": f"Bearer {token}"},
            timeout=10,
        )
        if resp.status_code == 200:
            data = resp.json()
            return {
                "display_name": data.get("displayName", ""),
                "avatar_url": data.get("pictureUrl", ""),
            }
        return {"display_name": "", "avatar_url": ""}
