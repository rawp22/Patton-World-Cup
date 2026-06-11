from __future__ import annotations

from collections import defaultdict
import base64
from copy import deepcopy
from datetime import datetime, time, timedelta
import json
from html import escape
from itertools import product
from pathlib import Path
from typing import Any
from zoneinfo import ZoneInfo

from app.data_store import load_all
from app.scoring import calculate_scores


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "outputs" / "world-cup-fantasy-dashboard.html"
SITE_OUTPUT_PATH = ROOT / "site" / "index.html"

FLAG_CODE = {
    "Algeria": "dz", "Argentina": "ar", "Australia": "au", "Austria": "at",
    "Belgium": "be", "Bosnia and Herzegovina": "ba", "Brazil": "br",
    "Canada": "ca", "Cape Verde": "cv", "Colombia": "co", "Croatia": "hr",
    "Curacao": "cw", "Czechia": "cz", "DR Congo": "cd", "Ecuador": "ec",
    "Egypt": "eg", "England": "gb-eng", "France": "fr", "Germany": "de",
    "Ghana": "gh", "Haiti": "ht", "Iran": "ir", "Iraq": "iq",
    "Ivory Coast": "ci", "Japan": "jp", "Jordan": "jo", "Mexico": "mx",
    "Morocco": "ma", "Netherlands": "nl", "New Zealand": "nz", "Norway": "no",
    "Panama": "pa", "Paraguay": "py", "Portugal": "pt", "Qatar": "qa",
    "Saudi Arabia": "sa", "Scotland": "gb-sct", "Senegal": "sn", "South Africa": "za",
    "South Korea": "kr", "Spain": "es", "Sweden": "se", "Switzerland": "ch",
    "Tunisia": "tn", "Turkiye": "tr", "United States": "us", "Uruguay": "uy",
    "Uzbekistan": "uz",
}

FLAG_BASE_URL = "../static/flags"
ROUND_ORDER = ["Round of 32", "Round of 16", "Quarterfinals", "Semifinals", "Third Place", "Final"]
EASTERN = ZoneInfo("America/New_York")
UTC = ZoneInfo("UTC")


