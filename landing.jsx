/* ============================================================
   Landing page — live ticker, today's slate, host cities
   ============================================================ */
const { useState, useEffect, useRef } = React;
const WC = window.WC;

function Countdown({ to }) {
  const ms = Date.parse(to) - Date.now();
  if (ms <= 0) return null;
  const d = Math.floor(ms / 86400e3);
  const h = Math.floor((ms % 86400e3) / 3600e3);
  const m = Math.floor((ms % 3600e3) / 60e3);
  const s = Math.floor((ms % 60e3) / 1e3);
  const cell = (v, lbl) => (
    <div style={{ textAlign: "center" }}>
      <div className="display" style={{ fontSize: 34, lineHeight: 1 }}>{String(v).padStart(2, "0")}</div>
      <div className="label" style={{ fontSize: 9 }}>{lbl}</div>
    </div>
  );
  return (
    <div style={{ display: "flex", gap: 18, justifyContent: "center", alignItems: "center" }}>
      {cell(d, "days")}<span className="display" style={{ fontSize: 24 }}>:</span>
      {cell(h, "hrs")}<span className="display" style={{ fontSize: 24 }}>:</span>
      {cell(m, "min")}<span className="display" style={{ fontSize: 24 }}>:</span>
      {cell(s, "sec")}
    </div>
  );
}

function LiveTicker({ go }) {
  const m = WC.headline();
  if (!m) return null;
  const live = isLiveStatus(m.status);
  const ha = m.home.fifa_code, aa = m.away.fifa_code;
  const upcoming = m.status === "upcoming";
  return (
    <div
      onClick={() => go("match", { num: m.match_number })}
      className="sticker lift"
      style={{
        display: "flex", alignItems: "center", flexWrap: "wrap", justifyContent: "center",
        gap: "10px 16px", padding: "13px 16px", cursor: "pointer",
        borderColor: "var(--sun-d)", background: "#fff6ee",
        maxWidth: "min(600px, 100%)",
      }}
    >
      <StatusBadge match={m} />
      <div style={{ display: "flex", alignItems: "center", gap: 10, justifyContent: "center", minWidth: 0 }}>
        <Flag code={ha} size={24} />
        <span className="display" style={{ fontSize: 24 }}>{ha || "TBD"}</span>
        {upcoming
          ? <span className="display" style={{ fontSize: 20, color: "var(--ink-soft)" }}>vs</span>
          : <span className="mono" style={{ fontSize: 24, fontWeight: 700, color: "var(--sun-d)", whiteSpace: "nowrap" }}>
              {m.home.score != null ? m.home.score : "–"}–{m.away.score != null ? m.away.score : "–"}
            </span>}
        <span className="display" style={{ fontSize: 24 }}>{aa || "TBD"}</span>
        <Flag code={aa} size={24} />
        <span className="mono" style={{ fontSize: 11, color: "var(--ink-soft)", flexShrink: 0 }}>
          {live ? "Watch →" : upcoming ? "Preview →" : "Recap →"}
        </span>
      </div>
    </div>
  );
}

function CityCard({ letters, city, country, venue, rot, color }) {
  const flags = { USA: "🇺🇸", Canada: "🇨🇦", Mexico: "🇲🇽" };
  return (
    <div className="sticker lift" style={{ padding: "16px 14px 14px", transform: `rotate(${rot}deg)`, textAlign: "center", width: 168 }}>
      <Sticker letters={letters} size={56} color={color} style={{ margin: "0 auto 10px" }} />
      <div className="display" style={{ fontSize: 19, lineHeight: 1 }}>{city}</div>
      <div className="mono" style={{ fontSize: 10.5, color: "var(--ink-soft)", marginTop: 5 }}>{venue}</div>
      <div style={{ marginTop: 8 }}>
        <span className="chip" style={{ fontSize: 10 }}>{flags[country]} {country}</span>
      </div>
    </div>
  );
}

