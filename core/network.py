"""
network.py — Internet connectivity checker for Nexis-I.
Used to decide between online (Gemini) and offline (Ollama) backends.
"""

import socket


def is_online(host: str = "generativelanguage.googleapis.com", port: int = 443, timeout: float = 3.0) -> bool:
    """Returns True if we can reach the internet (specifically Google's API)."""
    try:
        with socket.create_connection((host, port), timeout=timeout):
            return True
    except (socket.timeout, OSError):
        return False


def is_ollama_running(url: str = "http://localhost:11434", timeout: float = 2.0) -> bool:
    """Returns True if Ollama is running locally."""
    try:
        import requests
        r = requests.get(url, timeout=timeout)
        return r.status_code == 200
    except Exception:
        return False
