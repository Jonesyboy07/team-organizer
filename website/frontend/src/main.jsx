import React, { useEffect, useState } from "react";
import { createRoot } from "react-dom/client";
import "./style.css";

async function api(path, options = {}) {
  const response = await fetch(path, { credentials: "same-origin", ...options });
  const data = await response.json().catch(() => ({}));
  if (!response.ok) throw new Error(data.error || `Request failed (${response.status})`);
  return data;
}

function Icon({ name }) {
  const paths = {
    mark: <><path d="M4 17 12 3l8 14"/><path d="M7 12h10M9 17l3-5 3 5"/></>,
    server: <><rect x="3" y="4" width="18" height="7" rx="1"/><rect x="3" y="13" width="18" height="7" rx="1"/><path d="M7 7h.01M7 16h.01M11 7h6M11 16h6"/></>,
    users: <><path d="M16 21v-2a4 4 0 0 0-4-4H6a4 4 0 0 0-4 4v2"/><circle cx="9" cy="7" r="4"/><path d="M22 21v-2a4 4 0 0 0-3-3.87M16 3.13a4 4 0 0 1 0 7.75"/></>,
    calendar: <><rect x="3" y="5" width="18" height="16" rx="2"/><path d="M16 3v4M8 3v4M3 11h18"/></>,
    activity: <><path d="M3 12h4l3-8 4 16 3-8h4"/></>,
    arrow: <><path d="M5 12h14M13 6l6 6-6 6"/></>,
    plus: <><path d="M12 5v14M5 12h14"/></>,
    shield: <><path d="M12 22s8-4 8-11V5l-8-3-8 3v6c0 7 8 11 8 11Z"/><path d="m9 12 2 2 4-4"/></>,
    logout: <><path d="M9 21H5a2 2 0 0 1-2-2V5a2 2 0 0 1 2-2h4"/><path d="m16 17 5-5-5-5M21 12H9"/></>,
    clock: <><circle cx="12" cy="12" r="9"/><path d="M12 7v5l3 2"/></>,
  };
  return <svg aria-hidden="true" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="1.7" strokeLinecap="round" strokeLinejoin="round">{paths[name]}</svg>;
}

function Brand() {
  return <div className="brand"><span className="brand-mark"><Icon name="mark" /></span><span>TEAM ORGANIZER<small>CONTROL ROOM</small></span></div>;
}

function PublicEntry() {
  const [loginUrl, setLoginUrl] = useState("/auth/discord/login");
  useEffect(() => { api("/api/session").then((data) => setLoginUrl(data.login_url)); }, []);
  return <div className="public-shell">
    <header className="topbar"><Brand /><a className="nav-link" href="/privacy">Privacy</a><a className="nav-link" href="/terms">Terms</a></header>
    <main className="entry-grid">
      <section className="entry-copy">
        <div className="eyebrow"><span className="pulse" /> PRIVATE DASHBOARD <span className="eyebrow-rule" /></div>
        <h1>Your teams,<br /><em>in formation.</em></h1>
        <p className="entry-lede">One calm place to keep schedules moving, activities organized, and team settings current.</p>
        <div className="entry-note"><Icon name="shield" /><span>Server details and personal stats stay behind Discord sign-in. You only see servers you own, administer, or captain.</span></div>
        <a className="primary-button login-button" href={loginUrl}>Continue with Discord <Icon name="arrow" /></a>
        <div className="entry-foot">Your data stays with the bot owner. <span>Questions? Contact <strong>j0nesy_</strong> on Discord.</span></div>
      </section>
      <aside className="entry-art" aria-label="Dashboard access overview">
        <div className="art-top"><span>ACCESS STATUS</span><span className="status-indicator">PRIVATE <i /></span></div>
        <div className="art-main"><div className="art-number">01</div><div className="art-caption">A single workspace<br />for every team.</div></div>
        <div className="art-lines"><span /><span /><span /><span /><span /><span /><span /><span /></div>
        <div className="art-bottom"><span>TEAM ORGANIZER</span><span>DISCORD CONNECTED</span></div>
      </aside>
    </main>
    <footer className="site-footer"><span>TEAM ORGANIZER · PRIVATE BY DEFAULT</span><span>TERMS AND PRIVACY APPLY TO WEBSITE USE</span></footer>
  </div>;
}