function Marquee() {
  const items = ["48 teams · 16 cities · 3 nations", "June 11 – July 19", "104 matches, one trophy", "Final · July 19 · MetLife Stadium"];
  const chunk = (k) => (
    <div className="marquee-chunk" key={k}>
      {items.map((t, i) => (
        <React.Fragment key={i}>
          <span>{t}</span>
          <ZStar size={13} color="var(--amber)" ink="var(--amber)" />
        </React.Fragment>
      ))}
    </div>
  );
  return (
    <div className="marquee" aria-hidden="true">
      <div className="marquee-track">{[0, 1, 2, 3].map(chunk)}</div>
    </div>
  );
}

function MatchStrip({ title, kicker, color, matches, go, empty }) {
  if (!matches.length && !empty) return null;
  return (
    <div style={{ marginTop: 40 }}>
      <ZineHeading kicker={kicker} title={title} color={color} />
      {matches.length === 0 ? (
        <p className="mono" style={{ fontSize: 12, color: "var(--ink-soft)" }}>{empty}</p>
      ) : (
        <div style={{ display: "flex", flexWrap: "wrap", gap: 18 }}>
          {matches.map((m, i) => (
            <MatchNode key={m.match_number} num={m.match_number}
              onOpen={(num) => go("match", { num })} rot={(i % 3 - 1) * 0.9} />
          ))}
        </div>
      )}
    </div>
  );
}

