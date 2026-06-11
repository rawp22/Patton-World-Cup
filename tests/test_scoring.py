from app.scoring import calculate_scores


def test_group_dark_horse_points_stack():
    matches = [
        {
            "match_id": "M1",
            "stage": "group",
            "date": "2026-06-11",
            "team_a": "Haiti",
            "team_b": "Brazil",
            "result": "A_WIN",
        }
    ]
    users = [
        {
            "user_id": "u1",
            "display_name": "User",
            "champion": "Brazil",
            "dark_horse": "Haiti",
        }
    ]
    predictions = [{"user_id": "u1", "match_id": "M1", "prediction": "A_WIN"}]

    result = calculate_scores(matches, predictions, users, [], {})

    total = result["leaderboard"][0]
    assert total["group_points"] == 1
    assert total["dark_horse_points"] == 4
    assert total["total_points"] == 5


def test_knockout_and_dark_horse_points_stack():
    matches = [
        {
            "match_id": "M1",
            "stage": "QF",
            "date": "2026-07-01",
            "team_a": "Japan",
            "team_b": "Spain",
            "result": "A_WIN",
        }
    ]
    users = [
        {
            "user_id": "u1",
            "display_name": "User",
            "champion": "Brazil",
            "dark_horse": "Japan",
        }
    ]
    predictions = [{"user_id": "u1", "match_id": "M1", "prediction": "A_WIN"}]

    result = calculate_scores(matches, predictions, users, [], {})

    total = result["leaderboard"][0]
    assert total["knockout_points"] == 8
    assert total["dark_horse_points"] == 5
    assert total["total_points"] == 13


def test_champion_bonus_requires_final_winner():
    matches = [
        {
            "match_id": "R32",
            "stage": "R32",
            "date": "2026-06-28",
            "team_a": "Brazil",
            "team_b": "Japan",
            "result": "A_WIN",
        },
        {
            "match_id": "F",
            "stage": "F",
            "date": "2026-07-19",
            "team_a": "Brazil",
            "team_b": "France",
            "result": "A_WIN",
        },
    ]
    users = [
        {
            "user_id": "u1",
            "display_name": "User",
            "champion": "Brazil",
            "dark_horse": "Japan",
        }
    ]
    predictions = [
        {"user_id": "u1", "match_id": "R32", "prediction": "B_WIN"},
        {"user_id": "u1", "match_id": "F", "prediction": "B_WIN"},
    ]

    result = calculate_scores(matches, predictions, users, [], {})

    assert result["leaderboard"][0]["champion_points"] == 4


def test_leaderboard_ties_share_rank_and_skip_next_rank():
    matches = [
        {
            "match_id": "M1",
            "stage": "group",
            "date": "2026-06-11",
            "team_a": "A",
            "team_b": "B",
            "result": "A_WIN",
        }
    ]
    users = [
        {"user_id": "u1", "display_name": "Ava", "champion": "A", "dark_horse": "B"},
        {"user_id": "u2", "display_name": "Bea", "champion": "A", "dark_horse": "B"},
        {"user_id": "u3", "display_name": "Cam", "champion": "A", "dark_horse": "B"},
    ]
    predictions = [
        {"user_id": "u1", "match_id": "M1", "prediction": "A_WIN"},
        {"user_id": "u2", "match_id": "M1", "prediction": "A_WIN"},
        {"user_id": "u3", "match_id": "M1", "prediction": "B_WIN"},
    ]

    result = calculate_scores(matches, predictions, users, [], {})

    assert [row["rank"] for row in result["leaderboard"]] == [1, 1, 3]
