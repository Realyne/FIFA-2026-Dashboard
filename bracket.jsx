/* ============================================================
   Bracket graph — 32-team knockout (M73–M104), measured connectors
   Column order derived from feeds_into so edges nest cleanly.
   ============================================================ */
const { useState, useEffect, useRef } = React;
const WC = window.WC;

function ColHeader({ title, sub, color }) {
  return (
    <div style={{ textAlign: "center", marginBottom: 18 }}>
      <div className="display" style={{ fontSize: 22, color: "var(--ink)" }}>{title}</div>
      <div style={{ display: "inline-block", width: 46, height: 7, background: color, borderRadius: 5,
        transform: "rotate(-1.5deg)", margin: "5px 0 3px" }}></div>
      <div className="mono" style={{ fontSize: 10, color: "var(--ink-faint)", letterSpacing: ".1em" }}>{sub}</div>
    </div>
  );
}

/* Recursive column ordering: walk down from the final via slot match refs. */
function knockoutColumns() {
  const b = WC.store.bracket;
  const sources = (m) => {
    const out = [];
    [m.home_slot, m.away_slot].forEach((slot) => {
      if (slot && typeof slot === "object" && slot.type === "match_winner") out.push(slot.match_number);
    });
    return out;
  };
  const cols = { final: [104], sf: [], qf: [], r16: [], r32: [] };
  const order = ["final", "sf", "qf", "r16", "r32"];
  for (let i = 0; i < order.length - 1; i++) {
    const cur = cols[order[i]];
    const nxt = [];
    cur.forEach((num) => {
      const m = b[num];
      if (m) nxt.push(...sources(m));
    });
    cols[order[i + 1]] = nxt;
  }
  return cols;
}

