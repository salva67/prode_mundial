"""
Sincronización automática de resultados desde la API pública de ESPN.
No requiere API key ni registro.
Endpoint: https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard
"""

import urllib.request
import urllib.error
import json
from datetime import datetime, timedelta, timezone

ESPN_BASE = "https://site.api.espn.com/apis/site/v2/sports/soccer/fifa.world/scoreboard"

# Mapeo nombres ESPN (inglés) → nuestra DB (español)
TEAM_NAME_MAP = {
    "Mexico": "México",
    "South Africa": "Sudáfrica",
    "South Korea": "Corea del Sur",
    "Korea Republic": "Corea del Sur",
    "Czech Republic": "República Checa",
    "Czechia": "República Checa",
    "Canada": "Canadá",
    "Bosnia and Herzegovina": "Bosnia y Herzegovina",
    "Bosnia & Herzegovina": "Bosnia y Herzegovina",
    "Switzerland": "Suiza",
    "Brazil": "Brasil",
    "Morocco": "Marruecos",
    "Haiti": "Haití",
    "Scotland": "Escocia",
    "United States": "Estados Unidos",
    "USA": "Estados Unidos",
    "Turkey": "Turquía",
    "Türkiye": "Turquía",
    "Germany": "Alemania",
    "Curacao": "Curazao",
    "Curaçao": "Curazao",
    "Ivory Coast": "Costa de Marfil",
    "Côte d'Ivoire": "Costa de Marfil",
    "Netherlands": "Países Bajos",
    "Japan": "Japón",
    "Sweden": "Suecia",
    "Tunisia": "Túnez",
    "Belgium": "Bélgica",
    "Iran": "Irán",
    "New Zealand": "Nueva Zelanda",
    "Spain": "España",
    "Cape Verde": "Cabo Verde",
    "Saudi Arabia": "Arabia Saudita",
    "France": "Francia",
    "Norway": "Noruega",
    "Algeria": "Argelia",
    "Jordan": "Jordania",
    "Portugal": "Portugal",
    "DR Congo": "RD Congo",
    "Congo DR": "RD Congo",
    "Democratic Republic of Congo": "RD Congo",
    "Uzbekistan": "Uzbekistán",
    "England": "Inglaterra",
    "Croatia": "Croacia",
    "Panama": "Panamá",
    # Ya iguales en ambos: Argentina, Colombia, Uruguay, Qatar, Paraguay,
    # Australia, Ecuador, Senegal, Iraq, Austria, Ghana, Egypt, Belgium...
}


def normalize(name: str) -> str:
    return TEAM_NAME_MAP.get(name, name)


def fetch_day(date_str: str) -> list:
    """Trae los partidos de un día específico (formato YYYYMMDD)."""
    url = f"{ESPN_BASE}?dates={date_str}&limit=20"
    try:
        req = urllib.request.Request(url, headers={"User-Agent": "Mozilla/5.0"})
        with urllib.request.urlopen(req, timeout=10) as resp:
            data = json.loads(resp.read().decode())
            return data.get("events", [])
    except Exception:
        return []


def parse_finished_matches(events: list) -> list:
    """Extrae partidos terminados de la respuesta de ESPN."""
    results = []
    for event in events:
        try:
            status = event["status"]["type"]
            if not status.get("completed", False):
                continue

            competition = event["competitions"][0]
            competitors = competition["competitors"]

            home = next((c for c in competitors if c.get("homeAway") == "home"), competitors[0])
            away = next((c for c in competitors if c.get("homeAway") == "away"), competitors[1])

            results.append({
                "home_team": normalize(home["team"]["displayName"]),
                "away_team": normalize(away["team"]["displayName"]),
                "home_score": int(float(home.get("score", 0))),
                "away_score": int(float(away.get("score", 0))),
            })
        except (KeyError, ValueError, IndexError):
            continue
    return results


def sync_results(api_key: str, db) -> dict:
    """
    Sincroniza resultados con la base de datos.
    api_key se ignora — ESPN no requiere autenticación.
    Busca resultados de los últimos 10 días + hoy.
    """
    from models import Match, Prediction

    def compute_pts(ph, pa, rh, ra):
        if ph == rh and pa == ra:
            return 3
        def res(h, a): return "L" if h > a else ("V" if h < a else "E")
        return 1 if res(ph, pa) == res(rh, ra) else 0

    # Buscar en los últimos 10 días para no perder ningún partido
    today = datetime.now(timezone.utc)
    all_finished = []
    for days_back in range(0, 11):
        day = today - timedelta(days=days_back)
        date_str = day.strftime("%Y%m%d")
        events = fetch_day(date_str)
        all_finished.extend(parse_finished_matches(events))

    if not all_finished:
        return {"ok": False, "error": "No se pudo conectar a ESPN o no hay partidos terminados aún."}

    updated = 0
    skipped = 0
    not_found = []

    for am in all_finished:
        home_name = am["home_team"]
        away_name = am["away_team"]
        home_goal = am["home_score"]
        away_goal = am["away_score"]

        match = db.query(Match).filter_by(home_team=home_name, away_team=away_name).first()
        if not match:
            # Intentar orden invertido
            match = db.query(Match).filter_by(home_team=away_name, away_team=home_name).first()
            if match:
                home_goal, away_goal = away_goal, home_goal

        if not match:
            not_found.append(f"{home_name} vs {away_name}")
            continue

        if (match.status == "jugado"
                and match.home_score == home_goal
                and match.away_score == away_goal):
            skipped += 1
            continue

        match.home_score = home_goal
        match.away_score = away_goal
        match.status = "jugado"

        for pred in match.predictions:
            pred.points = compute_pts(pred.home_score, pred.away_score, home_goal, away_goal)

        updated += 1

    db.commit()

    return {
        "ok": True,
        "total_api": len(all_finished),
        "updated": updated,
        "skipped": skipped,
        "not_found": not_found,
    }
