/* ============================================================
   Bracket — classic mirrored World Cup layout, final in the center.
   Left half feeds SF M101, right half feeds SF M102; columns fan
   outward (R32 at the edges). Whole graph scales to fit the viewport
   width ("Fit") with an "Actual size" toggle for close reading.
   ============================================================ */
const { useState, useEffect, useRef } = React;
const WC = window.WC;

const NODE_W = 178;
const COL_GAP = 26;
const ROW_H = 122;        // R32 rows
const CENTER_W = 250;

function sourcesOf(m) {
  const out = [];
  [m.home_slot, m.away_slot].forEach((slot) => {
    if (slot && typeof slot === "object" && slot.type === "match_winner") out.push(slot.match_number);
  });
  return out;
}

/* halves[0] = subtree under SF 101, halves[1] = subtree under SF 102 */
function bracketHalves() {
  const b = WC.store.bracket;
  const expand = (nums) => nums.flatMap((n) => (b[n] ? sourcesOf(b[n]) : []));
  const final = b[104];
  if (!final) return null;
  return sourcesOf(final).map((sfNum) => {
    const sf = [sfNum];
    const qf = expand(sf);
    const r16 = expand(qf);
    const r32 = expand(r16);
    return { sf, qf, r16, r32 };
  });
}

/* ---- slim node: flag + code (or slot label) + score ---- */
function SlimLine({ side, winner, live }) {
  const code = side && side.fifa_code;
  return (
    <div style={{ display: "flex", alignItems: "center", gap: 7, padding: "4.5px 0", opacity: code ? 1 : 0.6 }}>
      <Flag code={code} badge size={20} />
      {code ? (
        <span className="mono" style={{ flex: 1, fontSize: 13, fontWeight: winner ? 800 : 600, letterSpacing: ".03em" }}>
          {code}
          {side.pen_score != null && <span style={{ fontSize: 9.5, color: "var(--ink-soft)", fontWeight: 600 }}> ({side.pen_score})</span>}
        </span>
      ) : (
        <span style={{ flex: 1, fontSize: 10.5, fontStyle: "italic", color: "var(--ink-soft)",
          whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis" }}>
          {(side && side.label) || "TBD"}
        </span>
      )}
      <span className="mono" style={{ fontSize: 15, fontWeight: 700, minWidth: 16, textAlign: "right",
        color: live ? "var(--sun-d)" : "var(--ink)" }}>
        {side && side.score != null ? side.score : "–"}
      </span>
    </div>
  );
}

function statusGlyph(m) {
  if (isLiveStatus(m.status)) {
    return <span className="mono" style={{ fontSize: 9, fontWeight: 800, color: "var(--sun-d)", display: "inline-flex", alignItems: "center", gap: 4 }}>
      <span className="live-dot" style={{ width: 7, height: 7 }}></span>
      {m.status === "ht" ? "HT" : m.status === "pens" ? "PENS" : (m.minute_display || "") + "'"}
    </span>;
  }
  if (m.status === "finished") return <span className="mono" style={{ fontSize: 9, fontWeight: 700, color: "var(--ink-faint)" }}>FT</span>;
  return <span className="mono" style={{ fontSize: 9, color: "var(--ink-faint)" }}>{WC.kickoffLocal(m, { hour: undefined, minute: undefined })}</span>;
}

function SlimNode({ num, onOpen }) {
  const m = WC.getMatch(num);
  if (!m) return null;
  const live = isLiveStatus(m.status);
  const [winA, winB] = matchWinnerSides(m);
  const home = m.home, away = m.away;
  const title = `${WC.sideLabel(home)} v ${WC.sideLabel(away)}`;
  return (
    <div className="sticker lift" onClick={() => onOpen(num)} title={title}
      style={{ width: NODE_W, padding: "7px 11px 8px", cursor: "pointer",
        borderColor: live ? "var(--sun-d)" : "var(--ink)",
        background: live ? "#fff6ee" : "var(--card)" }}>
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 2 }}>
        <span className="label" style={{ fontSize: 8.5, letterSpacing: ".08em" }}>M{m.match_number}</span>
        {statusGlyph(m)}
      </div>
      <SlimLine side={home} winner={winA} live={live} />
      <div style={{ height: 1, background: "repeating-linear-gradient(90deg,var(--ink-faint) 0 4px,transparent 4px 8px)" }}></div>
      <SlimLine side={away} winner={winB} live={live} />
    </div>
  );
}

