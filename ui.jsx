/* ============================================================
   Shared UI components → window
   (live-data edition: reads window.WC store)
   ============================================================ */
const { useState, useEffect, useRef } = React;
const WC = window.WC;

/* ---- Tape strip ---- */
function Tape({ style, variant }) {
  return <div className={"tape " + (variant || "")} style={style} aria-hidden="true"></div>;
}

/* ============ Simple SVG zine icons (basic shapes only) ============ */
function ZBall({ size = 24, ink = "#2c2016" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="10.4" fill="#fdfaf2" stroke={ink} strokeWidth="2"></circle>
      <polygon points="12,8 15.8,10.8 14.4,15.2 9.6,15.2 8.2,10.8" fill={ink}></polygon>
      <line x1="12" y1="8" x2="12" y2="2.6" stroke={ink} strokeWidth="1.6"></line>
      <line x1="15.8" y1="10.8" x2="20.8" y2="8.8" stroke={ink} strokeWidth="1.6"></line>
      <line x1="8.2" y1="10.8" x2="3.2" y2="8.8" stroke={ink} strokeWidth="1.6"></line>
      <line x1="14.4" y1="15.2" x2="17.6" y2="19.6" stroke={ink} strokeWidth="1.6"></line>
      <line x1="9.6" y1="15.2" x2="6.4" y2="19.6" stroke={ink} strokeWidth="1.6"></line>
    </svg>
  );
}
function ZSun({ size = 24, color = "var(--sun)", ink = "#2c2016" }) {
  const rays = [];
  for (let i = 0; i < 8; i++) {
    const a = (i * 45 * Math.PI) / 180;
    rays.push(<line key={i} x1={12 + Math.cos(a) * 8.2} y1={12 + Math.sin(a) * 8.2}
      x2={12 + Math.cos(a) * 11.2} y2={12 + Math.sin(a) * 11.2} stroke={ink} strokeWidth="2" strokeLinecap="round"></line>);
  }
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <g className="spin-slow">{rays}</g>
      <circle cx="12" cy="12" r="5.6" fill={color} stroke={ink} strokeWidth="2"></circle>
    </svg>
  );
}
function ZStar({ size = 24, color = "var(--amber)", ink = "#2c2016" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <polygon points="12,2.5 14.9,8.6 21.6,9.4 16.6,14 18,20.8 12,17.4 6,20.8 7.4,14 2.4,9.4 9.1,8.6"
        fill={color} stroke={ink} strokeWidth="1.8" strokeLinejoin="round"></polygon>
    </svg>
  );
}
function ZBolt({ size = 24, color = "var(--amber)", ink = "#2c2016" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <polygon points="13.5,2 5,13.5 10.8,13.5 9,22 19,10.5 13.2,10.5"
        fill={color} stroke={ink} strokeWidth="1.8" strokeLinejoin="round"></polygon>
    </svg>
  );
}
function ZTrophy({ size = 24, color = "var(--amber)", ink = "#2c2016" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M6 3.5 h12 v5.5 a6 6 0 0 1 -12 0 z" fill={color} stroke={ink} strokeWidth="1.8" strokeLinejoin="round"></path>
      <rect x="10.6" y="14.5" width="2.8" height="3.2" fill={ink}></rect>
      <rect x="6.8" y="17.7" width="10.4" height="3" rx="1" fill={color} stroke={ink} strokeWidth="1.8"></rect>
    </svg>
  );
}
function ZPennant({ size = 24, color = "var(--teal)", ink = "#2c2016" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <line x1="5" y1="2.5" x2="5" y2="21.5" stroke={ink} strokeWidth="2" strokeLinecap="round"></line>
      <polygon points="6.5,3.5 21,7 6.5,12.5" fill={color} stroke={ink} strokeWidth="1.8" strokeLinejoin="round"></polygon>
    </svg>
  );
}
function ZPin({ size = 14, color = "var(--sun-d)", ink = "#2c2016" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="9" r="6" fill={color} stroke={ink} strokeWidth="1.8"></circle>
      <polygon points="7.5,12.5 16.5,12.5 12,21.5" fill={color} stroke={ink} strokeWidth="1.8" strokeLinejoin="round"></polygon>
      <circle cx="12" cy="9" r="2.2" fill="#fdfaf2"></circle>
    </svg>
  );
}
function ZClock({ size = 24, ink = "#2c2016" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <circle cx="12" cy="12" r="9.5" fill="#fdfaf2" stroke={ink} strokeWidth="2"></circle>
      <line x1="12" y1="12" x2="12" y2="6.5" stroke={ink} strokeWidth="2" strokeLinecap="round"></line>
      <line x1="12" y1="12" x2="16" y2="14.5" stroke={ink} strokeWidth="2" strokeLinecap="round"></line>
    </svg>
  );
}
function ZCardIcon({ size = 16, color = "#f4c81d", ink = "#2c2016" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <rect x="7" y="3.5" width="11" height="16" rx="2" fill={color} stroke={ink} strokeWidth="1.8" transform="rotate(8 12 12)"></rect>
    </svg>
  );
}
function ZSubArrows({ size = 16, ink = "#2c2016" }) {
  return (
    <svg width={size} height={size} viewBox="0 0 24 24" aria-hidden="true">
      <path d="M4 8.5 h11 M12 5 l3.5 3.5 L12 12" fill="none" stroke="var(--teal-d)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"></path>
      <path d="M20 15.5 h-11 M12 12.5 l-3.5 3 L12 19" fill="none" stroke="var(--sun-d)" strokeWidth="2.2" strokeLinecap="round" strokeLinejoin="round"></path>
    </svg>
  );
}

