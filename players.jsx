/* ============================================================
   Players directory — 1,200+ real squad players, search + filters
   ============================================================ */
const { useState, useMemo } = React;
const WC = window.WC;

function PlayerCard({ p, go, idx }) {
  const veteran = (p.past_world_cups || []).length > 0;
  return (
    <div
      className="sticker lift drop"
      onClick={() => go("player", { id: p.player_id })}
      style={{ padding: "14px 16px", cursor: "pointer", display: "flex", alignItems: "center", gap: 13,
        background: veteran ? "#fff6ee" : "var(--card)",
        transform: `rotate(${(idx % 3 - 1) * 0.5}deg)`,
        animationDelay: Math.min(idx * 18, 420) + "ms" }}
    >
      <PlayerAvatar player={p} size={46} />
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ display: "flex", alignItems: "center", gap: 6 }}>
          <span style={{ fontWeight: 700, fontSize: 15, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{p.name}</span>
          {veteran && <ZStar size={13} />}
        </div>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-soft)", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          #{p.shirt_number != null ? p.shirt_number : "–"} · {p.position || "—"}{p.club ? " · " + p.club : ""}
        </div>
        <div className="mono" style={{ fontSize: 10, color: "var(--ink-faint)", marginTop: 1 }}>
          {p.caps != null ? p.caps + " caps" : ""}{p.intl_goals ? " · " + p.intl_goals + " goals" : ""}
        </div>
      </div>
      <div style={{ display: "flex", flexDirection: "column", alignItems: "center", gap: 3, flexShrink: 0 }}>
        <Flag code={p.fifa_code} badge size={26} />
        <span className="mono" style={{ fontSize: 9, color: "var(--ink-faint)" }}>{p.fifa_code}</span>
      </div>
    </div>
  );
}

