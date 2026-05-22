# =====================================================================
# FILE: lobby.py
# Otaqların yaradılması, lobby snapshot-ları, table broadcast helpers
# =====================================================================
from collections import OrderedDict

from constants import STAKE_TIERS
from room import GameRoom


# Qlobal vəziyyət (bütün modullar bunu paylaşır)
rooms        = OrderedDict()   # room_id -> GameRoom
lobby_users  = {}              # sid -> {'name', 'avatar'}


def init_lobby_rooms():
    """Hər tier üçün 2 otaq pre-create edirik."""
    for (tid, tname, sb, bb, buyin, minp, maxp) in STAKE_TIERS:
        for i in range(1, 3):
            rid = f"{tid.upper()}-{i:02d}"
            rooms[rid] = GameRoom(rid, tid, tname, sb, bb, buyin, minp, maxp)


def lobby_snapshot():
    return {
        'online': len(lobby_users) + sum(
            len(r.players) + len(r.spectators) for r in rooms.values()
        ),
        'tiers':  [{'id': t[0], 'name': t[1]} for t in STAKE_TIERS],
        'rooms':  [{
            'id':           r.room_id,
            'tier':         r.tier_id,
            'tier_name':    r.tier_name,
            'sb':           r.SB,
            'bb':           r.BB,
            'buy_in':       r.buy_in,
            'players':      len(r.players),
            'max_players':  r.max_players,
            'phase':        r.phase,
            'starts_in':    r.starts_in(),
        } for r in rooms.values()],
    }


def table_snapshot(room, viewer_sid=None, include_hand=True):
    reveal = [viewer_sid] if (viewer_sid in room.players and include_hand) else []
    return {
        'room_id':    room.room_id,
        'tier_name':  room.tier_name,
        'players':    room.public_players(reveal_sids=reveal),
        'state':      room.get_state(),
        'starts_in':  room.starts_in(),
        'spectator':  viewer_sid in room.spectators if viewer_sid else False,
    }


def broadcast_lobby(sio):
    sio.emit('lobby_state', lobby_snapshot(), room='LOBBY')


def broadcast_table_update(sio, room):
    """Hər oyunçuya öz əli ilə birlikdə yenilik göndərir."""
    for ps in list(room.players.keys()):
        sio.emit('table_update', {
            'players':   room.public_players(reveal_sids=[ps]),
            'starts_in': room.starts_in(),
        }, to=ps)
    for sp in list(room.spectators):
        sio.emit('table_update', {
            'players':   room.public_players(),
            'starts_in': room.starts_in(),
        }, to=sp)
    broadcast_lobby(sio)


def broadcast_result(sio, room, result, log_msg, action_label, actor_sid=None):
    """Bütün player_action / phase_change / hand_over / showdown event-ləri."""
    import eventlet  # late import — eventlet must already be patched in server.py

    event_type, event_data = result
    state = room.get_state()
    targets = list(room.players.keys()) + list(room.spectators)

    if event_type == 'turn':
        next_sid = event_data
        for ps in targets:
            is_player = ps in room.players
            sio.emit('player_acted', {
                'log':          log_msg,
                'action_label': action_label,
                'actor_sid':    actor_sid,
                'state':        state,
                'players':      room.public_players(
                                    reveal_sids=[ps] if is_player else []),
                'your_turn':    (next_sid == ps) and is_player,
            }, to=ps)

    elif event_type == 'phase_change':
        labels = {'flop': '── Flop ──', 'turn': '── Turn ──', 'river': '── River ──'}
        next_sid = room.to_act[0] if room.to_act else None
        for ps in targets:
            is_player = ps in room.players
            sio.emit('phase_changed', {
                'log':       log_msg,
                'phase_log': labels.get(event_data, event_data),
                'state':     state,
                'players':   room.public_players(
                                reveal_sids=[ps] if is_player else []),
                'your_turn': (next_sid == ps) and is_player,
            }, to=ps)

    elif event_type == 'hand_over':
        winners = event_data
        room.next_dealer()
        for ps in targets:
            is_player = ps in room.players
            sio.emit('hand_over', {
                'log':     log_msg,
                'winners': winners,
                'state':   state,
                'players': room.public_players(
                              reveal_sids=[ps] if is_player else []),
            }, to=ps)
        eventlet.spawn_after(3.0, lambda: hand_finished(sio, room))

    elif event_type == 'showdown':
        winners = event_data
        active_sids = [s for s, p in room.players.items()
                       if p.get('in_hand') and not p['folded']]
        room.next_dealer()
        for ps in targets:
            is_player = ps in room.players
            sio.emit('showdown', {
                'log':     log_msg,
                'winners': winners,
                'state':   state,
                'players': room.public_players(
                              reveal_sids=active_sids + ([ps] if is_player else [])),
            }, to=ps)
        eventlet.spawn_after(4.0, lambda: hand_finished(sio, room))


def hand_finished(sio, room):
    """Showdown / hand-over-dən sonra: busted-ları çıxar, yeni raunda hazırlaş."""
    busted = [s for s, p in room.players.items() if p['chips'] <= 0]
    for s in busted:
        if s in room.players:
            sio.emit('error', {'msg': 'Chips bitdi — lobbiyə qayıdırsınız'}, to=s)
            sio.leave_room(s, room.room_id)
            del room.players[s]
    room.phase = 'waiting'
    if len(room.players) >= room.min_players:
        # autostart re-schedule — events.py tərəfindən on_fire ötürülür
        from events import auto_start_room  # circular-safe
        room.schedule_autostart(auto_start_room)
    broadcast_table_update(sio, room)
