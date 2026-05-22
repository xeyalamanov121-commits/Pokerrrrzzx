# =====================================================================
# FILE: cards.py
# Kart dəstəsinin yaradılması və 5 kartlıq əllərin qiymətləndirilməsi
# =====================================================================
from itertools import combinations
from collections import Counter

from constants import SUITS, RANKS, RANK_VAL, HAND_NAMES  # noqa: F401


def make_deck():
    """52 kartlıq standart dəstə qaytarır."""
    return [
        {'rank': r, 'suit': s, 'red': s in ['♥', '♦']}
        for s in SUITS for r in RANKS
    ]


def _rv(c):
    return RANK_VAL[c['rank']]


def evaluate_5(cards):
    """5 kartlıq əlin qiymətləndirilməsi.
    Qaytarır: (category, [kicker-lər]) — böyüklük tuple müqayisəsi ilə işləyir.
    """
    vals = sorted([_rv(c) for c in cards], reverse=True)
    suits = [c['suit'] for c in cards]
    is_flush = len(set(suits)) == 1
    is_straight = (vals == list(range(vals[0], vals[0] - 5, -1)))

    # Wheel straight: A-2-3-4-5
    if not is_straight and vals[0] == 14 and vals[1:] == [5, 4, 3, 2]:
        is_straight = True
        vals = [5, 4, 3, 2, 1]

    cnt = Counter(vals)
    grp = sorted(cnt.items(), key=lambda x: (x[1], x[0]), reverse=True)

    if is_straight and is_flush:
        # Royal Flush vs Straight Flush
        return (9 if vals[0] == 14 else 8, vals)
    if grp[0][1] == 4:
        return (7, [grp[0][0], grp[1][0]])
    if grp[0][1] == 3 and grp[1][1] == 2:
        return (6, [grp[0][0], grp[1][0]])
    if is_flush:
        return (5, vals)
    if is_straight:
        return (4, vals)
    if grp[0][1] == 3:
        return (3, [grp[0][0]] + sorted([g[0] for g in grp[1:]], reverse=True))
    if grp[0][1] == 2 and grp[1][1] == 2:
        return (2, sorted([grp[0][0], grp[1][0]], reverse=True) + [grp[2][0]])
    if grp[0][1] == 2:
        return (1, [grp[0][0]] + sorted([g[0] for g in grp[1:]], reverse=True))
    return (0, vals)


def best_hand_score(hole, community):
    """Hole + community kartlarından ən yaxşı 5-li əli tapır."""
    all_cards = hole + community
    if len(all_cards) < 5:
        return evaluate_5(all_cards)
    best = None
    for combo in combinations(all_cards, 5):
        sc = evaluate_5(list(combo))
        if best is None or sc > best:
            best = sc
    return best
