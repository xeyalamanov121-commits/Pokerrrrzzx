# =====================================================================
# FILE: poker_server.py
# Poker Socket.IO server running on port 8002
# =====================================================================
import os
import mimetypes
import eventlet
eventlet.monkey_patch()

import eventlet.wsgi
import socketio

from constants import STAKE_TIERS
from lobby import init_lobby_rooms, rooms
from events import register_events

# Socket.IO server
sio = socketio.Server(cors_allowed_origins="*", async_mode='eventlet')
register_events(sio)

# Static file server
STATIC_DIR = os.path.join(os.path.dirname(__file__), 'static')

def static_app(environ, start_response):
    path = environ.get('PATH_INFO', '/')
    if path == '/health':
        start_response('200 OK', [('Content-Type', 'text/plain')])
        return [b'ok']

    if path in ('/', '/index.html'):
        rel = 'index.html'
    else:
        rel = path.lstrip('/')

    file_path = os.path.normpath(os.path.join(STATIC_DIR, rel))
    if not file_path.startswith(STATIC_DIR) or not os.path.isfile(file_path):
        start_response('404 Not Found', [('Content-Type', 'text/plain')])
        return [b'Not Found']

    ctype, _ = mimetypes.guess_type(file_path)
    ctype = ctype or 'application/octet-stream'
    with open(file_path, 'rb') as f:
        data = f.read()
    start_response('200 OK', [
        ('Content-Type', ctype + '; charset=utf-8'),
        ('Content-Length', str(len(data))),
    ])
    return [data]

app = socketio.WSGIApp(sio, static_app)

if __name__ == '__main__':
    init_lobby_rooms()
    port = int(os.environ.get('POKER_PORT', 8002))
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    print('  TEXAS HOLD\'EM POKER — Premium Edition')
    print(f'  Port: {port}')
    print(f'  Tiers: {", ".join(t[1] for t in STAKE_TIERS)}')
    print(f'  Rooms: {len(rooms)} ({len(STAKE_TIERS)} tier × 2)')
    print('  Min oyunçu / masa: 4   ·   Max: 6')
    print('  30 saniyə auto-start interval')
    print('━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━━')
    eventlet.wsgi.server(eventlet.listen(('0.0.0.0', port)), app, log_output=False)
