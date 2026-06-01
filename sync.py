"""
Sincronización automática de resultados desde la API de wc2026api.com
Documentación: https://www.wc2026api.com
"""

import urllib.request
import urllib.error
import json

API_BASE = "https://api.wc2026api.com"

# Mapeo de nombres en inglés (API) → español (nuestra DB)
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
    "Qatar": "Qatar",
    "Switzerland": "Suiza",
    "Brazil": "Brasil",
    "Morocco": "Marruecos",
    "Haiti": "Haití",
    "Scotland": "Escocia",
    "United States": "Estados Unidos",
    "USA": "Estados Unidos",
    "US": "Estados Unidos",
    "Paraguay": "Paraguay",
    "Australia": "Australia",
    "Turkey": "Turquía",
    "Türkiye": "Turquía",
    "Germany": "Alemania",
    "Curacao": "Curazao",
    "Curaçao": "Curazao",
    "Ivory Coast": "Costa de Marfil",
    "Côte d'Ivoire": "Costa de Marfil",
    "Ecuador": "Ecuador",
    "Netherlands": "Países Bajos",
    "Japan": "Japón",
    "Sweden": "Suecia",
    "Tunisia": "Túnez",
    "Belgium": "Bélgica",
    "Egypt": "Egipto",
    "Iran": "Irán",
    "New Zealand": "Nueva Zelanda",
    "Spain": "España",
    "Cape Verde": "Cabo Verde",
    "Saudi Arabia": "Arabia Saudita",
    "Uruguay": "Uruguay",
    "France": "Francia",
    "Senegal": "Senegal",
    "Iraq": "Iraq",
    "Norway": "Noruega",
    "Argentina": "Argentina",
    "Algeria": "Argelia",
    "Austria": "Austria",
    "Jordan": "Jordania",
    "Portugal": "Portugal",
    "DR Congo": "RD Congo",
    "Congo DR": "RD Congo",
    "Democratic Republic of Congo": "RD Congo",
    "Uzbekistan": "Uzbekistán",
    "Colombia": "Colombia",
    "England": "Inglaterra",
    "Croatia": "Croacia",
    "Ghana": "Ghana",
    "Panama": "Panamá",
}


def normalize(name: str) -> str:
    """Convierte nombre inglés de la API a español de nuestra DB."""
    return TEAM_NAME_MAP.get(name, name)


def extract_score(match: dict):
    """
    Extrae goles del dict de la API. Prueba distintos schemas posibles
    ya que la documentación no detalla el campo exacto para partidos terminados.
    Retorna (home_goals, away_goals) o None si no hay resultado todavía.
    """
    # Intentar distintas estructuras comunes de APIs de fútbol
    candidates = [
        # wc2026api probable
        (match.get("home_score"), match.get("away_score")),
        (match.get("homeScore"), match.get("awayScore")),
        (match.get("home_goals"), match.get("away_goals")),
        # objeto anidado
        (
            match.get("score", {}).get("home") if isinstance(match.get("score"), dict) else None,
            match.get("score", {}).get("away") if isinstance(match.get("score"), dict) else None,
        ),
        (
            match.get("goals", {}).get("home") if isinstance(match.get("goals"), dict) else None,
            match.get("goals", {}).get("away") if isinstance(match.get("goals"), dict) else None,
        ),
        (
            match.get("result", {}).get("home") if isinstance(match.get("result"), dict) else None,
            match.get("result", {}).get("away") if isinstance(match.get("result"), dict) else None,
        ),
    ]
    for h, a in candidates:
        if h is not None and a is not None:
            try:
                return int(h), int(a)
            except (ValueError, TypeError):
                continue
    return None