function Landing({ go }) {
  const cities = [
    { letters: "NYC", city: "New York", country: "USA", venue: "MetLife · The Final", rot: -2, color: "#dfeefa" },
    { letters: "CDMX", city: "Mexico City", country: "Mexico", venue: "Estadio Azteca · Opener", rot: 1.5, color: "#e3f3e7" },
    { letters: "TOR", city: "Toronto", country: "Canada", venue: "BMO Field", rot: -1, color: "#fbe6e3" },
    { letters: "LA", city: "Los Angeles", country: "USA", venue: "SoFi Stadium", rot: 2, color: "#fdf0d8" },
    { letters: "DAL", city: "Dallas", country: "USA", venue: "AT&T Stadium", rot: -1.5, color: "#fde9d7" },
    { letters: "VAN", city: "Vancouver", country: "Canada", venue: "BC Place", rot: 1, color: "#e3eff0" },
    { letters: "GDL", city: "Guadalajara", country: "Mexico", venue: "Estadio Akron", rot: -2, color: "#fbeede" },
    { letters: "SEA", city: "Seattle", country: "USA", venue: "Lumen Field", rot: 1.5, color: "#e8eef0" },
  ];

  const live = WC.liveMatches();
  const next = WC.nextMatches(6).filter((m) => !live.some((l) => l.match_number === m.match_number));
  const recent = WC.recentResults(6);
  const opener = WC.getMatch(1);
  const preTournament = opener && opener.status === "upcoming" && recent.length === 0 && live.length === 0;

  return (
    <div className="rise">
      {/* ============ HERO ============ */}
      <div style={{ position: "relative", overflow: "hidden", borderBottom: "3px solid var(--ink)" }}>
        <div className="halftone" style={{
          position: "absolute", inset: -40, color: "rgba(232,93,42,0.16)", zIndex: 0,
          maskImage: "radial-gradient(circle at 70% 30%, #000, transparent 60%)",
          WebkitMaskImage: "radial-gradient(circle at 70% 30%, #000, transparent 60%)",
        }}></div>

        <Sticker className="hero-deco" icon={<ZBall size={36} />} size={70} rot={-12} float="a" style={{ position: "absolute", left: "4%", top: 48, zIndex: 5 }} />
        <Sticker className="hero-deco" icon={<ZSun size={32} />} size={58} rot={10} float="b" color="#fdf0d8" style={{ position: "absolute", left: "30%", top: 18, zIndex: 5 }} />
        <Sticker className="hero-deco" icon={<ZPennant size={30} />} size={54} rot={-8} float="c" color="#dfeefa" style={{ position: "absolute", right: "26%", bottom: 30, zIndex: 5 }} />
        <Sticker className="hero-deco" icon={<ZBolt size={28} />} size={50} rot={14} float="d" color="#fbe6e3" style={{ position: "absolute", right: "7%", top: 70, zIndex: 5 }} />
        <Sticker className="hero-deco" icon={<ZTrophy size={34} />} size={62} rot={-6} float="b" color="#f6e3b0" style={{ position: "absolute", right: "13%", bottom: 90, zIndex: 5 }} />
        <Sticker className="hero-deco" icon={<ZStar size={26} />} size={46} rot={8} float="c" color="#e3f3e7" style={{ position: "absolute", left: "12%", bottom: 60, zIndex: 5 }} />
        <Tape className="hero-deco" style={{ left: "8%", top: 30, transform: "rotate(-8deg)" }} variant="teal" />
        <Tape className="hero-deco" style={{ right: "20%", top: 20, transform: "rotate(7deg)" }} variant="sun" />

        <div className="wrap" style={{ position: "relative", zIndex: 4, paddingTop: 56, paddingBottom: 48, textAlign: "center" }}>
          <div className="label" style={{ fontSize: 13, letterSpacing: ".24em", marginBottom: 14 }}>
            🇺🇸 USA · 🇨🇦 CANADA · 🇲🇽 MEXICO
          </div>
          <h1 className="display" style={{ fontSize: "clamp(56px, 11vw, 132px)", margin: "0 0 4px", color: "var(--ink)" }}>
            World&nbsp;Cup
          </h1>
          <div style={{ display: "flex", alignItems: "center", justifyContent: "center", gap: 18, flexWrap: "wrap" }}>
            <span className="display" style={{ fontSize: "clamp(50px, 10vw, 116px)", color: "var(--sun)",
              WebkitTextStroke: "2px var(--ink)", textShadow: "4px 5px 0 var(--ink)" }}>2026</span>
          </div>
          <p style={{ fontSize: 18, maxWidth: 580, margin: "20px auto 0", color: "var(--ink-soft)", lineHeight: 1.5 }}>
            48 teams. 16 cities. 104 matches across one continent — every score,
            lineup and bracket twist, live.
          </p>

          {preTournament && (
            <div style={{ margin: "26px auto 0", maxWidth: 420 }}>
              <div className="label" style={{ fontSize: 11, marginBottom: 10 }}>Kickoff · Mexico City</div>
              <Countdown to={opener.kickoff_utc} />
            </div>
          )}

          <div style={{ display: "flex", gap: 14, justifyContent: "center", marginTop: 26, flexWrap: "wrap" }}>
            <button className="btn" onClick={() => go("groups")}>Groups →</button>
            <button className="btn ghost" onClick={() => go("bracket")}>Bracket →</button>
            <button className="btn teal" onClick={() => go("players")}>Players →</button>
          </div>
          <div style={{ display: "flex", justifyContent: "center", marginTop: 30 }}>
            <LiveTicker go={go} />
          </div>
        </div>
      </div>

      {/* ============ MARQUEE ============ */}
      <Marquee />

      <div className="wrap">
        {live.length > 0 && (
          <MatchStrip title="On the pitch" kicker="Live right now" color="var(--sun)" matches={live} go={go} />
        )}
        <MatchStrip
          title={preTournament ? "Opening slate" : "Coming up"}
          kicker="Next kickoffs · shown in your local time" color="var(--teal)"
          matches={next} go={go}
          empty="The tournament schedule is complete." />
        {recent.length > 0 && (
          <MatchStrip title="Latest results" kicker="Full time" color="var(--amber)" matches={recent} go={go} />
        )}

        {/* ============ HOST CITIES ============ */}
        <div style={{ marginTop: 64 }}>
          <div style={{ display: "flex", alignItems: "flex-end", justifyContent: "space-between", flexWrap: "wrap", gap: 12 }}>
            <ZineHeading kicker="16 host cities · 3 nations" title="Where it happens" color="var(--teal)" />
            <p className="mono" style={{ fontSize: 12, color: "var(--ink-soft)", maxWidth: 320, marginBottom: 22 }}>
              From the Azteca to MetLife — a continent stitched together for one summer.
            </p>
          </div>
          <div style={{ display: "flex", flexWrap: "wrap", gap: 20, justifyContent: "center" }}>
            {cities.map((c) => <CityCard key={c.city} {...c} />)}
          </div>
        </div>
      </div>
    </div>
  );
}

window.Landing = Landing;