STYLE = """
:root { color-scheme: light; --bg:#f6f1e3; --ink:#231f18; --muted:#776b58; --line:#d8c79d; --panel:#fffdf7; --gold:#d6a735; --gold-dark:#a67614; --gold-soft:#f7e7b5; --gold-pale:#fbf5e6; --cream:#fffaf0; --shadow:rgb(83 61 24 / 10%); }
* { box-sizing:border-box; }
body { margin:0; background:var(--bg); color:var(--ink); font:15px/1.45 system-ui,-apple-system,BlinkMacSystemFont,"Segoe UI",sans-serif; }
.topbar { display:flex; align-items:end; justify-content:space-between; gap:24px; padding:28px clamp(16px,4vw,48px); background:linear-gradient(135deg, #5f4613, #d6a735); color:white; border-bottom:4px solid var(--gold); }
.eyebrow { margin:0 0 4px; color:#fff1c2; font-size:12px; font-weight:800; text-transform:uppercase; }
h1,h2,h3,h4 { margin:0; letter-spacing:0; } h1 { font-size:clamp(28px,5vw,44px); }
main { width:min(1180px, calc(100% - 32px)); margin:24px auto 48px; }
.hash { text-align:right; color:#fff4ce; } .hash code { color:white; }
.tab-radio { position:absolute; opacity:0; pointer-events:none; } .tabs { display:flex; gap:8px; margin:0 0 18px; flex-wrap:wrap; }
.tab-button { display:inline-flex; align-items:center; border:1px solid var(--line); border-radius:8px; background:var(--cream); color:var(--ink); cursor:pointer; font:inherit; font-weight:850; padding:10px 14px; text-decoration:none; -webkit-tap-highlight-color:transparent; touch-action:manipulation; }
.tab-button.active, #tab-matches:checked ~ .tabs label[for="tab-matches"], #tab-standings:checked ~ .tabs label[for="tab-standings"], #tab-knockout:checked ~ .tabs label[for="tab-knockout"] { background:var(--gold-dark); border-color:var(--gold-dark); color:white; box-shadow:inset 0 -3px 0 var(--gold); }
.tab-panel { display:none !important; } .tab-panel.is-active { display:block; } .tab-panel.standings.is-active { display:grid; } #tab-matches:checked ~ #matches-tab { display:block !important; } #tab-standings:checked ~ #standings-tab { display:grid !important; } #tab-knockout:checked ~ #knockout-tab { display:block !important; } #tab-standings:checked ~ #matches-tab, #tab-standings:checked ~ #knockout-tab, #tab-knockout:checked ~ #matches-tab, #tab-knockout:checked ~ #standings-tab, #tab-matches:checked ~ #standings-tab, #tab-matches:checked ~ #knockout-tab { display:none !important; }
.section-heading { display:flex; align-items:baseline; justify-content:space-between; gap:16px; margin:0 0 12px; }
.section-heading span { color:var(--muted); }
.panel,.date-group,.group-card,.round-card,.user-bracket { background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 8px 28px var(--shadow); }
.leaderboard-panel { margin-bottom:24px; overflow:hidden; border-top:4px solid var(--gold); } .leaderboard-panel .section-heading { padding:18px 20px 0; }
.table-wrap { overflow-x:auto; } table { width:100%; border-collapse:collapse; min-width:760px; table-layout:auto; }
.leaderboard-table { min-width:650px; } .leaderboard-table .rank-col { width:58px; } .leaderboard-table .user-col { width:24%; } .leaderboard-table .score-col { width:72px; } .leaderboard-table .ko-col { width:92px; } .leaderboard-table .draws-col { width:82px; }
th,td { padding:11px 12px; border-top:1px solid var(--line); text-align:left; vertical-align:top; }
th { color:var(--muted); font-size:12px; font-weight:900; text-transform:uppercase; } td:not(:nth-child(2)),th:not(:nth-child(2)) { text-align:right; }
small { color:var(--muted); } .total { color:var(--gold-dark); font-weight:950; }
.user-name,.team-name { display:flex; align-items:center; gap:8px; font-weight:850; } .flags { display:inline-flex; align-items:center; gap:4px; min-width:54px; }
.flag-wrap { display:inline-flex; align-items:center; } .flag-icon { width:24px; height:18px; object-fit:cover; border:1px solid var(--line); border-radius:3px; background:#fff; box-shadow:0 1px 2px rgb(83 61 24 / 12%); } .flag-fallback { color:var(--muted); font-size:11px; font-weight:900; }
.key { padding:0 20px 18px; } .key summary { cursor:pointer; color:var(--gold-dark); font-weight:900; width:max-content; }
.key ul { margin:10px 0 0; padding-left:20px; color:var(--muted); }
.spoiler-controls { display:flex; align-items:center; justify-content:space-between; gap:12px; padding:0 20px 16px; flex-wrap:wrap; color:var(--muted); }
.spoiler-controls button, .match-update-button { background:var(--gold-soft); border-color:var(--gold); color:var(--gold-dark); }
.spoiler-note { font-size:13px; font-weight:750; }
.matches,.standings,.knockout { display:grid; gap:16px; }
.toolbar { display:flex; gap:8px; flex-wrap:wrap; margin:0 0 16px; }
button { border:1px solid var(--line); border-radius:8px; background:var(--cream); color:var(--ink); cursor:pointer; font:inherit; font-weight:800; padding:9px 12px; }
button:hover { border-color:var(--gold); color:var(--gold-dark); }
.date-group,.group-card,.round-card { padding:18px; } .date-group h3,.group-card h3,.round-card h3 { margin-bottom:12px; }
.match-grid,.round-grid { display:grid; gap:10px; }
.match-card { border:1px solid var(--line); border-radius:8px; background:#fffaf0; position:relative; } .match-card[open] { border-color:var(--gold); z-index:5000; box-shadow:0 14px 34px rgb(83 61 24 / 18%); } .match-card[open] .impact { background:var(--panel); position:relative; z-index:5001; }
.match-card summary { display:grid; grid-template-columns:104px 1fr auto; gap:12px; align-items:center; padding:14px; cursor:pointer; }
.stage { color:var(--gold-dark); font-weight:950; } .teams { font-weight:850; } .result { color:var(--muted); }
.impact { padding:0 14px 16px; }
.venue { margin:0 0 10px; color:var(--muted); font-weight:750; }
.impact-grid { display:grid; grid-template-columns:1.1fr repeat(var(--scenario-count), 1fr); border:1px solid var(--line); border-radius:8px; overflow:hidden; }
.impact-cell { padding:10px 12px; border-top:1px solid var(--line); border-left:1px solid var(--line); text-align:center; }
.impact-cell.name { border-left:0; text-align:left; font-weight:800; }
.impact-head { background:var(--gold-soft); color:var(--gold-dark); font-weight:950; border-top:0; }
.impact-head:first-child { border-left:0; color:var(--muted); }
.points { font-weight:950; } .scenario-muted { opacity:.34; color:var(--muted); font-weight:650; } .scenario-active { color:var(--gold-dark); font-weight:950; background:#fff7dc; } .impact-head.scenario-active { background:#f1cf6a; } .impact-head.scenario-muted { background:#faf3df; }
.match-card.spoiler-hidden .scenario-muted, .match-card.spoiler-hidden .scenario-active { opacity:1; color:inherit; font-weight:950; background:transparent; }
.match-card.spoiler-hidden .impact-head.scenario-muted, .match-card.spoiler-hidden .impact-head.scenario-active { background:var(--gold-soft); color:var(--gold-dark); }
.result .spoiler-result { display:none; } .match-card.spoiler-hidden .result .live-result { display:none; } .match-card.spoiler-hidden .result .spoiler-result { display:inline; }
.spoiler-action { display:none; margin:0 0 10px; } .match-card.spoiler-hidden .spoiler-action { display:block; }
.conditions { margin-top:14px; padding:12px; border:1px solid var(--line); border-radius:8px; background:#fffdf7; color:var(--muted); }
.conditions strong { color:var(--ink); }
.standings-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(340px,1fr)); gap:16px; }
.standings table { min-width:0; } .standings td:nth-child(2), .standings th:nth-child(2) { text-align:left; }
.bracket-note { margin:0 0 14px; color:var(--muted); }
.round-card h3 span { color:var(--muted); font-size:13px; font-weight:750; }
.bracket-board { background:var(--panel); border:1px solid var(--line); border-radius:8px; box-shadow:0 8px 28px var(--shadow); padding:16px; overflow-x:auto; overflow-y:visible; }
.bracket-layout { display:grid; grid-template-columns:minmax(540px,1fr) minmax(220px,.42fr) minmax(540px,1fr); gap:14px; align-items:start; min-width:1220px; overflow:visible; } .bracket-headers { display:grid; grid-template-columns:minmax(540px,1fr) minmax(220px,.42fr) minmax(540px,1fr); gap:14px; min-width:1220px; margin-bottom:8px; } .bracket-header-half { display:grid; grid-template-columns:repeat(4, minmax(122px,1fr)); gap:10px; } .bracket-header-center { text-align:center; } .bracket-headers span { text-align:center; padding:6px 5px; border-radius:8px; background:var(--gold-soft); color:var(--gold-dark); font-size:12px; font-weight:900; }
.bracket-half { display:grid; grid-template-columns:repeat(4, minmax(122px,1fr)); grid-template-rows:repeat(15, minmax(28px, auto)); column-gap:10px; align-items:start; position:relative; overflow:visible; }
.bracket-slot { position:relative; z-index:1; }
.bracket-slot h4 { display:none; }
.bracket-slot .match-card { position:relative; z-index:1; overflow:visible; }
.bracket-slot .match-card[open] { z-index:9000; background:var(--panel); } .bracket-slot .match-card[open] .impact { position:fixed; top:16vh; left:50%; transform:translateX(-50%); width:min(92vw, 760px); max-height:72vh; overflow:auto; background:var(--panel); border:1px solid var(--gold); border-radius:8px; box-shadow:0 24px 70px rgb(35 31 24 / 35%); padding:14px; z-index:10000; }
.bracket-center { display:block; overflow:visible; position:relative; z-index:0; padding-top:420px; }
.bracket-center h4 { text-align:center; color:var(--gold-dark); margin:0 0 5px; } .bracket-center-slot { position:relative; } .bracket-center-slot.final-slot { margin:0; } .bracket-center-slot.third-slot { margin-top:96px; }
.bracket-center .match-card { position:relative; z-index:0; overflow:visible; }
.bracket-center .match-card[open] { z-index:9000; background:var(--panel); } .bracket-center .match-card[open] .impact { position:fixed; top:16vh; left:50%; transform:translateX(-50%); width:min(92vw, 760px); max-height:72vh; overflow:auto; background:var(--panel); border:1px solid var(--gold); border-radius:8px; box-shadow:0 24px 70px rgb(35 31 24 / 35%); padding:14px; z-index:10000; }
.bracket-center .match-card summary { grid-template-columns:1fr; padding:8px 9px; }
.bracket-half .match-card summary { grid-template-columns:1fr; gap:3px; padding:8px 9px; }
.bracket-half .stage, .bracket-center .stage { font-size:11px; }
.bracket-half .teams, .bracket-center .teams { font-size:12px; }
.bracket-half .result, .bracket-center .result { font-size:11px; }
.bracket-half .impact-grid, .bracket-center .impact-grid { min-width:520px; } .bracket-board .match-card[open] .venue { font-size:14px; }
.bracket-card-highlight { outline:3px solid var(--gold); box-shadow:0 0 0 4px rgb(214 167 53 / 22%); }
.user-brackets { display:grid; gap:12px; margin-top:24px; }
.user-bracket { overflow:hidden; }
.user-bracket summary { display:flex; align-items:center; gap:10px; padding:14px 16px; cursor:pointer; font-weight:900; color:var(--gold-dark); }
.user-bracket-body { padding:0 16px 16px; display:grid; gap:14px; }
.paper-grid { display:grid; grid-template-columns:repeat(auto-fit, minmax(260px,1fr)); gap:12px; }
.paper-group { border:1px solid var(--line); border-radius:8px; background:#fffaf0; padding:12px; }
.paper-group h4 { color:var(--gold-dark); margin-bottom:8px; }
.team-list { display:grid; gap:5px; margin-bottom:10px; }
.pick-list { display:grid; gap:6px; }
.pick-row { display:grid; grid-template-columns:1fr auto; gap:10px; padding:7px 0; border-top:1px solid var(--line); }
.pick { color:var(--gold-dark); font-weight:900; text-align:right; }
@media (max-width:720px) { .topbar { align-items:start; flex-direction:column; } .hash { text-align:left; } .match-card summary { grid-template-columns:1fr; } .result { justify-self:start; } .impact-grid { grid-template-columns:1fr; } .impact-cell { border-left:0; } .pick-row { grid-template-columns:1fr; } .pick { text-align:left; } }
"""


