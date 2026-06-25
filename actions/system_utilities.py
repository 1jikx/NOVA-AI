"""
system_utilities.py — Startup manager, uninstaller, disk analyzer,
duplicate file finder, and process killer.
"""
import hashlib
import json
import os
import shutil
import subprocess
import sys
from collections import defaultdict
from pathlib import Path

def _get_base_dir() -> Path:
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent.parent

BASE_DIR = _get_base_dir()


def _startup_list() -> str:
    results = []
    paths = [
        Path(os.environ.get("APPDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",
        Path(os.environ.get("PROGRAMDATA", "")) / "Microsoft" / "Windows" / "Start Menu" / "Programs" / "Startup",
    ]
    for p in paths:
        if p.exists():
            for f in p.iterdir():
                results.append(f"  ✅ {f.name}  ({f})")

    try:
        import winreg
        reg_paths = [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]
        for hive, path in reg_paths:
            try:
                key = winreg.OpenKey(hive, path)
                i = 0
                while True:
                    try:
                        name, value, _ = winreg.EnumValue(key, i)
                        results.append(f"  ✅ {name}  ({value[:80]})")
                        i += 1
                    except OSError:
                        break
                winreg.CloseKey(key)
            except Exception:
                pass
    except ImportError:
        pass

    if not results:
        return "No startup programs found."
    return f"📋 Startup programs ({len(results)}):\n\n" + "\n".join(results)


def _startup_disable(name: str) -> str:
    try:
        import winreg
        for hive, path in [
            (winreg.HKEY_CURRENT_USER, r"Software\Microsoft\Windows\CurrentVersion\Run"),
            (winreg.HKEY_LOCAL_MACHINE, r"Software\Microsoft\Windows\CurrentVersion\Run"),
        ]:
            try:
                key = winreg.OpenKey(hive, path, 0, winreg.KEY_SET_VALUE)
                winreg.DeleteValue(key, name)
                winreg.CloseKey(key)
                return f"Disabled startup: {name}"
            except FileNotFoundError:
                continue
    except ImportError:
        pass
    return f"Could not find startup entry: {name}"


def _uninstall(program_name: str) -> str:
    try:
        result = subprocess.run(
            ["wmic", "product", "where", f"name like '%{program_name}%'", "get", "name,identifyingnumber"],
            capture_output=True, text=True, timeout=30
        )
        lines = [l.strip() for l in result.stdout.strip().split("\n") if l.strip() and "IdentifyingNumber" not in l]
        if not lines:
            return f"No program found matching '{program_name}'."

        entries = []
        for line in lines:
            parts = line.split("  ")
            parts = [p.strip() for p in parts if p.strip()]
            if len(parts) >= 2:
                entries.append((parts[0], parts[1]))

        if not entries:
            return f"No program found matching '{program_name}'."

        name, guid = entries[0]
        return (
            f"Found: {name}\n"
            f"GUID: {guid}\n"
            f"To uninstall, run in admin terminal:\n"
            f'msiexec /x "{guid}"'
        )
    except Exception as e:
        return f"Uninstall search failed: {e}"


def _disk_analyze(path: str = "C:\\") -> str:
    target = Path(path)
    if not target.exists():
        return f"Path not found: {path}"

    total_size = 0
    folder_sizes = {}
    file_count = 0

    try:
        for item in target.rglob("*"):
            try:
                if item.is_file():
                    size = item.stat().st_size
                    total_size += size
                    file_count += 1
                    parent = str(item.parent)
                    folder_sizes[parent] = folder_sizes.get(parent, 0) + size
            except (PermissionError, OSError):
                continue
    except Exception as e:
        return f"Disk analysis failed: {e}"

    def fmt(b):
        if b < 1024: return f"{b} B"
        elif b < 1024**2: return f"{b/1024:.1f} KB"
        elif b < 1024**3: return f"{b/1024**2:.1f} MB"
        else: return f"{b/1024**3:.1f} GB"

    sorted_folders = sorted(folder_sizes.items(), key=lambda x: x[1], reverse=True)[:10]

    lines = [
        f"📊 Disk Analysis: {path}",
        f"   Total: {fmt(total_size)} in {file_count} files\n",
        "Top 10 largest folders:"
    ]
    for folder, size in sorted_folders:
        short = folder.replace(str(target), "").strip("\\") or str(target)
        lines.append(f"  {fmt(size):>10}  {short}")

    return "\n".join(lines)


def _find_duplicates(path: str = None) -> str:
    target = Path(path) if path else Path.home() / "Downloads"
    if not target.exists():
        return f"Path not found: {target}"

    hashes = defaultdict(list)
    scanned = 0

    for item in target.rglob("*"):
        if item.is_file() and item.stat().st_size > 1024:
            try:
                h = hashlib.md5(item.read_bytes()[:8192]).hexdigest()
                hashes[h].append(str(item))
                scanned += 1
            except (PermissionError, OSError):
                continue

    duplicates = {h: files for h, files in hashes.items() if len(files) > 1}

    if not duplicates:
        return f"No duplicates found in {target} (scanned {scanned} files)."

    lines = [f"🔍 Duplicates found in {target}:\n"]
    count = 0
    for h, files in list(duplicates.items())[:15]:
        size = Path(files[0]).stat().st_size
        def fmt(b):
            if b < 1024**2: return f"{b/1024:.0f} KB"
            else: return f"{b/1024**2:.1f} MB"
        lines.append(f"  [{fmt(size)}] {len(files)} copies:")
        for f in files:
            lines.append(f"    • {f}")
        lines.append("")
        count += 1

    lines.insert(1, f"Found {len(duplicates)} duplicate groups across {scanned} files.")
    return "\n".join(lines).strip()


def _process_list() -> str:
    import platform
    os_name = platform.system()

    if os_name == "Windows":
        result = subprocess.run(
            ["tasklist", "/FO", "CSV"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")[1:]
        processes = []
        for line in lines:
            parts = line.strip('"').split('","')
            if len(parts) >= 5:
                name = parts[0]
                pid = parts[1]
                mem = parts[4]
                try:
                    mem_mb = int(mem.replace(",", "").replace(" K", "").replace('"', '')) / 1024
                except:
                    mem_mb = 0
                processes.append((name, pid, mem_mb))
    else:
        result = subprocess.run(
            ["ps", "aux", "--sort=-rss"],
            capture_output=True, text=True, timeout=10
        )
        lines = result.stdout.strip().split("\n")[1:]
        processes = []
        for line in lines:
            parts = line.split(None, 10)
            if len(parts) >= 11:
                mem = float(parts[3])
                pid = parts[1]
                name = parts[10].split("/")[-1][:30]
                processes.append((name, pid, mem))

    processes.sort(key=lambda x: x[2], reverse=True)

    output = ["💻 Top processes by memory:\n"]
    for name, pid, mem in processes[:15]:
        output.append(f"  {mem:>8.1f} MB  PID:{pid:>6}  {name}")

    return "\n".join(output)


def _process_kill(name: str) -> str:
    import platform
    os_name = platform.system()
    if os_name == "Windows":
        result = subprocess.run(
            ["taskkill", "/IM", name, "/F"],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"Killed: {name}"
        return f"Failed to kill '{name}': {result.stderr.strip()}"
    else:
        result = subprocess.run(
            ["pkill", "-f", name],
            capture_output=True, text=True, timeout=10
        )
        if result.returncode == 0:
            return f"Killed: {name}"
        return f"Failed to kill '{name}' (may require sudo)"


def system_utilities(
    parameters: dict,
    response=None,
    player=None,
    speak=None,
) -> str:
    params = parameters or {}
    action = params.get("action", "list").lower().strip()

    if player:
        player.write_log(f"[System] {action}")

    print(f"[System] 🔧 Action: {action}  Params: {params}")

    if action == "startup_list":
        return _startup_list()
    elif action == "startup_disable":
        return _startup_disable(params.get("name", ""))
    elif action == "uninstall":
        return _uninstall(params.get("program", ""))
    elif action == "disk_analyze":
        return _disk_analyze(params.get("path", "C:\\"))
    elif action == "find_duplicates":
        return _find_duplicates(params.get("path"))
    elif action == "process_list":
        return _process_list()
    elif action == "process_kill":
        return _process_kill(params.get("name", ""))
    else:
        return f"Unknown system action: '{action}'"
