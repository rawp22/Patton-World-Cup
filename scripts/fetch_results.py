from __future__ import annotations

from collections import defaultdict
from datetime import datetime, timedelta
import json
import os
from pathlib import Path
import sys
import unicodedata
from urllib.parse import urlencode
from urllib.request import Request, urlopen

ROOT = Path(__file__).resolve().parent.parent
MATCHES_PATH = ROOT / "data" / "matches.json"
API_BASE = "https://v3.football.api-sports.io/fixtures"
ESPN_API_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"
LEAGUE_ID = os.environ.get("API_FOOTBALL_LEAGUE_ID", "1")
SEASON = os.environ.get("API_FOOTBALL_SEASON", "2026")
FINAL_STATUSES = {"FT", "AET", "PEN"}
EASTERN_OFFSET = "-04:00"

ALIASES = {
    "Bosnia and Herzegovina": ["Bosnia-Herzegovina", "Bosnia & Herzegovina"],
    "Curacao": ["Curaçao"],
    "DR Congo": ["Congo DR", "Congo D.R.", "Democratic Republic of the Congo"],
    "England": ["England"],
    "Ivory Coast": ["Côte d'Ivoire", "Cote d'Ivoire", "Côte dIvoire"],
    "Iran": ["IR Iran", "Iran"],
    "South Korea": ["Korea Republic", "Korea Rep.", "Republic of Korea"],
    "Turkiye": ["Türkiye", "Turkey"],
    "United States": ["USA", "United States of America", "USMNT"],
    "Cape Verde": ["Cabo Verde"],
}


def normalize(value: str) -> str:
    folded = unicodedata.normalize("NFKD", value or "").encode("ascii", "ignore").decode("ascii")
    return "".join(ch for ch in folded.lower() if ch.isalnum())


def team_keys(team: str) -> set[str]:
    values = {team, *ALIASES.get(team, [])}
    return {normalize(value) for value in values}


def kickoff_dt(match: dict) -> datetime:
    hour, minute = match["kickoff_et"].split()[0].split(":")
    return datetime.fromisoformat(f"{match['date']}T{hour}:{minute}:00{EASTERN_OFFSET}")


def now_dt() -> datetime:
    override = os.environ.get("SCORE_FETCH_NOW")
    if override:
        return datetime.fromisoformat(override.replace("Z", "+00:00"))
    return datetime.now().astimezone()


def get_json(url: str, api_key: str = "") -> dict:
    headers = {"x-apisports-key": api_key} if api_key else {}
    request = Request(url, headers=headers)
    with urlopen(request, timeout=20) as response:
        return json.loads(response.read().decode("utf-8"))


def espn_fixture_result_for_match(match: dict, events: list[dict]) -> tuple[str, int, int] | None:
    team_a_keys = team_keys(match["team_a"])
    team_b_keys = team_keys(match["team_b"])
    for event in events:
        competition = (event.get("competitions") or [{}])[0]
        status = competition.get("status") or event.get("status") or {}
        status_type = status.get("type", {})
        if not (status_type.get("completed") or status_type.get("state") == "post"):
            continue

        competitors = competition.get("competitors", [])
        if len(competitors) < 2:
            continue
        home = next((team for team in competitors if team.get("homeAway") == "home"), competitors[0])
        away = next((team for team in competitors if team.get("homeAway") == "away"), competitors[1])

        def names(competitor: dict) -> set[str]:
            team = competitor.get("team", {})
            values = {
                team.get("displayName", ""),
                team.get("name", ""),
                team.get("shortDisplayName", ""),
                team.get("abbreviation", ""),
                competitor.get("displayName", ""),
            }
            return {normalize(value) for value in values if value}

        home_keys = names(home)
        away_keys = names(away)
        direct = bool(home_keys & team_a_keys) and bool(away_keys & team_b_keys)
        reversed_order = bool(home_keys & team_b_keys) and bool(away_keys & team_a_keys)
        if not (direct or reversed_order):
            continue

        try:
            home_goals = int(home.get("score"))
            away_goals = int(away.get("score"))
        except (TypeError, ValueError):
            return None

        if home_goals == away_goals:
            result_home_away = "DRAW"
        elif home_goals > away_goals:
            result_home_away = "HOME_WIN"
        else:
            result_home_away = "AWAY_WIN"

        if direct:
            result = {"HOME_WIN": "A_WIN", "AWAY_WIN": "B_WIN", "DRAW": "DRAW"}[result_home_away]
            return result, home_goals, away_goals
        result = {"HOME_WIN": "B_WIN", "AWAY_WIN": "A_WIN", "DRAW": "DRAW"}[result_home_away]
        return result, away_goals, home_goals
    return None


