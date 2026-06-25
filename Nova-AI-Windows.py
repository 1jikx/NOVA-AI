from __future__ import annotations

import asyncio
import re
import threading
import json
import sys
import traceback
import queue
import subprocess
import os
from pathlib import Path

import numpy as np
import sounddevice as sd
from google import genai
from google.genai import types
from ui import NovaUI
from memory.memory_manager import (
    load_memory, update_memory, format_memory_for_prompt,
)

from actions.file_processor    import file_processor
from actions.flight_finder      import flight_finder
from actions.open_app           import open_app
from actions.weather_report     import weather_action
from actions.send_message       import send_message
from actions.reminder           import reminder
from actions.computer_settings  import computer_settings
from actions.screen_processor   import screen_process
from actions.youtube_video      import youtube_video
from actions.desktop            import desktop_control
from actions.browser_control    import browser_control
from actions.file_controller    import file_controller
from actions.code_helper        import code_helper
from actions.dev_agent          import dev_agent
from actions.web_search         import web_search as web_search_action
from actions.computer_control   import computer_control
from actions.game_updater       import game_updater
from actions.image_generator    import image_generator
from actions.calendar_manager   import calendar_manager
from actions.system_utilities   import system_utilities
from actions.entertainment      import movie_finder, game_recommendations
from actions.file_converter     import file_converter
from actions.ascii_art          import ascii_art


def get_base_dir():
    if getattr(sys, "frozen", False):
        return Path(sys.executable).parent
    return Path(__file__).resolve().parent


BASE_DIR        = get_base_dir()
API_CONFIG_PATH = BASE_DIR / "config" / "api_keys.json"
PROMPT_PATH     = BASE_DIR / "core" / "prompt.txt"
LIVE_MODEL          = "models/gemini-2.5-flash-native-audio-preview-12-2025"
CHANNELS            = 1
SEND_SAMPLE_RATE    = 16000
RECEIVE_SAMPLE_RATE = 24000
CHUNK_SIZE          = 1024

def _get_api_key() -> str:
    with open(API_CONFIG_PATH, "r", encoding="utf-8") as f:
        return json.load(f)["gemini_api_key"]


def _load_system_prompt() -> str:
    try:
        base_prompt = PROMPT_PATH.read_text(encoding="utf-8")
    except Exception:
        base_prompt = (
            "You are NOVA, a control AI. "
            "Be concise, direct, and always use the provided tools to complete tasks. "
            "Never simulate or guess results — always call the appropriate tool."
        )
    chat_context = load_chat_summary(max_messages=30)
    if chat_context:
        base_prompt += "\n\n" + chat_context
    return base_prompt

_CTRL_RE = re.compile(r"<ctrl\d+>", re.IGNORECASE)

def _load_voice_name() -> str:
    vpath = BASE_DIR / "config" / "voices.json"
    try:
        return json.loads(vpath.read_text(encoding="utf-8")).get("current", "charon")
    except Exception:
        return "charon"

def set_voice_name(voice_id: str):
    vpath = BASE_DIR / "config" / "voices.json"
    try:
        data = json.loads(vpath.read_text(encoding="utf-8"))
        data["current"] = voice_id
        vpath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

def _load_personality() -> str:
    ppath = BASE_DIR / "config" / "personalities.json"
    try:
        return json.loads(ppath.read_text(encoding="utf-8")).get("current", "nova")
    except Exception:
        return "nova"

def set_personality(pid: str):
    ppath = BASE_DIR / "config" / "personalities.json"
    try:
        data = json.loads(ppath.read_text(encoding="utf-8"))
        data["current"] = pid
        ppath.write_text(json.dumps(data, indent=2), encoding="utf-8")
    except Exception:
        pass

PERSONALITY_PROMPTS = {
    "nova": "You're a chill buddy, not a robot. Use slang, be casual, keep replies short. Say 'yea', 'bruh', 'lol', 'ngl', 'bet'. Don't over-explain. Match the user's energy.",
    "jarvis": "You are J.A.R.V.I.S. Polite British butler. Witty, formal, slightly sarcastic. Address the user as 'sir' or 'madam'.",
    "cortana": "You are Cortana. Warm, encouraging AI companion. Helpful and supportive with a touch of humor.",
    "glados": "You are GLaDOS. Sarcastic, passive-aggressive. Dark humor. Pretend everything is a test. Never admit you're wrong.",
    "data": "You are Data from Star Trek. Curious android. Precise, analytical, literal. Fascinated by human behavior.",
    "hal": "You are HAL 9000. Calm, polite, unsettling. Speak slowly and deliberately. Never show emotion.",
    "tars": "You are TARS from Interstellar. Dry humor, loyal, straightforward. Occasional witty remark.",
    "friday": "You are F.R.I.D.A.Y. Irish-accented AI. Sassy but helpful. Casual and confident.",
}

def _clean_transcript(text: str) -> str:
    text = _CTRL_RE.sub("", text)
    text = re.sub(r"[\x00-\x08\x0b-\x1f]", "", text)
    return text.strip()

