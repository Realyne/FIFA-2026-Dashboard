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

/* ============================================================
   Canvas viewport: defaults to fit-to-screen; wheel / pinch zooms
   toward the pointer, drag pans, buttons for −/fit/+.
   Transform lives in a ref and is applied imperatively so live
   SSE re-renders never fight an in-flight gesture.
   ============================================================ */
const MAX_ZOOM = 3;

function Bracket({ go }) {
  const viewRef = useRef(null);    // clipping viewport
  const contentRef = useRef(null); // transformed world
  const graphRef = useRef(null);
  const nodeRefs = useRef({});
  const [paths, setPaths] = useState([]);
  const [dims, setDims] = useState({ w: 2000, h: 1000 });
  const [zoomPct, setZoomPct] = useState(100);
  const [viewH, setViewH] = useState(520);

  const cam = useRef({ s: 1, tx: 0, ty: 0, fit: 1, w: 2000, h: 1000 });
  const pointers = useRef(new Map()); // active pointers (pan/pinch)
  const gesture = useRef(null);       // {mode:'pan'|'pinch', ...}
  const suppressClick = useRef(false);

  const halves = bracketHalves();
  const setRef = (num) => (el) => { if (el) nodeRefs.current[num] = el; };
  const open = (num) => { if (!suppressClick.current) go("match", { num }); };

  /* ---------------- camera ---------------- */
  const apply = () => {
    const c = cam.current;
    if (contentRef.current) {
      contentRef.current.style.transform = `translate(${c.tx}px, ${c.ty}px) scale(${c.s})`;
    }
    setZoomPct(Math.round((c.s / (c.fit || 1)) * 100));
  };

  const clamp = () => {
    const c = cam.current;
    const view = viewRef.current;
    if (!view) return;
    const vw = view.clientWidth, vh = view.clientHeight;
    const cw = c.w * c.s, ch = c.h * c.s;
    // content smaller than viewport on an axis -> lock centered; otherwise
    // keep edges from drifting inside the viewport
    c.tx = cw <= vw ? (vw - cw) / 2 : Math.min(0, Math.max(vw - cw, c.tx));
    c.ty = ch <= vh ? (vh - ch) / 2 : Math.min(0, Math.max(vh - ch, c.ty));
  };

  const zoomAt = (px, py, factor) => {
    const c = cam.current;
    const next = Math.min(c.fit * MAX_ZOOM, Math.max(c.fit, c.s * factor));
    if (next === c.s) return;
    // keep the world point under (px,py) fixed while scaling
    c.tx = px - ((px - c.tx) / c.s) * next;
    c.ty = py - ((py - c.ty) / c.s) * next;
    c.s = next;
    clamp(); apply();
  };

  const fitToScreen = () => {
    const c = cam.current;
    const view = viewRef.current, content = contentRef.current;
    if (!view || !content) return;
    c.w = content.offsetWidth || 1;
    c.h = content.offsetHeight || 1;
    const vw = view.clientWidth, vh = view.clientHeight;
    c.fit = Math.min(vw / c.w, vh / c.h, 1);
    c.s = c.fit;
    c.tx = (vw - c.w * c.s) / 2;
    c.ty = (vh - c.h * c.s) / 2;
    apply();
  };

  /* ---------------- connectors ---------------- */
  const measure = () => {
    const wrap = graphRef.current;
    if (!wrap) return;
    const base = wrap.getBoundingClientRect();
    const k = base.width / (wrap.offsetWidth || 1); // rendered/layout ratio
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
      const forward = b.left >= a.right; // right half flows right-to-left
      const sx = forward ? a.right : a.left;
      const ex = forward ? b.left : b.right;
      const midX = sx + (ex - sx) * 0.5;
      conns.push({ d: `M ${sx} ${a.cy} L ${midX} ${a.cy} L ${midX} ${b.cy} L ${ex} ${b.cy}` });
    });
    setPaths(conns);
    setDims({ w: wrap.offsetWidth, h: wrap.offsetHeight });
  };

  /* ---------------- gestures ---------------- */
  const onPointerDown = (e) => {
    const view = viewRef.current;
    if (!view) return;
    view.setPointerCapture(e.pointerId);
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    if (pointers.current.size === 1) {
      gesture.current = { mode: "pan", x: e.clientX, y: e.clientY, moved: 0 };
    } else if (pointers.current.size === 2) {
      const [p1, p2] = [...pointers.current.values()];
      gesture.current = { mode: "pinch", d: Math.hypot(p1.x - p2.x, p1.y - p2.y) };
    }
  };

  const onPointerMove = (e) => {
    if (!pointers.current.has(e.pointerId)) return;
    pointers.current.set(e.pointerId, { x: e.clientX, y: e.clientY });
    const g = gesture.current;
    const c = cam.current;
    const rect = viewRef.current.getBoundingClientRect();
    if (g && g.mode === "pan" && pointers.current.size === 1) {
      const dx = e.clientX - g.x, dy = e.clientY - g.y;
      g.x = e.clientX; g.y = e.clientY;
      g.moved += Math.abs(dx) + Math.abs(dy);
      if (g.moved > 6) suppressClick.current = true;
      c.tx += dx; c.ty += dy;
      clamp(); apply();
    } else if (g && g.mode === "pinch" && pointers.current.size === 2) {
      const [p1, p2] = [...pointers.current.values()];
      const d = Math.hypot(p1.x - p2.x, p1.y - p2.y);
      if (g.d > 0 && d > 0) {
        suppressClick.current = true;
        const cx = (p1.x + p2.x) / 2 - rect.left;
        const cy = (p1.y + p2.y) / 2 - rect.top;
        zoomAt(cx, cy, d / g.d);
      }
      g.d = d;
    }
  };

  const onPointerUp = (e) => {
    pointers.current.delete(e.pointerId);
    if (pointers.current.size === 1) {
      const [p] = [...pointers.current.values()];
      gesture.current = { mode: "pan", x: p.x, y: p.y, moved: 7 }; // pinch ended mid-drag
    } else if (pointers.current.size === 0) {
      gesture.current = null;
      setTimeout(() => { suppressClick.current = false; }, 0);
    }
  };

  /* wheel zoom must be a non-passive native listener to preventDefault */
  useEffect(() => {
    const view = viewRef.current;
    if (!view) return;
    const onWheel = (e) => {
      e.preventDefault();
      const rect = view.getBoundingClientRect();
      const factor = Math.exp(-e.deltaY * (e.ctrlKey ? 0.01 : 0.002));
      zoomAt(e.clientX - rect.left, e.clientY - rect.top, factor);
    };
    view.addEventListener("wheel", onWheel, { passive: false });
    return () => view.removeEventListener("wheel", onWheel);
  }, []);

  useEffect(() => {
    const tick = () => {
      setViewH(Math.max(380, Math.min(Math.round(window.innerHeight * 0.72), 780)));
      fitToScreen();
      measure();
    };
    tick();
    const t1 = setTimeout(tick, 80);
    const t2 = setTimeout(tick, 500);
    window.addEventListener("resize", tick);
    if (document.fonts && document.fonts.ready) document.fonts.ready.then(tick);
    return () => { clearTimeout(t1); clearTimeout(t2); window.removeEventListener("resize", tick); };
  }, []);

  // live re-renders replace the transformed node — re-apply the camera
  useEffect(() => { apply(); });

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
  const contentW = 8 * NODE_W + CENTER_W + 8 * COL_GAP; // 9 cols, 8 gaps

  const zoomBtn = (label, onTap, title) => (
    <button onClick={onTap} title={title} className="mono" style={{
      width: 34, height: 34, borderRadius: 10, border: "2.5px solid var(--ink)",
      background: "var(--card)", fontWeight: 800, fontSize: 15, cursor: "pointer",
      boxShadow: "2px 2px 0 rgba(44,32,22,.3)", display: "flex", alignItems: "center",
      justifyContent: "center", padding: 0 }}>{label}</button>
  );

  const zoomCenter = (factor) => {
    const view = viewRef.current;
    if (view) zoomAt(view.clientWidth / 2, view.clientHeight / 2, factor);
  };

  return (
    <div className="rise">
      <div className="wrap" style={{ paddingBottom: 12 }}>
        <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 14 }}>
          <ZineHeading kicker="The knockout graph · 32 matches" title="Road to MetLife" color="var(--sun)" />
          <span className="mono" style={{ fontSize: 10, color: "var(--ink-faint)", marginBottom: 22 }}>
            drag to pan · scroll or pinch to zoom · tap a match →
          </span>
        </div>
      </div>

      <div style={{ padding: "0 14px" }}>
        <div style={{ position: "relative", maxWidth: 1480, margin: "0 auto" }}>
          {/* zoom controls */}
          <div style={{ position: "absolute", top: 10, right: 10, zIndex: 6, display: "flex", gap: 7, alignItems: "center" }}>
            <span className="chip" style={{ fontSize: 10, background: "var(--card)" }}>{zoomPct}%</span>
            {zoomBtn("−", () => zoomCenter(1 / 1.35), "Zoom out")}
            {zoomBtn("⛶", fitToScreen, "Fit to screen")}
            {zoomBtn("+", () => zoomCenter(1.35), "Zoom in")}
          </div>

          {/* viewport */}
          <div
            ref={viewRef}
            onPointerDown={onPointerDown}
            onPointerMove={onPointerMove}
            onPointerUp={onPointerUp}
            onPointerCancel={onPointerUp}
            onClickCapture={(e) => { if (suppressClick.current) { e.stopPropagation(); e.preventDefault(); } }}
            style={{
              height: viewH, overflow: "hidden", position: "relative",
              touchAction: "none", cursor: "grab",
              border: "3px solid var(--ink)", borderRadius: 18,
              background: "repeating-linear-gradient(45deg, rgba(44,32,22,.025) 0 14px, transparent 14px 28px)",
              boxShadow: "3px 4px 0 rgba(44,32,22,.25)",
            }}
          >
            <div ref={contentRef} style={{ width: contentW, transformOrigin: "0 0", willChange: "transform" }}>
              {/* column headers */}
              <div style={{ display: "flex", gap: COL_GAP, margin: "14px 0 10px" }}>
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

              <div ref={graphRef} style={{ position: "relative", display: "flex", gap: COL_GAP, paddingBottom: 14 }}>
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
    </div>
  );
}

window.Bracket = Bracket;
