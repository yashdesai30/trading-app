#!/usr/bin/env python3
"""
Run Gunicorn for Render. Uses gthread (not eventlet) so the Groww feed thread
can run its own asyncio loop without "Cannot run the event loop while another loop is running".
"""
import os
import sys

port = os.environ.get("PORT", "10000")
sys.argv = [
    "gunicorn",
    "--bind", f"0.0.0.0:{port}",
    "--worker-class", "gthread",
    "-w", "1",
    "--threads", "4",
    "wsgi:application",
]
from gunicorn.app.wsgiapp import run
run()
