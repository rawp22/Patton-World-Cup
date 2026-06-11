# Automated Results Setup

This project fetches final scores automatically through GitHub Actions. The primary source is ESPN's public FIFA World Cup scoreboard. API-Football remains available as a fallback if a paid API key is configured, but it is not required for the normal workflow.

## How it works

The GitHub Action runs every 5 minutes during the tournament window, but the script only checks match dates that have unfinished matches at least two hours past kickoff.

When a final score is found, it updates `data/matches.json`, regenerates `site/index.html`, commits the change, and Netlify redeploys the same family URL.

## Optional API-Football fallback

API-Football free plans do not include 2026 season access. If you later subscribe to a paid API-Football plan, you can keep a repository secret named `API_FOOTBALL_KEY`; the fetcher will use it only as a fallback when ESPN does not match a result.
