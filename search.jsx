/* ============================================================
   Global search — find any country, match or player from anywhere.
   Opened from the topbar button, or with "/" or Cmd/Ctrl+K.
   All data is already in the store at load, so search is instant
   and offline: no round-trips per keystroke.
   ============================================================ */
const { useState, useEffect, useRef, useMemo } = React;
const WC = window.WC;

function ZSearch({ size = 18, color = "currentColor" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true" fill="none">
      <circle cx="10.5" cy="10.5" r="6.5" stroke={color} strokeWidth="2.4" />
      <line x1="15.5" y1="15.5" x2="21" y2="21" stroke={color} strokeWidth="2.4" strokeLinecap="round" />
    </svg>
  );
}

/* accent- and case-insensitive: "cote" matches "Côte d'Ivoire" */
function soNorm(s) {
  return (s == null ? "" : String(s)).normalize("NFD").replace(/[\u0300-\u036f]/g, "").toLowerCase().trim();
}

function roundLabelOf(m) {
  if (m.round === "group") return "Group " + m.group;
  return (WC.ROUNDS && WC.ROUNDS[m.round]) || m.round;
}

function teamNameOf(code) {
  const t = code && WC.store.teams[code];
  return t ? t.name : code;
}

/* one searchable haystack per entity, built once per overlay mount */
function buildIndex() {
  const S = WC.store;

  const countries = Object.keys(S.teams).map((c) => {
    const t = S.teams[c];
    return {
      kind: "country", code: t.fifa_code, name: t.name, group: t.group,
      hay: soNorm(t.name + " " + t.fifa_code),
      name_l: soNorm(t.name), code_l: soNorm(t.fifa_code),
    };
  });

  const matches = Object.keys(S.bracket).map((k) => S.bracket[k]).map((m) => {
    const hc = m.home.fifa_code, ac = m.away.fifa_code;
    const hn = hc ? teamNameOf(hc) : (m.home.label || "TBD");
    const an = ac ? teamNameOf(ac) : (m.away.label || "TBD");
    const v = S.venues[m.venue_id] || {};
    return {
      kind: "match", num: m.match_number, m, hc, ac, hn, an, round: roundLabelOf(m),
      hay: soNorm([hc, ac, hn, an, "m" + m.match_number, m.match_number, roundLabelOf(m), v.city].join(" ")),
    };
  });

  const players = (S.players || []).map((p) => ({
    kind: "player", id: p.player_id, p, name: p.name, code: p.fifa_code,
    hay: soNorm([p.name, p.fifa_code, teamNameOf(p.fifa_code), p.club, p.position].join(" ")),
    name_l: soNorm(p.name),
  }));

  return { countries, matches, players };
}

/* lower is better; -1 = no match */
function rank(it, q, terms) {
  if (it.code_l && it.code_l === q) return 0;
  if (it.name_l && it.name_l === q) return 0;
  if (it.name_l && it.name_l.startsWith(q)) return 1;
  if (it.hay.startsWith(q)) return 1;
  if (terms.every((t) => it.hay.includes(t))) return 2;
  return -1;
}

const CAP = 6;

function matchSub(m) {
  const rl = roundLabelOf(m);
  if (isLiveStatus(m.status)) return rl + " · LIVE" + (m.minute_display ? " " + m.minute_display + "'" : "");
  if (m.status === "finished") return rl + " · " + (m.home.score != null ? m.home.score : "–") + "–" + (m.away.score != null ? m.away.score : "–");
  return rl + " · " + WC.kickoffLocal(m, { weekday: "short" });
}

function SearchRow({ item, active, onHover, onChoose }) {
  let icon, title, sub, badge;
  if (item.kind === "country") {
    icon = <Flag code={item.code} badge size={26} />;
    title = item.name;
    sub = "Group " + item.group + " · " + item.code;
    badge = "Country";
  } else if (item.kind === "match") {
    icon = (item.hc && item.ac)
      ? <span className="srch-mflags"><Flag code={item.hc} badge size={18} /><Flag code={item.ac} badge size={18} /></span>
      : <ZBall size={22} />;
    title = item.hn + " v " + item.an;
    sub = matchSub(item.m);
    badge = "Match";
  } else {
    icon = <Flag code={item.code} badge size={26} />;
    const p = item.p;
    sub = (p.position || "—") + " · " + teamNameOf(item.code) + (p.club ? " · " + p.club : "");
    title = p.name;
    badge = "Player";
  }
  return (
    <div
      className={"srch-row" + (active ? " active" : "")}
      data-idx={item._i}
      role="option"
      aria-selected={active}
      onMouseEnter={onHover}
      onClick={onChoose}
    >
      <span className="srch-row-icon">{icon}</span>
      <span className="srch-row-main">
        <span className="srch-row-title">{title}</span>
        <span className="srch-row-sub">{sub}</span>
      </span>
      <span className="srch-badge">{badge}</span>
    </div>
  );
}

