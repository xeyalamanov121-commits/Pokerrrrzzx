// =====================================================================
// FILE: static/app.js
// Bütün frontend məntiqi: Socket.IO klienti + UI helpers + Audio
// =====================================================================
const AVATARS = ['🦁','🐯','🐺','🦊','🐻','🐼','🐸','🦅','🐲','🦄','👑','🎭'];

// ────────────── AUDIO ──────────────
const Audio = (() => {
  let ctx = null;
  const get = () => ctx || (ctx = new (window.AudioContext || window.webkitAudioContext)());
  const beep = (f, d, v = .12, t = 'sine') => {
    try {
      const c = get(), o = c.createOscillator(), g = c.createGain();
      o.connect(g); g.connect(c.destination);
      o.type = t; o.frequency.value = f;
      g.gain.setValueAtTime(v, c.currentTime);
      g.gain.exponentialRampToValueAtTime(.001, c.currentTime + d);
      o.start(); o.stop(c.currentTime + d);
    } catch (e) {}
  };
  return {
    card:      () => { beep(800, .08, .1); setTimeout(() => beep(1000, .06, .08), 80); },
    chip:      () => beep(600, .1, .12, 'triangle'),
    fold:      () => beep(250, .15, .1),
    win:       () => { [0,100,200].forEach(d => setTimeout(() => beep(880 + d*4, .2, .15), d)); },
    timer:     () => beep(440, .06, .05),
    chat:      () => beep(1200, .05, .06),
    your_turn: () => { beep(660, .1, .15); setTimeout(() => beep(880, .12, .15), 120); },
  };
})();

// ────────────── STATE ──────────────
const S = {
  socket: null,
  myName: '',
  myAvatar: AVATARS[0],
  myChips: 10000,
  myRoomId: null,
  myTurn: false,
  myHand: [],
  gameState: null,
  allPlayers: [],
  activeLeague: 'micro',
  rooms: [],
  tiers: [],
  timerInterval: null,
  isSpectator: false,
};

// ────────────── HELPERS ──────────────
const $ = id => document.getElementById(id);
const fmt = n => (n == null ? '0' : n.toLocaleString('en-US', { maximumFractionDigits: 2 }));
const esc = s => String(s).replace(/[&<>"']/g, c => ({
  '&':'&amp;','<':'&lt;','>':'&gt;','"':'&quot;',"'":'&#39;'
}[c]));
const phaseLabel = p => ({
  waiting:'Gözləmə', preflop:'Pre-Flop', flop:'Flop', turn:'Turn',
  river:'River', showdown:'Showdown', hand_over:'Bitdi'
}[p] || p);

function makeCard(c, small = false) {
  const d = document.createElement('div');
  d.className = 'card ' + (c.red ? 'red' : 'black') + (small ? ' sm' : '');
  d.innerHTML = `<span class="cr">${c.rank}</span><span class="cs">${c.suit}</span>`;
  return d;
}
function makeBack(small = false) {
  const d = document.createElement('div');
  d.className = 'card back' + (small ? ' sm' : '');
  return d;
}
function makeBadges(p) {
  let h = '';
  if (p.is_dealer) h += '<span class="badge badge-d">D</span>';
  if (p.is_sb)     h += '<span class="badge badge-sb">SB</span>';
  if (p.is_bb)     h += '<span class="badge badge-bb">BB</span>';
  if (p.all_in)    h += '<span class="badge badge-allin">ALL-IN</span>';
  if (p.folded)    h += '<span class="badge badge-fold">FOLD</span>';
  return h;
}
const getMyPlayer = () => S.allPlayers.find(p => p.sid === S.socket.id);

