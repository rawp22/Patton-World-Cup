# World Cup Fantasy Scoring System - Final Software Specification

## 1. System Overview

Build a lightweight web-based fantasy tournament scoring platform for a World Cup prediction pool.

The system stores participant predictions, ingests match results manually, recalculates all scores deterministically from raw inputs, and serves an HTML dashboard with a live leaderboard and match-level scoring impact views.

Core principle:

> The leaderboard is always a pure function of predictions, match data, user metadata, and recorded results.

There must be no hidden score state, no manual score edits, and no incremental scoring drift.

## 2. Core Objective

Any match in the tournament can be clicked to show exactly how each possible result affects every participant's score.

For each match, the system must show:

- If Team A wins, each user's score impact.
- If the match is a draw, each user's score impact when draws are valid.
- If Team B wins, each user's score impact.
- The category-level contribution behind each score.

## 3. MVP Technology Decisions

The MVP should use:

- Backend: Python with FastAPI.
- Database: SQLite.
- Frontend: Server-rendered HTML using Jinja templates.
- Scoring engine: Pure Python deterministic function layer.
- Data import format: CSV or JSON.
- Deployment mode: Local-first admin app, with dashboard pages viewable by participants.

Authentication is not required for MVP. Admin endpoints may be local-only or protected later.

## 4. User Types

### 4.1 Admin

The admin can:

- Load tournament matches.
- Load participant metadata.
- Load participant predictions.
- Enter or edit match results.
- Trigger full score recalculation.
- View the leaderboard.
- View match-level scoring impact.
- Export generated dashboard views.

### 4.2 Participants

Participants submit predictions once before the tournament starts.

Each participant selects:

- Group-stage match predictions.
- Knockout match predictions or bracket-derived knockout winners.
- Tournament champion.
- Dark horse team.

Champion and dark horse selections are fixed once submitted.

## 5. Data Model

### 5.1 Match

```json
{
  "match_id": "string",
  "stage": "group | R32 | R16 | QF | SF | F | 3RD",
  "date": "YYYY-MM-DD",
  "team_a": "string",
  "team_b": "string",
  "result": "A_WIN | B_WIN | DRAW | null",
  "goals_a": 0,
  "goals_b": 0
}
```

Rules:

- `DRAW` is valid for group-stage matches.
- Knockout matches should resolve to `A_WIN` or `B_WIN`.
- For knockout matches, `A_WIN` or `B_WIN` means the team advanced or won the tie, including extra time or penalties.
- Goals are stored for display and audit purposes. They do not affect scoring unless future rules are added.

### 5.2 User Metadata

```json
{
  "user_id": "string",
  "display_name": "string",
  "group": "string",
  "champion": "string",
  "dark_horse": "string"
}
```

Rules:

- `display_name` is shown on dashboards.
- `group` is optional and can be used for family, office, friend group, region, or league subdivision.
- Champion and dark horse may be the same team unless the admin config disallows it.
- If champion and dark horse are the same team, bonuses stack.

### 5.3 User Match Prediction

```json
{
  "user_id": "string",
  "match_id": "string",
  "prediction": "A_WIN | B_WIN | DRAW"
}
```

Rules:

- Group-stage predictions may include `DRAW`.
- Knockout predictions should be `A_WIN` or `B_WIN`.
- If participant input is bracket-based, the import layer should convert bracket choices into match-level predictions.

### 5.4 Optional 3rd Place Prediction

```json
{
  "user_id": "string",
  "third_place_winner": "string",
  "third_place_team_1": "string",
  "third_place_team_2": "string"
}
```

This table is optional but recommended if the 3rd-place scoring rule is enabled.

## 6. Scoring Rules

### 6.1 Group Stage Base Scoring

For each completed group-stage match:

- Correct prediction: `+1`
- Incorrect prediction: `0`

Correct prediction means the participant selected the actual result:

- Team A win.
- Team B win.
- Draw.

### 6.2 Knockout Base Scoring

For each completed knockout match, participants earn base points for correctly predicting the winner or advancing team.

| Stage | Base Points |
|---|---:|
| Round of 32 | 3 |
| Round of 16 | 5 |
| Quarterfinal | 8 |
| Semifinal | 8 |
| Final | 10 |

The 3rd-place match is handled by its own conditional scoring rule and does not use standard knockout base scoring unless explicitly enabled later.

### 6.3 Champion Bonus

If a participant's champion is the actual tournament winner, that participant earns `+2` for each knockout match won by that champion.

Eligible champion wins:

| Stage | Bonus |
|---|---:|
| Round of 32 win | 2 |
| Round of 16 win | 2 |
| Quarterfinal win | 2 |
| Semifinal win | 2 |
| Final win | 2 |