/* a row in the tournament Golden Boot (WC2026 goals) */
function ScorerCard({ s, go, idx, rank }) {
  const p = s.player;
  const t = WC.store.teams[s.fifa_code] || {};
  const clickable = !!p;
  return (
    <div
      className="sticker lift drop"
      onClick={clickable ? () => go("player", { id: p.player_id }) : undefined}
      style={{ padding: "14px 16px", cursor: clickable ? "pointer" : "default", display: "flex", alignItems: "center", gap: 13,
        background: "var(--card)", transform: `rotate(${(idx % 3 - 1) * 0.5}deg)`,
        animationDelay: Math.min(idx * 18, 420) + "ms" }}
    >
      <span className={"player-rank" + (rank <= 3 ? " top" : "")}>{rank}</span>
      {p ? <PlayerAvatar player={p} size={46} /> : <Flag code={s.fifa_code} badge size={40} />}
      <div style={{ minWidth: 0, flex: 1 }}>
        <div style={{ fontWeight: 700, fontSize: 15, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>{s.player_name}</div>
        <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-soft)", marginTop: 2, whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {p && p.position ? p.position + " · " : ""}{t.name || s.fifa_code}{p && p.club ? " · " + p.club : ""}
        </div>
        {s.penalties ? (
          <div className="mono" style={{ fontSize: 10, color: "var(--ink-faint)", marginTop: 1 }}>
            {s.penalties} {s.penalties === 1 ? "penalty" : "penalties"}
          </div>
        ) : null}
      </div>
      <div className="player-goals" aria-label={s.goals + " goals this tournament"}>
        <span className="player-goals-n">{s.goals}</span>
        <span className="player-goals-lbl mono">{s.goals === 1 ? "goal" : "goals"}</span>
        <Flag code={s.fifa_code} badge size={18} />
      </div>
    </div>
  );
}

function playerNorm(s) {
  return (s == null ? "" : String(s)).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

function PlayersPage({ go }) {
  const [q, setQ] = useState("");
  const [team, setTeam] = useState("");
  const [pos, setPos] = useState(null);
  const [vetsOnly, setVetsOnly] = useState(false);
  const [sortBy, setSortBy] = useState("caps"); // "caps" | "goals"
  const [shown, setShown] = useState(60);
  const inputRef = React.useRef(null);

  React.useEffect(() => { if (WC.fetchScorers) WC.fetchScorers(); }, []);

  const all = useMemo(() => {
    const list = WC.store.players.slice();
    list.sort((a, b) => (b.caps || 0) - (a.caps || 0) || (b.intl_goals || 0) - (a.intl_goals || 0));
    return list;
  }, [WC.store.players.length]);

  const needle = q.trim().toLowerCase();
  const filtered = all.filter((p) => {
    if (team && p.fifa_code !== team) return false;
    if (pos && p.position !== pos) return false;
    if (vetsOnly && !(p.past_world_cups || []).length) return false;
    if (needle) {
      const t = WC.store.teams[p.fifa_code] || {};
      const hay = (p.name + " " + (t.name || "") + " " + p.fifa_code + " " + (p.club || "") + " " + (p.position || "")).toLowerCase();
      if (hay.indexOf(needle) < 0) return false;
    }
    return true;
  });

  const POS = ["GK", "DF", "MF", "FW"];
  const teamCodes = Object.keys(WC.store.teams).sort();
  const visible = filtered.slice(0, shown);

  // tournament Golden Boot (WC2026 goals), each scorer mapped to a squad
  // player for their avatar/profile link (best-effort by ESPN id or name)
  const goalsMode = sortBy === "goals";
  const scorerRows = useMemo(() => {
    if (!goalsMode) return [];
    const byEspn = {}, byNameCode = {};
    WC.store.players.forEach((p) => {
      if (p.espn_id != null) byEspn[String(p.espn_id)] = p;
      byNameCode[p.fifa_code + "|" + playerNorm(p.name)] = p;
    });
    return (WC.store.scorers || []).map((s) => ({
      ...s,
      player: (s.player_espn_id != null && byEspn[String(s.player_espn_id)]) ||
        byNameCode[s.fifa_code + "|" + playerNorm(s.player_name)] || null,
    }));
  }, [goalsMode, WC.store.scorers, WC.store.players.length]);

  const scorersFiltered = scorerRows.filter((s) => {
    if (team && s.fifa_code !== team) return false;
    if (pos && (!s.player || s.player.position !== pos)) return false;
    if (vetsOnly && !(s.player && (s.player.past_world_cups || []).length)) return false;
    if (needle) {
      const t = WC.store.teams[s.fifa_code] || {};
      const hay = (s.player_name + " " + (t.name || "") + " " + s.fifa_code + " " + ((s.player && s.player.club) || "")).toLowerCase();
      if (hay.indexOf(needle) < 0) return false;
    }
    return true;
  });
  const scorersShown = scorersFiltered.slice(0, shown);

  return (
    <div className="rise wrap">
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}>
        <ZineHeading
          kicker={goalsMode ? "Golden Boot · goals scored in WC2026" : `${all.length} players · 48 squads`}
          title={goalsMode ? "Top scorers" : "The players"} color="var(--teal)" />
        <p className="mono" style={{ fontSize: 12, color: "var(--ink-soft)", marginBottom: 22 }}>
          {goalsMode ? `${scorersShown.length} of ${scorersFiltered.length} scorers` : `Showing ${visible.length} of ${filtered.length}`}
        </p>
      </div>

      {/* search bar */}
      <div style={{ display: "flex", gap: 14, alignItems: "center", flexWrap: "wrap", marginBottom: 16 }}>
        <div className="search-box">
          <input
            ref={inputRef}
            type="text"
            value={q}
            placeholder="Search by name, country, club, position…"
            onChange={(e) => { setQ(e.target.value); setShown(60); }}
            aria-label="Search players"
          />
          {q && <button className="btn ghost sm" style={{ boxShadow: "none", borderWidth: 2 }} onClick={() => setQ("")}>Clear</button>}
        </div>
        <select
          value={team}
          onChange={(e) => { setTeam(e.target.value); setShown(60); }}
          aria-label="Filter by squad"
          className="mono"
          style={{ padding: "10px 12px", border: "2.5px solid var(--ink)", borderRadius: 12,
            background: "var(--card)", fontSize: 12, fontWeight: 700, cursor: "pointer" }}>
          <option value="">All squads</option>
          {teamCodes.map((c) => (
            <option key={c} value={c}>{(WC.store.teams[c] || {}).name || c}</option>
          ))}
        </select>
        <span
          className={"chip filter-chip " + (vetsOnly ? "on" : "")}
          onClick={() => { setVetsOnly(!vetsOnly); setShown(60); }}
          style={{ display: "inline-flex", alignItems: "center", gap: 5 }}
        >
          <ZStar size={13} /> World Cup veterans
        </span>
      </div>

      {/* position filter + ranking sort */}
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 24 }}>
        <span className="label" style={{ fontSize: 10 }}>Position</span>
        <span className={"chip filter-chip " + (!pos ? "on" : "")} onClick={() => setPos(null)}>All</span>
        {POS.map((p) => (
          <span key={p} className={"chip filter-chip " + (pos === p ? "on" : "")}
            onClick={() => { setPos(pos === p ? null : p); setShown(60); }}>{p}</span>
        ))}
        <span style={{ flex: 1 }}></span>
        <span className="label" style={{ fontSize: 10 }}>Rank by</span>
        <span className={"chip filter-chip " + (sortBy === "caps" ? "on" : "")}
          onClick={() => { setSortBy("caps"); setShown(60); }}>Caps</span>
        <span className={"chip filter-chip " + (sortBy === "goals" ? "on" : "")}
          onClick={() => { setSortBy("goals"); setShown(60); }}
          style={{ display: "inline-flex", alignItems: "center", gap: 5 }}><ZBall size={13} /> Goals</span>
      </div>

      {/* grid */}
      {goalsMode ? (
        scorersFiltered.length === 0 ? (
          <div className="sticker" style={{ padding: 36, textAlign: "center", maxWidth: 480, margin: "30px auto" }}>
            <Sticker icon={<ZBall size={28} />} size={52} style={{ margin: "0 auto 12px" }} />
            <p className="mono" style={{ fontSize: 13, color: "var(--ink-soft)", margin: 0 }}>
              {(WC.store.scorers || []).length === 0
                ? "No goals scored yet — the board fills as matches are played."
                : "No scorers match this filter."}
            </p>
          </div>
        ) : (
          <>
            <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))", gap: 16 }}>
              {scorersShown.map((s, i) => (
                <ScorerCard key={s.player_espn_id || (s.fifa_code + s.player_name)} s={s} go={go} idx={i} rank={i + 1} />
              ))}
            </div>
            {scorersFiltered.length > shown && (
              <div style={{ textAlign: "center", marginTop: 26 }}>
                <button className="btn teal" onClick={() => setShown(shown + 90)}>
                  Show more ({scorersFiltered.length - shown} left)
                </button>
              </div>
            )}
          </>
        )
      ) : filtered.length === 0 ? (
        <div className="sticker" style={{ padding: 36, textAlign: "center", maxWidth: 480, margin: "30px auto" }}>
          <Sticker icon={<ZBall size={28} />} size={52} style={{ margin: "0 auto 12px" }} />
          <p className="mono" style={{ fontSize: 13, color: "var(--ink-soft)", margin: 0 }}>
            No players match "{q}". Try a different name, club or squad.
          </p>
        </div>
      ) : (
        <>
          <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(310px, 1fr))", gap: 16 }}>
            {visible.map((p, i) => <PlayerCard key={p.player_id} p={p} go={go} idx={i} />)}
          </div>
          {filtered.length > shown && (
            <div style={{ textAlign: "center", marginTop: 26 }}>
              <button className="btn teal" onClick={() => setShown(shown + 90)}>
                Show more ({filtered.length - shown} left)
              </button>
            </div>
          )}
        </>
      )}
    </div>
  );
}

window.PlayersPage = PlayersPage;