SCRIPT = """
const FEEDERS = {
  K089:['K073','K075'], K090:['K074','K077'], K091:['K076','K078'], K092:['K079','K080'],
  K093:['K083','K084'], K094:['K081','K082'], K095:['K086','K088'], K096:['K085','K087'],
  K097:['K089','K090'], K099:['K091','K092'], K098:['K093','K094'], K100:['K095','K096'],
  K101:['K097','K099'], K102:['K098','K100'], K104:['K101','K102'], K103:['K101','K102']
};
function showTab(tabId) {
  const targetId = tabId || 'matches-tab';
  const radioMap = {'matches-tab':'tab-matches','standings-tab':'tab-standings','knockout-tab':'tab-knockout'};
  const radio = document.getElementById(radioMap[targetId]);
  if (radio) radio.checked = true;
  document.querySelectorAll('.tab-button').forEach(button => {
    const selected = button.dataset.tab === targetId;
    button.classList.toggle('active', selected);
    button.setAttribute('aria-selected', selected ? 'true' : 'false');
  });
  document.querySelectorAll('.tab-panel').forEach(panel => {
    const selected = panel.id === targetId;
    panel.classList.toggle('is-active', selected);
    panel.removeAttribute('hidden');
    panel.style.display = selected ? (panel.classList.contains('standings') ? 'grid' : 'block') : 'none';
  });
}
function clearFeederHighlights() {
  document.querySelectorAll('.bracket-card-highlight').forEach(card => card.classList.remove('bracket-card-highlight'));
}
function highlightFeeders(matchId) {
  clearFeederHighlights();
  (FEEDERS[matchId] || []).forEach(id => {
    const card = document.querySelector(`#knockout-tab .match-card[data-match-id="${id}"]`);
    if (card) card.classList.add('bracket-card-highlight');
  });
}
function collapseOtherKnockoutCards(activeCard) {
  document.querySelectorAll('#knockout-tab .match-card[open]').forEach(card => {
    if (card !== activeCard) card.open = false;
  });
}
function activateTabControl(control, event) {
  if (!control) return false;
  if (event) event.preventDefault();
  showTab(control.dataset.tab);
  if (history && history.replaceState) history.replaceState(null, '', '#' + control.dataset.tab);
  else window.location.hash = control.dataset.tab;
  return true;
}

document.querySelectorAll('.tab-button').forEach(control => {
  control.addEventListener('click', event => activateTabControl(control, event), false);
  control.addEventListener('touchend', event => activateTabControl(control, event), false);
});

document.addEventListener('click', event => {
  const openKnockoutCard = document.querySelector('#knockout-tab .match-card[open]');
  if (openKnockoutCard && !event.target.closest('#knockout-tab .match-card[open]')) {
    openKnockoutCard.open = false;
    clearFeederHighlights();
  }
  const expandButton = event.target.closest('[data-expand-target]');
  if (expandButton) {
    event.preventDefault();
    document.querySelectorAll(expandButton.dataset.expandTarget).forEach(card => card.open = true);
    return;
  }
  const collapseButton = event.target.closest('[data-collapse-target]');
  if (collapseButton) {
    event.preventDefault();
    document.querySelectorAll(collapseButton.dataset.collapseTarget).forEach(card => card.open = false);
    clearFeederHighlights();
    return;
  }
  const matchUpdate = event.target.closest('[data-update-match]');
  if (matchUpdate) {
    event.preventDefault();
    revealMatch(matchUpdate.closest('.match-card'));
    return;
  }
  const leaderboardUpdate = event.target.closest('[data-update-leaderboard]');
  if (leaderboardUpdate) {
    event.preventDefault();
    revealLeaderboard();
    return;
  }
  const summary = event.target.closest('#knockout-tab .match-card summary');
  if (summary) {
    const card = summary.closest('.match-card');
    const wasOpen = card.open;
    collapseOtherKnockoutCards(card);
    window.setTimeout(() => {
      if (!wasOpen && card.open) highlightFeeders(card.dataset.matchId);
      else if (card.open) highlightFeeders(card.dataset.matchId);
      else clearFeederHighlights();
    }, 0);
  }
});

document.addEventListener('touchend', event => {
  const openKnockoutCard = document.querySelector('#knockout-tab .match-card[open]');
  if (openKnockoutCard && !event.target.closest('#knockout-tab .match-card[open]')) {
    openKnockoutCard.open = false;
    clearFeederHighlights();
  }
}, false);

document.addEventListener('toggle', event => {
  if (!event.target.matches('#knockout-tab .match-card')) return;
  if (event.target.open) {
    collapseOtherKnockoutCards(event.target);
    highlightFeeders(event.target.dataset.matchId);
  }
}, true);

function applyMatchSpoilers() {
  const now = Date.now();
  document.querySelectorAll('.match-card[data-result][data-reveal-at]').forEach(card => {
    if (!card.dataset.result) return;
    const storageKey = `matchReveal:${card.dataset.matchId}`;
    const manuallyRevealed = localStorage.getItem(storageKey) === '1';
    const autoRevealed = Date.parse(card.dataset.revealAt) <= now;
    card.classList.toggle('spoiler-hidden', !(manuallyRevealed || autoRevealed));
  });
}
function revealMatch(card) {
  if (!card) return;
  localStorage.setItem(`matchReveal:${card.dataset.matchId}`, '1');
  card.classList.remove('spoiler-hidden');
}
function renderLeaderboardRows(rows) {
  return rows.map(row => `
<tr>
  <td>${row.rank}</td>
  <td>${row.user_html}</td>
  <td class="total">${row.total_points}</td>
  <td>${row.group_points}</td>
  <td>${row.knockout_points}</td>
  <td>${row.dark_horse_points}</td>
  <td>${row.champion_points}</td>
  <td>${row.draws}</td>
</tr>`).join('');
}
function spoilerSafeLeaderboardRows() {
  const data = window.LEADERBOARD_SNAPSHOTS || {snapshots:[{reveal_at:'baseline', rows:[]}], live:[]};
  const now = Date.now();
  let selected = data.snapshots[0] || {rows:[]};
  data.snapshots.forEach(snapshot => {
    if (snapshot.reveal_at !== 'baseline' && Date.parse(snapshot.reveal_at) <= now) selected = snapshot;
  });
  return selected.rows || [];
}
function applyLeaderboardSpoilerMode() {
  const tbody = document.querySelector('.leaderboard-table tbody');
  if (!tbody || !window.LEADERBOARD_SNAPSHOTS) return;
  const revealed = localStorage.getItem('leaderboardReveal') === '1';
  tbody.innerHTML = renderLeaderboardRows(revealed ? window.LEADERBOARD_SNAPSHOTS.live : spoilerSafeLeaderboardRows());
  const button = document.querySelector('[data-update-leaderboard]');
  const note = document.querySelector('[data-leaderboard-note]');
  if (button) button.textContent = revealed ? 'Showing updated leaderboard' : 'Update leaderboard';
  if (button) button.disabled = revealed;
  if (note) note.textContent = revealed ? 'Live results are revealed on this device.' : 'Spoiler-free until noon ET the day after each completed match, unless updated here.';
}
function revealLeaderboard() {
  localStorage.setItem('leaderboardReveal', '1');
  applyLeaderboardSpoilerMode();
}

document.addEventListener('DOMContentLoaded', () => {
  const initial = window.location.hash ? window.location.hash.slice(1) : 'matches-tab';
  showTab(document.getElementById(initial) ? initial : 'matches-tab');
  applyMatchSpoilers();
  applyLeaderboardSpoilerMode();
});
window.addEventListener('hashchange', () => {
  const target = window.location.hash ? window.location.hash.slice(1) : 'matches-tab';
  if (document.getElementById(target)) showTab(target);
});
showTab(window.location.hash ? window.location.hash.slice(1) : 'matches-tab');
"""


