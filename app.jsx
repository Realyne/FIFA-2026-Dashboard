/* ============================================================
   App — routing, topbar, store subscription
   ============================================================ */
const { useState, useEffect } = React;
const WC = window.WC;

function parseHash() {
  const h = (window.location.hash || "#/").replace(/^#\/?/, "");
  const parts = h.split("/").filter(Boolean);
  if (parts.length === 0) return { view: "landing", params: {} };
  if (parts[0] === "bracket") return { view: "bracket", params: {} };
  if (parts[0] === "groups") return { view: "groups", params: { group: parts[1] || null } };
  if (parts[0] === "players") return { view: "players", params: {} };
  if (parts[0] === "match") return { view: "match", params: { num: parseInt(parts[1], 10) } };
  if (parts[0] === "player") return { view: "player", params: { id: parts[1] } };
  return { view: "landing", params: {} };
}
function toHash(view, params) {
  if (view === "landing") return "#/";
  if (view === "bracket") return "#/bracket";
  if (view === "groups") return params.group ? "#/groups/" + params.group : "#/groups";
  if (view === "players") return "#/players";
  if (view === "match") return "#/match/" + params.num;
  if (view === "player") return "#/player/" + params.id;
  return "#/";
}

function ConnectionDot() {
  const c = WC.store.connection;
  const color = c === "live" ? "#3f9d56" : c === "connecting" ? "var(--amber)" : c === "polling" ? "var(--amber)" : "#d8341f";
  const label = c === "live" ? "live feed" : c === "connecting" ? "connecting" : c === "polling" ? "reconnecting" : "offline";
  return (
    <span className="mono" title={"Data connection: " + label}
      style={{ display: "inline-flex", alignItems: "center", gap: 5, fontSize: 9.5, color: "var(--ink-soft)" }}>
      <span style={{ width: 8, height: 8, borderRadius: "50%", background: color, display: "inline-block" }}></span>
      {label}
    </span>
  );
}

function Topbar({ route, go, back }) {
  const headline = WC.headline();
  const headlineLive = headline && isLiveStatus(headline.status);
  const crumbs = [];
  crumbs.push(<a key="h" onClick={() => go("landing")}>Home</a>);
  if (route.view === "bracket") crumbs.push(<span key="s1">/</span>, <span key="b" style={{ color: "var(--paper)" }}>Bracket</span>);
  if (route.view === "groups") crumbs.push(<span key="s1">/</span>, <span key="b" style={{ color: "var(--paper)" }}>Groups</span>);
  if (route.view === "players") crumbs.push(<span key="s1">/</span>, <span key="b" style={{ color: "var(--paper)" }}>Players</span>);
  if (route.view === "match") {
    const m = WC.getMatch(route.params.num);
    const lbl = m
      ? (m.home.fifa_code || "TBD") + " v " + (m.away.fifa_code || "TBD")
      : "Match";
    crumbs.push(<span key="s1">/</span>, <a key="b" onClick={() => go("bracket")}>Matches</a>,
      <span key="s2">/</span>, <span key="m" style={{ color: "var(--paper)" }}>{lbl}</span>);
  }
  if (route.view === "player") {
    const p = WC.store.playersById[route.params.id];
    crumbs.push(<span key="s1">/</span>, <a key="b" onClick={() => go("players")}>Players</a>,
      <span key="s2">/</span>, <span key="m" style={{ color: "var(--paper)" }}>{p ? p.name : "Player"}</span>);
  }
  return (
    <div className="topbar">
      <div className="brand" onClick={() => go("landing")}>
        <ZBall size={22} /> WC26
      </div>
      {route.view !== "landing" && (
        <button
          onClick={back}
          style={{ fontFamily: "var(--font-mono)", fontSize: 11, fontWeight: 700, textTransform: "uppercase",
            letterSpacing: ".08em", cursor: "pointer", background: "transparent", color: "var(--paper)",
            border: "2px solid var(--ink-soft)", borderRadius: 30, padding: "5px 13px", whiteSpace: "nowrap" }}
          onMouseEnter={(e) => { e.currentTarget.style.borderColor = "var(--amber)"; e.currentTarget.style.color = "var(--amber)"; }}
          onMouseLeave={(e) => { e.currentTarget.style.borderColor = "var(--ink-soft)"; e.currentTarget.style.color = "var(--paper)"; }}
        >← Back</button>
      )}
      <div className="crumbs">{crumbs}</div>
      <div className="spacer"></div>
      <div className="topnav">
        <span className={"navlink " + (route.view === "landing" ? "active" : "")} onClick={() => go("landing")}>Home</span>
        <span className={"navlink " + (route.view === "groups" ? "active" : "")} onClick={() => go("groups")}>Groups</span>
        <span className={"navlink " + (route.view === "bracket" ? "active" : "")} onClick={() => go("bracket")}>Bracket</span>
        <span className={"navlink " + (route.view === "players" || route.view === "player" ? "active" : "")} onClick={() => go("players")}>Players</span>
        {headline && (
          <span className="navlink" onClick={() => go("match", { num: headline.match_number })} style={{ display: "flex", alignItems: "center", gap: 6 }}>
            {headlineLive && <span className="live-dot" style={{ background: "var(--sun)" }}></span>}
            {headlineLive ? "Live" : "Next"}
          </span>
        )}
      </div>
    </div>
  );
}

/* fixed bottom tab bar — visible only on small screens (see styles.css) */
function BottomBar({ route, go }) {
  const headline = WC.headline();
  const headlineLive = headline && isLiveStatus(headline.status);
  const tabs = [
    { key: "landing", label: "Home", active: route.view === "landing", onTap: () => go("landing") },
    { key: "groups", label: "Groups", active: route.view === "groups", onTap: () => go("groups") },
    { key: "bracket", label: "Bracket", active: route.view === "bracket", onTap: () => go("bracket") },
    { key: "players", label: "Players", active: route.view === "players" || route.view === "player", onTap: () => go("players") },
  ];
  if (headline) {
    tabs.push({
      key: "live", live: headlineLive,
      label: headlineLive ? "Live" : "Next",
      active: route.view === "match" && route.params.num === headline.match_number,
      onTap: () => go("match", { num: headline.match_number }),
    });
  }
  return (
    <nav className="bottombar" aria-label="Main">
      {tabs.map((t) => (
        <span key={t.key} className={"bnav" + (t.active ? " active" : "")} onClick={t.onTap}>
          <span style={{ display: "inline-flex", alignItems: "center", gap: 4 }}>
            {t.live && <span className="live-dot" style={{ background: t.active ? "var(--ink)" : "var(--sun)" }}></span>}
            {t.label}
          </span>
        </span>
      ))}
    </nav>
  );
}

function Footer() {
  return (
    <div style={{ marginTop: 56, padding: "26px 0 34px", borderTop: "3px solid var(--ink)", textAlign: "center" }}>
      <p className="mono" style={{ fontSize: 10.5, color: "var(--ink-faint)", lineHeight: 1.8, maxWidth: 640, margin: "0 auto" }}>
        Live scores &amp; lineups via ESPN's public feeds · Career data from
        {" "}<a href="https://www.wikidata.org" target="_blank" rel="noopener noreferrer" style={{ color: "var(--ink-soft)" }}>Wikidata</a>
        {" "}&amp; Wikipedia squad lists · Flags by
        {" "}<a href="https://flagcdn.com" target="_blank" rel="noopener noreferrer" style={{ color: "var(--ink-soft)" }}>flagpedia</a>
        <br />
        A <a href="https://realyne.com" target="_blank" rel="noopener noreferrer" style={{ color: "var(--ink-soft)", fontWeight: 700 }}>Realyne 2026</a> project
        · Unofficial fan site — not affiliated with FIFA or any team. Schedule shown in your local time.
      </p>
      <div style={{ marginTop: 10 }}><ConnectionDot /></div>
    </div>
  );
}

function App() {
  const [route, setRoute] = useState(parseHash());
  const [, force] = useState(0);
  const histRef = React.useRef([]);

  useEffect(() => {
    const onHash = () => { setRoute(parseHash()); window.scrollTo(0, 0); };
    window.addEventListener("hashchange", onHash);
    return () => window.removeEventListener("hashchange", onHash);
  }, []);

  // store updates (SSE patches, fetches) + 1s clock tick for "next kickoff" countdowns
  useEffect(() => WC.subscribe(() => force((n) => n + 1)), []);
  useEffect(() => {
    const t = setInterval(() => force((n) => n + 1), 1000);
    return () => clearInterval(t);
  }, []);

  const go = (view, params = {}) => {
    const h = toHash(view, params);
    const cur = window.location.hash || "#/";
    if (cur === h) { setRoute({ view, params }); window.scrollTo(0, 0); return; }
    histRef.current.push(cur);
    if (histRef.current.length > 50) histRef.current.shift();
    window.location.hash = h;
  };

  const back = () => {
    const prev = histRef.current.pop();
    if (prev && prev !== (window.location.hash || "#/")) window.location.hash = prev;
    else go("landing");
  };

  if (!WC.store.ready) {
    return (
      <div className="app">
        <Topbar route={{ view: "landing", params: {} }} go={go} back={back} />
        <LoadingSplash />
        <BottomBar route={{ view: "landing", params: {} }} go={go} />
      </div>
    );
  }

  let body = null;
  if (route.view === "landing") body = <Landing go={go} />;
  else if (route.view === "bracket") body = <Bracket go={go} />;
  else if (route.view === "groups") body = <GroupsPage go={go} group={route.params.group} />;
  else if (route.view === "players") body = <PlayersPage go={go} />;
  else if (route.view === "match") body = <MatchDetail num={route.params.num} go={go} />;
  else if (route.view === "player") body = <PlayerDetail id={route.params.id} go={go} />;

  return (
    <div className="app">
      <Topbar route={route} go={go} back={back} />
      {body}
      <Footer />
      <BottomBar route={route} go={go} />
    </div>
  );
}

ReactDOM.createRoot(document.getElementById("root")).render(<App />);
