#!/usr/bin/env python3
"""
Run Gunicorn for Render.  Uses gthread worker with real OS threads so the
Groww feed can run its own asyncio loop without eventlet interference.
"""
import os
import sys

port = os.environ.get("PORT", "10000")
sys.argv = [
    "gunicorn",
    "--bind", f"0.0.0.0:{port}",
    "--worker-class", "gthread",
    "-w", "1",
    "--threads", "20",
    "--timeout", "120",
    "wsgi:application",
]
from gunicorn.app.wsgiapp import run
run()
