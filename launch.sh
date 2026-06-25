#!/bin/bash
# NOVA Launcher — always uses the correct venv
cd "$(dirname "$0")"
source venv/bin/activate
exec python3 main.py
