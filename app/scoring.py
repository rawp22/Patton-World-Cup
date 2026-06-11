from __future__ import annotations

from collections import defaultdict
from copy import deepcopy
from dataclasses import dataclass
from hashlib import sha256
import json
from math import ceil
from typing import Any


KNOCKOUT_POINTS = {
    "R32": 3,
    "R16": 5,
    "QF": 8,
    "SF": 8,
    "F": 10,
}

KNOCKOUT_STAGES = set(KNOCKOUT_POINTS)
DEFAULT_ISLAND_NATIONS = {"Haiti", "Curacao", "Curaçao", "New Zealand", "Cape Verde"}


@dataclass(frozen=True)
class ScoreConfig:
    island_nations: set[str]
    third_place_enabled: bool = True

    @classmethod
    def from_dict(cls, config: dict[str, Any] | None = None) -> "ScoreConfig":
        config = config or {}
        return cls(
            island_nations=set(config.get("island_nations", DEFAULT_ISLAND_NATIONS)),
            third_place_enabled=config.get("third_place_enabled", True),
        )


def calculate_scores(
    matches: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    users: list[dict[str, Any]],
    third_place_predictions: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    """Calculate all fantasy scores from raw inputs.

    This function intentionally treats all totals as derived data. Callers can
    persist the returned run if they want an audit trail, but they should never
    mutate prior totals.
    """
    score_config = ScoreConfig.from_dict(config)
    predictions_by_user_match = {
        (row["user_id"], row["match_id"]): row["prediction"] for row in predictions
    }
    third_place_by_user = {
        row["user_id"]: row for row in (third_place_predictions or [])
    }
    users_by_id = {user["user_id"]: user for user in users}
    completed_matches = [match for match in matches if match.get("result")]
    tournament_winner = _find_tournament_winner(completed_matches)
    champion_win_counts = _champion_knockout_win_counts(completed_matches)
    eligible_third_place_users = _eligible_third_place_users(
        users, predictions, score_config
    )

    totals = {
        user["user_id"]: {
            "user_id": user["user_id"],
            "display_name": user.get("display_name", user["user_id"]),
            "group": user.get("group", ""),
            "group_points": 0,
            "knockout_points": 0,
            "champion_points": 0,
            "dark_horse_points": 0,
            "third_place_points": 0,
            "total_points": 0,
        }
        for user in users
    }
    breakdowns: list[dict[str, Any]] = []

    for match in sorted(completed_matches, key=lambda item: (item["date"], item["match_id"])):
        for user in users:
            user_id = user["user_id"]
            predicted = predictions_by_user_match.get((user_id, match["match_id"]))
            row = score_match_for_user(
                match=match,
                user=user,
                predicted_result=predicted,
                tournament_winner=tournament_winner,
                champion_win_counts=champion_win_counts,
                third_place_prediction=third_place_by_user.get(user_id),
                third_place_eligible=user_id in eligible_third_place_users,
            )
            breakdowns.append(row)
            _add_points(totals[user_id], row)

    leaderboard = sorted(
        totals.values(),
        key=lambda row: (-row["total_points"], row["display_name"].lower()),
    )
    _assign_ranks(leaderboard)

    return {
        "input_hash": _input_hash(matches, predictions, users, third_place_predictions, config),
        "leaderboard": leaderboard,
        "totals": totals,
        "breakdowns": breakdowns,
        "match_impacts": {
            match["match_id"]: simulate_match_impact(
                match,
                matches,
                predictions,
                users,
                third_place_predictions,
                config,
            )
            for match in matches
        },
    }


def score_match_for_user(
    match: dict[str, Any],
    user: dict[str, Any],
    predicted_result: str | None,
    tournament_winner: str | None,
    champion_win_counts: dict[str, int],
    third_place_prediction: dict[str, Any] | None,
    third_place_eligible: bool,
) -> dict[str, Any]:
    result = match.get("result")
    points = {
        "group_points": 0,
        "knockout_points": 0,
        "champion_points": 0,
        "dark_horse_points": 0,
        "third_place_points": 0,
    }
    explanations: list[str] = []

    if not result:
        return _breakdown_row(match, user, predicted_result, result, points, "Unplayed.")

    if match["stage"] == "group":
        if predicted_result == result:
            points["group_points"] += 1
            explanations.append("Correct group result (+1)")
    elif match["stage"] in KNOCKOUT_POINTS:
        if predicted_result == result:
            amount = KNOCKOUT_POINTS[match["stage"]]
            points["knockout_points"] += amount
            explanations.append(f"Correct {match['stage']} winner (+{amount})")

    winner = _winner_for_match(match)
    dark_horse = user.get("dark_horse")
    if dark_horse and _team_in_match(match, dark_horse):
        if match["stage"] == "group":
            if winner == dark_horse:
                points["dark_horse_points"] += 3
                explanations.append("Dark horse group win (+3)")
            elif result == "DRAW":
                points["dark_horse_points"] += 1
                explanations.append("Dark horse group draw (+1)")
        elif match["stage"] in KNOCKOUT_STAGES and winner == dark_horse:
            points["dark_horse_points"] += 5
            explanations.append("Dark horse knockout win (+5)")

    champion = user.get("champion")
    if (
        champion
        and match["stage"] in KNOCKOUT_STAGES
        and winner == champion
        and predicted_result == result
    ):
        points["champion_points"] += 2
        explanations.append("Champion picked knockout win bonus (+2)")

    if match["stage"] == "3RD" and third_place_eligible:
        if _third_place_prediction_hits(match, third_place_prediction):
            points["third_place_points"] += 8
            explanations.append("Eligible 3rd-place prediction hit (+8)")

    if not explanations:
        explanations.append("No points")

    return _breakdown_row(match, user, predicted_result, result, points, "; ".join(explanations) + ".")


def simulate_match_impact(
    match: dict[str, Any],
    matches: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    users: list[dict[str, Any]],
    third_place_predictions: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> list[dict[str, Any]]:
    scenarios = ["A_WIN", "B_WIN"] if match["stage"] != "group" else ["A_WIN", "DRAW", "B_WIN"]
    rows: list[dict[str, Any]] = []
    matches_by_id = {row["match_id"]: deepcopy(row) for row in matches}

    for scenario in scenarios:
        scenario_matches = list(matches_by_id.values())
        for scenario_match in scenario_matches:
            if scenario_match["match_id"] == match["match_id"]:
                scenario_match["result"] = scenario
        scenario_result = calculate_scores_without_impacts(
            scenario_matches, predictions, users, third_place_predictions, config
        )
        for breakdown in scenario_result["breakdowns"]:
            if breakdown["match_id"] == match["match_id"]:
                row = dict(breakdown)
                row["scenario"] = scenario
                rows.append(row)
    return rows


def calculate_scores_without_impacts(
    matches: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    users: list[dict[str, Any]],
    third_place_predictions: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    result = calculate_scores_core(matches, predictions, users, third_place_predictions, config)
    return result


def calculate_scores_core(
    matches: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    users: list[dict[str, Any]],
    third_place_predictions: list[dict[str, Any]] | None = None,
    config: dict[str, Any] | None = None,
) -> dict[str, Any]:
    score_config = ScoreConfig.from_dict(config)
    predictions_by_user_match = {
        (row["user_id"], row["match_id"]): row["prediction"] for row in predictions
    }
    third_place_by_user = {
        row["user_id"]: row for row in (third_place_predictions or [])
    }
    completed_matches = [match for match in matches if match.get("result")]
    tournament_winner = _find_tournament_winner(completed_matches)
    champion_win_counts = _champion_knockout_win_counts(completed_matches)
    eligible_third_place_users = _eligible_third_place_users(users, predictions, score_config)

    totals = {
        user["user_id"]: {
            "user_id": user["user_id"],
            "display_name": user.get("display_name", user["user_id"]),
            "group": user.get("group", ""),
            "group_points": 0,
            "knockout_points": 0,
            "champion_points": 0,
            "dark_horse_points": 0,
            "third_place_points": 0,
            "total_points": 0,
        }
        for user in users
    }
    breakdowns = []

    for match in sorted(completed_matches, key=lambda item: (item["date"], item["match_id"])):
        for user in users:
            user_id = user["user_id"]
            row = score_match_for_user(
                match,
                user,
                predictions_by_user_match.get((user_id, match["match_id"])),
                tournament_winner,
                champion_win_counts,
                third_place_by_user.get(user_id),
                user_id in eligible_third_place_users,
            )
            breakdowns.append(row)
            _add_points(totals[user_id], row)

    leaderboard = sorted(totals.values(), key=lambda row: (-row["total_points"], row["display_name"].lower()))
    _assign_ranks(leaderboard)
    return {"leaderboard": leaderboard, "totals": totals, "breakdowns": breakdowns}


def _breakdown_row(
    match: dict[str, Any],
    user: dict[str, Any],
    predicted_result: str | None,
    actual_result: str | None,
    points: dict[str, int],
    explanation: str,
) -> dict[str, Any]:
    total = sum(points.values())
    return {
        "match_id": match["match_id"],
        "stage": match["stage"],
        "date": match["date"],
        "team_a": match["team_a"],
        "team_b": match["team_b"],
        "user_id": user["user_id"],
        "display_name": user.get("display_name", user["user_id"]),
        "actual_result": actual_result,
        "predicted_result": predicted_result,
        **points,
        "total_points": total,
        "explanation": explanation,
    }


def _add_points(total_row: dict[str, Any], score_row: dict[str, Any]) -> None:
    for field in (
        "group_points",
        "knockout_points",
        "champion_points",
        "dark_horse_points",
        "third_place_points",
    ):
        total_row[field] += score_row[field]
    total_row["total_points"] += score_row["total_points"]


def _assign_ranks(leaderboard: list[dict[str, Any]]) -> None:
    previous_points = None
    previous_rank = 0
    for index, row in enumerate(leaderboard, start=1):
        if row["total_points"] != previous_points:
            previous_rank = index
        row["rank"] = previous_rank
        previous_points = row["total_points"]


def _winner_for_match(match: dict[str, Any]) -> str | None:
    if match.get("result") == "A_WIN":
        return match["team_a"]
    if match.get("result") == "B_WIN":
        return match["team_b"]
    return None


def _team_in_match(match: dict[str, Any], team: str) -> bool:
    return team in {match["team_a"], match["team_b"]}


def _find_tournament_winner(matches: list[dict[str, Any]]) -> str | None:
    for match in matches:
        if match["stage"] == "F" and match.get("result"):
            return _winner_for_match(match)
    return None


def _champion_knockout_win_counts(matches: list[dict[str, Any]]) -> dict[str, int]:
    counts: dict[str, int] = defaultdict(int)
    for match in matches:
        if match["stage"] in KNOCKOUT_STAGES:
            winner = _winner_for_match(match)
            if winner:
                counts[winner] += 1
    return counts


def _eligible_third_place_users(
    users: list[dict[str, Any]],
    predictions: list[dict[str, Any]],
    config: ScoreConfig,
) -> set[str]:
    if not config.third_place_enabled:
        return set()

    draw_counts: dict[str, int] = defaultdict(int)
    for prediction in predictions:
        if prediction["prediction"] == "DRAW":
            draw_counts[prediction["user_id"]] += 1

    sorted_counts = sorted(draw_counts.values(), reverse=True)
    draw_eligible: set[str] = set()
    if sorted_counts:
        cutoff_index = max(0, ceil(len(users) * 0.25) - 1)
        cutoff = sorted_counts[min(cutoff_index, len(sorted_counts) - 1)]
        draw_eligible = {
            user["user_id"] for user in users if draw_counts[user["user_id"]] >= cutoff
        }

    island_eligible = {
        user["user_id"]
        for user in users
        if user.get("dark_horse") in config.island_nations
    }
    return draw_eligible | island_eligible


def _third_place_prediction_hits(
    match: dict[str, Any], prediction: dict[str, Any] | None
) -> bool:
    if not prediction:
        return False
    winner = _winner_for_match(match)
    predicted_teams = {
        prediction.get("third_place_team_1"),
        prediction.get("third_place_team_2"),
    }
    actual_teams = {match["team_a"], match["team_b"]}
    predicted_winner_hit = prediction.get("third_place_winner") == winner
    predicted_teams_hit = predicted_teams == actual_teams
    return predicted_winner_hit or predicted_teams_hit


def _input_hash(*parts: Any) -> str:
    payload = json.dumps(parts, sort_keys=True, ensure_ascii=True)
    return sha256(payload.encode("utf-8")).hexdigest()