function Metric({ icon, label, value, note }) {
  return <div className="metric"><div className="metric-top"><span>{label}</span><Icon name={icon} /></div><strong>{value ?? "—"}</strong><small>{note}</small></div>;
}

function Dashboard() {
  const [auth, setAuth] = useState(null);
  const [data, setData] = useState(null);
  const [admin, setAdmin] = useState(null);
  const [selected, setSelected] = useState("");
  const [page, setPage] = useState("overview");
  const [serverTab, setServerTab] = useState("teams");
  const [serverQuery, setServerQuery] = useState("");
  const [guild, setGuild] = useState(null);
  const [actions, setActions] = useState([]);
  const [busy, setBusy] = useState(false);
  const [message, setMessage] = useState("");
  const [teamChoice, setTeamChoice] = useState("");

  async function loadWorkspace() {
    const [dashboard, history] = await Promise.all([api("/api/dashboard"), api("/api/actions")]);
    setData(dashboard);
    setActions(history.actions);
    setSelected((current) => current || dashboard.guilds[0]?.id || "");
  }

  async function loadAdmin() {
    if (!auth?.owner) return;
    setAdmin(await api("/api/admin"));
  }

  useEffect(() => {
    api("/api/session").then(async (value) => {
      setAuth(value);
      if (value.authenticated) {
        await loadWorkspace();
        if (value.owner) setAdmin(await api("/api/admin"));
      }
    }).catch((error) => setMessage(error.message));
  }, []);

  useEffect(() => {
    if (!selected || !auth?.authenticated) return;
    api(`/api/guilds/${selected}`).then((value) => {
      setGuild(value);
      setTeamChoice((current) => current || value.teams[0]?.team_name || "");
    }).catch((error) => setMessage(error.message));
  }, [selected, auth]);

  useEffect(() => {
    if (!auth?.authenticated) return undefined;
    const timer = window.setInterval(() => {
      const guildRequest = selected ? api(`/api/guilds/${selected}`) : Promise.resolve(null);
      const adminRequest = auth.owner ? api("/api/admin") : Promise.resolve(null);
      Promise.all([api("/api/actions"), api("/api/dashboard"), guildRequest, adminRequest]).then(([history, dashboard, guildData, adminData]) => {
        setActions(history.actions);
        setData(dashboard);
        if (guildData) setGuild(guildData);
        if (adminData) setAdmin(adminData);
      }).catch(() => {});
    }, 10000);
    return () => window.clearInterval(timer);
  }, [auth, selected]);

  async function submit(type, payload, guildId = selected) {
    setBusy(true);
    setMessage("");
    try {
      await api("/api/actions", {
        method: "POST",
        headers: { "Content-Type": "application/json", "X-CSRF-Token": auth.csrf_token },
        body: JSON.stringify({ type, guild_id: guildId, payload }),
      });
      setMessage("Added to the bot queue. This view will update when it is processed.");
      await loadWorkspace();
      await loadAdmin();
    } catch (error) {
      setMessage(error.message);
    } finally {
      setBusy(false);
    }
  }

  async function logout() {
    await api("/auth/logout", { method: "POST", headers: { "X-CSRF-Token": auth.csrf_token } });
    window.location.reload();
  }

  if (!auth) return <div className="loading-state"><Brand /><span>Connecting your workspace…</span></div>;
  if (!auth.authenticated || !data) return <PublicEntry />;

  const activeGuild = data.guilds.find((item) => item.id === selected);
  const selectedTeam = guild?.teams.find((item) => item.team_name === teamChoice);
  const visibleActions = actions.filter((action) => action.guild_id === selected);
  const filteredGuilds = data.guilds.filter((item) => item.name.toLocaleLowerCase().includes(serverQuery.trim().toLocaleLowerCase()));
  const trackedUsers = data.is_owner ? data.metrics.tracked_users : null;
  const openServer = (guildId) => {
    setSelected(guildId);
    setGuild(null);
    setTeamChoice("");
    setServerTab("teams");
    setPage("server");
  };
  const pageTitle = page === "bot-admin" ? "Bot administration" : page === "server" ? activeGuild?.name || "Server workspace" : "Overview";

  return <div className="app-shell">
    <aside className="sidebar">
      <Brand />
      <div className="side-label">DASHBOARD</div>
      <button className={`side-nav ${page === "overview" ? "active" : ""}`} aria-current={page === "overview" ? "page" : undefined} onClick={() => setPage("overview")}><Icon name="activity" /><span>Overview</span></button>
      {auth.owner && <button className={`side-nav ${page === "bot-admin" ? "active" : ""}`} aria-current={page === "bot-admin" ? "page" : undefined} onClick={() => setPage("bot-admin")}><Icon name="shield" /><span>Bot admin</span></button>}
      <div className="side-label server-list-label">YOUR SERVERS <span>{data.guilds.length}</span></div>
      {data.guilds.length > 5 && <input className="server-search" type="search" aria-label="Filter servers" placeholder="Filter servers" value={serverQuery} onChange={(event) => setServerQuery(event.target.value)} />}
      <nav className="server-list" aria-label="Your servers">
        {data.guilds.length ? filteredGuilds.map((item) => <button key={item.id} className={`server-nav ${page === "server" && selected === item.id ? "active" : ""}`} aria-current={page === "server" && selected === item.id ? "page" : undefined} onClick={() => openServer(item.id)} title={item.name}>
          <span className="server-initial">{item.name.slice(0, 1).toUpperCase()}</span><span className="server-nav-name">{item.name}</span><span className="server-role-dot" title={item.can_manage ? "Server administrator" : "Team captain"} />
        </button>) : <p className="server-list-empty">No managed servers</p>}
        {data.guilds.length > 0 && !filteredGuilds.length && <p className="server-list-empty">No matching servers</p>}
      </nav>
      <div className="side-footer"><div className="user-avatar">{(auth.user.global_name || auth.user.username || "D").slice(0, 1).toUpperCase()}</div><div className="user-id"><strong>{auth.user.global_name || auth.user.username}</strong><small>DISCORD ACCOUNT</small></div><button title="Sign out" className="icon-button" onClick={logout}><Icon name="logout" /></button></div>
    </aside>
    <main className="main-area">
      <header className="workspace-header"><div><span className="crumb">CONTROL ROOM <i>/</i> {page === "server" ? activeGuild?.name || "SERVER" : page === "bot-admin" ? "OWNER CONTROLS" : "YOUR WORKSPACE"}</span><h1>{pageTitle}</h1></div><div className="header-meta"><span className={data.bot_online ? "online-dot" : "offline-dot"} />BOT {data.bot_online ? "ONLINE" : "OFFLINE"} <span className="version">v{data.version}</span></div></header>
      <div className="content-wrap">
        {message && <div className="notice" role="status"><span>{message}</span><button onClick={() => setMessage("")} aria-label="Dismiss">×</button></div>}
        {page === "bot-admin" && data.is_owner && <OwnerAdminPanel admin={admin} busy={busy} submit={submit} />}
        {page === "overview" && <>
        <section className="metrics-grid" aria-label="Dashboard statistics">
          <Metric icon="server" label={data.is_owner ? "BOT SERVERS" : "YOUR SERVERS"} value={data.metrics.server_count} note={data.is_owner ? "Across the bot network" : "You can administer or captain"} />
          <Metric icon="users" label={data.is_owner ? "TRACKED USERS" : "YOUR TEAMS"} value={data.is_owner ? (trackedUsers ?? "—") : data.metrics.team_count} note={data.is_owner ? "Private owner-only stat" : "Within your managed servers"} />
          <Metric icon="clock" label="UPTIME" value={data.uptime_started_at ? elapsed(data.uptime_started_at) : "Offline"} note="Since the bot last started" />
          <Metric icon="activity" label="LATEST RELEASE" value={`v${data.version}`} note="Current bot version" />
        </section>
        <section className="overview-lower"><div><div className="eyebrow">SERVER WORKSPACES <span className="eyebrow-rule" /></div><h2>Pick up where your teams work</h2><p>Choose a server from the left to manage its teams, schedules, activities, and settings.</p></div><div className="overview-server-count">{data.guilds.length.toString().padStart(2, "0")}<small>AVAILABLE SERVERS</small></div></section>
        <section className="overview-feed">
          <div className="release-note"><div className="release-icon"><Icon name="activity" /></div><div><span className="panel-kicker">LATEST UPDATE</span><p>{data.recent_update}</p></div><span className="release-version">v{data.version}</span></div>
          <section className="queue-section"><div className="panel-heading"><div><span className="panel-kicker">YOUR BOT ACTIONS</span><h3>Recent activity</h3></div><span className="queue-live"><i /> AUTO-REFRESH</span></div>{actions.length ? <div className="queue-list">{actions.slice(0, 6).map((item) => <div className="queue-row" key={item.action_id}><span className={`queue-state ${item.status}`}>{item.status}</span><strong>{actionLabel(item.action_type)}</strong><span className="queue-result">{item.result || "Waiting for the bot to process this action."}</span><time>{relativeTime(item.created_at)}</time></div>)}</div> : <p className="queue-empty">Queued actions from your accessible servers will appear here.</p>}</section>
        </section>
        </>}
        {page === "server" && (!activeGuild ? <section className="empty-state"><Icon name="server" /><h2>Choose a server</h2><p>Your authorized servers are listed in the left navigation.</p></section> : <>
          <div className="server-workspace-tabs" role="tablist" aria-label="Server workspace sections">
            <button className={serverTab === "teams" ? "active" : ""} aria-selected={serverTab === "teams"} role="tab" onClick={() => setServerTab("teams")}><Icon name="users" />Teams &amp; activities</button>
            {activeGuild.can_manage && <button className={serverTab === "settings" ? "active" : ""} aria-selected={serverTab === "settings"} role="tab" onClick={() => setServerTab("settings")}><Icon name="shield" />Server setup</button>}
          </div>
          {serverTab === "teams" && <>
          <section className="section-heading"><div><div className="eyebrow">TEAM OPERATIONS <span className="eyebrow-rule" /></div><h2>Teams &amp; activities</h2></div><span className="team-count">{guild?.teams.length || 0} VISIBLE TEAMS</span></section>
          {!guild ? <div className="loading-line">Loading server configuration…</div> : <div className="operations-layout">
            <section className="teams-panel">
              <div className="panel-heading"><div><span className="panel-kicker">CONFIGURATION</span><h3>Teams in {guild.name}</h3></div><span className="panel-count">{guild.teams.length.toString().padStart(2, "0")}</span></div>
              {guild.teams.length ? <div className="team-list">{guild.teams.map((team, index) => <article className="team-row" key={team.team_name}>
                <div className="team-index">{String(index + 1).padStart(2, "0")}</div><div className="team-info"><h4>{team.team_name}</h4><div className="team-meta"><span>{gameName(data.games, team.game_id)}</span><span>{team.timezone}</span><span className={team.scrim_requests_enabled ? "enabled" : "disabled"}>{team.scrim_requests_enabled ? "SCRIMS OPEN" : "SCRIMS PAUSED"}</span></div></div>
                <div className="team-actions"><button title="Send weekly schedule" disabled={busy} onClick={() => submit("schedule.send", { team_name: team.team_name })}><Icon name="calendar" /></button><button title="Create activity" disabled={busy} onClick={() => { setTeamChoice(team.team_name); document.getElementById("activity-name")?.focus(); }}><Icon name="plus" /></button>{(team.can_manage || team.is_captain) && <button title="Edit team settings" onClick={() => setTeamChoice(team.team_name)} className={teamChoice === team.team_name ? "selected-tool" : ""}><Icon name="users" /></button>}</div>
              </article>)}</div> : <div className="empty-inline">No teams are configured for this server yet.</div>}
              {guild.can_manage && <details className="create-team"><summary><Icon name="plus" /> Create a team <span>SERVER OWNER / ADMIN</span></summary><form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); submit("team.create", Object.fromEntries(form)); event.currentTarget.reset(); }}>
                <label>Team name<input name="team_name" required minLength="2" maxLength="50" placeholder="e.g. Northstar" /></label>
                <label>Game<select name="game_id" required defaultValue=""><option value="" disabled>Select a game</option>{data.games.map((game) => <option value={game.id} key={game.id}>{game.name}</option>)}</select></label>
                <label>Captain user ID<input name="team_captain_id" required inputMode="numeric" placeholder="Discord user ID" /></label>
                <label>Team role<select name="team_role_id" required defaultValue=""><option value="" disabled>Select a role</option>{guild.roles.map((role) => <option value={role.id} key={role.id}>{role.name}</option>)}</select></label>
                <label>Schedule channel<select name="team_schedule_channel" required defaultValue=""><option value="" disabled>Select a text channel</option>{guild.channels.map((channel) => <option value={channel.id} key={channel.id}>{channel.name}</option>)}</select></label>
                <label>Request channel<select name="team_request_channel" required defaultValue=""><option value="" disabled>Select a text channel</option>{guild.channels.map((channel) => <option value={channel.id} key={channel.id}>{channel.name}</option>)}</select></label>
                <label>Timezone<select name="timezone" defaultValue="UTC">{data.timezones.map((timezone) => <option key={timezone}>{timezone}</option>)}</select></label>
                <button className="small-submit" disabled={busy}>Add to queue <Icon name="arrow" /></button>
              </form></details>}
              {selectedTeam && <TeamSettings key={selectedTeam.team_name} team={selectedTeam} data={data} guild={guild} busy={busy} submit={submit} />}
            </section>
            <aside className="action-column">
              {selectedTeam && <section className="form-panel"><div className="panel-heading"><div><span className="panel-kicker">TEAM CAPTAIN</span><h3>New activity</h3></div><Icon name="calendar" /></div><form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); submit("event.create", { team_name: selectedTeam.team_name, event_name: form.get("event_name"), date: form.get("date"), time: form.get("time") }); }}>
                <label>Team<select value={teamChoice} onChange={(event) => setTeamChoice(event.target.value)}>{guild.teams.map((team) => <option value={team.team_name} key={team.team_name}>{team.team_name}</option>)}</select></label>
                <label>Activity name<input id="activity-name" name="event_name" required maxLength="100" placeholder="Scrim, practice, review…" /></label>
                <div className="form-split"><label>Date<input type="date" name="date" required /></label><label>Time<input type="time" name="time" required /></label></div>
                <button className="primary-button form-submit" disabled={busy}>Queue activity <Icon name="arrow" /></button>
              </form><p className="form-footnote">Posted to the team's configured schedule channel.</p></section>}
              {selectedTeam && <section className="form-panel settings-panel"><div className="panel-heading"><div><span className="panel-kicker">TEAM PREFERENCES</span><h3>{selectedTeam.team_name}</h3></div><Icon name="users" /></div><form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const fields = { region_id: form.get("region_id"), scrim_requests_enabled: form.get("scrim_requests_enabled") === "on" }; if (form.get("game_id")) fields.game_id = form.get("game_id"); submit("team.update", { team_name: selectedTeam.team_name, fields }); }}>
                {!selectedTeam.game_id && <label>Assign a game<select name="game_id" defaultValue=""><option value="">Leave unassigned</option>{data.games.map((game) => <option value={game.id} key={game.id}>{game.name}</option>)}</select></label>}
                <label>Scrim region<select name="region_id" defaultValue={selectedTeam.region_id}><option value="">Not set</option>{data.regions.map((region) => <option value={region.id} key={region.id}>{region.name}</option>)}</select></label>
                <label className="toggle-label"><span>Accept match requests</span><input type="checkbox" name="scrim_requests_enabled" defaultChecked={selectedTeam.scrim_requests_enabled} /></label>
                <button className="secondary-button" disabled={busy}>Save team preferences</button>
              </form></section>}
            </aside>
          </div>}
          </>}
          {serverTab === "settings" && <>{!guild ? <div className="loading-line">Loading server configuration…</div> : <>
            <section className="section-heading"><div><div className="eyebrow">SERVER ADMINISTRATION <span className="eyebrow-rule" /></div><h2>Setup &amp; access</h2></div><span className="team-count">{guild.setup_complete ? "SETUP COMPLETE" : "SETUP REQUIRED"}</span></section>
            <ServerSettings guild={guild} busy={busy} submit={submit} />
          </>}</>}
          <section className="queue-section"><div className="panel-heading"><div><span className="panel-kicker">LIVE BOT BRIDGE</span><h3>Recent actions</h3></div><span className="queue-live"><i /> REFRESHES AUTOMATICALLY</span></div>
            {visibleActions.length ? <div className="queue-list">{visibleActions.map((item) => <div className="queue-row" key={item.action_id}><span className={`queue-state ${item.status}`}>{item.status}</span><strong>{actionLabel(item.action_type)}</strong><span className="queue-result">{item.result || "Waiting for the bot to process this action."}</span><time>{relativeTime(item.created_at)}</time></div>)}</div> : <p className="queue-empty">Actions you submit will appear here with their processing status.</p>}
          </section>
        </>)}
        {page === "bot-admin" && data.is_owner && <section className="owner-queue-section"><div className="panel-heading"><div><span className="panel-kicker">OWNER ACTIONS</span><h3>Bot administration history</h3></div><span className="queue-live"><i /> REFRESHES AUTOMATICALLY</span></div>{actions.length ? <div className="queue-list">{actions.map((item) => <div className="queue-row" key={item.action_id}><span className={`queue-state ${item.status}`}>{item.status}</span><strong>{actionLabel(item.action_type)}</strong><span className="queue-result">{item.result || "Waiting for the bot to process this action."}</span><time>{relativeTime(item.created_at)}</time></div>)}</div> : <p className="queue-empty">Bot-wide owner actions will appear here.</p>}</section>}
      </div>
      <footer className="workspace-footer"><span>PRIVATE DASHBOARD · ACCESS RESTRICTED BY DISCORD MEMBERSHIP</span><span><a href="/terms">Terms</a><a href="/privacy">Privacy</a><span>Contact j0nesy_ on Discord</span></span></footer>
    </main>
  </div>;
}