function SearchOverlay({ onClose, go }) {
  const [q, setQ] = useState("");
  const [active, setActive] = useState(0);
  const inputRef = useRef(null);
  const resultsRef = useRef(null);
  const index = useMemo(buildIndex, []);

  useEffect(() => {
    if (inputRef.current) inputRef.current.focus();
    const prev = document.body.style.overflow;
    document.body.style.overflow = "hidden";
    return () => { document.body.style.overflow = prev; };
  }, []);

  const { sections, flat } = useMemo(() => {
    const query = soNorm(q);
    if (!query) return { sections: [], flat: [] };
    const terms = query.split(/\s+/).filter(Boolean);
    const run = (arr, tiebreak) => {
      const scored = arr
        .map((it) => ({ it, s: rank(it, query, terms) }))
        .filter((x) => x.s >= 0)
        .sort((a, b) => a.s - b.s || tiebreak(a.it, b.it));
      return { items: scored.slice(0, CAP).map((x) => x.it), total: scored.length };
    };
    const byName = (a, b) => a.name.localeCompare(b.name);
    const c = run(index.countries, byName);
    const m = run(index.matches, (a, b) => a.num - b.num);
    const p = run(index.players, byName);
    const secs = [];
    if (c.items.length) secs.push({ key: "country", label: "Countries", ...c });
    if (m.items.length) secs.push({ key: "match", label: "Matches", ...m });
    if (p.items.length) secs.push({ key: "player", label: "Players", ...p });
    let n = 0;
    secs.forEach((sec) => sec.items.forEach((it) => { it._i = n++; }));
    return { sections: secs, flat: secs.flatMap((s) => s.items) };
  }, [q, index]);

  const activeSafe = flat.length ? Math.min(active, flat.length - 1) : 0;

  useEffect(() => {
    const el = resultsRef.current && resultsRef.current.querySelector('[data-idx="' + activeSafe + '"]');
    if (el) el.scrollIntoView({ block: "nearest" });
  }, [activeSafe, q]);

  const choose = (it) => {
    if (!it) return;
    if (it.kind === "country") go("groups", { group: it.group });
    else if (it.kind === "match") go("match", { num: it.num });
    else if (it.kind === "player") go("player", { id: it.id });
    onClose();
  };

  const onKeyDown = (e) => {
    if (e.key === "Escape") { e.preventDefault(); onClose(); }
    else if (e.key === "ArrowDown") { e.preventDefault(); setActive((a) => Math.min(flat.length - 1, a + 1)); }
    else if (e.key === "ArrowUp") { e.preventDefault(); setActive((a) => Math.max(0, a - 1)); }
    else if (e.key === "Enter") { e.preventDefault(); choose(flat[activeSafe]); }
  };

  return (
    <div className="srch-backdrop" onClick={onClose} role="dialog" aria-modal="true" aria-label="Search">
      <div className="srch-panel" onClick={(e) => e.stopPropagation()}>
        <div className="srch-top">
          <ZSearch size={18} color="var(--ink-soft)" />
          <input
            ref={inputRef}
            value={q}
            onChange={(e) => { setQ(e.target.value); setActive(0); }}
            onKeyDown={onKeyDown}
            placeholder="Search countries, matches, players…"
            aria-label="Search"
            autoComplete="off" autoCorrect="off" autoCapitalize="off" spellCheck="false"
          />
          <button className="srch-esc" onClick={onClose} aria-label="Close">esc</button>
        </div>

        <div className="srch-results" ref={resultsRef} role="listbox">
          {!q.trim() ? (
            <div className="srch-empty srch-hint">
              Find any country, match or player.<br />
              <span style={{ display: "inline-block", marginTop: 8 }}>
                <kbd>↑</kbd> <kbd>↓</kbd> to move · <kbd>↵</kbd> to open · <kbd>esc</kbd> to close
              </span>
            </div>
          ) : flat.length === 0 ? (
            <div className="srch-empty">No results for “{q.trim()}”.</div>
          ) : (
            sections.map((sec) => (
              <div key={sec.key}>
                <div className="srch-group-label">
                  {sec.label}{sec.total > sec.items.length ? " · " + sec.total : ""}
                </div>
                {sec.items.map((it) => (
                  <SearchRow
                    key={it._i}
                    item={it}
                    active={it._i === activeSafe}
                    onHover={() => setActive(it._i)}
                    onChoose={() => choose(it)}
                  />
                ))}
                {sec.total > sec.items.length ? (
                  <div className="srch-more">+{sec.total - sec.items.length} more — keep typing to narrow</div>
                ) : null}
              </div>
            ))
          )}
        </div>
      </div>
    </div>
  );
}

window.SearchOverlay = SearchOverlay;
window.ZSearch = ZSearch;
