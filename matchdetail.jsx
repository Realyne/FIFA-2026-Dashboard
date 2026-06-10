/* ============================================================
   Match detail view — live events, lineups, stats from the API
   ============================================================ */
const { useState, useEffect, useRef } = React;
const WC = window.WC;

function EvIcon({ type }) {
  if (type === "goal" || type === "pen_goal" || type === "own_goal") return <ZBall size={16} />;
  if (type === "yellow") return <ZCardIcon size={16} color="#f4c81d" />;
  if (type === "red") return <ZCardIcon size={16} color="#d8341f" />;
  return <ZSubArrows size={16} />;
}

function evNote(ev) {
  if (ev.type === "pen_goal") return "Penalty";
  if (ev.type === "own_goal") return "Own goal";
  if (ev.type === "goal" && ev.assist_name) return "Assist: " + ev.assist_name;
  return null;
}

function StatBar({ label, a, b, pct }) {
  if (a == null && b == null) return null;
  a = a || 0; b = b || 0;
  const total = pct ? 100 : (a + b || 1);
  const aw = pct ? a : Math.round((a / total) * 100);
  const bw = 100 - aw;
  return (
    <div style={{ marginBottom: 14 }}>
      <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 5 }}>
        <span className="mono" style={{ fontSize: 14, fontWeight: 700 }}>{a}{pct ? "%" : ""}</span>
        <span className="label" style={{ fontSize: 10 }}>{label}</span>
        <span className="mono" style={{ fontSize: 14, fontWeight: 700 }}>{b}{pct ? "%" : ""}</span>
      </div>
      <div style={{ display: "flex", height: 10, gap: 3 }}>
        <div style={{ width: aw + "%", background: "var(--sun)", borderRadius: "5px 2px 2px 5px", transition: "width .5s" }}></div>
        <div style={{ width: bw + "%", background: "var(--teal)", borderRadius: "2px 5px 5px 2px", transition: "width .5s" }}></div>
      </div>
    </div>
  );
}

function TimelineRow({ ev, homeCode }) {
  const isHome = ev.fifa_code === homeCode;
  const note = evNote(ev);
  const card = (
    <div className="sticker" style={{ padding: "8px 12px", display: "inline-flex", flexDirection: "column",
      maxWidth: 240, textAlign: "left", borderWidth: 2,
      background: ev.type.indexOf("goal") >= 0 ? "#fff6ee" : "var(--card)",
      borderColor: ev.type.indexOf("goal") >= 0 ? "var(--sun-d)" : "var(--ink)" }}>
      <div style={{ display: "flex", alignItems: "center", gap: 7 }}>
        <EvIcon type={ev.type} />
        <span style={{ fontWeight: 700, fontSize: 14 }}>{ev.player_name || "—"}</span>
        <Flag code={ev.fifa_code} badge size={16} />
      </div>
      {note && <span className="mono" style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 2 }}>{note}</span>}
      {ev.sub_off_player && <span className="mono" style={{ fontSize: 11, color: "var(--ink-soft)", marginTop: 2 }}>↳ for {ev.sub_off_player}</span>}
    </div>
  );
  return (
    <div className="tl-grid" style={{ display: "grid", gridTemplateColumns: "minmax(0,1fr) 46px minmax(0,1fr)", alignItems: "center", columnGap: 12 }}>
      <div style={{ display: "flex", justifyContent: "flex-end" }}>{isHome ? card : null}</div>
      <div style={{ display: "flex", justifyContent: "center" }}>
        <div className="mono tl-minute" style={{ width: 42, height: 42, borderRadius: "50%", background: "var(--ink)", color: "var(--paper)",
          display: "flex", alignItems: "center", justifyContent: "center", fontWeight: 700, fontSize: 12, border: "2px solid var(--ink)" }}>
          {ev.minute}'
        </div>
      </div>
      <div style={{ display: "flex", justifyContent: "flex-start" }}>{!isHome ? card : null}</div>
    </div>
  );
}

function findPlayerId(lp, code) {
  /* lineup row -> player directory id, for deep links */
  const squad = WC.store.playersByTeam[code] || [];
  let hit = squad.find((p) => p.espn_id && lp.player_espn_id && p.espn_id === lp.player_espn_id);
  if (!hit && lp.shirt_number != null) hit = squad.find((p) => p.shirt_number === lp.shirt_number);
  if (!hit) {
    const norm = (s) => (s || "").toLowerCase().normalize("NFD").replace(/[̀-ͯ]/g, "");
    hit = squad.find((p) => norm(p.name) === norm(lp.name));
  }
  return hit ? hit.player_id : null;
}

