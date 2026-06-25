"""
ascii_art.py — Convert images to ASCII/text art.
Uses Pillow to resize and map pixels to ASCII characters.
"""
import sys
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()

ASCII_CHARS = "@%#*+=-:. "
ASCII_CHARS_DENSE = "$@B%8&WM#*oahkbdpqwmZO0QLCJUYXzcvunxrjft/\\|()1{}[]?-_+~<>i!lI;:,\"^`'. "


def _image_to_ascii(
    image_path: str,
    width: int = 100,
    dense: bool = False,
    invert: bool = False,
) -> str:
    try:
        from PIL import Image
    except ImportError:
        return "Pillow not installed. Run: pip install Pillow"

    source = Path(image_path)
    if not source.exists():
        return f"File not found: {image_path}"

    chars = ASCII_CHARS_DENSE if dense else ASCII_CHARS
    if invert:
        chars = chars[::-1]

    img = Image.open(str(source)).convert("L")

    aspect = img.height / img.width
    new_height = int(width * aspect * 0.55)
    img = img.resize((width, new_height))

    pixels = list(img.getdata())

    lines = []
    for row in range(new_height):
        line = ""
        for col in range(width):
            pixel = pixels[row * width + col]
            char_idx = min(int(pixel / 256 * len(chars)), len(chars) - 1)
            line += chars[char_idx]
        lines.append(line)

    return "\n".join(lines)


def _save_ascii_art(ascii_text: str, filename: str) -> str:
    out_dir = BASE_DIR / "generated_images"
    out_dir.mkdir(exist_ok=True)
    path = out_dir / filename
    path.write_text(ascii_text, encoding="utf-8")
    return str(path)


def ascii_art(
    parameters: dict,
    response=None,
    player=None,
    speak=None,
) -> str:
    params = parameters or {}
    source = params.get("source", "").strip()
    width = int(params.get("width", 100))
    dense = params.get("dense", False)
    invert = params.get("invert", False)
    save = params.get("save", True)

    if not source:
        return "Please provide an image file path."

    if player:
        player.write_log(f"[ASCII] Converting: {Path(source).name}")

    print(f"[ASCII] 🎨 Source: {source}  Width: {width}  Dense: {dense}")

    ascii_text = _image_to_ascii(source, width, dense, invert)

    if ascii_text.startswith("File not found") or ascii_text.startswith("Pillow"):
        return ascii_text

    if save:
        ts = __import__("time").time()
        path = _save_ascii_art(ascii_text, f"ascii_{int(ts)}.txt")
        print(f"[ASCII] ✅ Saved: {path}")

    preview = ascii_text[:500]
    if len(ascii_text) > 500:
        preview += "\n... (truncated)"

    return f"ASCII art created ({width}x{len(ascii_text.splitlines())} chars):\n\n{preview}"
