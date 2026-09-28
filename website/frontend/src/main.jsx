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
  const [selected, setSelected] = useState("");
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

  useEffect(() => {
    api("/api/session").then(async (value) => {
      setAuth(value);
      if (value.authenticated) await loadWorkspace();
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
      Promise.all([api("/api/actions"), api("/api/dashboard"), guildRequest]).then(([history, dashboard, guildData]) => {
        setActions(history.actions);
        setData(dashboard);
        if (guildData) setGuild(guildData);
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
  const trackedUsers = data.is_owner ? data.metrics.tracked_users : null;

  return <div className="app-shell">
    <aside className="sidebar">
      <Brand />
      <div className="side-label">WORKSPACE</div>
      <label className="server-picker"><span>SERVER</span><select value={selected} onChange={(event) => { setSelected(event.target.value); setGuild(null); setTeamChoice(""); }} aria-label="Select server">
        {data.guilds.length ? data.guilds.map((item) => <option value={item.id} key={item.id}>{item.name}</option>) : <option value="">No managed servers</option>}
      </select><b>⌄</b></label>
      {activeGuild && <div className="server-access"><span className="access-dot" />{activeGuild.can_manage ? "SERVER ADMIN" : "TEAM CAPTAIN"}</div>}
      <div className="side-label side-label-lower">YOUR VIEW</div>
      <div className="side-nav"><span className="nav-marker" /><Icon name="activity" /><span>Overview</span></div>
      <div className="side-footer"><div className="user-avatar">{(auth.user.global_name || auth.user.username || "D").slice(0, 1).toUpperCase()}</div><div className="user-id"><strong>{auth.user.global_name || auth.user.username}</strong><small>DISCORD ACCOUNT</small></div><button title="Sign out" className="icon-button" onClick={logout}><Icon name="logout" /></button></div>
    </aside>
    <main className="main-area">
      <header className="workspace-header"><div><span className="crumb">CONTROL ROOM <i>/</i> {activeGuild?.name || "YOUR SERVERS"}</span><h1>{activeGuild?.name || "Your dashboard"}</h1></div><div className="header-meta"><span className={data.bot_online ? "online-dot" : "offline-dot"} />BOT {data.bot_online ? "ONLINE" : "OFFLINE"} <span className="version">v{data.version}</span></div></header>
      <div className="content-wrap">
        {message && <div className="notice" role="status"><span>{message}</span><button onClick={() => setMessage("")} aria-label="Dismiss">×</button></div>}
        <section className="metrics-grid" aria-label="Dashboard statistics">
          <Metric icon="server" label={data.is_owner ? "BOT SERVERS" : "YOUR SERVERS"} value={data.metrics.server_count} note={data.is_owner ? "Across the bot network" : "You can administer or captain"} />
          <Metric icon="users" label={data.is_owner ? "TRACKED USERS" : "YOUR TEAMS"} value={data.is_owner ? (trackedUsers ?? "—") : data.metrics.team_count} note={data.is_owner ? "Private owner-only stat" : "Within your managed servers"} />
          <Metric icon="clock" label="UPTIME" value={data.uptime_started_at ? elapsed(data.uptime_started_at) : "Offline"} note="Since the bot last started" />
          <Metric icon="activity" label="LATEST RELEASE" value={`v${data.version}`} note="Current bot version" />
        </section>

        {!activeGuild ? <section className="empty-state"><Icon name="server" /><h2>No managed servers found</h2><p>You need to own or administer a server with the bot, or captain a configured team.</p></section> : <>
          <section className="section-heading"><div><div className="eyebrow">TEAM OPERATIONS <span className="eyebrow-rule" /></div><h2>Teams &amp; activity</h2></div><span className="team-count">{guild?.teams.length || 0} VISIBLE TEAMS</span></section>
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
          <section className="queue-section"><div className="panel-heading"><div><span className="panel-kicker">LIVE BOT BRIDGE</span><h3>Recent actions</h3></div><span className="queue-live"><i /> REFRESHES AUTOMATICALLY</span></div>
            {visibleActions.length ? <div className="queue-list">{visibleActions.map((item) => <div className="queue-row" key={item.action_id}><span className={`queue-state ${item.status}`}>{item.status}</span><strong>{actionLabel(item.action_type)}</strong><span className="queue-result">{item.result || "Waiting for the bot to process this action."}</span><time>{relativeTime(item.created_at)}</time></div>)}</div> : <p className="queue-empty">Actions you submit will appear here with their processing status.</p>}
          </section>
          <section className="release-note"><div className="release-icon"><Icon name="activity" /></div><div><span className="panel-kicker">LATEST UPDATE</span><p>{data.recent_update}</p></div><span className="release-version">v{data.version}</span></section>
        </>}
      </div>
      <footer className="workspace-footer"><span>PRIVATE DASHBOARD · ACCESS RESTRICTED BY DISCORD MEMBERSHIP</span><span><a href="/terms">Terms</a><a href="/privacy">Privacy</a><span>Contact j0nesy_ on Discord</span></span></footer>
    </main>
  </div>;
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
function actionLabel(type) { return ({ "team.create": "Team created", "team.update": "Team settings updated", "team.delete": "Team deleted", "schedule.send": "Schedule sent", "event.create": "Activity created" })[type] || type; }
function relativeTime(value) { const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000)); return seconds < 60 ? "just now" : seconds < 3600 ? `${Math.floor(seconds / 60)}m ago` : seconds < 86400 ? `${Math.floor(seconds / 3600)}h ago` : `${Math.floor(seconds / 86400)}d ago`; }
function elapsed(value) { const seconds = Math.max(0, Math.floor((Date.now() - new Date(value).getTime()) / 1000)); const days = Math.floor(seconds / 86400); const hours = Math.floor((seconds % 86400) / 3600); const minutes = Math.floor((seconds % 3600) / 60); return days ? `${days}d ${hours}h` : `${hours}h ${minutes}m`; }

createRoot(document.getElementById("react-root")).render(<Dashboard />);