# TEXAS HOLD'EM POKER - Premium 3D Edition

## 🎰 Xülasə

Premium 3D görünüşlü, real-time multiplayer Texas Hold'em poker tətbiqi. Həm **web brauzerdə**, həm də **mobil telefonda (React Native Expo)** işləyir.

## ✨ Xüsusiyyətlər

### 🎨 Premium 3D Dizayn
- ✅ 3D görünüşlü poker masası (rotateX 3D transform)
- ✅ İşıldayan qızıl borderlər və animasiyalar
- ✅ Premium kart animasiyaları
- ✅ Parlayan seat effektləri (aktiv oyunçular üçün)
- ✅ Smooth 3D transformlar və shadow effektləri

### 🎯 Oyun Mexanikası
- ✅ Real-time multiplayer (Socket.IO)
- ✅ 4-6 oyunçu dəstəyi
- ✅ 30 saniyə auto-start interval (AUTOSTART_WAIT = 30)
- ✅ Her masada oyunçuların mövqeyləri görünür
- ✅ Canlı formatda qoşulma
- ✅ 6 fərqli stake tier (Micro → Elite)
- ✅ Texas Hold'em qaydaları
- ✅ Fold, Check, Call, Raise, All-In

### 📱 Platform Dəstəyi
- ✅ **Web versiya** (HTML/CSS/JavaScript + Socket.IO)
- ✅ **Mobile versiya** (React Native Expo + Socket.IO client)
- ✅ Eyni backend server (port 8002)

## 🏗️ Arxitektura

```
/app
├── backend/
│   ├── poker_server.py       # Socket.IO poker serveri (port 8002)
│   ├── cards.py              # Kart mexanikası və hand evaluation
│   ├── room.py               # Oyun otağı məntqi
│   ├── lobby.py              # Lobby və broadcast helpers
│   ├── events.py             # Socket.IO event handlers
│   ├── constants.py          # AUTOSTART_WAIT=30, stake tiers
│   └── static/
│       ├── index.html        # Web versiya
│       ├── app.js            # Web frontend məntqi
│       └── styles.css        # Premium 3D CSS dizaynı
│
└── frontend/
    └── app/
        ├── index.tsx         # Ana səhifə (poker buttonla)
        └── poker.tsx         # Expo mobile poker interface
```

## 🚀 Servislər

### Backend (Port 8002)
```bash
sudo supervisorctl status poker
# poker                            RUNNING   pid 1341

# Loglar
tail -f /var/log/supervisor/poker.err.log
tail -f /var/log/supervisor/poker.out.log
```

### Frontend (Expo)
```bash
sudo supervisorctl status expo
# expo                             RUNNING

# Restart
sudo supervisorctl restart expo
```

## 🌐 URL-lər

### Web Versiya
- **Local**: http://localhost:8002
- **Health Check**: http://localhost:8002/health

### Mobile Versiya (Expo)
- Ana səhifədə "🎰 Oyna" buttonuna klikləyin
- `/poker` route-una yönləndirilir
- Socket.IO ilə port 8002-yə qoşulur

## 🎮 Necə Oynamaq

### Web Versiya
1. Brauzerdə açın: http://localhost:8002
2. Adınızı və avatar seçin
3. "🎰 Lobbiyə Keç" klikləyin
4. Stake tier seçin və masaya oturun
5. 4+ oyunçu toplananda oyun 30 saniyədə avtomatik başlayır

### Mobile Versiya
1. Expo app-i açın
2. Ana səhifədə "🎰 Oyna" basın
3. Profil seçin (ad + avatar)
4. Lobbidən masa seçin
5. Gözləmə otağında 30 sn sayım başlayır (4+ oyunçu)

## 🎨 Premium 3D Effektlər

### Poker Masası
```css
.poker-table {
  transform: rotateX(8deg);
  animation: tableGlow 4s ease-in-out infinite;
  box-shadow:
    0 0 0 8px rgba(212,168,67,.3),
    0 0 30px 10px rgba(212,168,67,.2),
    0 20px 80px rgba(0,0,0,.8),
    inset 0 0 100px rgba(0,0,0,.6);
}
```

### Aktiv Seats
```css
.seat.is-turn {
  animation: seatPulse 1.5s ease-in-out infinite;
  box-shadow:
    0 0 20px rgba(39,174,96,.6),
    0 0 40px rgba(39,174,96,.3);
}
```

### Kart Animasiyaları
```css
.card {
  animation: cardDeal .35s cubic-bezier(.34,1.56,.64,1);
  transform: translateZ(10px);
  box-shadow:
    0 2px 4px rgba(0,0,0,.3),
    0 4px 12px rgba(0,0,0,.5),
    inset 0 1px 2px rgba(255,255,255,.6);
}
```

## 📊 Stake Tiers

| Tier | Name | SB | BB | Buy-In | Players |
|------|------|----|----|--------|---------|
| Micro | Micro · 0.20/0.40 | $0.20 | $0.40 | $20 | 4-6 |
| Low | Low · 1/2 | $1 | $2 | $100 | 4-6 |
| Mid | Mid · 5/10 | $5 | $10 | $500 | 4-6 |
| High | High · 25/50 | $25 | $50 | $2500 | 4-6 |
| VIP | VIP · 100/200 | $100 | $200 | $10000 | 4-6 |
| Elite | Elite · 500/1000 | $500 | $1000 | $50000 | 4-6 |

## 🔧 Konfiqurasiya

### constants.py
```python
TURN_TIMEOUT   = 30   # Oyunçunun növbə vaxtı
AUTOSTART_WAIT = 30   # 30 saniyə auto-start
```

### Socket.IO Events
- `lobby_join` - Lobbiyə qoşul
- `join_table` - Masaya qoşul
- `leave_table` - Masadan çıx
- `player_action` - Oyunçu hərəkəti (fold/call/raise)
- `round_started` - Raund başladı
- `player_acted` - Oyunçu hərəkət etdi
- `phase_changed` - Fase dəyişdi (flop/turn/river)
- `showdown` - Showdown
- `hand_over` - El bitdi

## 🎯 Tamamlanmış Tələblər

✅ **Masa hissəsi düzəldildi** - Premium 3D dizayn
✅ **Canlı formatda qoşulma** - Real-time Socket.IO
✅ **Hər kəsin yeri görünür** - Visual seat positions
✅ **Premium işıldayan dizayn** - 3D effects və glow animations
✅ **30 saniyə interval** - AUTOSTART_WAIT = 30
✅ **Həm web, həm mobile** - Universal backend

## 📱 Mobile-Specific Notes

React Native Expo versiyası:
- Socket.IO client ilə port 8002-yə bağlanır
- Cross-platform (iOS + Android + Web)
- Touch-friendly interface
- Responsive dizayn

## 🐛 Debug

```bash
# Poker server logs
tail -f /var/log/supervisor/poker.err.log

# Check if running
curl http://localhost:8002/health

# Restart
sudo supervisorctl restart poker
sudo supervisorctl restart expo
```

## 🎉 Nəticə

Premium 3D Texas Hold'em poker tətbiqi hazırdır! 

- 🌐 Web: `http://localhost:8002`
- 📱 Mobile: Expo app `/poker` route
- 🎰 30 saniyə auto-start
- ✨ 3D parlayan effektlər
- 🎮 Real-time multiplayer

**Uğurlar! 🎰🃏**