def render_standalone_dashboard() -> str:
    data = load_all()
    result = calculate_scores(**data)
    users_by_id = {user["user_id"]: user for user in data["users"]}
    correct_draws = _correct_draw_counts(data["matches"], data["predictions"])
    predictions_by_user_match = {(row["user_id"], row["match_id"]): row["prediction"] for row in data["predictions"]}
    leaderboard_order = [row["user_id"] for row in result["leaderboard"]]
    matches_by_date = defaultdict(list)
    knockout_by_round = defaultdict(list)
    for match in sorted(data["matches"], key=lambda item: (_display_group_date_key(item), _time_sort_key(item), item["match_id"])):
        if match["stage"] == "group":
            matches_by_date[_display_group_date_key(match)].append(match)
        else:
            knockout_by_round[match.get("round_label", match["stage"])].append(match)
    groups = _groups([match for match in data["matches"] if match["stage"] == "group"])

    leaderboard_snapshots = _leaderboard_snapshots(data)
    leaderboard_rows = "\n".join(_leaderboard_json_row_html(row) for row in leaderboard_snapshots["snapshots"][0]["rows"])
    group_matches = [match for match in data["matches"] if match["stage"] == "group"]
    report_match_ids = _final_group_match_ids(group_matches)
    match_sections = "\n".join(_date_section(date, matches, result["match_impacts"], leaderboard_order, report_match_ids) for date, matches in matches_by_date.items())
    standings_sections = "\n".join(_group_card(group, teams, data["matches"]) for group, teams in groups.items())
    user_bracket_sections = _user_group_brackets(leaderboard_order, users_by_id, group_matches, groups, predictions_by_user_match)
    knockout_sections = _knockout_bracket(knockout_by_round, result["match_impacts"], leaderboard_order)

    return f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>Patton World Cup</title>
  <style>{STYLE}</style>
