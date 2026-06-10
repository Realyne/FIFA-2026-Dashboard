/* ============================================================
   Player detail — real career data (Wikipedia squads + Wikidata)
   No photos by design: initials avatar + outbound fifa.com link.
   ============================================================ */
const WC = window.WC;

function StatTile({ value, label, color }) {
  return (
    <div className="sticker" style={{ padding: "14px 12px", textAlign: "center", flex: 1, minWidth: 88 }}>
      <div className="display" style={{ fontSize: 34, color: color || "var(--ink)", lineHeight: 1 }}>{value != null ? value : "—"}</div>
      <div className="label" style={{ fontSize: 9, marginTop: 4 }}>{label}</div>
    </div>
  );
}

function teamMatchFor(code) {
  /* deep-link target: live > next upcoming > most recent for this team */
  const ms = Object.keys(WC.store.bracket).map((k) => WC.store.bracket[k])
    .filter((m) => m.home.fifa_code === code || m.away.fifa_code === code)
    .sort((a, b) => Date.parse(a.kickoff_utc) - Date.parse(b.kickoff_utc));
  if (!ms.length) return null;
  const live = ms.find((m) => isLiveStatus(m.status));
  if (live) return live;
  const next = ms.find((m) => m.status === "upcoming");
  return next || ms[ms.length - 1];
}