function OwnerAdminPanel({ admin, busy, submit }) {
  if (!admin) return <section className="owner-admin"><div className="panel-heading"><div><span className="panel-kicker">BOT OWNER</span><h3>Administration</h3></div><span className="loading-line">Loading controls…</span></div></section>;
  const queueOwner = (type, payload = {}) => submit(type, payload, "0");
  return <section className="owner-admin">
    <div className="panel-heading owner-heading"><div><span className="panel-kicker">BOT OWNER CONTROL</span><h3>Administration</h3></div><span className="owner-chip"><Icon name="shield" /> OWNER ONLY</span></div>
    <div className="admin-grid">
      <section className="admin-module"><div className="module-title"><div><span className="panel-kicker">RELEASE</span><h4>Version &amp; update broadcast</h4></div></div>
        <form className="admin-form" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); queueOwner("owner.version_set", { version: form.get("version") }); }}>
          <label>Bot version<input name="version" required maxLength="30" defaultValue={admin.version} /></label><button className="small-submit" disabled={busy}>Queue version <Icon name="arrow" /></button>
        </form>
        <form className="admin-form broadcast-form" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); if (window.confirm("Broadcast this update to every configured update channel?")) queueOwner("owner.update_broadcast", { text: form.get("text") }); }}>
          <label>Update message<textarea name="text" required maxLength="1800" defaultValue={admin.update_text} rows="3" /></label><button className="small-submit" disabled={busy}>Save &amp; broadcast <Icon name="arrow" /></button>
        </form>
      </section>
      <section className="admin-module"><div className="module-title"><div><span className="panel-kicker">PRESENCE</span><h4>Rotating bot statuses</h4></div><button className="icon-button" title="Refresh bot status" disabled={busy} onClick={() => queueOwner("owner.status_refresh")}><Icon name="activity" /></button></div>
        <form className="admin-form status-add-form" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); queueOwner("owner.status_add", { text: form.get("text") }); event.currentTarget.reset(); }}><label>Add status template<input name="text" required maxLength="100" placeholder="Helping {total_teams} teams" /></label><button className="small-submit" disabled={busy}>Add status <Icon name="plus" /></button></form>
        <div className="status-admin-list">{admin.statuses.map((status) => <div className="status-admin-row" key={`${status.source}-${status.text}`}><span className={`status-toggle-dot ${status.enabled ? "active" : ""}`} /><span className="status-source">{status.source}</span><span className="status-admin-text">{status.text}</span><button className={status.enabled ? "disable-status" : "enable-status"} disabled={busy} title={status.enabled ? "Disable status" : "Enable status"} onClick={() => queueOwner(status.enabled ? "owner.status_remove" : "owner.status_enable", { text: status.text })}>{status.enabled ? "Disable" : "Enable"}</button></div>)}</div>
      </section>
      <section className="admin-module command-module"><div className="module-title"><div><span className="panel-kicker">COMMANDS</span><h4>Bot command registry</h4></div></div><p>Sync slash commands to Discord or rebuild the help command cache.</p><div className="admin-button-row"><button className="secondary-button" disabled={busy} onClick={() => queueOwner("owner.sync_commands")}>Sync commands</button><button className="secondary-button" disabled={busy} onClick={() => queueOwner("owner.refresh_help_docs")}>Refresh help docs</button></div></section>
      <section className="admin-module server-admin-module"><div className="module-title"><div><span className="panel-kicker">BOT SERVERS</span><h4>Server access &amp; restrictions</h4></div><span className="panel-count">{admin.servers.length}</span></div>
        <div className="owner-server-list">{admin.servers.map((server) => <article className="owner-server-row" key={server.id}>
          <div className="owner-server-heading"><span className="server-initial">{server.name.slice(0, 1).toUpperCase()}</span><div><h5>{server.name}</h5><small>{server.id}</small></div><span className={`server-setup-badge ${server.setup_complete ? "complete" : "incomplete"}`}>{server.setup_complete ? "READY" : "SETUP NEEDED"}</span></div>
          <div className="server-facts"><span>{server.member_count} members</span><span>{server.team_count} teams</span><span>{server.team_creation_blacklisted ? "Team creation disabled" : "Team creation enabled"}</span><span className="owner-team-names">{server.team_names.length ? `Teams: ${server.team_names.join(", ")}` : "No teams configured"}</span></div>
          <div className="admin-button-row"><button className="secondary-button" disabled={busy} onClick={() => queueOwner("owner.server_blacklist", { target_guild_id: server.id, blacklisted: !server.team_creation_blacklisted })}>{server.team_creation_blacklisted ? "Allow team creation" : "Disable team creation"}</button><button className="danger-button" disabled={busy} onClick={() => { const confirmation = window.prompt(`Type server ID ${server.id} to ban this server and make the bot leave.`); if (confirmation === server.id) queueOwner("owner.server_ban", { target_guild_id: server.id, confirm_id: confirmation }); }}>Ban &amp; leave</button></div>
        </article>)}</div>
        {!!admin.banned_server_ids.length && <div className="banned-servers"><span className="panel-kicker">BANNED SERVER IDS</span><p>{admin.banned_server_ids.join(" · ")}</p></div>}
      </section>
    </div>
  </section>;
}