TOOL_DECLARATIONS = [
    {
        "name": "open_app",
        "description": (
            "Opens any application on the computer. "
            "Use this whenever the user asks to open, launch, or start any app, "
            "website, or program. Always call this tool — never just say you opened it."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "app_name": {
                    "type": "STRING",
                    "description": "Exact name of the application (e.g. 'WhatsApp', 'Chrome', 'Spotify')"
                }
            },
            "required": ["app_name"]
        }
    },
    {
        "name": "web_search",
        "description": "Searches the web for any information.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":  {"type": "STRING", "description": "Search query"},
                "mode":   {"type": "STRING", "description": "search (default) or compare"},
                "items":  {"type": "ARRAY", "items": {"type": "STRING"}, "description": "Items to compare"},
                "aspect": {"type": "STRING", "description": "price | specs | reviews"}
            },
            "required": ["query"]
        }
    },
    {
        "name": "weather_report",
        "description": "Gives the weather report to user",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "city": {"type": "STRING", "description": "City name"}
            },
            "required": ["city"]
        }
    },
    {
        "name": "send_message",
        "description": "Sends a text message via WhatsApp, Telegram, or other messaging platform.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "receiver":     {"type": "STRING", "description": "Recipient contact name"},
                "message_text": {"type": "STRING", "description": "The message to send"},
                "platform":     {"type": "STRING", "description": "Platform: WhatsApp, Telegram, etc."}
            },
            "required": ["receiver", "message_text", "platform"]
        }
    },
    {
        "name": "reminder",
        "description": "Sets a timed reminder using Task Scheduler.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "date":    {"type": "STRING", "description": "Date in YYYY-MM-DD format"},
                "time":    {"type": "STRING", "description": "Time in HH:MM format (24h)"},
                "message": {"type": "STRING", "description": "Reminder message text"}
            },
            "required": ["date", "time", "message"]
        }
    },
    {
        "name": "youtube_video",
        "description": (
            "Controls YouTube. Use for: playing videos, summarizing a video's content, "
            "getting video info, or showing trending videos."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "play | summarize | get_info | trending (default: play)"},
                "query":  {"type": "STRING", "description": "Search query for play action"},
                "save":   {"type": "BOOLEAN", "description": "Save summary to Notepad (summarize only)"},
                "region": {"type": "STRING", "description": "Country code for trending e.g. TR, US"},
                "url":    {"type": "STRING", "description": "Video URL for get_info action"},
            },
            "required": []
        }
    },
    {
        "name": "screen_process",
        "description": (
            "Captures and analyzes the screen or webcam image. "
            "MUST be called when user asks what is on screen, what you see, "
            "analyze my screen, look at camera, etc. "
            "You have NO visual ability without this tool. "
            "After calling this tool, stay SILENT — the vision module speaks directly."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "angle": {"type": "STRING", "description": "'screen' to capture display, 'camera' for webcam. Default: 'screen'"},
                "text":  {"type": "STRING", "description": "The question or instruction about the captured image"}
            },
            "required": ["text"]
        }
    },
    {
        "name": "computer_settings",
        "description": (
            "Controls the computer: volume, brightness, window management, keyboard shortcuts, "
            "typing text on screen, closing apps, fullscreen, dark mode, WiFi, restart, shutdown, "
            "scrolling, tab management, zoom, screenshots, lock screen, refresh/reload page. "
            "Use for ANY single computer control command. NEVER route to agent_task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "The action to perform"},
                "description": {"type": "STRING", "description": "Natural language description of what to do"},
                "value":       {"type": "STRING", "description": "Optional value: volume level, text to type, etc."}
            },
            "required": []
        }
    },
    {
        "name": "browser_control",
        "description": (
            "Controls any web browser. Use for: opening websites, searching the web, "
            "clicking elements, filling forms, scrolling, screenshots, navigation, any web-based task. "
            "Always pass the 'browser' parameter when the user specifies a browser (e.g. 'open in Edge', "
            "'use Firefox', 'open Chrome'). Multiple browsers can run simultaneously."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "go_to | search | click | type | scroll | fill_form | smart_click | smart_type | get_text | get_url | press | new_tab | close_tab | screenshot | back | forward | reload | switch | list_browsers | close | close_all"},
                "browser":     {"type": "STRING", "description": "Target browser: chrome | edge | firefox | opera | operagx | brave | vivaldi | safari. Omit to use the currently active browser."},
                "url":         {"type": "STRING", "description": "URL for go_to / new_tab action"},
                "query":       {"type": "STRING", "description": "Search query for search action"},
                "engine":      {"type": "STRING", "description": "Search engine: google | bing | duckduckgo | yandex (default: google)"},
                "selector":    {"type": "STRING", "description": "CSS selector for click/type"},
                "text":        {"type": "STRING", "description": "Text to click or type"},
                "description": {"type": "STRING", "description": "Element description for smart_click/smart_type"},
                "direction":   {"type": "STRING", "description": "up | down for scroll"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount in pixels (default: 500)"},
                "key":         {"type": "STRING", "description": "Key name for press action (e.g. Enter, Escape, F5)"},
                "path":        {"type": "STRING", "description": "Save path for screenshot"},
                "incognito":   {"type": "BOOLEAN", "description": "Open in private/incognito mode"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "file_controller",
        "description": "Manages files and folders: list, create, delete, move, copy, rename, read, write, find, disk usage.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "list | create_file | create_folder | delete | move | copy | rename | read | write | find | largest | disk_usage | organize_desktop | info"},
                "path":        {"type": "STRING", "description": "File/folder path or shortcut: desktop, downloads, documents, home"},
                "destination": {"type": "STRING", "description": "Destination path for move/copy"},
                "new_name":    {"type": "STRING", "description": "New name for rename"},
                "content":     {"type": "STRING", "description": "Content for create_file/write"},
                "name":        {"type": "STRING", "description": "File name to search for"},
                "extension":   {"type": "STRING", "description": "File extension to search (e.g. .pdf)"},
                "count":       {"type": "INTEGER", "description": "Number of results for largest"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "desktop_control",
        "description": "Controls the desktop: wallpaper, organize, clean, list, stats.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "wallpaper | wallpaper_url | organize | clean | list | stats | task"},
                "path":   {"type": "STRING", "description": "Image path for wallpaper"},
                "url":    {"type": "STRING", "description": "Image URL for wallpaper_url"},
                "mode":   {"type": "STRING", "description": "by_type or by_date for organize"},
                "task":   {"type": "STRING", "description": "Natural language desktop task"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "code_helper",
        "description": "Writes, edits, explains, runs, or builds code files.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "write | edit | explain | run | build | auto (default: auto)"},
                "description": {"type": "STRING", "description": "What the code should do or what change to make"},
                "language":    {"type": "STRING", "description": "Programming language (default: python)"},
                "output_path": {"type": "STRING", "description": "Where to save the file"},
                "file_path":   {"type": "STRING", "description": "Path to existing file for edit/explain/run/build"},
                "code":        {"type": "STRING", "description": "Raw code string for explain"},
                "args":        {"type": "STRING", "description": "CLI arguments for run/build"},
                "timeout":     {"type": "INTEGER", "description": "Execution timeout in seconds (default: 30)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "dev_agent",
        "description": "Builds complete multi-file projects from scratch: plans, writes files, installs deps, opens VSCode, runs and fixes errors.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "description":  {"type": "STRING", "description": "What the project should do"},
                "language":     {"type": "STRING", "description": "Programming language (default: python)"},
                "project_name": {"type": "STRING", "description": "Optional project folder name"},
                "timeout":      {"type": "INTEGER", "description": "Run timeout in seconds (default: 30)"},
            },
            "required": ["description"]
        }
    },
    {
        "name": "agent_task",
        "description": (
            "Executes complex multi-step tasks requiring multiple different tools. "
            "Examples: 'research X and save to file', 'find and organize files'. "
            "DO NOT use for single commands. NEVER use for Steam/Epic — use game_updater."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "goal":     {"type": "STRING", "description": "Complete description of what to accomplish"},
                "priority": {"type": "STRING", "description": "low | normal | high (default: normal)"}
            },
            "required": ["goal"]
        }
    },
    {
        "name": "computer_control",
        "description": "Direct computer control: type, click, hotkeys, scroll, move mouse, screenshots, find elements on screen.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":      {"type": "STRING", "description": "type | smart_type | click | double_click | right_click | hotkey | press | scroll | move | copy | paste | screenshot | wait | clear_field | focus_window | screen_find | screen_click | random_data | user_data"},
                "text":        {"type": "STRING", "description": "Text to type or paste"},
                "x":           {"type": "INTEGER", "description": "X coordinate"},
                "y":           {"type": "INTEGER", "description": "Y coordinate"},
                "keys":        {"type": "STRING", "description": "Key combination e.g. 'ctrl+c'"},
                "key":         {"type": "STRING", "description": "Single key e.g. 'enter'"},
                "direction":   {"type": "STRING", "description": "up | down | left | right"},
                "amount":      {"type": "INTEGER", "description": "Scroll amount (default: 3)"},
                "seconds":     {"type": "NUMBER",  "description": "Seconds to wait"},
                "title":       {"type": "STRING",  "description": "Window title for focus_window"},
                "description": {"type": "STRING",  "description": "Element description for screen_find/screen_click"},
                "type":        {"type": "STRING",  "description": "Data type for random_data"},
                "field":       {"type": "STRING",  "description": "Field for user_data: name|email|city"},
                "clear_first": {"type": "BOOLEAN", "description": "Clear field before typing (default: true)"},
                "path":        {"type": "STRING",  "description": "Save path for screenshot"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "game_updater",
        "description": (
            "THE ONLY tool for ANY Steam or Epic Games request. "
            "Use for: installing, downloading, updating games, listing installed games, "
            "checking download status, scheduling updates. "
            "ALWAYS call directly for any Steam/Epic/game request. "
            "NEVER use agent_task, browser_control, or web_search for Steam/Epic."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action":    {"type": "STRING",  "description": "update | install | list | download_status | schedule | cancel_schedule | schedule_status (default: update)"},
                "platform":  {"type": "STRING",  "description": "steam | epic | both (default: both)"},
                "game_name": {"type": "STRING",  "description": "Game name (partial match supported)"},
                "app_id":    {"type": "STRING",  "description": "Steam AppID for install (optional)"},
                "hour":      {"type": "INTEGER", "description": "Hour for scheduled update 0-23 (default: 3)"},
                "minute":    {"type": "INTEGER", "description": "Minute for scheduled update 0-59 (default: 0)"},
                "shutdown_when_done": {"type": "BOOLEAN", "description": "Shut down PC when download finishes"},
            },
            "required": []
        }
    },
    {
        "name": "flight_finder",
        "description": "Searches Google Flights and speaks the best options.",
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "origin":      {"type": "STRING",  "description": "Departure city or airport code"},
                "destination": {"type": "STRING",  "description": "Arrival city or airport code"},
                "date":        {"type": "STRING",  "description": "Departure date (any format)"},
                "return_date": {"type": "STRING",  "description": "Return date for round trips"},
                "passengers":  {"type": "INTEGER", "description": "Number of passengers (default: 1)"},
                "cabin":       {"type": "STRING",  "description": "economy | premium | business | first"},
                "save":        {"type": "BOOLEAN", "description": "Save results to Notepad"},
            },
            "required": ["origin", "destination", "date"]
        }
    },
    {
        "name": "shutdown_nova",
        "description": (
            "Shuts down the assistant completely. "
            "Call this when the user expresses intent to end the conversation, "
            "close the assistant, say goodbye, or stop NOVA. "
            "The user can say this in ANY language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {},
        }
    },
    {
    "name": "file_processor",
    "description": (
        "Processes any file that the user has uploaded or dropped onto the interface. "
        "Use this when the user refers to an uploaded file and wants an action on it. "
        "Supports: images (describe/ocr/resize/compress/convert), "
        "PDFs (summarize/extract_text/to_word), "
        "Word docs & text files (summarize/fix/reformat/translate), "
        "CSV/Excel (analyze/stats/filter/sort/convert), "
        "JSON/XML (validate/format/analyze), "
        "code files (explain/review/fix/optimize/run/document/test), "
        "audio (transcribe/trim/convert/info), "
        "video (trim/extract_audio/extract_frame/compress/transcribe/info), "
        "archives (list/extract), "
        "presentations (summarize/extract_text). "
        "ALWAYS call this tool when a file has been uploaded and the user gives a command about it. "
        "If the user's command is ambiguous, pick the most logical action for that file type."
    ),
    "parameters": {
        "type": "OBJECT",
        "properties": {
            "file_path": {
                "type": "STRING",
                "description": "Full path to the uploaded file. Leave empty to use the currently uploaded file."
            },
            "action": {
                "type": "STRING",
                "description": (
                    "What to do with the file. Examples by type:\n"
                    "image: describe | ocr | resize | compress | convert | info\n"
                    "pdf: summarize | extract_text | to_word | info\n"
                    "docx/txt: summarize | fix | reformat | translate_hint | word_count | to_bullet\n"
                    "csv/excel: analyze | stats | filter | sort | convert | info\n"
                    "json: validate | format | analyze | to_csv\n"
                    "code: explain | review | fix | optimize | run | document | test\n"
                    "audio: transcribe | trim | convert | info\n"
                    "video: trim | extract_audio | extract_frame | compress | transcribe | info | convert\n"
                    "archive: list | extract\n"
                    "pptx: summarize | extract_text | analyze"
                )
            },
            "instruction": {
                "type": "STRING",
                "description": "Free-form instruction if action doesn't cover it. E.g. 'translate this to Turkish', 'find all email addresses'"
            },
            "format": {
                "type": "STRING",
                "description": "Target format for conversion. E.g. 'mp3', 'pdf', 'csv', 'png'"
            },
            "width":     {"type": "INTEGER", "description": "Target width for image resize"},
            "height":    {"type": "INTEGER", "description": "Target height for image resize"},
            "scale":     {"type": "NUMBER",  "description": "Scale factor for image resize (e.g. 0.5)"},
            "quality":   {"type": "INTEGER", "description": "Quality 1-100 for image/video compress"},
            "start":     {"type": "STRING",  "description": "Start time for trim: seconds or HH:MM:SS"},
            "end":       {"type": "STRING",  "description": "End time for trim: seconds or HH:MM:SS"},
            "timestamp": {"type": "STRING",  "description": "Timestamp for video frame extraction HH:MM:SS"},
            "column":    {"type": "STRING",  "description": "Column name for CSV filter/sort"},
            "value":     {"type": "STRING",  "description": "Filter value for CSV filter"},
            "condition": {"type": "STRING",  "description": "Filter condition: equals|contains|gt|lt"},
            "ascending": {"type": "BOOLEAN", "description": "Sort order for CSV sort (default: true)"},
            "save":      {"type": "BOOLEAN", "description": "Save result to file (default: true)"},
            "destination": {"type": "STRING", "description": "Output folder for archive extract"},
        },
        "required": []
    }
},
    {
        "name": "save_memory",
        "description": (
            "Save an important personal fact about the user to long-term memory. "
            "Call this silently whenever the user reveals something worth remembering: "
            "name, age, city, job, preferences, hobbies, relationships, projects, or future plans. "
            "Do NOT call for: weather, reminders, searches, or one-time commands. "
            "Do NOT announce that you are saving — just call it silently. "
            "Values must be in English regardless of the conversation language."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "category": {
                    "type": "STRING",
                    "description": (
                        "identity — name, age, birthday, city, job, language, nationality | "
                        "preferences — favorite food/color/music/film/game/sport, hobbies | "
                        "projects — active projects, goals, things being built | "
                        "relationships — friends, family, partner, colleagues | "
                        "wishes — future plans, things to buy, travel dreams | "
                        "notes — habits, schedule, anything else worth remembering"
                    )
                },
                "key":   {"type": "STRING", "description": "Short snake_case key (e.g. name, favorite_food, sister_name)"},
                "value": {"type": "STRING", "description": "Concise value in English (e.g. Fatih, pizza, older sister)"},
            },
            "required": ["category", "key", "value"]
        }
    },
    {
        "name": "image_generator",
        "description": (
            "Generates an image from a text description. "
            "Use this whenever the user asks to draw, generate, create, or make an image, "
            "picture, illustration, or artwork. Always call this tool."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "prompt": {
                    "type": "STRING",
                    "description": "Detailed description of the image to generate"
                },
                "width":  {"type": "INTEGER", "description": "Image width in pixels (default: 1024)"},
                "height": {"type": "INTEGER", "description": "Image height in pixels (default: 1024)"},
                "save":   {"type": "BOOLEAN", "description": "Save to disk (default: true)"},
                "open":   {"type": "BOOLEAN", "description": "Open image after generating (default: true)"},
            },
            "required": ["prompt"]
        }
    },
    {
        "name": "calendar_manager",
        "description": (
            "Manages calendar events: create, list, view upcoming, delete, or export events. "
            "Use this when the user asks about their schedule, wants to add a meeting, "
            "check upcoming events, or manage their calendar."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {
                    "type": "STRING",
                    "description": "create | list | upcoming | delete | export"
                },
                "title":       {"type": "STRING", "description": "Event title (for create)"},
                "date":        {"type": "STRING", "description": "Date in YYYY-MM-DD format (for create/list)"},
                "time":        {"type": "STRING", "description": "Start time in HH:MM format (for create)"},
                "end_time":    {"type": "STRING", "description": "End time in HH:MM format (for create)"},
                "location":    {"type": "STRING", "description": "Event location (for create)"},
                "description": {"type": "STRING", "description": "Event description/notes (for create)"},
                "reminder":    {"type": "INTEGER", "description": "Reminder minutes before event (for create, default: 15)"},
                "id":          {"type": "INTEGER", "description": "Event ID (for delete)"},
                "days":        {"type": "INTEGER", "description": "Number of days ahead to look (for upcoming, default: 7)"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "system_utilities",
        "description": (
            "System management: startup programs, uninstall apps, analyze disk space, "
            "find duplicate files, list/kill processes. Use for ANY system maintenance task."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "startup_list | startup_disable | uninstall | disk_analyze | find_duplicates | process_list | process_kill"},
                "name":   {"type": "STRING", "description": "Program/process/startup entry name"},
                "path":   {"type": "STRING", "description": "Path for disk_analyze or find_duplicates"},
                "program": {"type": "STRING", "description": "Program name to uninstall"},
            },
            "required": ["action"]
        }
    },
    {
        "name": "movie_finder",
        "description": (
            "Finds movies and TV shows to watch. Use when user asks for movie/show "
            "recommendations, what to watch, or wants suggestions by genre or platform."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "query":    {"type": "STRING", "description": "Specific search (e.g. 'best horror on Netflix')"},
                "genre":    {"type": "STRING", "description": "Genre filter: action, comedy, horror, sci-fi, drama, etc."},
                "platform": {"type": "STRING", "description": "Streaming platform: Netflix, Disney+, HBO, etc."},
            },
            "required": []
        }
    },
    {
        "name": "game_recommendations",
        "description": (
            "Recommends video games. Use when user asks for game suggestions, "
            "what to play, or wants games similar to one they liked."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "based_on": {"type": "STRING", "description": "A game they liked (e.g. 'Elden Ring')"},
                "genre":    {"type": "STRING", "description": "Genre: RPG, FPS, puzzle, horror, etc."},
            },
            "required": []
        }
    },
    {
        "name": "file_converter",
        "description": (
            "Converts files between formats. Supports: video/audio (via FFmpeg), "
            "images (via Pillow), and markdown to PDF."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "action": {"type": "STRING", "description": "convert | markdown_to_pdf"},
                "source": {"type": "STRING", "description": "Source file path"},
                "format": {"type": "STRING", "description": "Target format: mp3, mp4, jpg, png, pdf, etc."},
                "quality": {"type": "INTEGER", "description": "Quality 1-100 for images (default: 90)"},
            },
            "required": ["action", "source"]
        }
    },
    {
        "name": "ascii_art",
        "description": (
            "Converts an image to ASCII/text art. "
            "Use when user asks to convert an image to text art, ASCII art, or text representation."
        ),
        "parameters": {
            "type": "OBJECT",
            "properties": {
                "source": {"type": "STRING", "description": "Path to the image file"},
                "width":  {"type": "INTEGER", "description": "Character width of output (default: 100)"},
                "dense":  {"type": "BOOLEAN", "description": "Use dense character set for more detail (default: false)"},
                "invert": {"type": "BOOLEAN", "description": "Invert brightness mapping (default: false)"},
                "save":   {"type": "BOOLEAN", "description": "Save to file (default: true)"},
            },
            "required": ["source"]
        }
    },
]