/* ---- Die-cut sticker (emoji, SVG icon, or letters) ---- */
function Sticker({ emoji, icon, letters, label, size = 64, rot = 0, color = "var(--card)", style, className, float, children }) {
  const floatCls = float ? " float-" + float : "";
  return (
    <div
      className={"sticker diecut" + floatCls + " " + (className || "")}
      style={{
        width: size, height: size, borderRadius: "50%", background: color,
        display: "flex", alignItems: "center", justifyContent: "center",
        fontSize: size * 0.5, lineHeight: 1, "--rot": rot + "deg",
        overflow: "hidden",
        ...(float ? {} : { transform: `rotate(${rot}deg)` }),
        ...style,
      }}
      title={label || ""}
    >
      {children ? children :
       icon ? icon :
       letters ? <span className="display" style={{ fontSize: size * 0.3, letterSpacing: ".02em" }}>{letters}</span> :
       <span style={{ filter: "drop-shadow(1px 1px 0 rgba(44,32,22,0.2))" }}>{emoji}</span>}
    </div>
  );
}

/* ---- Flag token (flagcdn image keyed by FIFA code) ---- */
function Flag({ code, size = 22, badge = false }) {
  const t = code ? WC.store.teams[code] : null;
  const dim = { width: size, height: size };
  if (!t) {
    return (
      <span className="flag-badge" style={{ ...dim, fontSize: size * 0.45, display: "inline-flex",
        alignItems: "center", justifyContent: "center", background: "var(--paper-2)" }}>?</span>
    );
  }
  const img = (
    <img
      src={t.flag_url}
      srcSet={t.flag_url_svg ? t.flag_url_svg + " 2x" : undefined}
      alt={t.name + " flag"}
      loading="lazy"
      style={{ width: "100%", height: "100%", objectFit: "cover", display: "block" }}
    />
  );
  if (badge) {
    return (
      <span className="flag-badge" style={{ ...dim, padding: 0, overflow: "hidden",
        display: "inline-flex", flexShrink: 0 }}>{img}</span>
    );
  }
  return (
    <span style={{ ...dim, display: "inline-flex", borderRadius: 4, overflow: "hidden",
      border: "1.5px solid var(--ink)", flexShrink: 0, boxShadow: "1px 1px 0 rgba(44,32,22,.25)" }}>{img}</span>
  );
}

/* ---- Initials avatar over team colors (no player photos by design) ---- */
function PlayerAvatar({ player, size = 46 }) {
  const t = WC.store.teams[player.fifa_code] || {};
  return (
    <div className="sticker diecut" style={{
      width: size, height: size, borderRadius: "50%", flexShrink: 0,
      background: t.color_primary || "var(--paper-2)",
      display: "flex", alignItems: "center", justifyContent: "center",
    }}>
      <span className="display" style={{
        fontSize: size * 0.38,
        color: t.color_secondary || "#fff",
        textShadow: "1px 1px 0 rgba(44,32,22,.45)", letterSpacing: ".02em",
      }}>{WC.initials(player.name)}</span>
    </div>
  );
}

/* ---- Striped photo placeholder ---- */
function PhotoPlaceholder({ label = "photo", style, children, className }) {
  return (
    <div className={"photo-ph " + (className || "")} style={style}>
      {children || <span className="ph-label">{label}</span>}
    </div>
  );
}

/* ---- Status chip: upcoming | live | ht | et | pens | finished ---- */
function StatusBadge({ match }) {
  const s = match.status;
  if (s === "live" || s === "et") {
    const lbl = (s === "et" ? "ET" : "LIVE") + (match.minute_display ? " · " + match.minute_display + "'" : "");
    return <span className="chip live"><span className="live-dot"></span>{lbl}</span>;
  }
  if (s === "ht") return <span className="chip live"><span className="live-dot"></span>HT</span>;
  if (s === "pens") return <span className="chip live"><span className="live-dot"></span>PENS</span>;
  if (s === "finished") return <span className="chip finished">Full time</span>;
  return <span className="chip upcoming">{WC.kickoffLocal(match)}</span>;
}

function isLiveStatus(s) {
  return s === "live" || s === "ht" || s === "et" || s === "pens";
}

