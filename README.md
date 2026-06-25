# NOVA — Neural Operations & Virtual Assistant

> A personal AI desktop assistant built by **1jikx** — powered by Google Gemini's real-time audio API.

NOVA is not just another chatbot. It's a fully voice-controlled AI that sees your screen, controls your computer, manages your files, searches the web, writes code, generates images, and much more — all through natural conversation.

---

## What NOVA Can Do

| Category | Capabilities |
|---|---|
| **Voice Control** | Real-time voice conversation using Gemini's native audio model. Talk to NOVA like you'd talk to a person. |
| **Screen Vision** | Capture and analyze your screen or webcam. NOVA can read what's on your display and respond to it. |
| **Browser Control** | Open websites, search the web, click buttons, fill forms — across Chrome, Edge, Firefox, Opera, Brave, and more. |
| **Computer Control** | Type, click, scroll, manage windows, adjust volume/brightness, dark mode, screenshots, keyboard shortcuts. |
| **File Management** | Create, delete, move, copy, rename, search, organize, and analyze files and folders. |
| **Code Assistant** | Write, edit, explain, run, and debug code. Build complete multi-file projects from a single prompt. |
| **App Launcher** | Open any application on your computer with a voice command. |
| **Web Search** | Search the web, compare products, find information on anything. |
| **File Processing** | Summarize PDFs, convert formats, analyze CSVs, transcribe audio/video, OCR images, and more. |
| **Image Generation** | Generate images from text descriptions using AI. |
| **YouTube** | Play videos, summarize content, get trending videos, and extract info. |
| **Messaging** | Send messages via WhatsApp, Telegram, and other platforms. |
| **Reminders & Calendar** | Set timed reminders and manage calendar events. |
| **Weather & Flights** | Get weather reports and search Google Flights. |
| **Game Management** | Install, update, and schedule updates for Steam and Epic Games. |
| **Entertainment** | Get movie recommendations by genre/platform and game suggestions. |
| **System Utilities** | Manage startup programs, uninstall apps, analyze disk space, find duplicates, manage processes. |
| **Desktop Control** | Change wallpapers, organize desktop, clean files. |
| **Memory** | NOVA remembers things about you — your name, preferences, projects, and habits. |
| **ASCII Art** | Convert any image to text/ASCII art. |

---

## About

**NOVA** stands for **Neural Operations & Virtual Assistant**.

It was built as a personal project to explore what a truly capable AI assistant could look like — not limited to text chat, but able to actually *do things* on your computer. NOVA uses Google Gemini's real-time audio streaming API to have fluid voice conversations, combined with a full suite of tools that let it interact with your operating system, browsers, files, and the internet.

### The Vision

Most AI assistants stop at conversation. NOVA goes further — it's an AI that can **see your screen**, **control your mouse and keyboard**, **manage your files**, **write and run code**, and **take real actions** on your behalf. The goal was to build something that feels less like a chatbot and more like a real assistant sitting at your computer.

### The Tech

- **Gemini 2.5 Flash** — Real-time voice AI with native audio
- **PyQt6** — Custom dark HUD interface with animated status ring, audio-reactive visuals, and system metrics
- **Tool Architecture** — 25+ tools covering system control, web, files, code, media, and more
- **Long-term Memory** — Persistent memory system that learns about you over time
- **Multi-browser Support** — Playwright-powered browser automation
- **Cross-platform** — Works on Windows, Linux, and macOS

---

## Getting Started

### Prerequisites

- Python 3.10+
- A Google Gemini API key

### Installation

```bash
git clone https://github.com/1jikx/NOVA-AI.git
cd NOVA-AI
python -m venv venv
source venv/bin/activate   # Linux/macOS
venv\Scripts\activate      # Windows
pip install -r requirements.txt
```

### Run

```bash
python main.py  OR ./launch.sh for Linux AND  for windows just double click the run.cmd file 
```

NOVA will open its HUD interface, ask for your Gemini API key (if not set), and connect. Start talking.

---

## How It Works

```
User speaks
    ↓
Gemini processes audio + text
    ↓
Gemini calls tools (via function declarations)
    ↓
NOVA executes tools on your machine
    ↓
Results sent back to Gemini
    ↓
NOVA responds with voice
```

The entire loop runs in real-time. NOVA listens to your microphone, streams audio to Gemini, Gemini decides what to do and calls the appropriate tool, NOVA executes it locally, and the result is fed back into the conversation — all within seconds.

---

## Customization

NOVA comes with configurable themes, voices, and personalities:

- **Themes** — Switch between color schemes (Nova, Cyberpunk, Midnight, etc.)
- **Voices** — Choose from different Gemini voices
- **Personalities** — Change how NOVA communicates (formal, casual, etc.)

All settings are accessible from the in-app settings panel.

---

## Built by

**1jikx** — a developer who wanted an AI that actually works for them, not just talks to them.

---

## License

MIT