function PlayerDetail({ id, go }) {
  const p = WC.store.playersById[id];
  if (!p) return <div className="wrap" style={{ paddingTop: 40 }}>Player not found.</div>;
  const t = WC.store.teams[p.fifa_code] || {};
  const age = WC.age(p.dob);
  const perGame = p.caps ? ((p.intl_goals || 0) / p.caps).toFixed(2) : null;
  const wcs = p.past_world_cups || [];
  const teamMatch = teamMatchFor(p.fifa_code);
  const posLabel = { GK: "Goalkeeper", DF: "Defender", MF: "Midfielder", FW: "Forward" }[p.position] || p.position;

  return (
    <div className="rise wrap">
      <div className="player-grid" style={{ display: "grid", gridTemplateColumns: "minmax(280px, 0.85fr) 1.15fr", gap: 28, alignItems: "stretch" }}>

        {/* ---------- LEFT: identity card (no photo by design) ---------- */}
        <div className="sticker" style={{ padding: 0, overflow: "hidden", position: "relative", minHeight: "62vh", display: "flex" }}>
          <div style={{ flex: 1, width: "100%", position: "relative",
            background: `linear-gradient(160deg, ${t.color_primary || "#888"} 0%, ${t.color_primary || "#888"} 55%, ${t.color_secondary || "#ccc"} 55.2%)` }}>
            <span className="display" style={{ position: "absolute", inset: 0, display: "flex", alignItems: "center",
              justifyContent: "center", fontSize: "min(42vh, 300px)", color: "rgba(255,255,255,0.16)",
              textShadow: "3px 3px 0 rgba(44,32,22,0.18)" }}>{p.shirt_number != null ? p.shirt_number : ""}</span>
            <span className="display" style={{ position: "absolute", top: "30%", left: "50%", transform: "translateX(-50%)",
              fontSize: 64, color: "#fff", textShadow: "3px 3px 0 rgba(44,32,22,.4)" }}>{WC.initials(p.name)}</span>
          </div>
          <Sticker size={60} rot={-8} color="#fff" style={{ position: "absolute", top: 16, left: 16, zIndex: 4 }}>
            <Flag code={p.fifa_code} size={58} />
          </Sticker>
          <div className="sticker diecut" style={{ position: "absolute", top: 18, right: 18, width: 56, height: 56, borderRadius: "50%",
            background: "var(--card)", display: "flex", alignItems: "center", justifyContent: "center", zIndex: 4 }}>
            <span className="display" style={{ fontSize: 26 }}>{p.shirt_number != null ? p.shirt_number : "–"}</span>
          </div>
          <div style={{ position: "absolute", bottom: 0, left: 0, right: 0, background: "var(--ink)", color: "var(--paper)",
            padding: "14px 18px", zIndex: 4 }}>
            <div className="display" style={{ fontSize: 30, lineHeight: .95 }}>{p.name}</div>
            <div className="mono" style={{ fontSize: 11, color: "var(--amber)", marginTop: 4, letterSpacing: ".08em" }}>
              {(t.name || p.fifa_code).toUpperCase()} · #{p.shirt_number != null ? p.shirt_number : "–"} · {p.position || ""}
            </div>
          </div>
        </div>

        {/* ---------- RIGHT: data ---------- */}
        <div style={{ display: "flex", flexDirection: "column", gap: 18 }}>
          <div>
            <div className="label" style={{ marginBottom: 8 }}>{posLabel}{wcs.length ? " · World Cup veteran" : ""}</div>
            <h1 className="display" style={{ fontSize: 52, margin: "0 0 10px", lineHeight: .9 }}>{p.name}</h1>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              <span className="chip" style={{ display: "inline-flex", alignItems: "center", gap: 6 }}>
                <Flag code={p.fifa_code} size={15} /> {t.name || p.fifa_code}
              </span>
              {p.club && <span className="chip">{p.club}</span>}
              {p.dob && <span className="chip">b. {p.dob}</span>}
              {t.group && <span className="chip" style={{ cursor: "pointer" }} onClick={() => go("groups", { group: t.group })}>Group {t.group}</span>}
            </div>
          </div>

          {/* stat tiles */}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <StatTile value={p.caps} label="Caps" color="var(--sun-d)" />
            <StatTile value={p.intl_goals} label="Int'l goals" color="var(--teal-d)" />
            <StatTile value={age} label="Age" />
            <StatTile value={perGame} label="Goals / cap" color="var(--amber)" />
          </div>

          {/* World Cup history */}
          <div className="sticker" style={{ padding: "16px 20px" }}>
            <div className="label" style={{ marginBottom: 10 }}>World Cup appearances</div>
            <div style={{ display: "flex", gap: 8, flexWrap: "wrap" }}>
              {wcs.map((y) => (
                <span key={y} className="chip" style={{ background: "var(--paper-2)", borderColor: "var(--ink)", fontSize: 11 }}>{y}</span>
              ))}
              <span className="chip" style={{ background: "var(--amber)", borderColor: "var(--ink)", fontSize: 11, display: "inline-flex", alignItems: "center", gap: 5 }}>
                <ZStar size={12} /> 2026
              </span>
            </div>
            {!wcs.length && (
              <p className="mono" style={{ fontSize: 10.5, color: "var(--ink-faint)", margin: "10px 0 0" }}>
                First World Cup — or earlier appearances not yet recorded on Wikidata.
              </p>
            )}
          </div>

          {/* outbound + nav */}
          <div style={{ display: "flex", gap: 12, flexWrap: "wrap" }}>
            <a className="btn" href={p.fifa_profile_url || ("https://www.fifa.com/en/search?q=" + encodeURIComponent(p.name))}
              target="_blank" rel="noopener noreferrer" style={{ textDecoration: "none" }}>
              FIFA profile ↗
            </a>
            {teamMatch && (
              <button className="btn teal" onClick={() => go("match", { num: teamMatch.match_number })}>
                {t.name || p.fifa_code}'s {isLiveStatus(teamMatch.status) ? "live match" : teamMatch.status === "upcoming" ? "next match" : "last match"} →
              </button>
            )}
            <button className="btn ghost" onClick={() => go("players")}>← All players</button>
          </div>

          <p className="mono" style={{ fontSize: 10.5, color: "var(--ink-faint)", lineHeight: 1.7 }}>
            Caps &amp; goals as of squad announcement (Wikipedia) refreshed weekly from Wikidata ·
            World Cup history from Wikidata · No player imagery — official profile via the FIFA link above.
          </p>
        </div>
      </div>
    </div>
  );
}

window.PlayerDetail = PlayerDetail;