</head>
<body>
  <header class="topbar">
    <div>
      <p class="eyebrow">World Cup 2026 fantasy pool</p>
      <h1>Patton World Cup</h1>
    </div>
    <div class="hash">Input hash<br><code>{escape(result["input_hash"][:16])}</code></div>
  </header>
  <main>
    <input class="tab-radio" type="radio" name="dashboard-tab" id="tab-matches" checked>
    <input class="tab-radio" type="radio" name="dashboard-tab" id="tab-standings">
    <input class="tab-radio" type="radio" name="dashboard-tab" id="tab-knockout">
    <nav class="tabs" aria-label="Dashboard views">
      <label class="tab-button" data-tab="standings-tab" for="tab-standings" role="button" aria-selected="false">Group Standings/Brackets</label>
      <label class="tab-button" data-tab="matches-tab" for="tab-matches" role="button" aria-selected="true">Group Matches</label>
      <label class="tab-button" data-tab="knockout-tab" for="tab-knockout" role="button" aria-selected="false">Knockout</label>
    </nav>
    <section class="panel leaderboard-panel">
      <div class="section-heading"><h2>Leaderboard</h2><span>{len(result["leaderboard"])} participants</span></div>
      <div class="table-wrap">
        <table class="leaderboard-table">
          <colgroup><col class="rank-col"><col class="user-col"><col class="score-col"><col class="score-col"><col class="ko-col"><col class="score-col"><col class="score-col"><col class="draws-col"></colgroup>
          <thead><tr><th>Rank</th><th>User</th><th>Total</th><th>Group</th><th>Knockout</th><th>DHB</th><th>CB</th><th># Draws</th></tr></thead>
          <tbody>{leaderboard_rows}</tbody>
        </table>
      </div>
      <div class="spoiler-controls"><span class="spoiler-note" data-leaderboard-note>Spoiler-free until noon ET the day after each completed match, unless updated here.</span><button type="button" data-update-leaderboard>Update leaderboard</button></div>
      <details class="key">
        <summary>Key</summary>
        <ul>
          <li><strong>Group</strong> = points from group stage</li>
          <li><strong>Knockout</strong> = points from knockout stage</li>
          <li><strong>Dark Horse Bonus</strong> = points from dark horse group stage wins/draws and knockout stage wins</li>
          <li><strong>Champion Bonus</strong> = points from champion winning knockout stage games</li>
          <li><strong># Draws</strong> = number of correctly predicted draws during group stage</li>
        </ul>
      </details>
    </section>
    <section id="matches-tab" class="tab-panel">
      <div class="section-heading"><h2>Group Matches</h2><span>Click a match for outcome points</span></div>
      <div class="toolbar"><button type="button" data-expand-target="#matches-tab .match-card">Expand all</button><button type="button" data-collapse-target="#matches-tab .match-card">Collapse all</button></div>
      <div class="matches">{match_sections}</div>
    </section>
    <section id="standings-tab" class="tab-panel standings">
      <div class="section-heading"><h2>Group Standings/Brackets</h2><span>Updated from entered match results</span></div>
      <div class="standings-grid">{standings_sections}</div>
      <section class="user-brackets"><div class="section-heading"><h2>User Group Brackets</h2><span>Participant picks in leaderboard order</span></div>{user_bracket_sections}</section>
    </section>
    <section id="knockout-tab" class="tab-panel">
      <div class="section-heading"><h2>Knockout</h2><span>Projected slots update after group-stage qualification is known</span></div>
      <p class="bracket-note">Round of 32 slots use FIFA's published position labels. Placeholder teams such as 1A, 2B, or 3C/E/F/H/I will resolve once group standings and best third-place qualifiers are known.</p>
      <div class="toolbar"><button type="button" data-expand-target="#knockout-tab .match-card">Expand all</button><button type="button" data-collapse-target="#knockout-tab .match-card">Collapse all</button></div>
      <div class="knockout">{knockout_sections}</div>
    </section>
  </main>
  <script>window.LEADERBOARD_SNAPSHOTS = {json.dumps(leaderboard_snapshots)};</script>
  <script>{SCRIPT}</script>