Rules:

- The champion bonus is based on the champion's actual tournament path.
- The user does not need to have correctly predicted each individual champion match to receive this bonus.
- The bonus is only awarded if the selected champion wins the tournament.

### 6.4 Dark Horse Scoring

Each participant selects one dark horse team.

#### Group Stage

For each completed group-stage match involving the participant's dark horse:

- Dark horse wins: `+3`
- Dark horse draws: `+1`
- Additional correct prediction bonus: `+1`

Examples:

- Dark horse wins and user predicted that result: `+4`
- Dark horse wins and user did not predict that result: `+3`
- Dark horse draws and user predicted draw: `+2`
- Dark horse draws and user did not predict draw: `+1`
- Dark horse loses: `0`, unless other base scoring rules apply separately.

#### Knockout Stage

For each completed knockout match won by the participant's dark horse:

- Dark horse win: `+5`

Rules:

- The user does not need to have correctly predicted the knockout match to receive the dark horse knockout bonus.
- Dark horse points stack with knockout base points and champion bonus points where applicable.

### 6.5 3rd Place Conditional Scoring

The 3rd-place rule is enabled only if the tournament includes a 3rd-place match.

A participant is eligible for 3rd-place scoring if either condition is true:

- The participant is in the top 25% of users by number of pre-tournament draw predictions.
- The participant's dark horse is an island nation listed in system configuration.

Default island nation config:

```json
["Haiti", "Curacao", "New Zealand", "Cape Verde"]
```

Eligibility rules:

- Draw prediction counts are calculated from submitted predictions before the tournament starts.
- If multiple users are tied at the top-25% cutoff, all tied users qualify.

Eligible users earn `+8` if either condition is true:

- They correctly predict the winner of the 3rd-place match.
- They correctly predict both teams appearing in the 3rd-place match.

Rules:

- Maximum 3rd-place score per user is `+8`.
- A user who satisfies both scoring conditions still earns `+8`, not `+16`.
- If explicit 3rd-place prediction data is unavailable, this rule should be disabled for MVP rather than inferred ambiguously.

## 7. Score Categories

Each user's total score is composed of category totals:

```json
{
  "user_id": "string",
  "group_points": 0,
  "knockout_points": 0,
  "champion_points": 0,
  "dark_horse_points": 0,
  "third_place_points": 0,
  "total_points": 0
}
```

Rules:

- Categories are additive.
- A single match may contribute to multiple categories.
- `total_points` is the sum of all category totals.

## 8. Scoring Engine Requirements

The scoring engine must:

- Recalculate all user scores from scratch after each result update.
- Produce deterministic output from raw inputs.
- Store full scoring breakdown per user per match.
- Never rely on previous score totals.
- Avoid external dependencies inside the core scoring function.
- Be covered by unit tests for each scoring category.

Recommended scoring function signature:

```python
def calculate_scores(matches, predictions, users, config):
    ...
```

The function should return:

- Leaderboard rows.
- Per-user category totals.
- Per-match scoring breakdowns.
- Match impact simulations for unplayed or clicked matches.

## 9. Match-Level Breakdown

For every completed match and every user, store:

```json
{
  "match_id": "string",
  "user_id": "string",
  "actual_result": "A_WIN | B_WIN | DRAW",
  "predicted_result": "A_WIN | B_WIN | DRAW",
  "group_points": 0,
  "knockout_points": 0,
  "champion_points": 0,
  "dark_horse_points": 0,
  "third_place_points": 0,
  "total_points": 0,
  "explanation": "string"
}
```

The `explanation` field should be concise and human-readable, for example:

```text
Correct quarterfinal winner (+8); dark horse knockout win (+5).
```

## 10. Match Impact View

For each match, the system must simulate possible outcomes and show every user's score impact.

### 10.1 Group Match Impact

Group matches have three possible outcomes:

- Team A wins.
- Draw.
- Team B wins.

### 10.2 Knockout Match Impact

Knockout matches have two possible outcomes:

- Team A wins or advances.
- Team B wins or advances.

`DRAW` should not be displayed as an outcome for knockout impact views.

### 10.3 Impact Row Shape

```json
{
  "match_id": "string",
  "scenario": "A_WIN",
  "user_id": "string",
  "display_name": "string",
  "group_points": 0,
  "knockout_points": 0,
  "champion_points": 0,
  "dark_horse_points": 0,
  "third_place_points": 0,
  "total_points": 0,
  "explanation": "string"
}
```

Impact views should show the marginal points created by that match outcome, not the user's full tournament total.

## 11. Frontend Requirements

### 11.1 Match Dashboard

The match dashboard must:

- Group matches by date.
- Show team names, stage, result, and score if available.
- Use clickable match cards or rows.
- Expand or navigate to the match impact view.
- Clearly distinguish completed and unplayed matches.

