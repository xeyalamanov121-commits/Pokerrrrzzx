# =====================================================================
# FILE: room.py
# Bir poker masasının tam state-i + bütün hərəkət məntiqi
# =====================================================================
import random
import time
from collections import OrderedDict

import eventlet
import socketio as _sio_lib  # noqa: F401  (sio referansı events-də import olur)

from constants import TURN_TIMEOUT, AUTOSTART_WAIT, HAND_NAMES
from cards import make_deck, best_hand_score


class GameRoom:
    def __init__(self, room_id, tier_id, tier_name,
                 sb, bb, buy_in, min_p, max_p):
        self.room_id     = room_id
        self.tier_id     = tier_id
        self.tier_name   = tier_name
        self.SB          = sb
        self.BB          = bb
        self.buy_in      = buy_in
        self.min_players = min_p
        self.max_players = max_p

        self.players     = OrderedDict()   # sid -> player dict
        self.spectators  = set()
        self.phase       = 'waiting'
        self.deck        = []
        self.community   = []
        self.pot         = 0
        self.current_bet = 0
        self.dealer_idx  = 0
        self.to_act      = []
        self.round_num   = 0
        self.sb_sid      = None
        self.bb_sid      = None
        self.last_raise  = bb

        self.turn_timer      = None
        self.autostart_timer = None
        self.autostart_at    = None  # epoch when auto-start fires

    # ---------- köməkçi ----------
    def _sids(self):
        return list(self.players.keys())

    def _active(self):
        return [(s, p) for s, p in self.players.items()
                if p.get('in_hand') and not p['folded']]

    def starts_in(self):
        if self.autostart_at is None:
            return None
        rem = int(self.autostart_at - time.time())
        return max(0, rem)

    # ---------- avto-start ----------
    def schedule_autostart(self, on_fire):
        """on_fire: callable(room) — gerçəkdən raundu başladan funksiya."""
        if self.autostart_timer:
            try:
                self.autostart_timer.cancel()
            except Exception:
                pass
            self.autostart_timer = None
            self.autostart_at = None
        if self.phase != 'waiting':
            return
        if len(self.players) < self.min_players:
            return
        self.autostart_at = time.time() + AUTOSTART_WAIT

        def fire():
            if self.phase == 'waiting' and len(self.players) >= self.min_players:
                on_fire(self)

        self.autostart_timer = eventlet.spawn_after(AUTOSTART_WAIT, fire)

    def cancel_autostart(self):
        if self.autostart_timer:
            try:
                self.autostart_timer.cancel()
            except Exception:
                pass
        self.autostart_timer = None
        self.autostart_at = None

    # ---------- raund / blind ----------
    def start_round(self):
        self.deck = make_deck()
        random.shuffle(self.deck)
        self.community   = []
        self.pot         = 0
        self.current_bet = self.BB
        self.phase       = 'preflop'
        self.last_raise  = self.BB
        self.round_num  += 1
        self.cancel_autostart()
        self._cancel_timer()

        sids = self._sids()
        n = len(sids)
        for sid in sids:
            self.players[sid].update({
                'hand':    [self.deck.pop(), self.deck.pop()],
                'bet':     0,
                'folded':  False,
                'all_in':  False,
                'in_hand': True,
            })

        if n == 2:
            sb_idx = self.dealer_idx % n
            bb_idx = (self.dealer_idx + 1) % n
        else:
            sb_idx = (self.dealer_idx + 1) % n
            bb_idx = (self.dealer_idx + 2) % n

        self.sb_sid = sids[sb_idx]
        self.bb_sid = sids[bb_idx]
        self._post_blind(self.sb_sid, self.SB)
        self._post_blind(self.bb_sid, self.BB)

        first_idx = sb_idx if n == 2 else (bb_idx + 1) % n
        self._build_to_act(first_idx)
        if self.to_act:
            self._schedule_timer()
        return self.sb_sid, self.bb_sid

    def _post_blind(self, sid, amount):
        p = self.players[sid]
        actual = min(amount, p['chips'])
        p['chips'] = round(p['chips'] - actual, 2)
        p['bet']   = round(actual, 2)
        self.pot   = round(self.pot + actual, 2)
        if p['chips'] <= 0:
            p['all_in'] = True
            if sid in self.to_act:
                self.to_act.remove(sid)

    def _build_to_act(self, first_idx):
        sids = self._sids()
        n = len(sids)
        self.to_act = []
        for i in range(n):
            sid = sids[(first_idx + i) % n]
            p = self.players[sid]
            if p.get('in_hand') and not p['folded'] and not p['all_in']:
                self.to_act.append(sid)

    # ---------- növbə taymeri ----------
    def _cancel_timer(self):
        if self.turn_timer:
            try:
                self.turn_timer.cancel()
            except Exception:
                pass
            self.turn_timer = None

    def _schedule_timer(self, on_autofold=None):
        self._cancel_timer()
        if not self.to_act or on_autofold is None:
            return
        sid = self.to_act[0]

        def _autofold():
            if self.to_act and self.to_act[0] == sid:
                on_autofold(self, sid)

        self.turn_timer = eventlet.spawn_after(TURN_TIMEOUT, _autofold)

    def attach_autofold_callback(self, cb):
        """events.py-dən autofold callback-ini saxlayır."""
        self._autofold_cb = cb

    # _schedule_timer-i events tərəfdən gələn callback ilə yenidən səsləndir
    def _schedule_timer_internal(self):
        cb = getattr(self, '_autofold_cb', None)
        self._schedule_timer(on_autofold=cb)

    # ---------- player action API ----------
    def can_check(self, sid):
        return self.players[sid]['bet'] >= self.current_bet

    def _remove_to_act(self, sid):
        if sid in self.to_act:
            self.to_act.remove(sid)

    def apply_fold(self, sid):
        self._cancel_timer()
        p = self.players[sid]
        p['folded']  = True
        p['in_hand'] = False
        self._remove_to_act(sid)
        return self._after_action()

    def apply_check(self, sid):
        self._cancel_timer()
        self._remove_to_act(sid)
        return self._after_action()

    def apply_call(self, sid):
        self._cancel_timer()
        p = self.players[sid]
        amount = round(min(self.current_bet - p['bet'], p['chips']), 2)
        p['chips'] = round(p['chips'] - amount, 2)
        p['bet']   = round(p['bet'] + amount, 2)
        self.pot   = round(self.pot + amount, 2)
        if p['chips'] <= 0:
            p['all_in'] = True
        self._remove_to_act(sid)
        return self._after_action()

    def apply_raise(self, sid, raise_by):
        self._cancel_timer()
        p = self.players[sid]
        call_amt  = max(0, self.current_bet - p['bet'])
        raise_by  = max(raise_by, self.last_raise)
        total     = round(min(call_amt + raise_by, p['chips']), 2)
        p['chips'] = round(p['chips'] - total, 2)
        p['bet']   = round(p['bet'] + total, 2)
        self.pot   = round(self.pot + total, 2)

        actual_raise = p['bet'] - self.current_bet
        if actual_raise > self.last_raise:
            self.last_raise = actual_raise
        self.current_bet = p['bet']
        if p['chips'] <= 0:
            p['all_in'] = True

        sids = self._sids()
        n = len(sids)
        raiser_i = sids.index(sid)
        self.to_act = []
        for i in range(1, n):
            nxt = sids[(raiser_i + i) % n]
            pp = self.players[nxt]
            if pp.get('in_hand') and not pp['folded'] and not pp['all_in']:
                self.to_act.append(nxt)
        return self._after_action()

    def apply_allin(self, sid):
        return self.apply_raise(sid, self.players[sid]['chips'])

    # ---------- state machine ----------
    def _after_action(self):
        active = self._active()
        if len(active) == 1:
            w_sid = active[0][0]
            won = self._pot_to(w_sid)
            self.phase = 'hand_over'
            self._cancel_timer()
            return ('hand_over', [{
                'sid':       w_sid,
                'name':      active[0][1]['name'],
                'avatar':    active[0][1].get('avatar', ''),
                'hand':      active[0][1]['hand'],
                'hand_name': '',
                'pot_won':   won,
            }])
        if self.to_act:
            self._schedule_timer_internal()
            return ('turn', self.to_act[0])
        return self._next_phase()

    def _start_street_betting(self):
        for p in self.players.values():
            p['bet'] = 0
        self.current_bet = 0
        self.last_raise  = self.BB
        sids = self._sids()
        n = len(sids)
        first_idx = (self.dealer_idx + 1) % n if n else 0
        self._build_to_act(first_idx)
        if self.to_act:
            self._schedule_timer_internal()
        return bool(self.to_act)

    def _next_phase(self):
        self._cancel_timer()
        if self.phase == 'preflop':
            self.community = [self.deck.pop(), self.deck.pop(), self.deck.pop()]
            self.phase = 'flop'
        elif self.phase == 'flop':
            self.community.append(self.deck.pop())
            self.phase = 'turn'
        elif self.phase == 'turn':
            self.community.append(self.deck.pop())
            self.phase = 'river'
        elif self.phase == 'river':
            return self._showdown()

        can_bet = self._start_street_betting()
        if not can_bet:
            return self._next_phase()
        return ('phase_change', self.phase)

    def _showdown(self):
        self.phase = 'showdown'
        self._cancel_timer()
        active = self._active()
        if len(active) == 1:
            w_sid = active[0][0]
            won = self._pot_to(w_sid)
            return ('showdown', [{
                'sid':       w_sid,
                'name':      active[0][1]['name'],
                'avatar':    active[0][1].get('avatar', ''),
                'hand':      active[0][1]['hand'],
                'hand_name': '',
                'pot_won':   won,
            }])

        results = []
        for sid, p in active:
            score = best_hand_score(p['hand'], self.community)
            results.append({
                'sid':       sid,
                'name':      p['name'],
                'avatar':    p.get('avatar', ''),
                'score':     score,
                'hand':      p['hand'],
                'hand_name': HAND_NAMES[score[0]],
            })
        best = max(r['score'] for r in results)
        winners = [r for r in results if r['score'] == best]
        share = round(self.pot / len(winners), 2)
        for w in winners:
            self.players[w['sid']]['chips'] = round(
                self.players[w['sid']]['chips'] + share, 2)
            w['pot_won'] = share
        self.pot = 0
        return ('showdown', winners)

    def _pot_to(self, sid):
        amount = round(self.pot, 2)
        self.players[sid]['chips'] = round(self.players[sid]['chips'] + amount, 2)
        self.pot = 0
        return amount

    def next_dealer(self):
        sids = self._sids()
        if sids:
            self.dealer_idx = (self.dealer_idx + 1) % len(sids)

    # ---------- snapshot API ----------
    def get_state(self):
        current = self.to_act[0] if self.to_act else None
        return {
            'phase':          self.phase,
            'community':      self.community,
            'pot':            round(self.pot, 2),
            'current_bet':    round(self.current_bet, 2),
            'current_player': current,
            'round_num':      self.round_num,
            'small_blind':    self.SB,
            'big_blind':      self.BB,
            'min_raise':      self.last_raise,
        }

    def public_players(self, reveal_sids=None):
        reveal_sids = set(reveal_sids or [])
        sids = self._sids()
        n = len(sids)
        result = []
        for i, sid in enumerate(sids):
            p = self.players[sid]
            is_dealer = (n > 0 and i == self.dealer_idx % n)
            pd = {
                'sid':        sid,
                'name':       p['name'],
                'avatar':     p.get('avatar', '🦁'),
                'chips':      round(p['chips'], 2),
                'bet':        round(p['bet'], 2),
                'folded':     p['folded'],
                'all_in':     p.get('all_in', False),
                'in_hand':    p.get('in_hand', False),
                'is_current': bool(self.to_act and self.to_act[0] == sid),
                'is_dealer':  is_dealer,
                'is_sb':      sid == self.sb_sid,
                'is_bb':      sid == self.bb_sid,
            }
            if sid in reveal_sids:
                pd['hand'] = p.get('hand', [])
            result.append(pd)
        return result