function LineupChip({ lp, code, go, align }) {
  const pid = findPlayerId(lp, code);
  return (
    <div onClick={() => pid && go("player", { id: pid })}
      className="lift"
      style={{ display: "flex", alignItems: "center", gap: 10, padding: "6px 10px",
        cursor: pid ? "pointer" : "default",
        borderRadius: 10, transition: "background .12s", flexDirection: align === "right" ? "row-reverse" : "row" }}
      onMouseEnter={(e) => { if (pid) e.currentTarget.style.background = "rgba(232,93,42,0.1)"; }}
      onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
      <span className="mono" style={{ width: 26, height: 26, borderRadius: "50%", border: "2px solid var(--ink)",
        display: "flex", alignItems: "center", justifyContent: "center", fontSize: 11, fontWeight: 700, flexShrink: 0,
        background: "var(--card)" }}>{lp.shirt_number != null ? lp.shirt_number : "–"}</span>
      <div style={{ minWidth: 0, textAlign: align === "right" ? "right" : "left" }}>
        <div style={{ fontWeight: 600, fontSize: 13.5, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {lp.name}
        </div>
        {lp.position && <div className="mono" style={{ fontSize: 9.5, color: "var(--ink-faint)" }}>{lp.position}</div>}
      </div>
    </div>
  );
}

function LineupColumn({ lineup, code, go, align }) {
  const t = WC.store.teams[code] || {};
  return (
    <div style={{ flex: 1, minWidth: 240 }}>
      <div style={{ display: "flex", alignItems: "center", gap: 8, padding: "0 10px", marginBottom: 8,
        flexDirection: align === "right" ? "row-reverse" : "row" }}>
        <Flag code={code} badge size={22} />
        <span style={{ fontWeight: 700, fontSize: 14 }}>{t.name || code}</span>
        {lineup.formation && <span className="chip" style={{ fontSize: 9.5 }}>{lineup.formation}</span>}
      </div>
      <div className="label" style={{ fontSize: 9.5, margin: "4px 0 2px", padding: "0 10px", textAlign: align === "right" ? "right" : "left" }}>Starting XI</div>
      {(lineup.starters || []).map((lp) => <LineupChip key={(lp.player_espn_id || lp.name) + "-s"} lp={lp} code={code} go={go} align={align} />)}
      {(lineup.bench || []).length > 0 && (
        <>
          <div className="label" style={{ fontSize: 9.5, margin: "10px 0 2px", padding: "0 10px", textAlign: align === "right" ? "right" : "left" }}>Bench</div>
          {(lineup.bench || []).map((lp) => <LineupChip key={(lp.player_espn_id || lp.name) + "-b"} lp={lp} code={code} go={go} align={align} />)}
        </>
      )}
    </div>
  );
}

function TeamHero({ side }) {
  const code = side.fifa_code;
  const t = code ? WC.store.teams[code] : null;
  return (
    <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 6, flex: 1, minWidth: 0 }}>
      <Sticker size={68} rot={-3} color="#fff">
        {code
          ? <Flag code={code} size={66} />
          : <ZClock size={30} />}
      </Sticker>
      <div className="display hero-team-name" style={{ fontSize: 24, textAlign: "center", lineHeight: 1 }}>
        {t ? t.name : (side.label || "TBD")}
      </div>
      <div className="mono" style={{ fontSize: 12, color: "var(--ink-soft)" }}>{code || "—"}</div>
    </div>
  );
}

