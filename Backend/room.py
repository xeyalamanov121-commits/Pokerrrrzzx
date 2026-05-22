# =====================================================================
# FILE: room.py
# Bir poker masasının tam state-i + bütün hərəkət məntiqi
# =====================================================================
import random
import time
from collections import OrderedDict

import eventlet
import socketio as _sio_lib

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
        self.autostart_at    = None

    # ---------- köməkçi funksiyalar ----------
    def _sids(self):
        return list(self.players.keys())

    def _active(self):
        return [(s, p) for s, p in self.players.items()
                if p.get('in_hand') and not p['folded']]

    # ---------- raund / blind məntiqi ----------
    def start_round(self):
        self.deck = make_deck()
        random.shuffle(self.deck)
        self.community   = []
        self.pot         = 0
        self.current_bet = self.BB
        self.phase       = 'preflop'
        self.last_raise  = self.BB
        self.round_num  += 1
        
        # Oyunçuların əllərini payla
        sids = self._sids()
        for sid in sids:
            self.players[sid].update({
                'hand':    [self.deck.pop(), self.deck.pop()],
                'bet':     0,
                'folded':  False,
                'all_in':  False,
                'in_hand': True,
            })
        return True

    # ---------- player action API ----------
    def apply_fold(self, sid):
        p = self.players[sid]
        p['folded']  = True
        p['in_hand'] = False
        return self._after_action()

    def apply_call(self, sid):
        p = self.players[sid]
        amount = round(min(self.current_bet - p['bet'], p['chips']), 2)
        p['chips'] = round(p['chips'] - amount, 2)
        p['bet']   = round(p['bet'] + amount, 2)
        self.pot   = round(self.pot + amount, 2)
        return self._after_action()

    # ---------- state machine və showdown ----------
    def _showdown(self):
        self.phase = 'showdown'
        active = self._active()
        results = []
        for sid, p in active:
            score = best_hand_score(p['hand'], self.community)
            results.append({
                'sid':       sid,
                'score':     score,
                'hand':      p['hand'],
                'hand_name': HAND_NAMES[score[0]],
            })
        # Qalibi təyin et və potu böl
        best = max(r['score'] for r in results)
        winners = [r for r in results if r['score'] == best]
        return winners

    # ---------- snapshot API ----------
    def get_state(self):
        return {
            'phase':          self.phase,
            'community':      self.community,
            'pot':            round(self.pot, 2),
            'current_bet':    round(self.current_bet, 2),
            'round_num':      self.round_num,
        }