def fixture_result_for_match(match: dict, fixtures: list[dict]) -> tuple[str, int, int] | None:
    team_a_keys = team_keys(match["team_a"])
    team_b_keys = team_keys(match["team_b"])
    for fixture in fixtures:
        teams = fixture.get("teams", {})
        home = teams.get("home", {})
        away = teams.get("away", {})
        home_key = normalize(home.get("name", ""))
        away_key = normalize(away.get("name", ""))
        direct = home_key in team_a_keys and away_key in team_b_keys
        reversed_order = home_key in team_b_keys and away_key in team_a_keys
        if not (direct or reversed_order):
            continue

        status = fixture.get("fixture", {}).get("status", {}).get("short")
        if status not in FINAL_STATUSES:
            return None

        goals = fixture.get("goals", {})
        home_goals = goals.get("home")
        away_goals = goals.get("away")
        if home_goals is None or away_goals is None:
            return None

        home_winner = home.get("winner")
        away_winner = away.get("winner")
        if home_winner is True:
            result_home_away = "HOME_WIN"
        elif away_winner is True:
            result_home_away = "AWAY_WIN"
        elif home_goals == away_goals:
            result_home_away = "DRAW"
        elif home_goals > away_goals:
            result_home_away = "HOME_WIN"
        else:
            result_home_away = "AWAY_WIN"

        if direct:
            result = {"HOME_WIN": "A_WIN", "AWAY_WIN": "B_WIN", "DRAW": "DRAW"}[result_home_away]
            return result, int(home_goals), int(away_goals)
        result = {"HOME_WIN": "B_WIN", "AWAY_WIN": "A_WIN", "DRAW": "DRAW"}[result_home_away]
        return result, int(away_goals), int(home_goals)
    return None


def pending_dates(matches: list[dict], now: datetime) -> dict[str, list[dict]]:
    grouped: dict[str, list[dict]] = defaultdict(list)
    for match in matches:
        if match.get("result") or not match.get("kickoff_et"):
            continue
        if now >= kickoff_dt(match) + timedelta(hours=2):
            grouped[match["date"]].append(match)
    return grouped


def fetch_fixtures(date: str, api_key: str) -> list[dict]:
    query = urlencode({"league": LEAGUE_ID, "season": SEASON, "date": date})
    payload = get_json(f"{API_BASE}?{query}", api_key)
    errors = payload.get("errors")
    if errors:
        print(f"API-Football returned errors for {date}: {errors}", file=sys.stderr)
    return payload.get("response", [])


def fetch_espn_events(date: str) -> list[dict]:
    query = urlencode({"dates": date.replace("-", "")})
    payload = get_json(f"{ESPN_API_BASE}?{query}", api_key="")
    return payload.get("events", [])


def update_results() -> int:
    api_key = os.environ.get("API_FOOTBALL_KEY")
    matches = json.loads(MATCHES_PATH.read_text(encoding="utf-8"))
    now = now_dt()
    dates = pending_dates(matches, now)
    if not dates:
        print("No pending matches are old enough to check.")
        return 0

    updated = 0
    for date, date_matches in sorted(dates.items()):
        espn_events = fetch_espn_events(date)
        fixtures = []
        if api_key:
            try:
                fixtures = fetch_fixtures(date, api_key)
            except Exception as exc:  # noqa: BLE001
                print(f"API-Football fetch failed for {date}: {exc}", file=sys.stderr)
        print(
            f"Checked {date}: {len(espn_events)} ESPN events and {len(fixtures)} API-Football fixtures "
            f"for {len(date_matches)} pending matches."
        )
        for match in date_matches:
            result = espn_fixture_result_for_match(match, espn_events)
            source = "ESPN"
            if not result and fixtures:
                result = fixture_result_for_match(match, fixtures)
                source = "API-Football"
            if not result:
                continue
            outcome, goals_a, goals_b = result
            match["result"] = outcome
            match["goals_a"] = goals_a
            match["goals_b"] = goals_b
            updated += 1
            print(
                f"Updated {match['match_id']} from {source}: "
                f"{match['team_a']} {goals_a}-{goals_b} {match['team_b']} ({outcome})"
            )

    if updated:
        MATCHES_PATH.write_text(json.dumps(matches, indent=2, ensure_ascii=False) + "\n", encoding="utf-8")
    else:
        print("No final scores found yet.")
    return updated


if __name__ == "__main__":
    changed = update_results()
    if changed:
        import subprocess
        subprocess.run([sys.executable, "generate_html_dashboard.py"], cwd=ROOT, check=True)
    print(f"matches_updated={changed}")