### 11.2 Leaderboard Dashboard

The leaderboard must display:

| Rank | User | Group | Knockout | Champion | Dark Horse | 3rd Place | Total |
|---:|---|---:|---:|---:|---:|---:|---:|

Rules:

- Sort by `total_points` descending.
- Tied users should share the same rank.
- The next rank should skip accordingly. Example: `1, 1, 3`.

### 11.3 User Comparison View

Recommended for MVP if time allows.

The comparison view should:

- Compare any two users side by side.
- Show category totals.
- Show match-by-match differences.
- Highlight matches where one user can gain over another.

## 12. Admin Workflow

### 12.1 Before Tournament

Admin loads:

- Match dataset.
- User metadata.
- User predictions.
- Optional 3rd-place prediction data.
- Scoring config.

### 12.2 Daily During Tournament

Admin:

1. Opens admin result entry page.
2. Enters match result:

```json
{
  "match_id": "string",
  "result": "A_WIN",
  "goals_a": 2,
  "goals_b": 1
}
```

3. Saves result.
4. Triggers recalculation.
5. Reviews updated leaderboard and match breakdown.

Admin edits to match results are allowed. Any edit must trigger full recalculation from raw inputs.

## 13. API Endpoints

### 13.1 Public/View Endpoints

```http
GET /
GET /matches
GET /leaderboard
GET /users
GET /match-impact/{match_id}
GET /users/{user_id}
GET /compare?user_a={user_id}&user_b={user_id}
```

### 13.2 Admin/Data Endpoints

```http
POST /admin/import/matches
POST /admin/import/users
POST /admin/import/predictions
POST /admin/match-result
POST /admin/recalculate
```

### 13.3 JSON API Endpoints

```http
GET /api/matches
GET /api/users
GET /api/leaderboard
GET /api/match-impact/{match_id}
POST /api/match-result
POST /api/recalculate
```

The HTML pages may consume these JSON endpoints or render directly from server-side data.

## 14. Database Tables

Recommended SQLite tables:

- `matches`
- `users`
- `predictions`
- `third_place_predictions`
- `results`
- `score_runs`
- `score_totals`
- `score_breakdowns`

### 14.1 `score_runs`

Each recalculation should create a score run record for auditability.

```json
{
  "score_run_id": "string",
  "created_at": "datetime",
  "input_hash": "string"
}
```

The current leaderboard should come from the latest score run.

## 15. Import Formats

MVP must support JSON imports.

CSV import is recommended for admin convenience.

Participant bracket images are out of scope for MVP unless manually transcribed into structured prediction data. Image upload can be added later as an assisted data-entry workflow.

## 16. Testing Requirements

Unit tests must cover:

- Group-stage correct and incorrect predictions.
- Group-stage dark horse win, draw, and loss.
- Knockout base scoring by stage.
- Champion bonus only when champion wins tournament.
- Champion bonus across each knockout round.
- Dark horse knockout win bonus.
- Champion and dark horse stacking.
- 3rd-place eligibility by draw prediction percentile.
- 3rd-place eligibility by configured island nation.
- 3rd-place max score of `+8`.
- Full recalculation after edited results.
- Leaderboard tie ranking.

## 17. Non-Goals for MVP

The MVP does not require:

- Authentication.
- WebSockets.
- Exact-score prediction.
- Payment handling.
- Automated real-world result feeds.
- Image-to-data bracket extraction.
- Mobile-specific native app behavior.

The HTML should still be responsive enough to work on phones, but mobile optimization is not a separate MVP feature.

## 18. Optional Enhancements

Future enhancements may include:

- Authentication and admin login.
- Real-time updates with WebSockets.
- CSV export.
- Historical replay mode.
- Participant-facing prediction submission form.
- Image upload with assisted OCR/transcription.
- Automated match result ingestion.
- Mobile-first dashboard layout.
- League/group filters.
- Scenario simulation across multiple future matches.

## 19. Acceptance Criteria

The MVP is complete when:

- Admin can import matches, users, and predictions.
- Admin can enter or edit match results.
- Admin can trigger full recalculation.
- Leaderboard updates deterministically from raw data.
- Every user's category totals are visible.
- Every completed match has a per-user scoring breakdown.
- Every match has a clickable impact view showing possible outcome effects.
- All scoring rules in this spec are covered by tests.
- Re-running recalculation on unchanged inputs produces identical outputs.

## 20. Build Estimate

Expected MVP effort:

- One engineer: 1-2 weeks.
- AI-assisted implementation: potentially faster.

This is a lightweight fantasy sports analytics platform with deterministic scoring, manual result ingestion, and interactive simulation views.
