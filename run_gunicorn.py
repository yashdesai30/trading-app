#!/usr/bin/env python3
"""
Run Gunicorn with eventlet after patching the process.
Must call eventlet.monkey_patch() before any other imports so RLock etc. are greened.
"""
import os
import sys

import eventlet
eventlet.monkey_patch()

# Now run gunicorn (same process is patched; workers will inherit if forked after this)
port = os.environ.get("PORT", "10000")
sys.argv = [
    "gunicorn",
    "--bind", f"0.0.0.0:{port}",
    "--worker-class", "eventlet",
    "-w", "1",
    "wsgi:application",
]
from gunicorn.app.wsgiapp import run
run()