function ServerSettings({ guild, busy, submit }) {
  function readSettings(form) {
    return {
      bot_channels: [...form.querySelector('[name="bot_channels"]').selectedOptions].map((option) => option.value),
      admin_roles: [...form.querySelector('[name="admin_roles"]').selectedOptions].map((option) => option.value),
      update_logs_channel: form.querySelector('[name="update_logs_channel"]').value,
      bot_logs_channel: form.querySelector('[name="bot_logs_channel"]').value,
    };
  }
  return <section className="server-settings">
    <form onSubmit={(event) => { event.preventDefault(); submit("server.settings_update", { fields: readSettings(event.currentTarget) }); }}>
      <label>Allowed bot command channels<select name="bot_channels" multiple size="4" defaultValue={guild.settings.bot_channels}>{guild.channels.map((channel) => <option key={channel.id} value={channel.id}>{channel.name}</option>)}</select><small>Select all channels where regular members may use bot commands.</small></label>
      <label>Administrator roles<select name="admin_roles" multiple size="4" defaultValue={guild.settings.admin_roles}>{guild.roles.map((role) => <option key={role.id} value={role.id}>{role.name}</option>)}</select><small>These roles can use server-admin bot controls.</small></label>
      <label>Update log channel<select name="update_logs_channel" defaultValue={guild.settings.update_logs_channel}><option value="">Not configured</option>{guild.channels.map((channel) => <option key={channel.id} value={channel.id}>{channel.name}</option>)}</select></label>
      <label>Bot log channel<select name="bot_logs_channel" defaultValue={guild.settings.bot_logs_channel}><option value="">Not configured</option>{guild.channels.map((channel) => <option key={channel.id} value={channel.id}>{channel.name}</option>)}</select></label>
      <button className="small-submit" disabled={busy}>Save server settings <Icon name="arrow" /></button>
      {!guild.setup_complete && <button className="secondary-button" type="button" disabled={busy} onClick={(event) => { if (window.confirm("Save these settings and complete setup? The bot requires at least one command channel, admin role, update-log channel, and bot-log channel.")) submit("server.settings_update", { fields: { ...readSettings(event.currentTarget.form), SetupComplete: true } }); }}>Save settings &amp; complete setup</button>}
    </form>
    {guild.can_moderate_suggestions && <div className="suggestion-admin"><div className="module-title"><div><span className="panel-kicker">GAME SUGGESTIONS</span><h4>Suggestion access</h4></div></div><form className="suggestion-block-form" onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); submit("suggestion.blacklist", { target_user_id: form.get("target_user_id") }); event.currentTarget.reset(); }}><label>Block user by Discord ID<input name="target_user_id" inputMode="numeric" pattern="[0-9]+" required placeholder="Discord user ID" /></label><button className="small-submit" disabled={busy}>Block suggestions</button></form><div className="suggestion-block-list">{guild.blacklisted_suggesters.map((userId) => <div key={userId}><span>{userId}</span><button disabled={busy} onClick={() => submit("suggestion.unblacklist", { target_user_id: userId })}>Restore access</button></div>)}{!guild.blacklisted_suggesters.length && <p>No users are currently blocked from suggestions.</p>}</div></div>}
  </section>;
}

