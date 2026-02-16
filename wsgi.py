# Gunicorn entry point (used with eventlet worker; see run_gunicorn.py).
from server import app

# Flask app is the WSGI callable; SocketIO is mounted on it.
application = app