// ────────────── UI ──────────────
const UI = {
  showScreen(id) {
    document.querySelectorAll('.screen').forEach(s => s.classList.remove('active'));
    $(id).classList.add('active');
  },
  toast(msg, dur = 3500) {
    const t = $('toast');
    t.textContent = msg;
    t.classList.add('show');
    clearTimeout(t._t);
    t._t = setTimeout(() => t.classList.remove('show'), dur);
  },
  addLog(msg, cls = '') {
    const p = $('panelLog');
    const d = document.createElement('div');
    d.className = 'log-line ' + cls;
    const now = new Date();
    d.innerHTML = `<span class="log-time">${now.getHours().toString().padStart(2,'0')}:${now.getMinutes().toString().padStart(2,'0')}</span>${esc(msg)}`;
    p.appendChild(d);
    p.scrollTop = p.scrollHeight;
  },
  addChat(name, av, msg, isMe = false) {
    const p = $('panelChat');
    const d = document.createElement('div');
    d.className = 'chat-msg' + (isMe ? ' is-me' : '');
    d.innerHTML = `<span class="cm-name">${esc(av||'')} ${esc(name)}:</span><span>${esc(msg)}</span>`;
    p.appendChild(d);
    p.scrollTop = p.scrollHeight;
    if (!isMe) Audio.chat();
  },
  addLobbyChat(name, av, msg, sys = false) {
    const p = $('lobbyChatList');
    const d = document.createElement('div');
    d.className = 'lc-msg' + (sys ? ' is-sys' : '');
    if (sys) {
      d.innerHTML = esc(msg);
    } else {
      d.innerHTML = `<span class="lc-av">${esc(av||'')}</span><span class="lc-nm">${esc(name)}:</span>${esc(msg)}`;
    }
    p.appendChild(d);
    while (p.children.length > 100) p.removeChild(p.firstChild);
    p.scrollTop = p.scrollHeight;
  },
  toggleMobChat() { $('lobbySide').classList.toggle('mob-open'); },

  renderAvatarGrid() {
    const g = $('avatarGrid');
    g.innerHTML = '';
    AVATARS.forEach(av => {
      const d = document.createElement('div');
      d.className = 'av-pick' + (av === S.myAvatar ? ' sel' : '');
      d.textContent = av;
      d.onclick = () => { S.myAvatar = av; UI.renderAvatarGrid(); };
      g.appendChild(d);
    });
  },
  renderLeagueTabs() {
    const tb = $('leagueTabs');
    tb.innerHTML = '';
    S.tiers.forEach(t => {
      const d = document.createElement('div');
      d.className = 'league-tab' + (t.id === S.activeLeague ? ' active' : '');
      d.textContent = t.name;
      d.onclick = () => { S.activeLeague = t.id; UI.renderLeagueTabs(); UI.renderLobbyList(); };
      tb.appendChild(d);
    });
  },
  renderLobbyList() {
    const list = $('lobbyList');
    list.innerHTML = '';
    const rooms = S.rooms.filter(r => r.tier === S.activeLeague);
    if (!rooms.length) {
      list.innerHTML = '<div style="text-align:center;color:var(--muted);padding:30px;font-size:.85em">Bu liqada otaq tapılmadı</div>';
      return;
    }
    rooms.forEach(r => {
      const card = document.createElement('div');
      card.className = 'room-card';
      const status = r.phase === 'waiting' ? (r.players >= 4 ? 'starting' : 'waiting') : 'playing';
      const statusTxt = status === 'waiting' ? 'GÖZLƏMƏ' : status === 'starting' ? 'BAŞLAYIR' : 'OYUNDA';
      card.innerHTML = `
        <div class="rc-col"><div class="rc-lbl">Buy-In</div><div class="rc-val">${fmt(r.buy_in)}</div></div>
        <div class="rc-col"><div class="rc-lbl">Blinds</div><div class="rc-val">${fmt(r.sb)}/${fmt(r.bb)}</div></div>
        <div class="rc-col"><div class="rc-lbl">Players</div><div class="rc-val">${r.players}/${r.max_players}</div></div>
        <div class="rc-col"><span class="rc-status ${status}">${statusTxt}</span></div>
        <div class="rc-actions">
          <button class="rc-btn rc-enter" ${r.players >= r.max_players ? 'disabled' : ''} onclick="UI.enterRoom('${r.id}')">Enter</button>
          ${r.phase !== 'waiting' ? `<button class="rc-btn rc-watch" onclick="UI.spectateRoom('${r.id}')">👁 Watch</button>` : ''}
        </div>`;
      list.appendChild(card);
    });
  },

  enterLobby() {
    S.myName = ($('playerName').value || '').trim().slice(0, 16)
               || ('Player_' + Math.floor(Math.random() * 9999));
    $('hdrAv').textContent = S.myAvatar;
    $('hdrNm').textContent = S.myName;
    $('hdrCh').textContent = '💰 ' + fmt(S.myChips);
    S.socket.emit('lobby_join', { name: S.myName, avatar: S.myAvatar });
    UI.showScreen('lobbyScreen');
  },
  enterRoom(rid)    { S.socket.emit('join_table', { room_id: rid, spectate: false }); },
  spectateRoom(rid) { S.socket.emit('join_table', { room_id: rid, spectate: true  }); },
  leaveRoom() {
    S.socket.emit('leave_table', {});
    S.myRoomId = null;
    UI.showScreen('lobbyScreen');
    S.socket.emit('lobby_join', { name: S.myName, avatar: S.myAvatar });
  },
  copyRoomId() {
    navigator.clipboard.writeText(S.myRoomId).then(() => {
      $('copyHint').textContent = '✓ Kopyalandı!';
      setTimeout(() => { $('copyHint').textContent = '📋 Klikləyib kopyala'; }, 2000);
    }).catch(() => {});
  },

  updateWaitList(players, startsIn) {
    const list = $('waitPlayersList');
    list.innerHTML = '';
    players.forEach(p => {
      const d = document.createElement('div');
      d.className = 'player-row';
      d.innerHTML = `<span class="av">${esc(p.avatar||'🦁')}</span><span class="pr-name">${esc(p.name)}</span><span class="pr-chips">${fmt(p.chips)}</span>`;
      list.appendChild(d);
    });
    const need = Math.max(0, 4 - players.length);
    const c = $('countdownNum');
    const s = $('waitStatus');
    if (startsIn != null && players.length >= 4) {
      c.style.display = 'block';
      c.textContent   = startsIn;
      s.className     = 'wait-status go';
      s.textContent   = `🎰 ${startsIn} saniyəyə oyun başlayır!`;
    } else {
      c.style.display = 'none';
      s.className     = 'wait-status';
      s.textContent   = need > 0 ? `Daha ${need} oyunçu gözlənilir (min 4)…` : `${players.length} oyunçu hazır`;
    }
  },

  toggleSide()      { $('gameSide').classList.toggle('collapsed'); },
  switchTab(t) {
    $('tabLog').classList.toggle('active', t === 'log');
    $('tabChat').classList.toggle('active', t === 'chat');
    $('panelLog').classList.toggle('active', t === 'log');
    $('panelChat').classList.toggle('active', t === 'chat');
  },
  toggleRaise()     { $('raisePanel').classList.toggle('open'); },
  closeRaise()      { $('raisePanel').classList.remove('open'); },
  updateRaise(val)  { $('raiseVal').textContent = fmt(parseFloat(val)); },

  renderSeat(el, p) {
    el.style.display = 'block';
    el.className = 'seat opp-pos-' + el.dataset.idx
      + (p.is_current ? ' is-turn' : '')
      + (p.folded ? ' folded' : '')
      + (p.all_in ? ' is-allin' : '');
    el.innerHTML = `
      <div class="seat-badges">${makeBadges(p)}</div>
      <div class="seat-av">${esc(p.avatar||'🦁')}</div>
      <div class="seat-name">${esc(p.name)}</div>
      <div class="seat-chips">${fmt(p.chips)}</div>
      <div class="seat-bet">${p.bet > 0 ? fmt(p.bet) : ''}</div>
      <div class="seat-action"></div>
      <div class="seat-cards" id="oppCards${el.dataset.idx}"></div>`;
    const cards = document.getElementById('oppCards' + el.dataset.idx);
    if (p.hand && p.hand.length) {
      p.hand.forEach(c => cards.appendChild(makeCard(c, true)));
    } else if (p.in_hand && !p.folded) {
      cards.appendChild(makeBack(true));
      cards.appendChild(makeBack(true));
    }
  },

  renderGame(data) {
    const { state, players } = data;
    S.gameState  = state;
    S.allPlayers = players;
    const pp = $('phasePill');
    pp.textContent = phaseLabel(state.phase);
    pp.className   = 'phase-pill ' + state.phase;
    $('tbRoom').textContent  = S.myRoomId || '—';
    $('tbPot').textContent   = fmt(state.pot);
    $('tbBet').textContent   = fmt(state.current_bet);
    $('tbRound').textContent = state.round_num || '—';
    $('potDisp').textContent = 'Pot: ' + fmt(state.pot);

    const me = getMyPlayer();
    const opps = players.filter(p => p.sid !== S.socket.id);

    if (me) {
      $('myName').textContent  = me.name + (S.isSpectator ? ' (Spectator)' : ' (Sən)');
      $('myChips').textContent = fmt(me.chips);
      $('myBet').textContent   = me.bet > 0 ? 'Mərc: ' + fmt(me.bet) : '';
      $('myBadges').innerHTML  = makeBadges(me);
      $('myAv').textContent    = me.avatar || S.myAvatar;
      $('mySeat').className    = 'my-seat'
        + (me.is_current ? ' is-turn' : '')
        + (me.folded ? ' folded' : '')
        + (me.all_in ? ' is-allin' : '');
    } else if (S.isSpectator) {
      $('mySeat').style.display = 'none';
    }

    const cc = $('communityArea');
    const newCards = state.community || [];
    if (newCards.length !== cc.children.length) {
      cc.innerHTML = '';
      newCards.forEach(c => { cc.appendChild(makeCard(c)); Audio.card(); });
    }

    opps.forEach((p, i) => {
      if (i >= 5) return;
      const el = $('opp' + i);
      el.dataset.idx = i;
      UI.renderSeat(el, p);
    });
    for (let i = opps.length; i < 5; i++) $('opp' + i).style.display = 'none';
  },

  renderMyHand(hand) {
    S.myHand = hand;
    const el = $('myCards');
    el.innerHTML = '';
    hand.forEach(c => el.appendChild(makeCard(c)));
    Audio.card();
  },

  setMyTurn(t) {
    S.myTurn = t;
    $('actionsBar').style.display = (t && !S.isSpectator) ? 'block' : 'none';
    $('tbTurn').style.display     = t ? 'inline' : 'none';
    if (t) {
      UI.updateActionButtons();
      UI.startTimer(30);
      Audio.your_turn();
    } else {
      UI.stopTimer();
    }
  },

  updateActionButtons() {
    if (!S.gameState) return;
    const me = getMyPlayer();
    if (!me) return;
    const callAmt  = Math.max(0, Math.min(S.gameState.current_bet - (me.bet || 0), me.chips));
    const canCheck = (me.bet || 0) >= S.gameState.current_bet;
    $('btnCheck').style.display = canCheck ? 'inline-flex' : 'none';
    $('btnCall').style.display  = canCheck ? 'none' : 'inline-flex';
    $('callSub').textContent    = callAmt > 0 ? fmt(callAmt) : '';

    const slider = $('raiseSlider');
    const minR   = S.gameState.min_raise || S.gameState.big_blind || 1;
    slider.min   = minR;
    slider.max   = me.chips;
    slider.step  = Math.max(minR / 4, 0.1);
    slider.value = Math.min(Math.max(minR * 2, minR), me.chips);
    UI.updateRaise(slider.value);

    const pot = S.gameState.pot || 0;
    const bb  = S.gameState.big_blind || 1;
    const qb  = $('quickBets');
    qb.innerHTML = '';
    const bets = [
      { l: 'Min',  v: minR    },
      { l: '2BB',  v: bb * 2  },
      { l: '3BB',  v: bb * 3  },
      { l: '½Pot', v: pot / 2 },
      { l: 'Pot',  v: pot     },
    ].filter(b => b.v > 0 && b.v <= me.chips && b.v >= minR);

    const seen = new Set();
    bets.forEach(b => {
      const k = Math.round(b.v * 100);
      if (seen.has(k)) return;
      seen.add(k);
      const btn = document.createElement('button');
      btn.className = 'qb-btn';
      btn.textContent = `${b.l} (${fmt(b.v)})`;
      btn.onclick = () => {
        const sl = $('raiseSlider');
        sl.value = Math.min(b.v, sl.max);
        UI.updateRaise(sl.value);
        $('raisePanel').classList.add('open');
      };
      qb.appendChild(btn);
    });
  },

  startTimer(secs) {
    UI.stopTimer();
    const bar = $('timerBar');
    bar.style.transition = 'none';
    bar.style.width      = '100%';
    bar.style.background = 'var(--green2)';
    requestAnimationFrame(() => {
      bar.style.transition = `width ${secs}s linear, background ${secs * 0.5}s linear`;
      bar.style.width      = '0%';
      bar.style.background = 'var(--red2)';
    });
    let rem = secs;
    S.timerInterval = setInterval(() => {
      rem--;
      if (rem <= 5 && rem > 0) Audio.timer();
      if (rem <= 0) clearInterval(S.timerInterval);
    }, 1000);
  },
  stopTimer() {
    clearInterval(S.timerInterval);
    const b = $('timerBar');
    b.style.transition = 'none';
    b.style.width      = '0%';
  },

  closeOverlay() { $('resultOverlay').classList.remove('show'); },

  showWinnerOverlay(title, winners, allPlayers, showNext = true) {
    $('overlayTitle').textContent     = title;
    $('nextRoundBtn').style.display   = showNext ? 'inline-flex' : 'none';

    let html = '';
    if (winners.length === 1) {
      const w = winners[0];
      html += `<div class="winner-name">🏆 ${esc(w.avatar||'')} ${esc(w.name)}</div>`;
      if (w.hand_name) html += `<div class="winner-hand">${esc(w.hand_name)}</div>`;
      html += `<div class="winner-pot">+${fmt(w.pot_won || 0)}</div>`;
      if (w.hand && w.hand.length) {
        html += '<div class="winner-cards">';
        w.hand.forEach(c => {
          html += `<div class="card ${c.red ? 'red' : 'black'}"><span class="cr">${c.rank}</span><span class="cs">${c.suit}</span></div>`;
        });
        html += '</div>';
      }
    } else {
      html += `<div class="winner-pot">Split pot — ${fmt((winners[0]||{}).pot_won || 0)} each</div>`;
      winners.forEach(w => {
        html += `<div class="winner-name" style="font-size:1.05em">🏆 ${esc(w.avatar||'')} ${esc(w.name)}</div>`;
      });
    }

    const revealed = (allPlayers || []).filter(p => p.hand && p.hand.length);
    if (revealed.length > 1) {
      const wSids = new Set(winners.map(w => w.sid));
      html += '<div class="all-hands" style="margin-top:10px">';
      revealed.forEach(p => {
        const isW = wSids.has(p.sid);
        html += `<div class="hand-row ${isW ? 'is-winner-row' : ''}"><span class="hr-player">${esc(p.avatar||'')} ${esc(p.name)}</span><div class="hr-cards">`;
        p.hand.forEach(c => {
          html += `<div class="card sm ${c.red ? 'red' : 'black'}"><span class="cr">${c.rank}</span><span class="cs">${c.suit}</span></div>`;
        });
        html += `</div><span class="hr-name">${esc(p.hand_name||'')}</span></div>`;
      });
      html += '</div>';
    }

    $('overlayBody').innerHTML = html;
    $('resultOverlay').classList.add('show');
    Audio.win();
  },
};