/* ---- One team line inside a match node ---- */
function TeamLine({ side, winner, live }) {
  const code = side && side.fifa_code;
  const t = code ? WC.store.teams[code] : null;
  const name = t ? t.name : (side && side.label) || "TBD";
  const score = side ? side.score : null;
  return (
    <div style={{
      display: "flex", alignItems: "center", gap: 10, padding: "7px 0",
      opacity: code ? 1 : 0.55, fontWeight: winner ? 700 : 500,
    }}>
      <Flag code={code} badge size={28} />
      <span style={{ flex: 1, fontSize: 15.5, letterSpacing: ".01em",
        fontWeight: winner ? 700 : 500, color: "var(--ink)", whiteSpace: "nowrap",
        overflow: "hidden", textOverflow: "ellipsis",
        fontStyle: code ? "normal" : "italic" }}>
        {name}
        {side && side.pen_score != null && <span className="mono" style={{ fontSize: 11, color: "var(--ink-soft)" }}> ({side.pen_score})</span>}
      </span>
      <span className="mono" style={{
        fontSize: 20, fontWeight: 700, minWidth: 22, textAlign: "right",
        color: live ? "var(--sun-d)" : "var(--ink)",
      }}>
        {score != null ? score : "–"}
      </span>
    </div>
  );
}

function matchWinnerSides(m) {
  if (m.status !== "finished") return [false, false];
  const hs = m.home.score, as = m.away.score;
  if (hs == null || as == null) return [false, false];
  if (hs !== as) return [hs > as, as > hs];
  const hp = m.home.pen_score, ap = m.away.pen_score;
  if (hp != null && ap != null) return [hp > ap, ap > hp];
  return [false, false];
}

/* ---- Reusable match node card (bracket + lists) ---- */
function MatchNode({ num, onOpen, compact, rot = 0 }) {
  const m = WC.getMatch(num);
  if (!m) return null;
  const live = isLiveStatus(m.status);
  const [winA, winB] = matchWinnerSides(m);
  const v = WC.store.venues[m.venue_id] || {};
  const roundLbl = m.round === "group" ? "Group " + m.group : WC.ROUNDS[m.round];
  return (
    <div
      className="sticker lift"
      onClick={() => onOpen(num)}
      style={{
        width: compact ? 230 : 252, padding: "11px 14px", cursor: "pointer",
        transform: `rotate(${rot}deg)`,
        borderColor: live ? "var(--sun-d)" : "var(--ink)",
        background: live ? "#fff6ee" : "var(--card)",
      }}
    >
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginBottom: 6, gap: 6 }}>
        <span className="label" style={{ fontSize: 9.5, letterSpacing: ".09em", whiteSpace: "nowrap" }}>
          {roundLbl} · M{m.match_number}
        </span>
        <StatusBadge match={m} />
      </div>
      <TeamLine side={m.home} winner={winA} live={live} />
      <div style={{ height: 1, background: "repeating-linear-gradient(90deg,var(--ink-faint) 0 5px,transparent 5px 10px)" }}></div>
      <TeamLine side={m.away} winner={winB} live={live} />
      <div style={{ display: "flex", justifyContent: "space-between", alignItems: "center", marginTop: 8, gap: 8 }}>
        <span className="mono" style={{ fontSize: 10, color: "var(--ink-faint)", whiteSpace: "nowrap", overflow: "hidden", textOverflow: "ellipsis", display: "inline-flex", alignItems: "center", gap: 4 }}>
          <ZPin size={11} /> {(v.city || "").split("(")[0].trim()}
        </span>
        <span className="mono" style={{ fontSize: 10, color: "var(--ink-faint)", whiteSpace: "nowrap" }}>
          {WC.kickoffLocal(m, { hour: undefined, minute: undefined })}
        </span>
      </div>
    </div>
  );
}

/* ---- Section heading with halftone underline ---- */
function ZineHeading({ kicker, title, color = "var(--sun)" }) {
  return (
    <div style={{ marginBottom: 18 }}>
      {kicker && <div className="label" style={{ marginBottom: 6 }}>{kicker}</div>}
      <h2 className="display" style={{ fontSize: 38, margin: 0, color: "var(--ink)", display: "flex", alignItems: "center", gap: 12 }}>
        <span style={{ whiteSpace: "nowrap" }}>{title}</span>
        <span style={{ display: "inline-block", width: 70, height: 10, flexShrink: 0,
          background: color, borderRadius: 6, transform: "rotate(-1.5deg)" }}></span>
      </h2>
    </div>
  );
}

/* ---- Loading / connection banner ---- */
function LoadingSplash() {
  return (
    <div style={{ minHeight: "60vh", display: "flex", flexDirection: "column",
      alignItems: "center", justifyContent: "center", gap: 18 }}>
      <Sticker icon={<ZBall size={40} />} size={76} float="a" />
      <div className="display" style={{ fontSize: 30 }}>Warming up…</div>
      <p className="mono" style={{ fontSize: 12, color: "var(--ink-soft)" }}>
        {WC.store.error ? "Can't reach the data service — retrying" : "Fetching live tournament data"}
      </p>
    </div>
  );
}

Object.assign(window, {
  Tape, Sticker, Flag, PlayerAvatar, PhotoPlaceholder, StatusBadge, TeamLine,
  MatchNode, ZineHeading, LoadingSplash, isLiveStatus, matchWinnerSides,
  ZBall, ZSun, ZStar, ZBolt, ZTrophy, ZPennant, ZPin, ZClock, ZCardIcon, ZSubArrows,
});