function TeamSettings({ team, data, guild, busy, submit }) {
  if (!team.can_manage) return null;
  return <details className="edit-team"><summary>Edit owner settings <span>SERVER ADMIN</span></summary><form onSubmit={(event) => { event.preventDefault(); const form = new FormData(event.currentTarget); const fields = Object.fromEntries(form); if (!fields.team_name) delete fields.team_name; submit("team.update", { team_name: team.team_name, fields }); }}>
    <label>Team name<input name="team_name" defaultValue={team.team_name} required minLength="2" maxLength="50" /></label>
    <label>Game<select name="game_id" defaultValue={team.game_id}>{team.game_id && !data.games.some((game) => game.id === team.game_id) && <option value={team.game_id}>Current game ({team.game_id})</option>}{data.games.map((game) => <option value={game.id} key={game.id}>{game.name}</option>)}</select></label>
    <label>Captain user ID<input name="team_captain_id" defaultValue={team.team_captain_id} inputMode="numeric" required /></label>
    <label>Team role<select name="team_role_id" defaultValue={team.team_role_id} required>{guild.roles.map((role) => <option value={role.id} key={role.id}>{role.name}</option>)}</select></label>
    <label>Schedule channel<select name="team_schedule_channel" defaultValue={team.team_schedule_channel} required>{guild.channels.map((channel) => <option value={channel.id} key={channel.id}>{channel.name}</option>)}</select></label>
    <label>Request channel<select name="team_request_channel" defaultValue={team.team_request_channel} required>{guild.channels.map((channel) => <option value={channel.id} key={channel.id}>{channel.name}</option>)}</select></label>
    <label>Timezone<select name="timezone" defaultValue={team.timezone}>{data.timezones.map((timezone) => <option key={timezone}>{timezone}</option>)}</select></label>
    <button className="small-submit" disabled={busy}>Queue settings <Icon name="arrow" /></button>
  </form><button className="delete-team" disabled={busy} onClick={() => { if (window.confirm(`Delete ${team.team_name}? This cannot be undone.`)) submit("team.delete", { team_name: team.team_name }); }}>Delete team</button></details>;
}

