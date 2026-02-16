# Gunicorn entry point: run eventlet.monkey_patch() before any other imports.
# Must be the first executable lines so RLock etc. are greened.
import eventlet
eventlet.monkey_patch()

from server import app

# Flask app is the WSGI callable; SocketIO is mounted on it.
application = app
