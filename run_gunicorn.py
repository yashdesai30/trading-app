#!/usr/bin/env python3
"""
Run Gunicorn for Render.  Uses the eventlet worker so that the eventlet
monkey-patching in server.py is compatible with Gunicorn's concurrency model.
"""
import os
import sys

port = os.environ.get("PORT", "10000")
sys.argv = [
    "gunicorn",
    "--bind", f"0.0.0.0:{port}",
    "--worker-class", "eventlet",
    "-w", "1",
    "--timeout", "120",
    "wsgi:application",
]
from gunicorn.app.wsgiapp import run
run()
