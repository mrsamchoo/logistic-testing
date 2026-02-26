"""
Instagram DM API adapter (via Instagram Graph API / Meta Platform).
"""

import hashlib
import hmac
import requests
from messaging.platforms.base import BasePlatformAdapter


class InstagramAdapter(BasePlatformAdapter):

    def send_message(self, recipient_id, message_type="text", content=""):
        token = self.credentials.get("access_token", "")
        ig_id = self.credentials.get("instagram_account_id", "")

        payload = {
            "recipient": {"id": recipient_id},
            "message": {"text": content},
        }

        resp = requests.post(
            f"https://graph.facebook.com/v18.0/{ig_id}/messages",
            params={"access_token": token},
            json=payload,
            timeout=10,
        )

        if resp.status_code == 200:
            data = resp.json()
            return True, data.get("message_id", "")
        return False, f"Instagram error: {resp.status_code} - {resp.text}"

    def verify_webhook(self, request):
        app_secret = self.credentials.get("app_secret", "")
        signature = request.headers.get("X-Hub-Signature-256", "")
        body = request.get_data()

        if not signature.startswith("sha256="):
            return False

        expected = "sha256=" + hmac.new(
            app_secret.encode("utf-8"),
            body,
            hashlib.sha256,
        ).hexdigest()

        return hmac.compare_digest(signature, expected)

    def verify_webhook_challenge(self, request):
        """Handle Instagram webhook verification GET request."""
        verify_token = self.credentials.get("verify_token", self.credentials.get("app_secret", "")[:20])
        mode = request.args.get("hub.mode")
        token = request.args.get("hub.verify_token")
        challenge = request.args.get("hub.challenge")

        if mode == "subscribe" and token == verify_token:
            return challenge
        return None

    def parse_webhook(self, request):
        body = request.get_json()
        messages = []

        for entry in body.get("entry", []):
            for messaging_event in entry.get("messaging", []):
                sender_id = messaging_event.get("sender", {}).get("id", "")
                message = messaging_event.get("message", {})

                if not message:
                    continue

                message_type = "text"
                content = message.get("text", "")
                metadata = {}

                if message.get("attachments"):
                    attachment = message["attachments"][0]
                    att_type = attachment.get("type", "")
                    if att_type == "image":
                        message_type = "image"
                        content = "[Image]"
                        metadata["url"] = attachment.get("payload", {}).get("url", "")
                    elif att_type == "story_mention":
                        message_type = "text"
                        content = "[Story Mention]"
                        metadata["url"] = attachment.get("payload", {}).get("url", "")

                messages.append({
                    "platform_user_id": sender_id,
                    "display_name": "",
                    "avatar_url": "",
                    "message_type": message_type,
                    "content": content,
                    "metadata": metadata,
                    "platform_message_id": message.get("mid", ""),
                })

        return messages
