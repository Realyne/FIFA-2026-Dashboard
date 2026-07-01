/* ============================================================
   FIFA World Cup 2026 — Live data layer
   Consumes the wc2026-data-service API + SSE stream.
   Attaches everything to window.WC.

   Store shape:
     teams:    { FRA: {fifa_code, name, group, flag_url, color_*, ...} }
     venues:   { metlife: {id, name, city, country, capacity, tz} }
     bracket:  { 1..104: resolved match entry (home/away {fifa_code,label,
                 score,pen_score,provisional}, status, minute_display,
                 kickoff_utc, venue_id, round, group, feeds_into) }
     standings:{ A..L: {complete, rows:[...]}}
     details:  { match_number: MatchDetail }  (fetched lazily, SSE-refreshed)
     players:  [ ...all players ]  (player directory)
   ============================================================ */
(function () {
  "use strict";

  /* ---------- API base ---------- */
  // Same-origin by default (Nginx proxies /api/wc/). For local dev where the
  // SPA is served by a static server, point at the local backend.
  var API_BASE = window.WC_API_BASE != null
    ? window.WC_API_BASE
    : (location.port && location.port !== "80" && location.port !== "443" && location.port !== "8000"
        ? "http://" + location.hostname + ":8000"
        : "");

  var ROUNDS = {
    group: "Group stage",
    r32: "Round of 32",
    r16: "Round of 16",
    qf: "Quarterfinal",
    sf: "Semifinal",
    third_place: "Third place",
    final: "FINAL",
  };

  var store = {
    ready: false,
    error: null,
    teams: {},
    venues: {},
    bracket: {},      // by match_number
    standings: {},
    details: {},      // by match_number
    players: [],
    playersById: {},
    playersByTeam: {},
    scorers: [],      // tournament top scorers (Golden Boot), lazily loaded
    connection: "connecting", // connecting | live | polling | down
  };

  var listeners = [];
  function emit() {
    for (var i = 0; i < listeners.length; i++) {
      try { listeners[i](); } catch (e) { console.error(e); }
    }
  }
  function subscribe(fn) {
    listeners.push(fn);
    return function () {
      var i = listeners.indexOf(fn);
      if (i >= 0) listeners.splice(i, 1);
    };
  }

  function getJSON(path) {
    return fetch(API_BASE + path).then(function (r) {
      if (!r.ok) throw new Error(path + " -> " + r.status);
      return r.json();
    });
  }

  /* ---------- initial load ---------- */
  function applyBracket(list) {
    list.forEach(function (m) { store.bracket[m.match_number] = m; });
  }

  function init() {
    return Promise.all([
      getJSON("/api/wc/teams"),
      getJSON("/api/wc/venues"),
      getJSON("/api/wc/bracket"),
      getJSON("/api/wc/standings"),
      getJSON("/api/wc/players"),
    ]).then(function (res) {
      res[0].forEach(function (t) { store.teams[t.fifa_code] = t; });
      res[1].forEach(function (v) { store.venues[v.id] = v; });
      applyBracket(res[2]);
      store.standings = res[3];
      store.players = res[4];
      res[4].forEach(function (p) {
        store.playersById[p.player_id] = p;
        (store.playersByTeam[p.fifa_code] = store.playersByTeam[p.fifa_code] || []).push(p);
      });
      store.ready = true;
      emit();
      connectSSE();
      fetchScorers(); // non-blocking: never gate app load on it
    }).catch(function (err) {
      console.error("WC init failed", err);
      store.error = String(err);
      store.connection = "down";
      emit();
      setTimeout(init, 8000); // keep trying — kiosk-style resilience
    });
  }

  /* ---------- SSE live updates ---------- */
  var es = null;
  var backoff = 1000;

  function refreshDerived() {
    return Promise.all([
      getJSON("/api/wc/bracket").then(applyBracket),
      getJSON("/api/wc/standings").then(function (s) { store.standings = s; }),
      // goals move the scorer board; tolerate a missing endpoint (pre-deploy)
      getJSON("/api/wc/scorers").then(function (s) { store.scorers = s; }, function () {}),
    ]);
  }

  function fetchScorers() {
    return getJSON("/api/wc/scorers").then(function (s) {
      store.scorers = s; emit();
    }, function () {});
  }

  function applyMatchPatch(patch) {
    var n = patch.match_number;
    var entry = store.bracket[n];
    var st = patch.state;
    if (entry && st) {
      entry.status = st.status;
      entry.minute_display = st.minute_display;
      if (st.home) {
        entry.home.score = st.home.score;
        entry.home.pen_score = st.home.pen_score;
        if (st.home.fifa_code) { entry.home.fifa_code = st.home.fifa_code; entry.home.label = null; }
      }
      if (st.away) {
        entry.away.score = st.away.score;
        entry.away.pen_score = st.away.pen_score;
        if (st.away.fifa_code) { entry.away.fifa_code = st.away.fifa_code; entry.away.label = null; }
      }
    }
    // refresh open detail for matches we're showing
    if (store.details[n]) fetchDetail(n, true);
  }

  function connectSSE() {
    if (es) { try { es.close(); } catch (e) {} }
    es = new EventSource(API_BASE + "/api/wc/stream");
    es.onopen = function () {
      store.connection = "live";
      backoff = 1000;
      // resync after reconnect: bracket + standings cover all scores
      refreshDerived().then(emit, emit);
    };
    es.onmessage = function (msg) {
      try {
        var patch = JSON.parse(msg.data);
        if (patch.type === "match") applyMatchPatch(patch);
        else if (patch.type === "bracket") refreshDerived().then(emit);
        emit();
      } catch (e) { console.error("bad SSE frame", e); }
    };
    es.onerror = function () {
      store.connection = "polling";
      emit();
      try { es.close(); } catch (e) {}
      es = null;
      backoff = Math.min(backoff * 2, 30000);
      setTimeout(connectSSE, backoff);
    };
  }

  /* ---------- match detail (lazy) ---------- */
  var detailInflight = {};
  function fetchDetail(n, force) {
    if (!force && store.details[n]) return Promise.resolve(store.details[n]);
    if (detailInflight[n]) return detailInflight[n];
    detailInflight[n] = getJSON("/api/wc/matches/" + n).then(function (d) {
      delete detailInflight[n];
      store.details[n] = d;
      emit();
      return d;
    }, function (err) {
      delete detailInflight[n];
      throw err;
    });
    return detailInflight[n];
  }

  /* ---------- accessors ---------- */
  function getMatch(n) { return store.bracket[n] || null; }

  function getMatchView(n) {
    /* merged bracket entry + detail (if loaded) for the match page */
    var m = store.bracket[n];
    if (!m) return null;
    var d = store.details[n];
    return {
      match: m,
      detail: d || null,
      events: d ? d.events || [] : [],
      lineups: d ? d.lineups || {} : {},
      stats: d ? d.stats || {} : {},
      shootout: d ? d.shootout || {} : {},
    };
  }

  function liveMatches() {
    var out = [];
    Object.keys(store.bracket).forEach(function (k) {
      var m = store.bracket[k];
      if (m.status === "live" || m.status === "ht" || m.status === "et" || m.status === "pens") out.push(m);
    });
    return out.sort(function (a, b) { return a.match_number - b.match_number; });
  }

  function nextMatches(count) {
    var now = Date.now();
    var up = Object.keys(store.bracket).map(function (k) { return store.bracket[k]; })
      .filter(function (m) { return m.status === "upcoming" && Date.parse(m.kickoff_utc) >= now - 2 * 3600e3; })
      .sort(function (a, b) { return Date.parse(a.kickoff_utc) - Date.parse(b.kickoff_utc); });
    return up.slice(0, count || 6);
  }

  function recentResults(count) {
    return Object.keys(store.bracket).map(function (k) { return store.bracket[k]; })
      .filter(function (m) { return m.status === "finished"; })
      .sort(function (a, b) { return Date.parse(b.kickoff_utc) - Date.parse(a.kickoff_utc); })
      .slice(0, count || 6);
  }

  function matchesOn(dateStr) { // "YYYY-MM-DD" UTC
    return Object.keys(store.bracket).map(function (k) { return store.bracket[k]; })
      .filter(function (m) { return m.kickoff_utc.slice(0, 10) === dateStr; })
      .sort(function (a, b) { return Date.parse(a.kickoff_utc) - Date.parse(b.kickoff_utc); });
  }

  function headline() {
    /* the single match the topbar/landing "Live" affordance points at */
    var live = liveMatches();
    if (live.length) return live[0];
    var next = nextMatches(1);
    if (next.length) return next[0];
    var rec = recentResults(1);
    return rec.length ? rec[0] : null;
  }

  function teamName(code) {
    var t = store.teams[code];
    return t ? t.name : code;
  }

  function sideLabel(side) {
    /* display text for one side of a match (resolved name or slot label) */
    if (!side) return "TBD";
    if (side.fifa_code) return teamName(side.fifa_code);
    return side.label || "TBD";
  }

  function kickoffLocal(m, opts) {
    var d = new Date(m.kickoff_utc);
    var fmt = Object.assign({ month: "short", day: "numeric", hour: "numeric", minute: "2-digit" }, opts || {});
    try { return d.toLocaleString([], fmt); } catch (e) { return m.kickoff_utc; }
  }

  function initials(name) {
    var parts = (name || "").trim().split(/\s+/);
    if (!parts.length) return "?";
    if (parts.length === 1) return parts[0].slice(0, 2).toUpperCase();
    return (parts[0][0] + parts[parts.length - 1][0]).toUpperCase();
  }

  function age(dob) {
    if (!dob) return null;
    var b = new Date(dob), now = new Date();
    var a = now.getFullYear() - b.getFullYear();
    var mm = now.getMonth() - b.getMonth();
    if (mm < 0 || (mm === 0 && now.getDate() < b.getDate())) a--;
    return a;
  }

  window.WC = {
    store: store,
    subscribe: subscribe,
    init: init,
    fetchDetail: fetchDetail,
    fetchScorers: fetchScorers,
    getMatch: getMatch,
    getMatchView: getMatchView,
    liveMatches: liveMatches,
    nextMatches: nextMatches,
    recentResults: recentResults,
    matchesOn: matchesOn,
    headline: headline,
    teamName: teamName,
    sideLabel: sideLabel,
    kickoffLocal: kickoffLocal,
    initials: initials,
    age: age,
    ROUNDS: ROUNDS,
    API_BASE: API_BASE,
  };

  init();
})();
