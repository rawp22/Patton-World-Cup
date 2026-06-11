from __future__ import annotations

from fastapi import FastAPI, HTTPException
from fastapi.responses import HTMLResponse

from app.data_store import load_all, save_json
from app.render import render_dashboard
from app.scoring import calculate_scores


app = FastAPI(title="World Cup Fantasy Scoring")


@app.get("/", response_class=HTMLResponse)
def dashboard() -> str:
    return render_dashboard()


@app.get("/api/leaderboard")
def leaderboard():
    data = load_all()
    return calculate_scores(**data)["leaderboard"]


@app.get("/api/matches")
def matches():
    return load_all()["matches"]


@app.get("/api/users")
def users():
    return load_all()["users"]


@app.get("/api/match-impact/{match_id}")
def match_impact(match_id: str):
    data = load_all()
    scores = calculate_scores(**data)
    if match_id not in scores["match_impacts"]:
        raise HTTPException(status_code=404, detail="Unknown match_id")
    return scores["match_impacts"][match_id]


@app.post("/api/match-result")
def update_match_result(payload: dict):
    data = load_all()
    for match in data["matches"]:
        if match["match_id"] == payload.get("match_id"):
            match["result"] = payload.get("result")
            match["goals_a"] = payload.get("goals_a")
            match["goals_b"] = payload.get("goals_b")
            save_json("matches.json", data["matches"])
            return {"ok": True, "match": match}
    raise HTTPException(status_code=404, detail="Unknown match_id")


@app.post("/api/recalculate")
def recalculate():
    data = load_all()
    return calculate_scores(**data)