</body>
</html>"""


def write_standalone_dashboard(path: Path = OUTPUT_PATH) -> Path:
    html = render_standalone_dashboard()
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(html, encoding="utf-8")
    SITE_OUTPUT_PATH.parent.mkdir(parents=True, exist_ok=True)
    SITE_OUTPUT_PATH.write_text(html, encoding="utf-8")
    return path



def _kickoff_clock(match):
    return (match.get("kickoff_et") or "99:99 ET").split()[0]


def _is_midnight_match(match):
    return _kickoff_clock(match) == "00:00"


def _display_group_date_key(match):
    date = datetime.strptime(match["date"], "%Y-%m-%d").date()
    if _is_midnight_match(match):
        date = date - timedelta(days=1)
    return date.isoformat()


def _time_sort_key(match):
    kickoff = _kickoff_clock(match)
    return "24:00" if kickoff == "00:00" else kickoff


def _match_reveal_at(match):
    date = datetime.strptime(_display_group_date_key(match), "%Y-%m-%d").date()
    reveal = datetime.combine(date + timedelta(days=1), time(12, 0), EASTERN)
    return reveal.astimezone(UTC).isoformat().replace("+00:00", "Z")


def _leaderboard_snapshots(data):
    users_by_id = {user["user_id"]: user for user in data["users"]}
    completed_reveals = sorted({
        _match_reveal_at(match)
        for match in data["matches"]
        if match.get("result")
    })
    snapshots = [{"reveal_at": "baseline", "rows": _leaderboard_snapshot_rows(data, users_by_id, None)}]
    for reveal_at in completed_reveals:
        snapshots.append({"reveal_at": reveal_at, "rows": _leaderboard_snapshot_rows(data, users_by_id, reveal_at)})
    live_result = calculate_scores(**data)
    live_draws = _correct_draw_counts(data["matches"], data["predictions"])
    return {
        "snapshots": snapshots,
        "live": _leaderboard_json_rows(live_result["leaderboard"], users_by_id, live_draws),
    }


def _leaderboard_snapshot_rows(data, users_by_id, reveal_at):
    matches = []
    for match in data["matches"]:
        snapshot_match = deepcopy(match)
        if snapshot_match.get("result") and (reveal_at is None or _match_reveal_at(snapshot_match) > reveal_at):
            snapshot_match["result"] = None
            snapshot_match["goals_a"] = None
            snapshot_match["goals_b"] = None
        matches.append(snapshot_match)
    snapshot_data = dict(data)
    snapshot_data["matches"] = matches
    result = calculate_scores(**snapshot_data)
    draws = _correct_draw_counts(matches, data["predictions"])
    return _leaderboard_json_rows(result["leaderboard"], users_by_id, draws)


def _leaderboard_json_rows(rows, users_by_id, draws):
    output = []
    for row in rows:
        user = users_by_id[row["user_id"]]
        item = {
            "rank": row["rank"],
            "user_html": f'<span class="user-name"><span class="flags">{_flag_pair(user.get("champion"), user.get("dark_horse"))}</span>{escape(row["display_name"])}</span>',
            "total_points": row["total_points"],
            "group_points": row["group_points"],
            "knockout_points": row["knockout_points"],
            "dark_horse_points": row["dark_horse_points"],
            "champion_points": row["champion_points"],
            "draws": draws[row["user_id"]],
        }
        output.append(item)
    return output


def _leaderboard_json_row_html(row):
    return f"""<tr>
  <td>{row["rank"]}</td>
  <td>{row["user_html"]}</td>
  <td class="total">{row["total_points"]}</td>
  <td>{row["group_points"]}</td>
  <td>{row["knockout_points"]}</td>
  <td>{row["dark_horse_points"]}</td>
  <td>{row["champion_points"]}</td>
  <td>{row["draws"]}</td>
</tr>"""


def _leaderboard_row(row, user, draws):
    flags = _flag_pair(user.get("champion"), user.get("dark_horse"))
    return f"""<tr>
  <td>{row["rank"]}</td>
  <td><span class="user-name"><span class="flags">{flags}</span>{escape(row["display_name"])}</span></td>
  <td class="total">{row["total_points"]}</td>
  <td>{row["group_points"]}</td>
  <td>{row["knockout_points"]}</td>
  <td>{row["dark_horse_points"]}</td>
  <td>{row["champion_points"]}</td>
  <td>{draws}</td>
</tr>"""


def _flag_pair(champion, dark_horse):
    return _flag_img(champion, "Champion") + _flag_img(dark_horse, "Dark horse")


def _flag_img(team, label):
    code = FLAG_CODE.get(team or "")
    safe_team = escape(team or "Unknown")
    if not code:
        return f'<span class="flag-fallback" title="{label}: {safe_team}">??</span>'
    safe_code = escape(code)
    fallback = escape(code.upper())
    flag_path = ROOT / "static" / "flags" / f"{safe_code}.svg"
    if flag_path.exists():
        encoded = base64.b64encode(flag_path.read_bytes()).decode("ascii")
        src = f"data:image/svg+xml;base64,{encoded}"
    else:
        src = f"{FLAG_BASE_URL}/{safe_code}.svg"
    return (
        f'<span class="flag-wrap">'
        f"<img class=\"flag-icon\" src=\"{src}\" alt=\"{safe_team}\" title=\"{label}: {safe_team}\" loading=\"lazy\" onerror=\"this.style.display='none';this.nextElementSibling.hidden=false\">"
        f'<span class="flag-fallback" hidden title="{label}: {safe_team}">{fallback}</span>'
        f'</span>'
    )


def _display_date(date):
    year, month, day = date.split("-")
    return f"{int(month)}/{int(day)}"


def _date_section(date, matches, impacts, leaderboard_order, report_match_ids):
    cards = "\n".join(
        _match_card(match, impacts[match["match_id"]], leaderboard_order, show_group_report=match["match_id"] in report_match_ids)
        for match in matches
    )
    return f"""<section class="date-group"><h3>{escape(_display_date(date))}</h3><div class="match-grid">{cards}</div></section>"""


def _knockout_bracket(knockout_by_round, impacts, leaderboard_order):
    def by_ids(round_label, ids):
        matches = {match["match_id"]: match for match in knockout_by_round.get(round_label, [])}
        return [matches[match_id] for match_id in ids if match_id in matches]

    left = [
        ("Round of 32", by_ids("Round of 32", ["K073", "K074", "K075", "K076", "K077", "K078", "K079", "K080"]), [1, 3, 5, 7, 9, 11, 13, 15], 1),
        ("Round of 16", by_ids("Round of 16", ["K089", "K090", "K091", "K092"]), [2, 6, 10, 14], 2),
        ("Quarter-finals", by_ids("Quarterfinals", ["K097", "K099"]), [4, 12], 3),
        ("Semi-finals", by_ids("Semifinals", ["K101"]), [8], 4),
    ]
    right = [
        ("Semi-finals", by_ids("Semifinals", ["K102"]), [8], 1),
        ("Quarter-finals", by_ids("Quarterfinals", ["K098", "K100"]), [4, 12], 2),
        ("Round of 16", by_ids("Round of 16", ["K093", "K094", "K095", "K096"]), [2, 6, 10, 14], 3),
        ("Round of 32", by_ids("Round of 32", ["K081", "K082", "K083", "K084", "K085", "K086", "K087", "K088"]), [1, 3, 5, 7, 9, 11, 13, 15], 4),
    ]
    final_html = "".join(_match_card(match, impacts[match["match_id"]], leaderboard_order) for match in by_ids("Final", ["K104"]))
    third_html = "".join(_match_card(match, impacts[match["match_id"]], leaderboard_order) for match in by_ids("Third Place", ["K103"]))
    left_html = _bracket_half(left, impacts, leaderboard_order, "left")
    right_html = _bracket_half(right, impacts, leaderboard_order, "right")
    return f"""<section class="bracket-board">
  <div class="bracket-headers"><div class="bracket-header-half"><span>Round of 32</span><span>Round of 16</span><span>Quarter-finals</span><span>Semi-finals</span></div><span class="bracket-header-center">Final</span><div class="bracket-header-half"><span>Semi-finals</span><span>Quarter-finals</span><span>Round of 16</span><span>Round of 32</span></div></div>
  <div class="bracket-layout">
    {left_html}
    <div class="bracket-center"><div class="bracket-center-slot final-slot">{final_html}</div><div class="bracket-center-slot third-slot">{third_html}</div></div>
    {right_html}
  </div>