function Bracket({ go }) {
  const wrapRef = useRef(null);
  const nodeRefs = useRef({});
  const [paths, setPaths] = useState([]);
  const [dims, setDims] = useState({ w: 1500, h: 2300 });

  const setRef = (num) => (el) => { if (el) nodeRefs.current[num] = el; };

  const cols = knockoutColumns();

  const measure = () => {
    const wrap = wrapRef.current;
    if (!wrap) return;
    const base = wrap.getBoundingClientRect();
    const rectOf = (num) => {
      const el = nodeRefs.current[num];
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return { left: r.left - base.left, right: r.right - base.left, cy: r.top - base.top + r.height / 2 };
    };
    const conns = [];
    Object.keys(WC.store.bracket).forEach((k) => {
      const m = WC.store.bracket[k];
      if (m.match_number < 73 || !m.feeds_into) return;
      const a = rectOf(m.match_number), b = rectOf(m.feeds_into);
      if (!a || !b) return;
      const midX = a.right + (b.left - a.right) * 0.5;
      conns.push({
        d: `M ${a.right} ${a.cy} L ${midX} ${a.cy} L ${midX} ${b.cy} L ${b.left} ${b.cy}`,
        kind: "solid",
      });
      const loserTarget = m.feeds_into_loser != null ? rectOf(m.feeds_into_loser) : null;
      if (loserTarget) {
        const mx = a.right + (loserTarget.left - a.right) * 0.4;
        conns.push({
          d: `M ${a.right} ${a.cy} L ${mx} ${a.cy} L ${mx} ${loserTarget.cy} L ${loserTarget.left} ${loserTarget.cy}`,
          kind: "faint",
        });
      }
    });
    setPaths(conns);
    setDims({ w: wrap.scrollWidth, h: wrap.scrollHeight });
  };

  useEffect(() => {
    const t1 = setTimeout(measure, 60);
    const t2 = setTimeout(measure, 400);
    const t3 = setTimeout(measure, 1700);
    window.addEventListener("resize", measure);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(measure);
    return () => { clearTimeout(t1); clearTimeout(t2); clearTimeout(t3); window.removeEventListener("resize", measure); };
  }, []);

  const open = (num) => go("match", { num });
  const H = 2360;
  let dropIdx = 0;

  const col = (nums, key) => (
    <div key={key} style={{ display: "flex", flexDirection: "column", justifyContent: "space-around",
      height: H, flexShrink: 0, width: 252 }}>
      {nums.map((n) => (
        <div ref={setRef(n)} key={n} className="drop" style={{ animationDelay: (dropIdx++ * 30) + "ms" }}>
          <MatchNode num={n} onOpen={open} compact rot={(n % 3 - 1) * 0.7} />
        </div>
      ))}
    </div>
  );

  const finalCol = (
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: 60, height: H, flexShrink: 0, width: 270 }}>
      <div ref={setRef(104)} className="drop" style={{ animationDelay: "900ms" }}>
        <div className="sticker lift" onClick={() => open(104)} style={{
          width: 264, padding: "16px", cursor: "pointer", background: "#f6e3b0",
          borderColor: "var(--sun-d)", borderWidth: 3, transform: "rotate(-0.6deg)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 8 }}>
            <span className="display" style={{ fontSize: 18, display: "inline-flex", alignItems: "center", gap: 7 }}>
              <ZTrophy size={20} /> The Final
            </span>
            <StatusBadge match={WC.getMatch(104)} />
          </div>
          <TeamLine side={WC.getMatch(104).home} />
          <div style={{ height: 1, background: "repeating-linear-gradient(90deg,var(--ink-faint) 0 5px,transparent 5px 10px)" }}></div>
          <TeamLine side={WC.getMatch(104).away} />
          <div className="mono" style={{ fontSize: 10, color: "var(--ink-soft)", marginTop: 8, display: "flex", alignItems: "center", gap: 5 }}>
            <ZPin size={11} /> MetLife Stadium · New York/New Jersey
          </div>
        </div>
      </div>
      <div ref={setRef(103)} className="drop" style={{ animationDelay: "960ms" }}>
        <div className="sticker lift" onClick={() => open(103)} style={{
          width: 234, padding: "10px 14px", cursor: "pointer", opacity: 0.92, transform: "rotate(0.8deg)" }}>
          <div className="label" style={{ fontSize: 9, marginBottom: 4 }}>3rd place · Jul 18 · Miami</div>
          <TeamLine side={WC.getMatch(103).home} />
          <TeamLine side={WC.getMatch(103).away} />
        </div>
      </div>
    </div>
  );

  return (
    <div className="rise">
      <div className="wrap" style={{ paddingBottom: 30 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}>
          <ZineHeading kicker="The knockout graph · 32 matches" title="Road to MetLife" color="var(--sun)" />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 22, flexWrap: "wrap" }}>
            <span className="chip"><span className="live-dot" style={{ background: "var(--sun-d)" }}></span> Live</span>
            <span className="chip finished" style={{ fontSize: 10 }}>Finished</span>
            <span className="chip upcoming" style={{ fontSize: 10 }}>Upcoming</span>
            <span className="mono" style={{ fontSize: 10, color: "var(--ink-faint)" }}>· slots fill in as groups finish · tap any node →</span>
          </div>
        </div>
      </div>

      {/* scroll area */}
      <div style={{ overflowX: "auto", paddingBottom: 30 }}>
        <div style={{ width: "max-content", minWidth: 1500, margin: "0 auto", padding: "0 28px" }}>
          <div style={{ display: "flex", gap: 46, justifyContent: "flex-start" }}>
            <div style={{ width: 252, flexShrink: 0 }}><ColHeader title="Round of 32" sub="JUN 28 – JUL 3" color="var(--teal)" /></div>
            <div style={{ width: 252, flexShrink: 0 }}><ColHeader title="Round of 16" sub="JUL 4 – 7" color="var(--amber)" /></div>
            <div style={{ width: 252, flexShrink: 0 }}><ColHeader title="Quarterfinals" sub="JUL 9 – 11" color="var(--sun)" /></div>
            <div style={{ width: 252, flexShrink: 0 }}><ColHeader title="Semifinals" sub="JUL 14 – 15" color="var(--sun-d)" /></div>
            <div style={{ width: 270, flexShrink: 0 }}><ColHeader title="Final" sub="JUL 19" color="var(--sun-d)" /></div>
          </div>

          <div ref={wrapRef} style={{ position: "relative", display: "flex", gap: 46 }}>
            <svg width={dims.w} height={dims.h} style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none", overflow: "visible" }}>
              {paths.map((p, i) => (
                <path key={i} d={p.d} fill="none"
                  className={p.kind === "faint" ? "" : "conn"}
                  stroke={p.kind === "faint" ? "var(--ink-faint)" : "var(--ink)"}
                  strokeWidth={p.kind === "faint" ? 1.5 : 2.5}
                  strokeDasharray={p.kind === "faint" ? "3 5" : "1 7"}
                  strokeLinecap="round" strokeLinejoin="round" opacity={p.kind === "faint" ? 0.5 : 0.65} />
              ))}
            </svg>

            <div style={{ position: "relative", zIndex: 1, display: "flex", gap: 46 }}>
              {col(cols.r32, "c32")}
              {col(cols.r16, "c16")}
              {col(cols.qf, "cqf")}
              {col(cols.sf, "csf")}
              {finalCol}
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.Bracket = Bracket;