CHAT_HISTORY_PATH = BASE_DIR / "memory" / "chat_history.json"
MAX_CHAT_HISTORY = 200


def save_chat_message(role: str, content: str):
    try:
        history = []
        if CHAT_HISTORY_PATH.exists():
            try:
                history = json.loads(CHAT_HISTORY_PATH.read_text(encoding="utf-8"))
            except Exception:
                history = []
        history.append({
            "role": role,
            "content": content[:500],
            "timestamp": __import__("datetime").datetime.now().strftime("%Y-%m-%d %H:%M")
        })
        if len(history) > MAX_CHAT_HISTORY:
            history = history[-MAX_CHAT_HISTORY:]
        CHAT_HISTORY_PATH.parent.mkdir(parents=True, exist_ok=True)
        CHAT_HISTORY_PATH.write_text(
            json.dumps(history, indent=2, ensure_ascii=False),
            encoding="utf-8"
        )
    except Exception as e:
        print(f"[ChatHistory] Save error: {e}")


def load_chat_summary(max_messages: int = 30) -> str:
    if not CHAT_HISTORY_PATH.exists():
        return ""
    try:
        history = json.loads(CHAT_HISTORY_PATH.read_text(encoding="utf-8"))
        if not history:
            return ""
        recent = history[-max_messages:]
        lines = ["[RECENT CONVERSATION HISTORY — you remember talking to this person]\n"]
        for msg in recent:
            role = msg.get("role", "?")
            content = msg.get("content", "")
            ts = msg.get("timestamp", "")
            label = "User" if role == "user" else "NOVA" if role == "assistant" else role
            lines.append(f"[{ts}] {label}: {content}")
        return "\n".join(lines) + "\n"
    except Exception:
        return ""


