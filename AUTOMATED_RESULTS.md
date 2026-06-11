# Automated Results Setup

This project can fetch final scores automatically through API-Football and GitHub Actions.

## One-time setup

1. Create an API-Football account: https://dashboard.api-football.com/register
2. Copy your API key from the API-Football dashboard.
3. In GitHub, open `rawp22/Patton-World-Cup`.
4. Go to Settings > Secrets and variables > Actions.
5. Click New repository secret.
6. Name: `API_FOOTBALL_KEY`
7. Secret: paste the API-Football key.
8. Save.

## How it works

The GitHub Action runs every 5 minutes during the tournament window, but the script only calls API-Football for match dates that have unfinished matches at least two hours past kickoff.

When a final score is found, it updates `data/matches.json`, regenerates `site/index.html`, commits the change, and Netlify redeploys the same family URL.

## Optional settings

The workflow assumes API-Football league id `1` and season `2026`. If API-Football uses a different league id for the 2026 World Cup, update `API_FOOTBALL_LEAGUE_ID` in `.github/workflows/fetch-results.yml`.