</section>"""


def _bracket_half(columns, impacts, leaderboard_order, side):
    slots = []
    for label, matches, rows, col in columns:
        for index, match in enumerate(matches):
            title = f'<h4>{escape(label)}</h4>' if index == 0 else ''
            card = _match_card(match, impacts[match["match_id"]], leaderboard_order)
            slots.append(f'<div class="bracket-slot" style="grid-column:{col};grid-row:{rows[index]};">{title}{card}</div>')
    return f'<div class="bracket-half {side}">{"".join(slots)}</div>'


def _round_section(label, matches, impacts, leaderboard_order):
    cards = "\n".join(_match_card(match, impacts[match["match_id"]], leaderboard_order) for match in matches)
    points = matches[0].get("round_points")
    point_label = f" · {points} pts for correct winner" if points else ""
    return f"""<section class="round-card"><h3>{escape(label)} <span>{point_label}</span></h3><div class="round-grid">{cards}</div></section>"""


def _match_card(match, impacts, leaderboard_order, show_group_report=False):
    result = match.get("result") or "Not played"
    score = ""
    if match.get("goals_a") is not None and match.get("goals_b") is not None:
        score = f"<span>{match['goals_a']} - {match['goals_b']}</span>"
    result_html = f'<span class="live-result">{escape(result)} {score}</span><span class="spoiler-result">Not played</span>' if match.get("result") else escape(result)
    reveal_at = _match_reveal_at(match) if match.get("result") else ""
    scenarios = _visible_scenarios(match)
    users = _ordered_users(impacts, leaderboard_order)
    by_user_scenario = {(row["user_id"], row["scenario"]): row["total_points"] for row in impacts}
    rows = []
    for user_id, name in users:
        cells = "\n".join(
            f'<div class="impact-cell points {_scenario_class(match, scenario)}">{_fmt_points(by_user_scenario.get((user_id, scenario), 0))}</div>'
            for scenario in scenarios
        )
        rows.append(f"""<div class="impact-cell name">{escape(name)}</div>{cells}""")
    headers = "\n".join(f'<div class="impact-cell impact-head {_scenario_class(match, scenario)}">{escape(_scenario_label(match, scenario))}</div>' for scenario in scenarios)
    condition_report = _match_condition_report(match) if show_group_report else ""
    stage = f"Group {escape(match.get('group', ''))}" if match["stage"] == "group" else escape(match.get("round_label", match["stage"]))
    meta_parts = [match.get("venue", "Venue TBD"), match.get("kickoff_et")]
    venue = f'<p class="venue">{escape(" · ".join(part for part in meta_parts if part))}</p>'
    result_attr = escape(match.get("result") or "")
    reveal_attr = escape(reveal_at)
    update_button = '<div class="spoiler-action"><button type="button" class="match-update-button" data-update-match>Update this match</button></div>' if match.get("result") else ""
    card_class = "match-card spoiler-hidden" if match.get("result") else "match-card"
    return f"""<details class="{card_class}" data-match-id="{escape(match["match_id"])}" data-result="{result_attr}" data-reveal-at="{reveal_attr}">
  <summary><span class="stage">{stage}</span><span class="teams">{escape(match["team_a"])} vs {escape(match["team_b"])}</span><span class="result">{result_html}</span></summary>
  <div class="impact">
    {venue}
    {update_button}
    <div class="impact-grid" style="--scenario-count:{len(scenarios)}">
      <div class="impact-cell impact-head">User</div>
      {headers}
      {''.join(rows)}
    </div>
    {condition_report}
  </div>
