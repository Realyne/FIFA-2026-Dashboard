/* ============================================================
   Groups — 12 standings tables + group fixtures
   ============================================================ */
const { useState } = React;
const WC = window.WC;

function StandingsTable({ group, rows, complete, go }) {
  const cellS = { padding: "6px 6px", fontSize: 12.5, whiteSpace: "nowrap" };
  const num = (v) => <td className="mono" style={{ ...cellS, textAlign: "center" }}>{v}</td>;
  return (
    <table className="standings-table" style={{ width: "100%", borderCollapse: "collapse" }}>
      <thead>
        <tr className="label" style={{ fontSize: 9, textAlign: "center" }}>
          <th style={{ ...cellS, textAlign: "left" }}>Team</th>
          <th style={cellS}>P</th><th style={cellS}>W</th><th style={cellS}>D</th>
          <th style={cellS}>L</th><th style={cellS}>GD</th><th style={cellS}>Pts</th>
        </tr>
      </thead>
      <tbody>
        {rows.map((r, i) => {
          const t = WC.store.teams[r.fifa_code] || {};
          const qualified = complete && i < 2;
          return (
            <tr key={r.fifa_code} style={{
              borderTop: "1.5px dashed var(--ink-faint)",
              background: qualified ? "rgba(63,157,86,0.10)" : i === 2 && complete ? "rgba(244,200,29,0.12)" : "transparent",
            }}>
              <td style={{ ...cellS, textAlign: "left" }}>
                <span style={{ display: "inline-flex", alignItems: "center", gap: 8 }}>
                  <span className="mono" style={{ width: 14, fontSize: 10, color: "var(--ink-faint)" }}>{i + 1}</span>
                  <Flag code={r.fifa_code} badge size={20} />
                  <span style={{ fontWeight: i < 2 ? 700 : 500 }}>{t.name || r.fifa_code}</span>
                </span>
              </td>
              {num(r.played)}{num(r.won)}{num(r.drawn)}{num(r.lost)}
              {num(r.gd > 0 ? "+" + r.gd : r.gd)}
              <td className="mono" style={{ ...cellS, textAlign: "center", fontWeight: 700 }}>{r.points}</td>
            </tr>
          );
        })}
      </tbody>
    </table>
  );
}

function GroupCard({ group, go, idx }) {
  const s = WC.store.standings[group];
  if (!s) return null;
  const matches = Object.keys(WC.store.bracket)
    .map((k) => WC.store.bracket[k])
    .filter((m) => m.round === "group" && m.group === group)
    .sort((a, b) => Date.parse(a.kickoff_utc) - Date.parse(b.kickoff_utc));
  const anyLive = matches.some((m) => isLiveStatus(m.status));
  return (
    <div className="sticker drop" style={{
      padding: "16px 16px 12px", transform: `rotate(${(idx % 3 - 1) * 0.4}deg)`,
      animationDelay: Math.min(idx * 40, 480) + "ms",
      borderColor: anyLive ? "var(--sun-d)" : "var(--ink)",
      background: anyLive ? "#fff6ee" : "var(--card)",
    }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
        <span className="display" style={{ fontSize: 22 }}>Group {group}</span>
        {anyLive
          ? <span className="chip live"><span className="live-dot"></span>LIVE</span>
          : <span className="chip" style={{ fontSize: 9.5 }}>{s.complete ? "Final" : "In play"}</span>}
      </div>
      <StandingsTable group={group} rows={s.rows} complete={s.complete} go={go} />
      <div style={{ marginTop: 10, borderTop: "2px solid var(--ink)", paddingTop: 8 }}>
        {matches.map((m) => {
          const live = isLiveStatus(m.status);
          return (
            <div key={m.match_number} onClick={() => go("match", { num: m.match_number })}
              className="lift"
              style={{ display: "flex", alignItems: "center", gap: 7, padding: "4px 6px",
                cursor: "pointer", borderRadius: 8, fontSize: 12 }}
              onMouseEnter={(e) => e.currentTarget.style.background = "rgba(232,93,42,0.08)"}
              onMouseLeave={(e) => e.currentTarget.style.background = "transparent"}>
              <span className="mono" style={{ fontSize: 9.5, color: "var(--ink-faint)", width: 56, flexShrink: 0 }}>
                {live ? (m.status === "ht" ? "HT" : (m.minute_display || "") + "'") : WC.kickoffLocal(m, { month: "numeric", day: "numeric", hour: undefined, minute: undefined })}
              </span>
              <Flag code={m.home.fifa_code} badge size={16} />
              <span style={{ width: 34 }} className="mono">{m.home.fifa_code}</span>
              <span className="mono" style={{ fontWeight: 700, color: live ? "var(--sun-d)" : "var(--ink)", width: 38, textAlign: "center" }}>
                {m.home.score != null ? m.home.score + "–" + m.away.score : "v"}
              </span>
              <span style={{ width: 34, textAlign: "right" }} className="mono">{m.away.fifa_code}</span>
              <Flag code={m.away.fifa_code} badge size={16} />
            </div>
          );
        })}
      </div>
    </div>
  );
}

function GroupsPage({ go, group }) {
  const groups = "ABCDEFGHIJKL".split("");
  const [filter, setFilter] = useState(group || null);
  const shown = filter ? [filter] : groups;
  return (
    <div className="rise wrap">
      <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}>
        <ZineHeading kicker="12 groups · top 2 + 8 best thirds advance" title="The groups" color="var(--teal)" />
        <p className="mono" style={{ fontSize: 12, color: "var(--ink-soft)", marginBottom: 22, maxWidth: 360 }}>
          72 group matches decide the 32-team knockout. Green = through, amber = third place (best 8 of 12 advance).
        </p>
      </div>
      <div style={{ display: "flex", gap: 8, flexWrap: "wrap", alignItems: "center", marginBottom: 20 }}>
        <span className={"chip filter-chip " + (!filter ? "on" : "")} onClick={() => setFilter(null)}>All</span>
        {groups.map((g) => (
          <span key={g} className={"chip filter-chip " + (filter === g ? "on" : "")}
            onClick={() => setFilter(filter === g ? null : g)}>{g}</span>
        ))}
      </div>
      <div style={{ display: "grid", gridTemplateColumns: "repeat(auto-fill, minmax(330px, 1fr))", gap: 20 }}>
        {shown.map((g, i) => <GroupCard key={g} group={g} go={go} idx={i} />)}
      </div>
    </div>
  );
}

window.GroupsPage = GroupsPage;
