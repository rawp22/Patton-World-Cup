from __future__ import annotations

from collections import defaultdict
from html import escape
from pathlib import Path
from typing import Any

from app.data_store import load_all
from app.scoring import calculate_scores


ROOT = Path(__file__).resolve().parent.parent
OUTPUT_PATH = ROOT / "outputs" / "initial-dashboard.html"


def render_dashboard() -> str:
    data = load_all()
    result = calculate_scores(**data)
    matches_by_date: dict[str, list[dict[str, Any]]] = defaultdict(list)
    for match in sorted(data["matches"], key=lambda item: (item["date"], item["match_id"])):
        matches_by_date[match["date"]].append(match)

    leaderboard_rows = "\n".join(_leaderboard_row(row) for row in result["leaderboard"])
    match_sections = "\n".join(
        _date_section(date, matches, result["match_impacts"]) for date, matches in matches_by_date.items()
    )

    html = f"""<!doctype html>
<html lang="en">
<head>
  <meta charset="utf-8">
  <meta name="viewport" content="width=device-width, initial-scale=1">
  <title>World Cup Fantasy Dashboard</title>
  <link rel="stylesheet" href="../static/styles.css">
</head>
<body>
  <header class="topbar">
    <div>
      <p class="eyebrow">Deterministic scoring MVP</p>
      <h1>World Cup Fantasy Dashboard</h1>
    </div>
    <div class="hash">Input hash<br><code>{escape(result["input_hash"][:16])}</code></div>
  </header>

  <main>
    <section class="panel leaderboard-panel">
      <div class="section-heading">
        <h2>Leaderboard</h2>
        <span>{len(result["leaderboard"])} participants</span>
      </div>
      <div class="table-wrap">
        <table>
          <thead>
            <tr>
              <th>Rank</th>
              <th>User</th>
              <th>Group</th>
              <th>Knockout</th>
              <th>Champion</th>
              <th>Dark Horse</th>
              <th>3rd</th>
              <th>Total</th>
            </tr>
          </thead>
          <tbody>
            {leaderboard_rows}
          </tbody>
        </table>
      </div>
    </section>

    <section class="matches">
      <div class="section-heading">
        <h2>Matches</h2>
        <span>Click a match to inspect scenario impact</span>
      </div>
      {match_sections}
    </section>
  </main>
</body>
</html>
"""
    return html


def write_dashboard(path: Path = OUTPUT_PATH) -> Path:
    path.parent.mkdir(parents=True, exist_ok=True)
    path.write_text(render_dashboard(), encoding="utf-8")
    return path


def _leaderboard_row(row: dict[str, Any]) -> str:
    return f"""<tr>
  <td>{row["rank"]}</td>
  <td><strong>{escape(row["display_name"])}</strong><br><small>{escape(row.get("group", ""))}</small></td>
  <td>{row["group_points"]}</td>
  <td>{row["knockout_points"]}</td>
  <td>{row["champion_points"]}</td>
  <td>{row["dark_horse_points"]}</td>
  <td>{row["third_place_points"]}</td>
  <td class="total">{row["total_points"]}</td>
</tr>"""


def _date_section(
    date: str, matches: list[dict[str, Any]], impacts: dict[str, list[dict[str, Any]]]
) -> str:
    cards = "\n".join(_match_card(match, impacts[match["match_id"]]) for match in matches)
    return f"""<section class="date-group">
  <h3>{escape(date)}</h3>
  <div class="match-grid">
    {cards}
  </div>
</section>"""


def _match_card(match: dict[str, Any], impacts: list[dict[str, Any]]) -> str:
    score = ""
    if match.get("goals_a") is not None and match.get("goals_b") is not None:
        score = f"<span>{match['goals_a']} - {match['goals_b']}</span>"
    result = match.get("result") or "Not played"
    scenarios = defaultdict(list)
    for row in impacts:
        scenarios[row["scenario"]].append(row)
    scenario_blocks = "\n".join(_scenario_block(name, rows) for name, rows in scenarios.items())
    return f"""<details class="match-card">
  <summary>
    <span class="stage">{escape(match["stage"])}</span>
    <span class="teams">{escape(match["team_a"])} vs {escape(match["team_b"])}</span>
    <span class="result">{escape(result)} {score}</span>
  </summary>
  <div class="impact">
    {scenario_blocks}
  </div>
</details>"""


def _scenario_block(name: str, rows: list[dict[str, Any]]) -> str:
    visible_name = {
        "A_WIN": "Team A wins",
        "B_WIN": "Team B wins",
        "DRAW": "Draw",
    }[name]
    body = "\n".join(
        f"""<tr>
  <td>{escape(row["display_name"])}</td>
  <td>{row["group_points"]}</td>
  <td>{row["knockout_points"]}</td>
  <td>{row["champion_points"]}</td>
  <td>{row["dark_horse_points"]}</td>
  <td>{row["third_place_points"]}</td>
  <td class="total">{row["total_points"]}</td>
  <td>{escape(row["explanation"])}</td>
</tr>"""
        for row in sorted(rows, key=lambda item: item["display_name"].lower())
    )
    return f"""<div class="scenario">
  <h4>{visible_name}</h4>
  <div class="table-wrap">
    <table class="impact-table">
      <thead>
        <tr>
          <th>User</th>
          <th>Group</th>
          <th>KO</th>
          <th>Champ</th>
          <th>Dark</th>
          <th>3rd</th>
          <th>Total</th>
          <th>Why</th>
        </tr>
      </thead>
      <tbody>{body}</tbody>
    </table>
  </div>
</div>"""


if __name__ == "__main__":
    path = write_dashboard()
    print(path)
