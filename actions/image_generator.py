"""
image_generator.py — Text-to-image generation using Pollinations.ai (free, no API key).
Also supports Google Gemini image generation if configured.
"""
import json
import sys
import time
from pathlib import Path
from urllib.parse import quote

import requests

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()


def _save_image(data: bytes, filename: str) -> str:
    out_dir = BASE_DIR / "generated_images"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / filename
    path.write_bytes(data)
    return str(path)


def _pollinations_generate(prompt: str, width: int = 1024, height: int = 1024) -> str:
    encoded = quote(prompt)
    url = f"https://image.pollinations.ai/prompt/{encoded}?width={width}&height={height}&nologo=true"
    resp = requests.get(url, timeout=120, stream=True)
    resp.raise_for_status()

    ts = int(time.time())
    filename = f"nova_{ts}.png"
    path = _save_image(resp.content, filename)
    return path


def _open_image(path: str):
    import platform
    import subprocess
    os_name = platform.system()
    try:
        if os_name == "Windows":
            subprocess.Popen(["start", path], shell=True)
        elif os_name == "Darwin":
            subprocess.Popen(["open", path])
        else:
            subprocess.Popen(["xdg-open", path])
    except Exception:
        pass


def image_generator(
    parameters: dict,
    response=None,
    player=None,
    speak=None,
) -> str:
    params = parameters or {}
    prompt = params.get("prompt", "").strip()
    width  = int(params.get("width", 1024))
    height = int(params.get("height", 1024))
    save   = params.get("save", True)
    open_after = params.get("open", True)

    if not prompt:
        return "Please provide a description of the image you want me to generate."

    if player:
        player.write_log(f"[ImageGen] Generating: {prompt[:50]}...")
    print(f"[ImageGen] 🎨 Prompt: {prompt!r}  Size: {width}x{height}")

    try:
        path = _pollinations_generate(prompt, width, height)
        print(f"[ImageGen] ✅ Saved: {path}")

        if open_after:
            _open_image(path)

        if player:
            player.write_log(f"[ImageGen] Image saved: {Path(path).name}")

        return f"Image generated and saved to {path}"

    except Exception as e:
        print(f"[ImageGen] ❌ Failed: {e}")
        return f"Image generation failed: {e}"
