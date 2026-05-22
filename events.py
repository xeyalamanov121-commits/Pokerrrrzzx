# =====================================================================
# FILE: events.py
# Socket.IO event handler-ləri: connect / disconnect / lobby / join /
# leave / player_action / chat
# =====================================================================
from constants import AVATARS
from lobby import (
    rooms, lobby_users,
    lobby_snapshot, table_snapshot,
    broadcast_lobby, broadcast_table_update, broadcast_result,
)


# ──────────────────────────────────────────────────────────
# avto-start callback (lobby.py-də referans alınır)
# ──────────────────────────────────────────────────────────
def auto_start_room(room):
    """Min oyunçu varsa raundu başlat və hamıya bildiriş göndər."""
    from server import sio  # late import: server-də qurulan instance
    if room.phase != 'waiting':
        return
    if len(room.players) < room.min_players:
        return

    sb_sid, bb_sid = room.start_round()  # noqa: F841
    state = room.get_state()

    # Aktiv oyunçulara öz hand-ı ilə
    for ps in room.players:
        hand = room.players[ps]['hand']
        your_turn = bool(room.to_act and room.to_act[0] == ps)
        sio.emit('round_started', {
            'hand':       hand,
            'state':      state,
            'players':    room.public_players(reveal_sids=[ps]),
            'sb':         room.SB,
            'bb':         room.BB,
            'your_turn':  your_turn,
        }, to=ps)

    # Tamaşaçılara (kart yox)
    for sp in list(room.spectators):
        sio.emit('round_started', {
            'hand':       [],
            'state':      state,
            'players':    room.public_players(),
            'sb':         room.SB,
            'bb':         room.BB,
            'your_turn':  False,
        }, to=sp)

    broadcast_lobby(sio)


# ──────────────────────────────────────────────────────────
# Autofold callback — room._schedule_timer-ə qoşulur
# ──────────────────────────────────────────────────────────
def autofold_player(room, sid):
    from server import sio
    if sid not in room.players:
        return
    name = room.players[sid]['name']
    result = room.apply_fold(sid)
    sio.emit('player_autofold', {'name': name}, room=room.room_id)
    broadcast_result(sio, room, result,
                     f'{name} vaxt keçdiyinə görə fold etdi', 'FOLD')