def fetch_finished_matches(api_key: str) -> tuple[list, str | None]:
    """
    Llama a la API y devuelve (lista_de_partidos_terminados, mensaje_error).
    """
    headers = {
        "Authorization": f"Bearer {api_key}",
        "Accept": "application/json",
    }

    # Intentar con parámetro status=finished primero, luego sin filtro
    urls = [
        f"{API_BASE}/matches?status=finished",
        f"{API_BASE}/matches?phase=FT",        # Full Time, a veces usado
        f"{API_BASE}/matches",                  # Traer todo y filtrar localmente
    ]

    last_error = None
    for url in urls:
        try:
            req = urllib.request.Request(url, headers=headers)
            with urllib.request.urlopen(req, timeout=10) as resp:
                data = json.loads(resp.read().decode())
                # La API puede devolver lista directa o {matches: [...]} o {data: [...]}
                if isinstance(data, list):
                    matches = data
                elif isinstance(data, dict):
                    matches = data.get("matches") or data.get("data") or data.get("results") or []
                else:
                    matches = []

                # Filtrar solo los terminados si no vino filtrado
                finished = []
                for m in matches:
                    status = (m.get("status") or m.get("phase") or "").lower()
                    if status in ("finished", "ft", "completed", "full_time", "fulltime", "played", "done"):
                        finished.append(m)
                    elif extract_score(m) is not None:
                        # Si tiene score aunque el status sea raro, incluirlo
                        finished.append(m)

                return finished, None

        except urllib.error.HTTPError as e:
            last_error = f"HTTP {e.code}: {e.reason}"
            if e.code == 401:
                return [], "API key inválida o sin permisos."
            if e.code == 429:
                return [], "Límite de requests diarios alcanzado (100/día en plan gratuito)."
            # 404 puede significar que el endpoint no existe, probar el siguiente
            continue
        except urllib.error.URLError as e:
            last_error = f"Error de conexión: {e.reason}"
            continue
        except Exception as e:
            last_error = str(e)
            continue

    return [], last_error or "No se pudo conectar a la API."


def sync_results(api_key: str, db) -> dict:
    """
    Sincroniza resultados de la API con la base de datos local.
    Retorna un dict con estadísticas del proceso.
    """
    from models import Match, Prediction

    def compute_pts(ph, pa, rh, ra):
        if ph == rh and pa == ra:
            return 3
        def res(h, a): return "L" if h > a else ("V" if h < a else "E")
        return 1 if res(ph, pa) == res(rh, ra) else 0

    api_matches, error = fetch_finished_matches(api_key)
    if error:
        return {"ok": False, "error": error}

    updated = 0
    skipped = 0
    not_found = []

    for am in api_matches:
        score = extract_score(am)
        if score is None:
            skipped += 1
            continue

        home_goal, away_goal = score
        home_api = normalize(am.get("home_team", ""))
        away_api = normalize(am.get("away_team", ""))

        if not home_api or not away_api:
            skipped += 1
            continue

        # Buscar partido en nuestra DB (por nombre de equipos)
        match = (
            db.query(Match)
            .filter_by(home_team=home_api, away_team=away_api)
            .first()
        )
        if not match:
            # Buscar también al revés (a veces la API invierte local/visitante)
            match = (
                db.query(Match)
                .filter_by(home_team=away_api, away_team=home_api)
                .first()
            )
            if match:
                home_goal, away_goal = away_goal, home_goal  # ajustar sentido

        if not match:
            not_found.append(f"{home_api} vs {away_api}")
            continue

        if match.status == "jugado" and match.home_score == home_goal and match.away_score == away_goal:
            skipped += 1
            continue  # Ya estaba cargado con mismo resultado

        match.home_score = home_goal
        match.away_score = away_goal
        match.status = "jugado"

        # Recalcular puntos de todos los pronósticos de este partido
        for pred in match.predictions:
            pred.points = compute_pts(pred.home_score, pred.away_score, home_goal, away_goal)

        updated += 1

    db.commit()

    return {
        "ok": True,
        "total_api": len(api_matches),
        "updated": updated,
        "skipped": skipped,
        "not_found": not_found,
    }
