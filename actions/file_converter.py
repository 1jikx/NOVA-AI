"""
file_converter.py — File format conversion and markdown to PDF.
Supports: video/audio conversion, image conversion, markdown to PDF.
"""
import subprocess
import sys
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()


def _check_ffmpeg() -> bool:
    try:
        subprocess.run(["ffmpeg", "-version"], capture_output=True, timeout=5)
        return True
    except Exception:
        return False


def _convert_media(src: str, dst_format: str) -> str:
    source = Path(src)
    if not source.exists():
        return f"File not found: {src}"

    out_dir = BASE_DIR / "converted"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{source.stem}.{dst_format}"

    try:
        result = subprocess.run(
            ["ffmpeg", "-y", "-i", str(source), str(out_path)],
            capture_output=True, text=True, timeout=300
        )
        if result.returncode == 0:
            return f"Converted: {out_path}"
        return f"FFmpeg error: {result.stderr[:200]}"
    except FileNotFoundError:
        return "FFmpeg not installed. Install from https://ffmpeg.org/download.html"
    except subprocess.TimeoutExpired:
        return "Conversion timed out (>5 min)."


def _convert_image(src: str, dst_format: str, quality: int = 90) -> str:
    source = Path(src)
    if not source.exists():
        return f"File not found: {src}"

    try:
        from PIL import Image
    except ImportError:
        return "Pillow not installed. Run: pip install Pillow"

    out_dir = BASE_DIR / "converted"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{source.stem}.{dst_format}"

    try:
        img = Image.open(str(source))
        if dst_format.lower() in ("jpg", "jpeg") and img.mode == "RGBA":
            img = img.convert("RGB")
        img.save(str(out_path), quality=quality)
        return f"Converted: {out_path}"
    except Exception as e:
        return f"Image conversion failed: {e}"


def _markdown_to_pdf(md_path: str) -> str:
    source = Path(md_path)
    if not source.exists():
        return f"File not found: {md_path}"

    out_dir = BASE_DIR / "converted"
    out_dir.mkdir(exist_ok=True)
    out_path = out_dir / f"{source.stem}.pdf"

    try:
        import markdown
        from weasyprint import HTML

        md_text = source.read_text(encoding="utf-8")
        html_body = markdown.markdown(md_text, extensions=["tables", "fenced_code"])

        full_html = f"""<!DOCTYPE html>
<html><head>
<meta charset="utf-8">
<style>
    body {{ font-family: sans-serif; padding: 40px; line-height: 1.6; color: #222; }}
    h1, h2, h3 {{ color: #111; }}
    code {{ background: #f4f4f4; padding: 2px 6px; border-radius: 3px; font-size: 0.9em; }}
    pre {{ background: #f4f4f4; padding: 12px; border-radius: 6px; overflow-x: auto; }}
    table {{ border-collapse: collapse; width: 100%; }}
    th, td {{ border: 1px solid #ddd; padding: 8px; text-align: left; }}
    th {{ background: #f8f8f8; }}
</style>
</head><body>{html_body}</body></html>"""

        HTML(string=full_html).write_pdf(str(out_path))
        return f"PDF created: {out_path}"

    except ImportError:
        return "Missing packages. Run: pip install markdown weasyprint"
    except Exception as e:
        return f"PDF conversion failed: {e}"


def file_converter(
    parameters: dict,
    response=None,
    player=None,
    speak=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "convert").lower().strip()
    source = params.get("source", "").strip()
    target_format = params.get("format", "").strip().lower().lstrip(".")
    quality = int(params.get("quality", 90))

    if player:
        player.write_log(f"[Converter] {action}: {source[:30]}")

    print(f"[Converter] 🔄 Action: {action}  Source: {source}  Format: {target_format}")

    if not source:
        return "Please provide a source file path."

    if action == "convert":
        if not target_format:
            return "Please provide a target format (e.g., mp3, mp4, jpg, png, pdf)."

        source_path = Path(source)
        ext = source_path.suffix.lower().lstrip(".")

        image_exts = {"jpg", "jpeg", "png", "gif", "bmp", "webp", "tiff", "ico"}
        video_exts = {"mp4", "avi", "mov", "mkv", "wmv", "flv", "webm", "m4v"}
        audio_exts = {"mp3", "wav", "ogg", "m4a", "aac", "flac", "wma", "opus"}

        if ext in image_exts or target_format in image_exts:
            return _convert_image(source, target_format, quality)
        elif ext in video_exts or ext in audio_exts or target_format in video_exts or target_format in audio_exts:
            if not _check_ffmpeg():
                return "FFmpeg not installed. Download from https://ffmpeg.org/download.html"
            return _convert_media(source, target_format)
        else:
            return f"Unsupported conversion: {ext} → {target_format}"

    elif action == "markdown_to_pdf":
        return _markdown_to_pdf(source)

    else:
        return f"Unknown converter action: '{action}'. Use: convert, markdown_to_pdf"