# ──────────────────────────────────────────────────────────
# Event handlers-i sio-ya qeyd edən funksiya
# ──────────────────────────────────────────────────────────
def register_events(sio):

    @sio.event
    def connect(sid, environ):
        print(f'[+] {sid}')

    @sio.event
    def disconnect(sid):
        print(f'[-] {sid}')
        lobby_users.pop(sid, None)

        for room_id, room in list(rooms.items()):
            if sid in room.spectators:
                room.spectators.discard(sid)
                sio.leave_room(sid, room_id)
                broadcast_table_update(sio, room)

            if sid in room.players:
                name = room.players[sid]['name']
                if room.phase not in ('waiting', 'hand_over', 'showdown'):
                    if room.to_act and room.to_act[0] == sid:
                        result = room.apply_fold(sid)
                        sio.emit('player_autofold', {'name': name}, room=room_id)
                        broadcast_result(sio, room, result,
                                         f'{name} ayrıldı → fold', 'FOLD')
                    elif room.players[sid].get('in_hand') and not room.players[sid]['folded']:
                        room.players[sid]['folded']  = True
                        room.players[sid]['in_hand'] = False
                        if sid in room.to_act:
                            room.to_act.remove(sid)
                del room.players[sid]
                if len(room.players) < room.min_players:
                    room.cancel_autostart()
                sio.emit('player_left', {'name': name}, room=room_id)
                broadcast_table_update(sio, room)
        broadcast_lobby(sio)

    # -------- LOBBY --------
    @sio.event
    def lobby_join(sid, data):
        name = (data.get('name') or 'Player')[:16]
        avatar = data.get('avatar') or AVATARS[0]
        if avatar not in AVATARS:
            avatar = AVATARS[0]
        lobby_users[sid] = {'name': name, 'avatar': avatar}
        sio.enter_room(sid, 'LOBBY')
        sio.emit('lobby_sys',
                 {'msg': f'{avatar} {name} lobbiyə qoşuldu'}, room='LOBBY')
        broadcast_lobby(sio)
        sio.emit('lobby_state', lobby_snapshot(), to=sid)

    @sio.event
    def lobby_chat(sid, data):
        if sid not in lobby_users:
            return
        msg = (data.get('msg') or '').strip()[:120]
        if not msg:
            return
        u = lobby_users[sid]
        sio.emit('lobby_chat',
                 {'sid': sid, 'name': u['name'], 'avatar': u['avatar'], 'msg': msg},
                 room='LOBBY')

    # -------- TABLE --------
    @sio.event
    def join_table(sid, data):
        room_id  = (data.get('room_id') or '').strip().upper()
        spectate = bool(data.get('spectate'))

        if room_id not in rooms:
            sio.emit('error', {'msg': 'Otaq tapılmadı!'}, to=sid)
            return
        room = rooms[room_id]

        if sid not in lobby_users:
            sio.emit('error', {'msg': 'Lobbiyə daxil olun'}, to=sid)
            return
        u = lobby_users[sid]

        # Başqa masada olub-olmaması
        for r in rooms.values():
            if sid in r.players or sid in r.spectators:
                sio.emit('error', {'msg': 'Artıq başqa masadasınız'}, to=sid)
                return

        # Oyun gedirsə avtomatik spectator
        if not spectate and room.phase != 'waiting':
            spectate = True

        if spectate:
            room.spectators.add(sid)
            sio.enter_room(sid, room_id)
            sio.leave_room(sid, 'LOBBY')
            snap = table_snapshot(room, viewer_sid=sid, include_hand=False)
            snap['in_game']    = room.phase != 'waiting'
            snap['spectator']  = True
            sio.emit('joined_table', snap, to=sid)
            broadcast_lobby(sio)
            return

        if len(room.players) >= room.max_players:
            sio.emit('error', {'msg': 'Masa doludur!'}, to=sid)
            return

        sio.enter_room(sid, room_id)
        sio.leave_room(sid, 'LOBBY')
        room.players[sid] = {
            'name':    u['name'],
            'avatar':  u['avatar'],
            'chips':   float(room.buy_in),
            'hand':    [],
            'bet':     0,
            'folded':  False,
            'all_in':  False,
            'in_hand': False,
        }

        # Autofold callback room-a bağlanır
        room.attach_autofold_callback(autofold_player)

        snap = table_snapshot(room, viewer_sid=sid)
        snap['in_game']   = False
        snap['spectator'] = False
        sio.emit('joined_table', snap, to=sid)

        if len(room.players) >= room.min_players:
            room.schedule_autostart(auto_start_room)
        broadcast_table_update(sio, room)

    @sio.event
    def leave_table(sid, data):
        for room_id, room in list(rooms.items()):
            if sid in room.spectators:
                room.spectators.discard(sid)
                sio.leave_room(sid, room_id)
                broadcast_table_update(sio, room)

            if sid in room.players:
                name = room.players[sid]['name']
                if room.phase not in ('waiting', 'hand_over', 'showdown') \
                        and room.players[sid].get('in_hand'):
                    if room.to_act and room.to_act[0] == sid:
                        result = room.apply_fold(sid)
                        broadcast_result(sio, room, result,
                                         f'{name} masadan ayrıldı → fold', 'FOLD')
                    else:
                        room.players[sid]['folded']  = True
                        room.players[sid]['in_hand'] = False
                        if sid in room.to_act:
                            room.to_act.remove(sid)
                del room.players[sid]
                sio.leave_room(sid, room_id)
                if len(room.players) < room.min_players:
                    room.cancel_autostart()
                sio.emit('player_left', {'name': name}, room=room_id)
                broadcast_table_update(sio, room)

        if sid in lobby_users:
            sio.enter_room(sid, 'LOBBY')
            sio.emit('lobby_state', lobby_snapshot(), to=sid)

    @sio.event
    def player_action(sid, data):
        room_id = None
        for rid, r in rooms.items():
            if sid in r.players:
                room_id = rid
                break
        if not room_id:
            return
        room = rooms[room_id]

        if not room.to_act or room.to_act[0] != sid:
            sio.emit('error', {'msg': 'Sıra sizdə deyil!'}, to=sid)
            return

        action = data.get('action')
        p = room.players[sid]
        pname = p['name']

        if action == 'fold':
            result   = room.apply_fold(sid)
            log_msg  = f'{pname} fold etdi'
            label    = 'FOLD'

        elif action == 'check':
            if not room.can_check(sid):
                sio.emit('error', {'msg': 'Check edə bilməzsiniz — call edin!'}, to=sid)
                return
            result  = room.apply_check(sid)
            log_msg = f'{pname} check etdi'
            label   = 'CHECK'

        elif action == 'call':
            call_amt = round(min(room.current_bet - p['bet'], p['chips']), 2)
            result   = room.apply_call(sid)
            log_msg  = f'{pname} call etdi ({call_amt})'
            label    = f'CALL {call_amt}'

        elif action == 'raise':
            try:
                amount = float(data.get('amount', room.BB))
            except Exception:
                amount = room.BB
            amount  = max(amount, room.last_raise)
            result  = room.apply_raise(sid, amount)
            log_msg = f'{pname} raise (+{amount})'
            label   = f'RAISE +{amount}'

        elif action == 'allin':
            amount  = p['chips']
            result  = room.apply_allin(sid)
            log_msg = f'{pname} ALL-IN! ({amount})'
            label   = f'ALL-IN {amount}'

        else:
            return

        broadcast_result(sio, room, result, log_msg, label, actor_sid=sid)

    @sio.event
    def table_chat(sid, data):
        for rid, room in rooms.items():
            if sid in room.players or sid in room.spectators:
                msg = (data.get('msg') or '').strip()[:120]
                if not msg:
                    return
                if sid in room.players:
                    name   = room.players[sid]['name']
                    avatar = room.players[sid].get('avatar', '')
                else:
                    u      = lobby_users.get(sid, {})
                    name   = u.get('name', 'Spectator')
                    avatar = u.get('avatar', '')
                sio.emit('table_chat',
                         {'sid': sid, 'name': name, 'avatar': avatar, 'msg': msg},
                         room=rid)
                return
