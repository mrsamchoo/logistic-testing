"""
AI service - abstraction over multiple AI providers for response suggestions.
"""

import json
import requests
from messaging.utils.encryption import decrypt_json
from messaging_db import get_ai_provider, get_default_ai_provider


AI_PROVIDERS = {
    "openai": {
        "label": "OpenAI",
        "models": ["gpt-4o", "gpt-4o-mini", "gpt-4-turbo", "gpt-3.5-turbo"],
        "default_model": "gpt-4o-mini",
    },
    "anthropic": {
        "label": "Anthropic (Claude)",
        "models": ["claude-sonnet-4-20250514", "claude-haiku-4-5-20251001", "claude-opus-4-20250514"],
        "default_model": "claude-sonnet-4-20250514",
    },
    "google_gemini": {
        "label": "Google Gemini",
        "models": ["gemini-2.0-flash", "gemini-1.5-pro", "gemini-1.5-flash"],
        "default_model": "gemini-2.0-flash",
    },
}

DEFAULT_SYSTEM_PROMPT = """You are a helpful customer service assistant.
Respond to the customer's message in a professional and friendly manner.
If the conversation is in Thai, reply in Thai. If in English, reply in English.
Keep responses concise and helpful."""


def generate_suggestion(org_id, conversation_messages, custom_system_prompt=None, provider_id=None):
    """Generate an AI response suggestion based on conversation context.

    Returns (success, suggestion_text_or_error)
    """
    if provider_id:
        provider = get_ai_provider(provider_id)
    else:
        provider = get_default_ai_provider(org_id)

    if not provider:
        return False, "No AI provider configured. Go to Settings > AI to add one."

    api_key = decrypt_json(provider["encrypted_api_key"]).get("api_key", "")
    if not api_key:
        return False, "AI provider API key is invalid."

    system_prompt = custom_system_prompt or provider["system_prompt"] or DEFAULT_SYSTEM_PROMPT
    model = provider["model_name"] or AI_PROVIDERS.get(provider["provider_type"], {}).get("default_model", "")
    max_tokens = provider["max_tokens"] or 500
    temperature = provider["temperature"] if provider["temperature"] is not None else 0.7

    # Build messages from conversation context
    messages = _build_context_messages(conversation_messages, system_prompt)

    try:
        if provider["provider_type"] == "openai":
            return _call_openai(api_key, model, messages, system_prompt, max_tokens, temperature)
        elif provider["provider_type"] == "anthropic":
            return _call_anthropic(api_key, model, messages, system_prompt, max_tokens, temperature)
        elif provider["provider_type"] == "google_gemini":
            return _call_gemini(api_key, model, messages, system_prompt, max_tokens, temperature)
        else:
            return False, f"Unknown provider type: {provider['provider_type']}"
    except requests.Timeout:
        return False, "AI request timed out. Please try again."
    except Exception as e:
        return False, f"AI error: {str(e)}"


def test_api_key(provider_type, api_key) -> tuple[bool, str]:
    """Test if an API key is valid."""
    try:
        if provider_type == "openai":
            resp = requests.get(
                "https://api.openai.com/v1/models",
                headers={"Authorization": f"Bearer {api_key}"},
                timeout=10,
            )
            return resp.status_code == 200, "Valid" if resp.status_code == 200 else f"Error: {resp.status_code}"

        elif provider_type == "anthropic":
            resp = requests.post(
                "https://api.anthropic.com/v1/messages",
                headers={
                    "x-api-key": api_key,
                    "anthropic-version": "2023-06-01",
                    "content-type": "application/json",
                },
                json={
                    "model": "claude-haiku-4-5-20251001",
                    "max_tokens": 10,
                    "messages": [{"role": "user", "content": "Hi"}],
                },
                timeout=10,
            )
            return resp.status_code == 200, "Valid" if resp.status_code == 200 else f"Error: {resp.status_code}"

        elif provider_type == "google_gemini":
            resp = requests.get(
                f"https://generativelanguage.googleapis.com/v1beta/models?key={api_key}",
                timeout=10,
            )
            return resp.status_code == 200, "Valid" if resp.status_code == 200 else f"Error: {resp.status_code}"

        return False, "Unknown provider"
    except Exception as e:
        return False, str(e)


def _build_context_messages(conversation_messages, system_prompt):
    """Convert DB messages to chat format."""
    chat_messages = []
    for msg in conversation_messages[-15:]:  # Last 15 messages for context
        role = "assistant" if msg["sender_type"] in ("admin", "ai") else "user"
        chat_messages.append({"role": role, "content": msg["content"]})
    return chat_messages


def _call_openai(api_key, model, messages, system_prompt, max_tokens, temperature):
    resp = requests.post(
        "https://api.openai.com/v1/chat/completions",
        headers={
            "Authorization": f"Bearer {api_key}",
            "Content-Type": "application/json",
        },
        json={
            "model": model,
            "messages": [{"role": "system", "content": system_prompt}] + messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=30,
    )
    if resp.status_code == 200:
        data = resp.json()
        return True, data["choices"][0]["message"]["content"]
    return False, f"OpenAI error: {resp.status_code} - {resp.text[:200]}"


def _call_anthropic(api_key, model, messages, system_prompt, max_tokens, temperature):
    resp = requests.post(
        "https://api.anthropic.com/v1/messages",
        headers={
            "x-api-key": api_key,
            "anthropic-version": "2023-06-01",
            "content-type": "application/json",
        },
        json={
            "model": model,
            "system": system_prompt,
            "messages": messages,
            "max_tokens": max_tokens,
            "temperature": temperature,
        },
        timeout=30,
    )
    if resp.status_code == 200:
        data = resp.json()
        return True, data["content"][0]["text"]
    return False, f"Anthropic error: {resp.status_code} - {resp.text[:200]}"


def _call_gemini(api_key, model, messages, system_prompt, max_tokens, temperature):
    # Convert to Gemini format
    contents = []
    for msg in messages:
        role = "user" if msg["role"] == "user" else "model"
        contents.append({"role": role, "parts": [{"text": msg["content"]}]})

    resp = requests.post(
        f"https://generativelanguage.googleapis.com/v1beta/models/{model}:generateContent?key={api_key}",
        headers={"Content-Type": "application/json"},
        json={
            "contents": contents,
            "systemInstruction": {"parts": [{"text": system_prompt}]},
            "generationConfig": {
                "maxOutputTokens": max_tokens,
                "temperature": temperature,
            },
        },
        timeout=30,
    )
    if resp.status_code == 200:
        data = resp.json()
        candidates = data.get("candidates", [])
        if candidates:
            return True, candidates[0]["content"]["parts"][0]["text"]
        return False, "No response generated"
    return False, f"Gemini error: {resp.status_code} - {resp.text[:200]}"