// ────────────── GAME ACTIONS ──────────────
const Game = {
  action(a) {
    if (S.isSpectator) return;
    S.socket.emit('player_action', { action: a });
    UI.closeRaise();
    UI.stopTimer();
  },
  confirmRaise() {
    const amount = parseFloat($('raiseSlider').value);
    S.socket.emit('player_action', { action: 'raise', amount });
    UI.closeRaise();
    UI.stopTimer();
  },
  nextRound() { UI.closeOverlay(); },
  sendChat() {
    const inp = $('chatInp');
    const msg = (inp.value || '').trim();
    if (!msg) return;
    S.socket.emit('table_chat', { msg });
    inp.value = '';
    UI.addChat(S.myName, S.myAvatar, msg, true);
    UI.switchTab('chat');
  },
  sendLobbyChat() {
    const inp = $('lobbyChatInp');
    const msg = (inp.value || '').trim();
    if (!msg) return;
    S.socket.emit('lobby_chat', { msg });
    inp.value = '';
    UI.addLobbyChat(S.myName, S.myAvatar, msg);
  },
};

// ────────────── SOCKET WIRING ──────────────
window.addEventListener('load', () => {
  S.socket = io();
  UI.renderAvatarGrid();
  if (!$('playerName').value) {
    $('playerName').value = 'Player_' + Math.floor(1000 + Math.random() * 9000);
  }

  S.socket.on('connect',     () => console.log('connected'));
  S.socket.on('lobby_state', d => {
    S.tiers = d.tiers;
    S.rooms = d.rooms;
    $('onlineCount').textContent = d.online;
    UI.renderLeagueTabs();
    UI.renderLobbyList();
  });
  S.socket.on('lobby_chat', d => {
    if (d.sid === S.socket.id) return;
    UI.addLobbyChat(d.name, d.avatar, d.msg);
  });
  S.socket.on('lobby_sys', d => UI.addLobbyChat('', '', d.msg, true));

  S.socket.on('joined_table', d => {
    S.myRoomId    = d.room_id;
    S.isSpectator = !!d.spectator;
    $('waitRoomId').textContent = d.tier_name;
    $('waitTitle').textContent  = d.spectator ? 'Tamaşaçı' : 'Gözləmə Otağı';
    UI.showScreen('waitingScreen');
    UI.updateWaitList(d.players, d.starts_in);
    if (d.in_game) {
      UI.showScreen('gameScreen');
      UI.renderGame(d);
      if (d.hand) UI.renderMyHand(d.hand);
      UI.setMyTurn(!!d.your_turn);
    }
  });

  S.socket.on('table_update', d => UI.updateWaitList(d.players, d.starts_in));

  S.socket.on('round_started', d => {
    UI.showScreen('gameScreen');
    UI.renderGame(d);
    if (d.hand) UI.renderMyHand(d.hand);
    UI.setMyTurn(!!d.your_turn);
    UI.addLog(`── Raund ${d.state.round_num} | SB:${fmt(d.sb)} BB:${fmt(d.bb)} ──`, 'gold');
  });

  S.socket.on('player_acted', d => {
    UI.renderGame(d);
    UI.setMyTurn(!!d.your_turn);
    const lbl = d.action_label || '';
    UI.addLog(d.log,
      lbl.startsWith('FOLD') ? 'red'
      : (lbl.startsWith('RAISE') || lbl.startsWith('ALL')) ? 'gold'
      : 'green'
    );
    Audio.chip();
  });

  S.socket.on('phase_changed', d => {
    UI.renderGame(d);
    UI.setMyTurn(!!d.your_turn);
    UI.addLog(d.log, 'green');
    UI.addLog(d.phase_log, 'phase');
  });

  S.socket.on('hand_over', d => {
    UI.renderGame(d);
    UI.setMyTurn(false);
    UI.addLog(d.log, 'red');
    const w = d.winners[0];
    UI.addLog(`🏆 ${w.name} qazandı (${fmt(w.pot_won)})`, 'gold');
    UI.showWinnerOverlay('El Bitdi!', d.winners, d.players, true);
  });

  S.socket.on('showdown', d => {
    UI.renderGame(d);
    UI.setMyTurn(false);
    UI.addLog(d.log, 'red');
    UI.showWinnerOverlay('Showdown!', d.winners, d.players, true);
  });

  S.socket.on('player_left',     d => UI.addLog(`${esc(d.name)} ayrıldı`, 'system'));
  S.socket.on('table_chat',      d => { if (d.sid !== S.socket.id) UI.addChat(d.name, d.avatar, d.msg); });
  S.socket.on('player_autofold', d => UI.addLog(`${esc(d.name)} vaxt keçdi → fold`, 'red'));
  S.socket.on('chips_update',    d => {
    S.myChips = d.chips;
    $('hdrCh').textContent = '💰 ' + fmt(d.chips);
  });
  S.socket.on('error', d => UI.toast(d.msg));
});