function MatchDetail({ num, go }) {
  const view = WC.getMatchView(num);
  useEffect(() => {
    WC.fetchDetail(num).catch(() => {});
    // refresh while on screen during live windows
    const t = setInterval(() => {
      const m = WC.getMatch(num);
      if (m && isLiveStatus(m.status)) WC.fetchDetail(num, true).catch(() => {});
    }, 30000);
    return () => clearInterval(t);
  }, [num]);

  if (!view) {
    return (
      <div className="wrap" style={{ paddingTop: 40, textAlign: "center" }}>
        <p className="mono">Match not found.</p>
        <button className="btn ghost" onClick={() => go("bracket")}>← Bracket</button>
      </div>
    );
  }
  const m = view.match;
  const v = WC.store.venues[m.venue_id] || {};
  const live = isLiveStatus(m.status);
  const finished = m.status === "finished";
  const upcoming = m.status === "upcoming";
  const events = (view.events || []).slice().reverse(); // newest first
  const stats = view.stats || {};
  const hs = stats.home || {}, as = stats.away || {};
  const hasStats = ["possession_pct", "shots", "shots_on_target", "corners", "fouls", "offsides"]
    .some((k) => hs[k] != null || as[k] != null);
  const lineups = view.lineups || {};
  const hasLineups = (lineups.home && (lineups.home.starters || []).length) ||
                     (lineups.away && (lineups.away.starters || []).length);
  const roundLbl = m.round === "group" ? "Group " + m.group + " · Match " + m.match_number
    : WC.ROUNDS[m.round] + " · Match " + m.match_number;
  const scoreKnown = m.home.score != null && m.away.score != null;

  return (
    <div className="rise wrap">
      <div style={{ textAlign: "center", marginBottom: 6 }}>
        <span className="chip" style={{ background: "var(--ink)", color: "var(--paper)" }}>{roundLbl}</span>
      </div>

      {/* scoreline hero */}
      <div className="sticker match-hero" style={{ padding: "28px 24px", position: "relative", marginBottom: 28, background: live ? "#fff6ee" : "var(--card)", borderColor: live ? "var(--sun-d)" : "var(--ink)" }}>
        <Tape style={{ left: "50%", top: -14, marginLeft: -46, transform: "rotate(-3deg)" }} variant={live ? "sun" : "teal"} />
        <div style={{ display: "flex", alignItems: "center", gap: 16 }}>
          <TeamHero side={m.home} />
          <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 8, flexShrink: 0 }}>
            {!scoreKnown ? (
              <div className="display" style={{ fontSize: 30, color: "var(--ink-soft)" }}>VS</div>
            ) : (
              <div key={`${m.home.score}-${m.away.score}`} className="display pop-score score-hero" style={{ fontSize: 62, lineHeight: 1, whiteSpace: "nowrap", color: live ? "var(--sun-d)" : "var(--ink)" }}>
                {m.home.score}<span style={{ color: "var(--ink-faint)", margin: "0 8px" }}>–</span>{m.away.score}
              </div>
            )}
            {m.home.pen_score != null && m.away.pen_score != null && (
              <div className="mono" style={{ fontSize: 12, color: "var(--ink-soft)" }}>
                {m.home.pen_score}–{m.away.pen_score} on penalties
              </div>
            )}
            <StatusBadge match={m} />
          </div>
          <TeamHero side={m.away} />
        </div>
        <div style={{ display: "flex", justifyContent: "center", alignItems: "center", gap: 10, marginTop: 20, flexWrap: "wrap" }}>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-soft)", display: "inline-flex", alignItems: "center", gap: 5 }}>
            <ZPin size={13} /> {v.name}{v.city ? " · " + v.city : ""}{v.country ? ", " + v.country : ""}
          </span>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-faint)" }}>—</span>
          <span className="mono" style={{ fontSize: 12, color: "var(--ink-soft)" }}>{WC.kickoffLocal(m, { weekday: "short" })} (your time)</span>
          {v.capacity && (<>
            <span className="mono" style={{ fontSize: 12, color: "var(--ink-faint)" }}>—</span>
            <span className="mono" style={{ fontSize: 12, color: "var(--ink-soft)" }}>Cap. {Number(v.capacity).toLocaleString()}</span>
          </>)}
        </div>
      </div>

      {/* two columns: timeline + stats */}
      <div style={{ display: "grid", gridTemplateColumns: hasStats ? "1.4fr 1fr" : "1fr", gap: 26, alignItems: "start" }} className="md-grid">
        <div>
          <ZineHeading kicker={live ? "Unfolding live" : finished ? "How it happened" : "Awaiting kickoff"} title="Key events" color="var(--sun)" />
          {upcoming ? (
            <div className="sticker" style={{ padding: 28, textAlign: "center" }}>
              <Sticker icon={<ZClock size={30} />} size={54} style={{ margin: "0 auto 12px" }} />
              <p className="mono" style={{ fontSize: 13, color: "var(--ink-soft)", margin: 0 }}>
                Kick-off {WC.kickoffLocal(m, { weekday: "long" })} · live timeline will appear here.
              </p>
            </div>
          ) : events.length === 0 ? (
            <p className="mono" style={{ fontSize: 13, color: "var(--ink-soft)" }}>
              No major events yet{m.minute_display ? " — " + m.minute_display + "'" : ""}.
            </p>
          ) : (
            <div style={{ position: "relative", display: "flex", flexDirection: "column", gap: 14 }}>
              <div style={{ position: "absolute", left: "50%", top: 0, bottom: 0, width: 3, marginLeft: -1.5,
                background: "repeating-linear-gradient(var(--ink-faint) 0 6px, transparent 6px 12px)", zIndex: 0 }}></div>
              {live && (
                <div style={{ textAlign: "center", zIndex: 1 }}>
                  <span className="chip live"><span className="live-dot"></span>{m.minute_display || ""}'</span>
                </div>
              )}
              {events.map((ev, i) => (
                <div key={ev.minute + "-" + ev.type + "-" + (ev.player_name || i)} style={{ zIndex: 1 }}
                  className={live && i === 0 ? (ev.fifa_code === m.home.fifa_code ? "slide-l" : "slide-r") : ""}>
                  <TimelineRow ev={ev} homeCode={m.home.fifa_code} />
                </div>
              ))}
            </div>
          )}
        </div>

        {hasStats && (
          <div>
            <ZineHeading kicker="Match stats" title="By the numbers" color="var(--teal)" />
            <div className="sticker" style={{ padding: "20px 22px" }}>
              <div style={{ display: "flex", justifyContent: "space-between", marginBottom: 16 }}>
                <span style={{ display: "flex", alignItems: "center", gap: 7 }}><Flag code={m.home.fifa_code} badge size={26} /><span className="mono" style={{ fontSize: 12, fontWeight: 700 }}>{m.home.fifa_code}</span></span>
                <span style={{ display: "flex", alignItems: "center", gap: 7 }}><span className="mono" style={{ fontSize: 12, fontWeight: 700 }}>{m.away.fifa_code}</span><Flag code={m.away.fifa_code} badge size={26} /></span>
              </div>
              <StatBar label="Possession" a={hs.possession_pct} b={as.possession_pct} pct />
              <StatBar label="Shots" a={hs.shots} b={as.shots} />
              <StatBar label="On target" a={hs.shots_on_target} b={as.shots_on_target} />
              <StatBar label="Corners" a={hs.corners} b={as.corners} />
              <StatBar label="Fouls" a={hs.fouls} b={as.fouls} />
              <StatBar label="Offsides" a={hs.offsides} b={as.offsides} />
            </div>
          </div>
        )}
      </div>

      {/* lineups */}
      {hasLineups ? (
        <div style={{ marginTop: 40 }}>
          <ZineHeading kicker="Tap a player for their profile" title="Lineups" color="var(--amber)" />
          <div className="sticker" style={{ padding: "22px 18px", position: "relative" }}>
            <Tape style={{ right: 30, top: -14, transform: "rotate(5deg)" }} />
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <LineupColumn lineup={lineups.home || {}} code={m.home.fifa_code} go={go} align="left" />
              <div style={{ width: 2, alignSelf: "stretch", background: "repeating-linear-gradient(var(--ink-faint) 0 6px, transparent 6px 12px)" }}></div>
              <LineupColumn lineup={lineups.away || {}} code={m.away.fifa_code} go={go} align="right" />
            </div>
          </div>
        </div>
      ) : (
        <div style={{ marginTop: 40 }}>
          <ZineHeading kicker="Announced ~1h before kickoff" title="Lineups" color="var(--amber)" />
          <p className="mono" style={{ fontSize: 12.5, color: "var(--ink-soft)" }}>
            Lineups aren't in yet.
            {m.home.fifa_code && <> Browse the squads: <a onClick={() => go("players")} style={{ cursor: "pointer", textDecoration: "underline" }}>player directory →</a></>}
          </p>
        </div>
      )}

      <div style={{ marginTop: 30, textAlign: "center", display: "flex", gap: 12, justifyContent: "center" }}>
        {m.round === "group"
          ? <button className="btn ghost" onClick={() => go("groups", { group: m.group })}>← Group {m.group}</button>
          : <button className="btn ghost" onClick={() => go("bracket")}>← Bracket</button>}
      </div>
    </div>
  );
}

window.MatchDetail = MatchDetail;