function ColTitle({ children }) {
  return <div className="label" style={{ fontSize: 9, textAlign: "center", letterSpacing: ".12em", marginBottom: 6 }}>{children}</div>;
}

function Bracket({ go }) {
  const graphRef = useRef(null);
  const outerRef = useRef(null);
  const nodeRefs = useRef({});
  const [paths, setPaths] = useState([]);
  const [dims, setDims] = useState({ w: 2000, h: 1000 });
  const [mode, setMode] = useState("fit");      // fit | full
  const [scale, setScale] = useState(1);

  const halves = bracketHalves();
  const setRef = (num) => (el) => { if (el) nodeRefs.current[num] = el; };
  const open = (num) => go("match", { num });

  const measure = () => {
    const wrap = graphRef.current;
    if (!wrap) return;
    const base = wrap.getBoundingClientRect();
    // rendered/layout ratio — divide screen coords back into layout space so
    // the SVG (which lives inside the scaled wrapper) lines up at any zoom
    const k = base.width / (wrap.offsetWidth || 1);
    const rectOf = (num) => {
      const el = nodeRefs.current[num];
      if (!el) return null;
      const r = el.getBoundingClientRect();
      return {
        left: (r.left - base.left) / k,
        right: (r.right - base.left) / k,
        cy: (r.top - base.top + r.height / 2) / k,
      };
    };
    const conns = [];
    Object.keys(WC.store.bracket).forEach((key) => {
      const m = WC.store.bracket[key];
      if (m.match_number < 73 || !m.feeds_into) return;
      const a = rectOf(m.match_number), b = rectOf(m.feeds_into);
      if (!a || !b) return;
      // direction-aware: left half flows →, right half flows ←
      const forward = b.left >= a.right;
      const sx = forward ? a.right : a.left;
      const ex = forward ? b.left : b.right;
      const midX = sx + (ex - sx) * 0.5;
      conns.push({ d: `M ${sx} ${a.cy} L ${midX} ${a.cy} L ${midX} ${b.cy} L ${ex} ${b.cy}`, kind: "solid" });
    });
    setPaths(conns);
    setDims({ w: wrap.scrollWidth, h: wrap.scrollHeight });
  };

  const computeScale = () => {
    const outer = outerRef.current, wrap = graphRef.current;
    if (!outer || !wrap) return;
    const avail = outer.clientWidth;
    const content = wrap.offsetWidth || 1;
    const s = Math.min(1, avail / content);
    // below ~0.45 the fit view is unreadable — fall back to scrolling
    setScale(mode === "fit" && s >= 0.45 ? s : 1);
  };

  useEffect(() => {
    const tick = () => { computeScale(); measure(); };
    const t1 = setTimeout(tick, 60);
    const t2 = setTimeout(tick, 450);
    window.addEventListener("resize", tick);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(tick);
    return () => { clearTimeout(t1); clearTimeout(t2); window.removeEventListener("resize", tick); };
  }, [mode]);

  if (!halves) return null;

  const colH = 8 * ROW_H;
  const column = (nums, key) => (
    <div key={key} style={{ display: "flex", flexDirection: "column", justifyContent: "space-around",
      height: colH, width: NODE_W, flexShrink: 0 }}>
      {nums.map((n) => <div ref={setRef(n)} key={n}><SlimNode num={n} onOpen={open} /></div>)}
    </div>
  );

  const final = WC.getMatch(104);
  const third = WC.getMatch(103);
  const centerCol = (
    <div style={{ display: "flex", flexDirection: "column", justifyContent: "center", gap: 26,
      height: colH, width: CENTER_W, flexShrink: 0 }}>
      <div ref={setRef(104)}>
        <div className="sticker lift" onClick={() => open(104)} style={{
          width: CENTER_W, padding: "14px 16px", cursor: "pointer", background: "#f6e3b0",
          borderColor: "var(--sun-d)", borderWidth: 3, transform: "rotate(-0.5deg)" }}>
          <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6 }}>
            <span className="display" style={{ fontSize: 17, display: "inline-flex", alignItems: "center", gap: 6 }}>
              <ZTrophy size={18} /> The Final
            </span>
            <StatusBadge match={final} />
          </div>
          <TeamLine side={final.home} />
          <div style={{ height: 1, background: "repeating-linear-gradient(90deg,var(--ink-faint) 0 5px,transparent 5px 10px)" }}></div>
          <TeamLine side={final.away} />
          <div className="mono" style={{ fontSize: 9.5, color: "var(--ink-soft)", marginTop: 6, display: "flex", alignItems: "center", gap: 5 }}>
            <ZPin size={11} /> Jul 19 · MetLife Stadium, NY/NJ
          </div>
        </div>
      </div>
      <div ref={setRef(103)}>
        <div className="sticker lift" onClick={() => open(103)} style={{
          width: CENTER_W - 30, margin: "0 auto", padding: "8px 12px", cursor: "pointer",
          opacity: 0.92, transform: "rotate(0.6deg)" }}>
          <div className="label" style={{ fontSize: 8.5, marginBottom: 2 }}>3rd place · Jul 18 · Miami</div>
          <SlimLine side={third.home} />
          <SlimLine side={third.away} />
        </div>
      </div>
    </div>
  );

  const [L, R] = halves;
  const contentW = 8 * (NODE_W + COL_GAP) + CENTER_W + COL_GAP;

  return (
    <div className="rise">
      <div className="wrap" style={{ paddingBottom: 16 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}>
          <ZineHeading kicker="The knockout graph · 32 matches" title="Road to MetLife" color="var(--sun)" />
          <div style={{ display: "flex", gap: 8, alignItems: "center", marginBottom: 22, flexWrap: "wrap" }}>
            <span className={"chip filter-chip " + (mode === "fit" ? "on" : "")} onClick={() => setMode("fit")}>Fit to screen</span>
            <span className={"chip filter-chip " + (mode === "full" ? "on" : "")} onClick={() => setMode("full")}>Actual size</span>
            <span className="mono" style={{ fontSize: 10, color: "var(--ink-faint)" }}>· slots fill in as groups finish · tap a node →</span>
          </div>
        </div>
      </div>

      <div ref={outerRef} style={{ overflowX: scale < 1 ? "hidden" : "auto", paddingBottom: 30 }}>
        <div style={{
          width: scale < 1 ? "100%" : "max-content",
          height: scale < 1 ? (colH + 60) * scale : undefined,
          margin: "0 auto",
          padding: scale < 1 ? 0 : "0 24px",
        }}>
          <div style={{ transform: `scale(${scale})`, transformOrigin: "top center", width: contentW, margin: "0 auto" }}>
            {/* column headers */}
            <div style={{ display: "flex", gap: COL_GAP, marginBottom: 10 }}>
              <div style={{ width: NODE_W }}><ColTitle>R32</ColTitle></div>
              <div style={{ width: NODE_W }}><ColTitle>R16</ColTitle></div>
              <div style={{ width: NODE_W }}><ColTitle>QF</ColTitle></div>
              <div style={{ width: NODE_W }}><ColTitle>SEMI</ColTitle></div>
              <div style={{ width: CENTER_W }}><ColTitle>FINAL · JUL 19</ColTitle></div>
              <div style={{ width: NODE_W }}><ColTitle>SEMI</ColTitle></div>
              <div style={{ width: NODE_W }}><ColTitle>QF</ColTitle></div>
              <div style={{ width: NODE_W }}><ColTitle>R16</ColTitle></div>
              <div style={{ width: NODE_W }}><ColTitle>R32</ColTitle></div>
            </div>

            <div ref={graphRef} style={{ position: "relative", display: "flex", gap: COL_GAP }}>
              <svg width={dims.w} height={dims.h} style={{ position: "absolute", inset: 0, zIndex: 0, pointerEvents: "none", overflow: "visible" }}>
                {paths.map((p, i) => (
                  <path key={i} d={p.d} fill="none" className="conn"
                    stroke="var(--ink)" strokeWidth="2.2" strokeDasharray="1 6"
                    strokeLinecap="round" strokeLinejoin="round" opacity="0.6" />
                ))}
              </svg>
              <div style={{ position: "relative", zIndex: 1, display: "flex", gap: COL_GAP }}>
                {column(L.r32, "l32")}
                {column(L.r16, "l16")}
                {column(L.qf, "lqf")}
                {column(L.sf, "lsf")}
                {centerCol}
                {column(R.sf, "rsf")}
                {column(R.qf, "rqf")}
                {column(R.r16, "r16r")}
                {column(R.r32, "r32r")}
              </div>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
}

window.Bracket = Bracket;
