# 🎰 POKER TƏTBİQİ - QURAŞDIRMA TƏLIMATI

## Backend (Python)
```bash
cd backend
pip install -r requirements.txt
python poker_server.py
# Server: http://localhost:8002
```

## Frontend Web
Backend serverini işə salandan sonra brauzerdə açın:
http://localhost:8002

## Frontend Mobile (Expo)
```bash
cd frontend
# poker.tsx faylını öz Expo layihənizə əlavə edin
# socket.io-client paketini install edin:
yarn add socket.io-client
```

## Konfiqurasiya
- `constants.py` - `AUTOSTART_WAIT = 30` (30 saniyə)
- `constants.py` - `TURN_TIMEOUT = 30` (oyunçu növbə vaxtı)

## Fayllar
- `poker_server.py` - Socket.IO server (port 8002)
- `room.py` - Oyun otağı məntiqi  
- `lobby.py` - Lobby management
- `events.py` - Socket event handlers
- `cards.py` - Texas Hold'em kart məntiqi
- `constants.py` - Stake tier-lər və konfiqurasiya
- `static/index.html` - Web UI HTML
- `static/styles.css` - Premium 3D CSS
- `static/app.js` - Frontend JavaScript