</details>"""


def _visible_scenarios(match):
    if match["stage"] == "group":
        return ["A_WIN", "DRAW", "B_WIN"]
    return ["A_WIN", "B_WIN"]


def _scenario_label(match, scenario):
    if scenario == "A_WIN":
        return f"{match['team_a']} wins"
    if scenario == "B_WIN":
        return f"{match['team_b']} wins"
    return "Draw"


def _scenario_class(match, scenario):
    result = match.get("result")
    if not result:
        return ""
    return "scenario-active" if scenario == result else "scenario-muted"


def _ordered_users(impacts, leaderboard_order):
    names = {}
    for row in impacts:
        names[row["user_id"]] = row["display_name"]
    return [(user_id, names[user_id]) for user_id in leaderboard_order if user_id in names]


def _fmt_points(value):
    return f"+{value}" if value > 0 else "0"


def _correct_draw_counts(matches, predictions):
    matches_by_id = {match["match_id"]: match for match in matches}
    counts = defaultdict(int)
    for prediction in predictions:
        match = matches_by_id[prediction["match_id"]]
        if match["stage"] == "group" and match.get("result") == "DRAW" and prediction["prediction"] == "DRAW":
            counts[prediction["user_id"]] += 1
    return counts


def _groups(matches):
    groups = defaultdict(list)
    for match in matches:
        group = match.get("group")
        for team in (match["team_a"], match["team_b"]):
            if team not in groups[group]:
                groups[group].append(team)
    return dict(sorted(groups.items()))


def _final_group_match_ids(group_matches):
    matches_by_group = defaultdict(list)
    for match in group_matches:
        matches_by_group[match.get("group")].append(match)
    report_ids = set()
    for matches in matches_by_group.values():
        final_matches = sorted(matches, key=lambda item: (_display_group_date_key(item), _time_sort_key(item), item["match_id"]))[-2:]
        report_ids.update(match["match_id"] for match in final_matches)
    return report_ids


def _team_label_with_flag(team):
    return f'<span class="team-name">{_flag_img(team, "Team")}<span>{escape(team)}</span></span>'


def _user_group_brackets(leaderboard_order, users_by_id, group_matches, groups, predictions_by_user_match):
    matches_by_group = defaultdict(list)
    for match in sorted(group_matches, key=lambda item: (item.get("group", ""), item["date"], item["match_id"])):
        matches_by_group[match.get("group")].append(match)
    sections = []
    for user_id in leaderboard_order:
        user = users_by_id[user_id]
        groups_html = []
        for group, teams in groups.items():
            team_rows = "".join(f'<span>{_team_label_with_flag(team)}</span>' for team in teams)
            pick_rows = "".join(_user_pick_row(user_id, match, predictions_by_user_match.get((user_id, match["match_id"]))) for match in matches_by_group[group])
            groups_html.append(f'''<section class="paper-group">
  <h4>Group {escape(group)}</h4>
  <div class="team-list">{team_rows}</div>
  <div class="pick-list">{pick_rows}</div>
</section>''')
        sections.append(f'''<details class="user-bracket">
  <summary>{_flag_pair(user.get("champion"), user.get("dark_horse"))}<span>{escape(user["display_name"])}</span></summary>
  <div class="user-bracket-body"><div class="paper-grid">{''.join(groups_html)}</div></div>
</details>''')
    return "".join(sections)


def _user_pick_row(user_id, match, prediction):
    team_a = escape(match["team_a"])
    team_b = escape(match["team_b"])
    if prediction == "A_WIN":
        matchup = f"<strong><u>{team_a}</u></strong> vs {team_b}"
    elif prediction == "B_WIN":
        matchup = f"{team_a} vs <strong><u>{team_b}</u></strong>"
    elif prediction == "DRAW":
        matchup = f"{team_a} vs {team_b} <strong>(D)</strong>"
    else:
        matchup = f"{team_a} vs {team_b}"
    return f'<div class="pick-row"><span>{matchup}</span></div>'


def _prediction_label(match, prediction):
    if prediction == "A_WIN":
        return f"{match['team_a']} wins"
    if prediction == "B_WIN":
        return f"{match['team_b']} wins"
    if prediction == "DRAW":
        return "Draw"
    return "No pick"


def _group_card(group, teams, matches):
    standings = _standings(group, teams, matches)
    rows = "\n".join(
        f"<tr><td>{i}</td><td>{_team_label_with_flag(row['team'])}</td><td>{row['mp']}</td><td>{row['pts']}</td><td>{row['w']}</td><td>{row['d']}</td><td>{row['l']}</td><td>{row['gf']}</td><td>{row['ga']}</td><td>{row['gd']}</td></tr>"
        for i, row in enumerate(standings, start=1)
    )
    report = _group_condition_report(group, teams, matches)
    return f"""<section class="group-card">
  <h3>Group {escape(group)}</h3>
  <div class="table-wrap"><table>
    <thead><tr><th>#</th><th>Team</th><th>MP</th><th>Pts</th><th>W</th><th>D</th><th>L</th><th>GF</th><th>GA</th><th>GD</th></tr></thead>
    <tbody>{rows}</tbody>
  </table></div>
  {report}
</section>"""


def _standings(group, teams, matches):
    table = {team: {"team": team, "mp": 0, "pts": 0, "w": 0, "d": 0, "l": 0, "gf": 0, "ga": 0, "gd": 0} for team in teams}
    for match in matches:
        if match.get("group") != group or not match.get("result"):
            continue
        a, b = match["team_a"], match["team_b"]
        ga, gb = match.get("goals_a") or 0, match.get("goals_b") or 0
        table[a]["mp"] += 1; table[b]["mp"] += 1
        table[a]["gf"] += ga; table[a]["ga"] += gb
        table[b]["gf"] += gb; table[b]["ga"] += ga
        if match["result"] == "A_WIN":
            table[a]["w"] += 1; table[a]["pts"] += 3; table[b]["l"] += 1
        elif match["result"] == "B_WIN":
            table[b]["w"] += 1; table[b]["pts"] += 3; table[a]["l"] += 1
        else:
            table[a]["d"] += 1; table[b]["d"] += 1; table[a]["pts"] += 1; table[b]["pts"] += 1
    for row in table.values():
        row["gd"] = row["gf"] - row["ga"]
    return sorted(table.values(), key=lambda row: (-row["pts"], -row["gd"], -row["gf"], row["team"]))


def _group_condition_report(group, teams, matches):
    standings = _standings(group, teams, matches)
    if not standings or min(row["mp"] for row in standings) < 2:
        return '<div class="conditions"><strong>Scenario report:</strong> available after every team in this group has played two matches.</div>'
    remaining = [match for match in matches if match.get("group") == group and not match.get("result")]
    if not remaining:
        return '<div class="conditions"><strong>Scenario report:</strong> group complete.</div>'
    lines = []
    for team in teams:
        positions = sorted(_possible_positions(team, teams, matches, remaining))
        lines.append(f"{escape(team)} can finish: {', '.join(str(pos) for pos in positions)} based on remaining win/draw/loss scenarios.")
    return '<div class="conditions"><strong>Scenario report:</strong><br>' + '<br>'.join(lines) + '<br><small>Tiebreakers applied: goal difference, goals scored, then head-to-head within this tournament. Outcome-only simulations use 1-0 wins and 0-0 draws, so exact goal margins can still change the report.</small></div>'


def _match_condition_report(match):
    return '<div class="conditions"><strong>Group standing report:</strong> this appears for third group games after every team in the group has played two matches.</div>'


def _possible_positions(team, teams, matches, remaining):
    positions = set()
    outcomes = ["A_WIN", "DRAW", "B_WIN"]
    for combo in product(outcomes, repeat=len(remaining)):
        simulated = [dict(match) for match in matches]
        by_id = {match["match_id"]: match for match in simulated}
        for match, outcome in zip(remaining, combo):
            target = by_id[match["match_id"]]
            target["result"] = outcome
            target["goals_a"] = 1 if outcome == "A_WIN" else 0
            target["goals_b"] = 1 if outcome == "B_WIN" else 0
        table = _standings(remaining[0]["group"], teams, simulated)
        for index, row in enumerate(table, start=1):
            if row["team"] == team:
                positions.add(index)
    return positions


if __name__ == "__main__":
    print(write_standalone_dashboard())