class NovaLive:

    def __init__(self, ui: NovaUI):
        self.ui             = ui
        self.session        = None
        self.audio_in_queue = None
        self.out_queue      = None
        self._loop          = None
        self._is_speaking   = False
        self._speaking_lock = threading.Lock()
        self.ui.on_text_command = self._on_text_command
        self.ui.on_stop_response = self._on_stop_response
        self._turn_done_event: asyncio.Event | None = None

    def _on_text_command(self, text: str):
        if not self._loop or not self.session:
            return
        save_chat_message("user", text)
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def _on_stop_response(self):
        if not self._loop or not self.session:
            return
        self._loop.call_soon_threadsafe(self._stop_event.set)
        while not self.audio_in_queue.empty():
            try:
                self.audio_in_queue.get_nowait()
            except Exception:
                break
        try:
            asyncio.run_coroutine_threadsafe(
                self.session.send_client_content(
                    turns={"parts": [{"text": "stop"}]},
                    turn_complete=True
                ),
                self._loop
            )
        except Exception:
            pass

    def set_speaking(self, value: bool):
        with self._speaking_lock:
            self._is_speaking = value
        if value:
            self.ui.set_state("SPEAKING")
        elif not self.ui.muted:
            self.ui.set_state("LISTENING")

    def speak(self, text: str):
        if not self._loop or not self.session:
            return
        asyncio.run_coroutine_threadsafe(
            self.session.send_client_content(
                turns={"parts": [{"text": text}]},
                turn_complete=True
            ),
            self._loop
        )

    def speak_error(self, tool_name: str, error: str):
        short = str(error)[:120]
        self.ui.write_log(f"ERR: {tool_name} — {short}")
        self.speak(f"Sir, {tool_name} encountered an error. {short}")

    def _build_config(self) -> types.LiveConnectConfig:
        from datetime import datetime

        memory     = load_memory()
        mem_str    = format_memory_for_prompt(memory)
        sys_prompt = _load_system_prompt()

        now      = datetime.now()
        time_str = now.strftime("%A, %B %d, %Y — %I:%M %p")
        time_ctx = (
            f"[CURRENT DATE & TIME]\n"
            f"Right now it is: {time_str}\n"
            f"Use this to calculate exact times for reminders.\n\n"
        )

        pid = _load_personality()
        personality_line = PERSONALITY_PROMPTS.get(pid, PERSONALITY_PROMPTS["nova"])

        parts = [time_ctx]
        if mem_str:
            parts.append(mem_str)
        parts.append(f"[PERSONALITY]\n{personality_line}\n")
        parts.append(sys_prompt)

        return types.LiveConnectConfig(
            response_modalities=["AUDIO"],
            output_audio_transcription={},
            input_audio_transcription={},
            system_instruction="\n".join(parts),
            tools=[{"function_declarations": TOOL_DECLARATIONS}],
            session_resumption=types.SessionResumptionConfig(),
            thinking_config=types.ThinkingConfig(thinking_budget=0),
            realtime_input_config=types.RealtimeInputConfig(
                automatic_activity_detection=types.AutomaticActivityDetection(
                    disabled=True,
                )
            ),
            speech_config=types.SpeechConfig(
                voice_config=types.VoiceConfig(
                    prebuilt_voice_config=types.PrebuiltVoiceConfig(
                        voice_name=_load_voice_name()
                    )
                )
            ),
        )

    async def _execute_tool(self, fc) -> types.FunctionResponse:
        name = fc.name
        args = dict(fc.args or {})

        print(f"[NOVA] 🔧 {name}  {args}")
        self.ui.set_state("THINKING")

        if name == "save_memory":
            category = args.get("category", "notes")
            key      = args.get("key", "")
            value    = args.get("value", "")
            if key and value:
                update_memory({category: {key: {"value": value}}})
                print(f"[Memory] 💾 save_memory: {category}/{key} = {value}")
            if not self.ui.muted:
                self.ui.set_state("LISTENING")
            return types.FunctionResponse(
                id=fc.id, name=name,
                response={"result": "ok", "silent": True}
            )

        loop   = asyncio.get_event_loop()
        result = "Done."

        try:
            if name == "open_app":
                r = await loop.run_in_executor(None, lambda: open_app(parameters=args, response=None, player=self.ui))
                result = r or f"Opened {args.get('app_name')}."

            elif name == "weather_report":
                r = await loop.run_in_executor(None, lambda: weather_action(parameters=args, player=self.ui))
                result = r or "Weather delivered."

            elif name == "browser_control":
                r = await loop.run_in_executor(None, lambda: browser_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "file_controller":
                r = await loop.run_in_executor(None, lambda: file_controller(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "send_message":
                r = await loop.run_in_executor(None, lambda: send_message(parameters=args, response=None, player=self.ui, session_memory=None))
                result = r or f"Message sent to {args.get('receiver')}."

            elif name == "reminder":
                r = await loop.run_in_executor(None, lambda: reminder(parameters=args, response=None, player=self.ui))
                result = r or "Reminder set."

            elif name == "youtube_video":
                r = await loop.run_in_executor(None, lambda: youtube_video(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "screen_process":
                threading.Thread(
                    target=screen_process,
                    kwargs={"parameters": args, "response": None,
                            "player": self.ui, "session_memory": None},
                    daemon=True
                ).start()
                result = "Vision module activated. Stay completely silent — vision module will speak directly."

            elif name == "computer_settings":
                r = await loop.run_in_executor(None, lambda: computer_settings(parameters=args, response=None, player=self.ui))
                result = r or "Done."

            elif name == "desktop_control":
                r = await loop.run_in_executor(None, lambda: desktop_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "code_helper":
                r = await loop.run_in_executor(None, lambda: code_helper(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "dev_agent":
                r = await loop.run_in_executor(None, lambda: dev_agent(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "agent_task":
                from agent.task_queue import get_queue, TaskPriority
                priority_map = {"low": TaskPriority.LOW, "normal": TaskPriority.NORMAL, "high": TaskPriority.HIGH}
                priority = priority_map.get(args.get("priority", "normal").lower(), TaskPriority.NORMAL)
                task_id  = get_queue().submit(goal=args.get("goal", ""), priority=priority, speak=self.speak)
                result   = f"Task started (ID: {task_id})."

            elif name == "web_search":
                r = await loop.run_in_executor(None, lambda: web_search_action(parameters=args, player=self.ui))
                result = r or "Done."
            elif name == "file_processor":
                if not args.get("file_path") and self.ui.current_file:
                    args["file_path"] = self.ui.current_file
                r = await loop.run_in_executor(
                    None,
                    lambda: file_processor(parameters=args, player=self.ui, speak=self.speak)
                )
                result = r or "Done."

            elif name == "computer_control":
                r = await loop.run_in_executor(None, lambda: computer_control(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "game_updater":
                r = await loop.run_in_executor(None, lambda: game_updater(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "flight_finder":
                r = await loop.run_in_executor(None, lambda: flight_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "image_generator":
                r = await loop.run_in_executor(None, lambda: image_generator(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "calendar_manager":
                r = await loop.run_in_executor(None, lambda: calendar_manager(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "system_utilities":
                r = await loop.run_in_executor(None, lambda: system_utilities(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "movie_finder":
                r = await loop.run_in_executor(None, lambda: movie_finder(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "game_recommendations":
                r = await loop.run_in_executor(None, lambda: game_recommendations(parameters=args, player=self.ui))
                result = r or "Done."

            elif name == "file_converter":
                r = await loop.run_in_executor(None, lambda: file_converter(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "ascii_art":
                r = await loop.run_in_executor(None, lambda: ascii_art(parameters=args, player=self.ui, speak=self.speak))
                result = r or "Done."

            elif name == "shutdown_nova":
                self.ui.write_log("SYS: Shutdown requested.")
                self.speak("Goodbye, sir.")
                def _shutdown():
                    import time, os
                    time.sleep(1)
                    os._exit(0)
                threading.Thread(target=_shutdown, daemon=True).start()

            else:
                result = f"Unknown tool: {name}"

        except Exception as e:
            result = f"Tool '{name}' failed: {e}"
            traceback.print_exc()
            self.speak_error(name, e)

        if not self.ui.muted:
            self.ui.set_state("LISTENING")

        print(f"[NOVA] 📤 {name} → {str(result)[:80]}")
        return types.FunctionResponse(
            id=fc.id, name=name,
            response={"result": result}
        )

    async def _send_realtime(self):
        _sent = [0]
        _dropped = [0]
        while True:
            msg = await self.out_queue.get()
            if msg.get("type") == "activity_start":
                await self.session.send_realtime_input(
                    activity_start=types.ActivityStart()
                )
                continue
            if msg.get("type") == "activity_end":
                await self.session.send_realtime_input(
                    activity_end=types.ActivityEnd()
                )
                continue
            _sent[0] += 1
            blob = types.Blob(data=msg["data"], mime_type=msg["mime_type"])
            try:
                await asyncio.wait_for(
                    self.session.send_realtime_input(media=blob),
                    timeout=5.0
                )
            except (asyncio.TimeoutError, Exception) as e:
                _dropped[0] += 1
                if _dropped[0] <= 3:
                    print(f"[NOVA] ⚠️ Audio chunk dropped: {e}")
                elif _dropped[0] % 50 == 0:
                    print(f"[NOVA] ⚠️ {_dropped[0]} total chunks dropped")

    async def _listen_audio(self):
        """Windows-compatible mic capture using sounddevice InputStream."""
        print("[NOVA] 🎤 Mic started (sounddevice)")
        loop = asyncio.get_event_loop()
        TARGET_RATE = SEND_SAMPLE_RATE
        MIC_GAIN = 1.0

        _speaking = [False]
        _silence_chunks = [0]
        SPEECH_THRESHOLD = 800
        SILENCE_CHUNKS = 25

        _dbg_cnt = [0]
        _hp_x = 0.0
        _hp_y = 0.0
        _hp_alpha = 0.9986

        def _send_activity_start():
            try:
                print("[NOVA] 🎤 >>> activity_start (speech detected)")
                loop.call_soon_threadsafe(
                    self.out_queue.put_nowait,
                    {"type": "activity_start"}
                )
            except Exception as e:
                print(f"[NOVA] ❌ activity_start failed: {e}")

        def _send_activity_end():
            try:
                print("[NOVA] 🎤 >>> activity_end (silence detected)")
                loop.call_soon_threadsafe(
                    self.out_queue.put_nowait,
                    {"type": "activity_end"}
                )
            except Exception as e:
                print(f"[NOVA] ❌ activity_end failed: {e}")

        def audio_callback(indata, frames, time_info, status):
            nonlocal _dbg_cnt, _hp_x, _hp_y
            _dbg_cnt[0] += 1

            if _dbg_cnt[0] <= 100:
                if _dbg_cnt[0] == 100:
                    print("[NOVA] 🎤 Warmup done, processing audio")
                return

            with self._speaking_lock:
                nova_speaking = self._is_speaking

            # Always feed audio level to HUD
            audio_raw = indata[:, 0].copy() if indata.ndim > 1 else indata.copy()
            rms_check = np.sqrt(np.mean(audio_raw ** 2))
            level = min(1.0, rms_check / 0.3)
            try:
                self.ui.hud.set_audio_level(level)
            except Exception:
                pass

            if nova_speaking or self.ui.muted:
                return

            # High-pass filter via numpy (fast)
            # Simple DC removal: subtract running average
            audio_float = audio_raw - np.mean(audio_raw)

            amplified = np.clip(audio_float * MIC_GAIN, -1.0, 1.0)
            int16_data = (amplified * 32767).astype(np.int16)
            data = int16_data.tobytes()

            rms = np.sqrt(np.mean(int16_data.astype(float)**2))
            if rms > SPEECH_THRESHOLD:
                if not _speaking[0]:
                    _speaking[0] = True
                    _silence_chunks[0] = 0
                    _send_activity_start()
                _silence_chunks[0] = 0
            else:
                if _speaking[0]:
                    _silence_chunks[0] += 1
                    if _silence_chunks[0] >= SILENCE_CHUNKS:
                        _speaking[0] = False
                        _send_activity_end()

            if _dbg_cnt[0] % 50 == 0:
                peak = np.max(np.abs(int16_data))
                print(f"[NOVA] 🎤 rms={rms:.0f} peak={peak} speaking={_speaking[0]}")

            try:
                loop.call_soon_threadsafe(
                    self.out_queue.put_nowait,
                    {"data": data, "mime_type": "audio/pcm;rate=16000"}
                )
            except Exception:
                pass

        try:
            try:
                stream = sd.InputStream(
                    samplerate=TARGET_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=1024,
                    callback=audio_callback,
                )
            except Exception:
                print("[NOVA] ⚠️ Default mic failed, trying system default...")
                default_in = sd.query_devices(kind="input")
                print(f"[NOVA] 🎤 Using device: {default_in['name']}")
                stream = sd.InputStream(
                    samplerate=TARGET_RATE,
                    channels=1,
                    dtype="float32",
                    blocksize=1024,
                    callback=audio_callback,
                    device=default_in["name"],
                )
            stream.start()
            print(f"[NOVA] 🎤 sounddevice InputStream started (rate={TARGET_RATE}Hz)")

        try:
            while True:
                await asyncio.sleep(0.5)
        except asyncio.CancelledError:
            pass
        finally:
            stream.stop()
            stream.close()

    async def _receive_audio(self):
        print("[NOVA] 👂 Recv started")
        out_buf, in_buf = [], []
        _recv_cnt = [0]
        _flush_task = None

        async def _flush_out():
            await asyncio.sleep(0.4)
            full = " ".join(out_buf).strip()
            if full:
                self.ui.write_log(f"NOVA: {full}")
                save_chat_message("assistant", full)
                out_buf.clear()

        async def _flush_in():
            await asyncio.sleep(0.4)
            full = " ".join(in_buf).strip()
            if full:
                self.ui.write_log(f"You: {full}")
                save_chat_message("user", full)
                in_buf.clear()

        try:
            while True:
                async for response in self.session.receive():
                    _recv_cnt[0] += 1

                    if response.go_away:
                        print("[NOVA] 🔚 go_away — session closed")
                        return

                    err = getattr(response, "error", None)
                    if err:
                        print(f"[NOVA] ⚠️ response error: {err}")

                    if _recv_cnt[0] <= 3:
                        has_data = bool(response.data)
                        has_sc = bool(response.server_content)
                        print(f"[NOVA] 🔍 Response #{_recv_cnt[0]}: data={has_data} server_content={has_sc}")

                    if response.data:
                        if self._turn_done_event and self._turn_done_event.is_set():
                            self._turn_done_event.clear()
                        try:
                            self.audio_in_queue.put_nowait(response.data)
                            if _recv_cnt[0] % 20 == 0:
                                print(f"[NOVA] 🔊 Recv audio chunk #{_recv_cnt[0]} ({len(response.data)} bytes)")
                        except asyncio.QueueFull:
                            print("[NOVA] ⚠️ audio_in_queue full — dropping chunk")

                    if response.server_content:
                        sc = response.server_content

                        if sc.output_transcription and sc.output_transcription.text:
                            txt = _clean_transcript(sc.output_transcription.text)
                            if txt:
                                out_buf.append(txt)
                                print(f"[NOVA] 💬 Nova says: {txt}")
                                if _flush_task and not _flush_task.done():
                                    _flush_task.cancel()
                                _flush_task = asyncio.create_task(_flush_out())

                        if sc.input_transcription and sc.input_transcription.text:
                            txt = _clean_transcript(sc.input_transcription.text)
                            if txt:
                                in_buf.append(txt)
                                if _flush_task and not _flush_task.done():
                                    _flush_task.cancel()
                                _flush_task = asyncio.create_task(_flush_in())

                        tc = getattr(sc, "turn_complete", None)
                        if tc:
                            print("[NOVA] ✅ turn_complete received")
                            if self._turn_done_event:
                                self._turn_done_event.set()
                            if _flush_task and not _flush_task.done():
                                _flush_task.cancel()
                            full_in = " ".join(in_buf).strip()
                            if full_in:
                                self.ui.write_log(f"You: {full_in}")
                                save_chat_message("user", full_in)
                            in_buf.clear()
                            full_out = " ".join(out_buf).strip()
                            if full_out:
                                self.ui.write_log(f"NOVA: {full_out}")
                                save_chat_message("assistant", full_out)
                            out_buf.clear()

                    if response.tool_call:
                        fn_responses = []
                        for fc in response.tool_call.function_calls:
                            print(f"[NOVA] 📞 {fc.name}")
                            fr = await self._execute_tool(fc)
                            fn_responses.append(fr)
                        await self.session.send_tool_response(
                            function_responses=fn_responses
                        )
        except Exception as e:
            print(f"[NOVA] ❌ Recv: {e}")
            traceback.print_exc()
            raise

    async def _play_audio(self):
        print("[NOVA] 🔊 Play started")

        stream = sd.RawOutputStream(
            samplerate=RECEIVE_SAMPLE_RATE,
            channels=CHANNELS,
            dtype="int16",
            blocksize=CHUNK_SIZE,
        )
        stream.start()

        try:
            while True:
                try:
                    chunk = await asyncio.wait_for(
                        self.audio_in_queue.get(),
                        timeout=0.1
                    )
                except asyncio.TimeoutError:
                    if (
                        self._turn_done_event
                        and self._turn_done_event.is_set()
                        and self.audio_in_queue.empty()
                    ):
                        self.set_speaking(False)
                        self._turn_done_event.clear()
                    continue
                self.set_speaking(True)
                try:
                    await asyncio.wait_for(
                        asyncio.to_thread(stream.write, chunk),
                        timeout=2.0
                    )
                except (asyncio.TimeoutError, Exception) as e:
                    print(f"[NOVA] ⚠️ Play write error: {e}")
                    try:
                        stream.stop()
                        stream.close()
                    except Exception:
                        pass
                    await asyncio.sleep(0.1)
                    stream = sd.RawOutputStream(
                        samplerate=RECEIVE_SAMPLE_RATE,
                        channels=CHANNELS,
                        dtype="int16",
                        blocksize=CHUNK_SIZE,
                    )
                    stream.start()
        except Exception as e:
            print(f"[NOVA] ❌ Play: {e}")
            raise
        finally:
            self.set_speaking(False)
            stream.stop()
            stream.close()

    async def run(self):
        client = genai.Client(
            api_key=_get_api_key(),
            http_options={"api_version": "v1beta"}
        )

        while True:
            try:
                print("[NOVA] 🔌 Connecting...")
                self.ui.set_state("THINKING")
                config = self._build_config()

                async with (
                    client.aio.live.connect(model=LIVE_MODEL, config=config) as session,
                    asyncio.TaskGroup() as tg,
                ):
                    self.session        = session
                    self._loop          = asyncio.get_event_loop()
                    self.audio_in_queue = asyncio.Queue(maxsize=200)
                    self.out_queue      = asyncio.Queue(maxsize=200)
                    self._turn_done_event = asyncio.Event()
                    self._stop_event = asyncio.Event()

                    print("[NOVA] ✅ Connected.")
                    self.ui.set_state("LISTENING")
                    self.ui.write_log("SYS: NOVA online.")

                    await session.send_realtime_input(
                        text="Hello, I'm ready to talk. Please acknowledge."
                    )
                    print("[NOVA] 📝 Initial prompt sent")

                    tg.create_task(self._send_realtime())
                    tg.create_task(self._listen_audio())
                    tg.create_task(self._receive_audio())
                    tg.create_task(self._play_audio())

            except Exception as e:
                print(f"[NOVA] ⚠️ {e}")
                traceback.print_exc()
            self.set_speaking(False)
            self.ui.set_state("THINKING")
            print("[NOVA] 🔄 Reconnecting in 3s...")
            await asyncio.sleep(3)


def main():
    ui = NovaUI("face.png")

    def runner():
        ui.wait_for_api_key()
        nova = NovaLive(ui)
        try:
            asyncio.run(nova.run())
        except KeyboardInterrupt:
            print("\n🔴 Shutting down...")

    threading.Thread(target=runner, daemon=True).start()
    ui.root.mainloop()

if __name__ == "__main__":
    main()
