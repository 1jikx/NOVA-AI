"""
llm_helper.py — Unified LLM helper for Nexis-I (Gemini only).

Used by action modules for text generation tasks:
  - file_processor: summarize/describe files
  - code_helper: review/explain/fix code
  - web_search: synthesize search results
  - computer_settings: natural language parsing
  - etc.

All functions use Gemini 2.5 Flash — no offline fallback.
"""

import json
import sys
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent


def _get_api_key() -> str:
    config_path = _get_base_dir() / "config" / "api_keys.json"
    try:
        with open(config_path, "r", encoding="utf-8") as f:
            return json.load(f)["gemini_api_key"]
    except Exception:
        return ""


def detect_backend() -> str:
    """Always returns "gemini" — online only."""
    return "gemini"


def get_backend() -> str:
    """Always returns "gemini" — online only."""
    return "gemini"


def chat(prompt: str, system_prompt: str = None, temperature: float = 0.7) -> str:
    """Simple text generation using Gemini 2.5 Flash."""
    return _gemini_chat(prompt, system_prompt, temperature)


def _gemini_chat(prompt: str, system_prompt: str = None, temperature: float = 0.7) -> str:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_get_api_key())

    config = types.GenerateContentConfig(
        temperature=temperature,
    )
    if system_prompt:
        config.system_instruction = system_prompt

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=prompt,
        config=config,
    )
    return response.text.strip()


def chat_with_tools(messages: list, tools: list = None) -> dict:
    """Tool-calling chat using Gemini. Returns {"text": str, "tool_calls": list}."""
    return _gemini_chat_with_tools(messages, tools)


def _gemini_chat_with_tools(messages: list, tools: list = None) -> dict:
    from google import genai
    from google.genai import types

    client = genai.Client(api_key=_get_api_key())

    contents = []
    for msg in messages:
        role = msg.get("role", "user")
        if role == "system":
            continue
        gemini_role = "model" if role == "assistant" else "user"
        contents.append(types.Content(
            role=gemini_role,
            parts=[types.Part(text=msg.get("content", ""))]
        ))

    config = types.GenerateContentConfig()
    if tools:
        config.tools = [{"function_declarations": tools}]

    system_prompt = next((m["content"] for m in messages if m.get("role") == "system"), None)
    if system_prompt:
        config.system_instruction = system_prompt

    response = client.models.generate_content(
        model="gemini-2.5-flash",
        contents=contents if contents else "",
        config=config,
    )

    result = {"text": "", "tool_calls": []}

    for part in response.candidates[0].content.parts:
        if hasattr(part, "text") and part.text:
            result["text"] += part.text
        if hasattr(part, "function_call") and part.function_call:
            fc = part.function_call
            result["tool_calls"].append({
                "name": fc.name,
                "args": dict(fc.args) if fc.args else {},
            })

    result["text"] = result["text"].strip()
    return result