function gameName(games, id) { return games.find((game) => game.id === id)?.name || id || "Game not set"; }
function actionLabel(type) { return ({ "team.create": "Team created", "team.update": "Team settings updated", "team.delete": "Team deleted", "schedule.send": "Schedule sent", "event.create": "Activity created", "server.settings_update": "Server settings updated", "owner.version_set": "Version updated", "owner.update_broadcast": "Update broadcast", "owner.status_add": "Status added", "owner.status_remove": "Status disabled", "owner.status_enable": "Status enabled", "owner.status_refresh": "Bot status refreshed", "owner.sync_commands": "Slash commands synced", "owner.refresh_help_docs": "Help docs refreshed", "owner.server_blacklist": "Team creation policy changed", "owner.server_ban": "Server banned" })[type] || type; }
function relativeTime(value) { const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000)); return seconds < 60 ? "just now" : seconds < 3600 ? `${Math.floor(seconds / 60)}m ago` : seconds < 86400 ? `${Math.floor(seconds / 3600)}h ago` : `${Math.floor(seconds / 86400)}d ago`; }
function elapsed(value) { const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000)); const days = Math.floor(seconds / 86400); const hours = Math.floor((seconds % 86400) / 3600); const minutes = Math.floor((seconds % 3600) / 60); return days ? `${days}d ${hours}h` : `${hours}h ${minutes}m`; }

createRoot(document.getElementById("react-root")).render(<Dashboard />);