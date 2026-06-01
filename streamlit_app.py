import streamlit as st
from models import engine, SessionLocal, User, Match, Prediction, init_db
from data.fixtures import GROUP_MATCHES, GROUPS, KNOCKOUT_ROUNDS, KNOCKOUT_SLOTS
from sync import sync_results

ADMIN_PASSWORD = "admin2026"

st.set_page_config(
    page_title="Prode Mundial 2026",
    page_icon="🏆",
    layout="wide",
    initial_sidebar_state="expanded",
)

# ── Bootstrap DB ──────────────────────────────────────────────────────────────

@st.cache_resource
def setup_db():
    init_db()
    db = SessionLocal()
    if db.query(Match).filter_by(stage="Grupos").count() == 0:
        for m in GROUP_MATCHES:
            db.add(Match(
                id=m["id"], stage=m["stage"], group=m["group"],
                home_team=m["home_team"], away_team=m["away_team"],
            ))
    for round_name, count in KNOCKOUT_SLOTS.items():
        if db.query(Match).filter_by(stage=round_name).count() == 0:
            for slot in range(1, count + 1):
                db.add(Match(
                    stage=round_name, slot=slot,
                    home_team=f"Por definir {slot}A",
                    away_team=f"Por definir {slot}B",
                ))
    db.commit()
    db.close()
    return True

setup_db()


# ── Helpers ───────────────────────────────────────────────────────────────────

def get_db():
    return SessionLocal()


def result_of(h, a):
    if h > a: return "L"
    if h < a: return "V"
    return "E"


def compute_points(ph, pa, rh, ra):
    if ph == rh and pa == ra:
        return 3
    if result_of(ph, pa) == result_of(rh, ra):
        return 1
    return 0


def recalculate(db):
    for m in db.query(Match).filter_by(status="jugado").all():
        for p in m.predictions:
            p.points = compute_points(p.home_score, p.away_score, m.home_score, m.away_score)
    db.commit()


def get_leaderboard(db):
    users = db.query(User).all()
    rows = []
    for u in users:
        preds = list(u.predictions)
        total = sum(p.points for p in preds)
        exact = sum(1 for p in preds if p.points == 3)
        result = sum(1 for p in preds if p.points == 1)
        rows.append({"user": u, "total": total, "exact": exact, "result": result, "n": len(preds)})
    rows.sort(key=lambda x: (-x["total"], -x["exact"]))
    for i, r in enumerate(rows):
        r["pos"] = i + 1
    return rows


# ── Login ─────────────────────────────────────────────────────────────────────

def page_login():
    col1, col2, col3 = st.columns([1, 2, 1])
    with col2:
        st.markdown("<h1 style='text-align:center'>🏆 Prode Mundial 2026</h1>", unsafe_allow_html=True)
        st.markdown("<p style='text-align:center; color:#94a3b8'>USA · Canadá · México</p>", unsafe_allow_html=True)
        st.divider()
        with st.form("login_form"):
            name = st.text_input("Tu nombre", placeholder="Ej: Rodrigo", max_chars=40)
            submitted = st.form_submit_button("▶ Entrar al Prode", use_container_width=True, type="primary")
        if submitted:
            name = name.strip()
            if not name:
                st.error("Ingresá tu nombre.")
            else:
                db = get_db()
                user = db.query(User).filter_by(name=name).first()
                if not user:
                    user = User(name=name)
                    db.add(user)
                    db.commit()
                    db.refresh(user)
                    st.success(f"¡Bienvenido, {name}! Tu cuenta fue creada.")
                else:
                    st.success(f"¡Hola de nuevo, {name}!")
                st.session_state["user_id"] = user.id
                st.session_state["user_name"] = user.name
                st.session_state["is_admin"] = user.is_admin
                db.close()
                st.rerun()
        st.markdown("""
        <p style='text-align:center; color:#64748b; font-size:0.85rem; margin-top:1rem'>
        Ingresá tu nombre y comenzás. Si ya tenés cuenta, continuás desde donde dejaste.
        </p>""", unsafe_allow_html=True)


# ── Dashboard ─────────────────────────────────────────────────────────────────

def page_dashboard():
    db = get_db()
    user = db.query(User).get(st.session_state["user_id"])
    preds = list(user.predictions)
    total_pts = sum(p.points for p in preds)
    n_preds = len(preds)
    played = db.query(Match).filter_by(status="jugado").count()
    leaderboard = get_leaderboard(db)
    my_pos = next((r["pos"] for r in leaderboard if r["user"].id == user.id), "-")

    st.title(f"Hola, {user.name} 👋")

    c1, c2, c3, c4 = st.columns(4)
    c1.metric("Mis puntos", total_pts)
    c2.metric("Mi posición", f"#{my_pos}")
    c3.metric("Pronósticos cargados", n_preds)
    c4.metric("Partidos jugados", played)

    st.divider()

    col_a, col_b = st.columns([1, 2])
    with col_a:
        st.subheader("⚡ Accesos rápidos")
        if st.button("✏️ Cargar pronósticos de grupos", use_container_width=True):
            st.session_state["page"] = "Pronósticos"
            st.rerun()
        if st.button("🗂️ Pronósticos eliminatorias", use_container_width=True):
            st.session_state["page"] = "Eliminatorias"
            st.rerun()
        if st.button("📊 Ver tabla completa", use_container_width=True):
            st.session_state["page"] = "Tabla"
            st.rerun()

    with col_b:
        st.subheader("🏆 Top del prode")
        if leaderboard:
            medals = {1: "🥇", 2: "🥈", 3: "🥉"}
            for r in leaderboard[:8]:
                medal = medals.get(r["pos"], f"#{r['pos']}")
                highlight = "**" if r["user"].id == user.id else ""
                st.markdown(
                    f"{medal} {highlight}{r['user'].name}{highlight} &nbsp;—&nbsp; "
                    f"**{r['total']} pts** &nbsp; 🎯 {r['exact']} exactos &nbsp; ✓ {r['result']} resultados"
                )
        else:
            st.info("Aún no hay pronósticos.")

    st.divider()
    st.caption("**Sistema de puntos:** 🎯 Resultado exacto = 3 pts &nbsp;|&nbsp; ✓ Resultado correcto (1X2) = 1 pt &nbsp;|&nbsp; Desempate: más exactos gana.")
    db.close()


# ── Pronósticos grupos ────────────────────────────────────────────────────────

def page_predictions():
    db = get_db()
    user_id = st.session_state["user_id"]
    st.title("✏️ Pronósticos — Fase de Grupos")
    st.caption("🎯 Exacto = 3 pts &nbsp;|&nbsp; ✓ Resultado = 1 pt &nbsp;|&nbsp; Los partidos jugados están bloqueados.")

    group_names = sorted(GROUPS.keys())
    tabs = st.tabs([f"Grupo {g}" for g in group_names])

    for tab, group_name in zip(tabs, group_names):
        with tab:
            matches = db.query(Match).filter_by(stage="Grupos", group=group_name).all()
            pending = [m for m in matches if m.status != "jugado"]
            played = [m for m in matches if m.status == "jugado"]

            if pending:
                with st.form(f"form_{group_name}"):
                    cols_header = st.columns([3, 1, 1, 3, 2])
                    cols_header[0].markdown("**Local**")
                    cols_header[1].markdown("**L**")
                    cols_header[3].markdown("**V**")
                    cols_header[4].markdown("**Visitante**")

                    inputs = {}
                    for m in pending:
                        pred = db.query(Prediction).filter_by(user_id=user_id, match_id=m.id).first()
                        cols = st.columns([3, 1, 1, 3, 2])
                        cols[0].markdown(f"<div style='text-align:right;padding-top:8px'>{m.home_team}</div>", unsafe_allow_html=True)
                        h_val = pred.home_score if pred else 0
                        a_val = pred.away_score if pred else 0
                        h = cols[1].number_input("", min_value=0, max_value=20, value=h_val, key=f"h_{m.id}", label_visibility="collapsed")
                        cols[2].markdown("<div style='text-align:center;padding-top:8px;font-weight:bold'>-</div>", unsafe_allow_html=True)
                        a = cols[3].number_input("", min_value=0, max_value=20, value=a_val, key=f"a_{m.id}", label_visibility="collapsed")
                        cols[4].markdown(f"<div style='padding-top:8px'>{m.away_team}</div>", unsafe_allow_html=True)
                        inputs[m.id] = (h, a)

                    if st.form_submit_button("💾 Guardar Grupo " + group_name, use_container_width=True, type="primary"):
                        saved = 0
                        for mid, (h, a) in inputs.items():
                            pred = db.query(Prediction).filter_by(user_id=user_id, match_id=mid).first()
                            if pred:
                                pred.home_score = h
                                pred.away_score = a
                            else:
                                db.add(Prediction(user_id=user_id, match_id=mid, home_score=h, away_score=a))
                            saved += 1
                        db.commit()
                        st.success(f"✓ {saved} pronósticos guardados.")
                        st.rerun()

            if played:
                st.markdown("##### Partidos jugados")
                for m in played:
                    pred = db.query(Prediction).filter_by(user_id=user_id, match_id=m.id).first()
                    cols = st.columns([3, 2, 3, 2])
                    cols[0].markdown(f"<div style='text-align:right'>{m.home_team}</div>", unsafe_allow_html=True)
                    cols[1].markdown(f"<div style='text-align:center;font-weight:bold;color:#22c55e'>{m.home_score} - {m.away_score}</div>", unsafe_allow_html=True)
                    cols[2].markdown(m.away_team)
                    if pred:
                        if pred.points == 3:
                            cols[3].markdown("🎯 **+3**")
                        elif pred.points == 1:
                            cols[3].markdown("✓ **+1**")
                        else:
                            cols[3].markdown(f"✗ 0 _(pronosticaste {pred.home_score}-{pred.away_score})_")
                    else:
                        cols[3].markdown("—")
    db.close()


# ── Eliminatorias ─────────────────────────────────────────────────────────────

def page_bracket():
    db = get_db()
    user_id = st.session_state["user_id"]
    st.title("🗂️ Fase Eliminatoria")
    st.caption("En eliminatorias no puede haber empate. El pronóstico se guarda partido a partido.")

    for round_name in KNOCKOUT_ROUNDS:
        st.subheader(f"🔴 {round_name}")
        matches = db.query(Match).filter_by(stage=round_name).order_by(Match.slot).all()
        cols_per_row = 2
        rows = [matches[i:i+cols_per_row] for i in range(0, len(matches), cols_per_row)]
        for row in rows:
            cols = st.columns(cols_per_row)
            for col, m in zip(cols, row):
                with col:
                    if m.home_team.startswith("Por definir"):
                        st.info(f"Partido {m.slot} — Por definir")
                        continue
                    pred = db.query(Prediction).filter_by(user_id=user_id, match_id=m.id).first()
                    if m.status == "jugado":
                        pts_str = ""
                        if pred:
                            pts_str = "🎯 +3" if pred.points == 3 else ("✓ +1" if pred.points == 1 else "✗ 0")
                        st.markdown(
                            f"**{m.home_team}** {m.home_score} - {m.away_score} **{m.away_team}**  \n"
                            f"_{pts_str}_"
                        )
                    else:
                        with st.form(f"ko_{m.id}"):
                            st.markdown(f"**{m.home_team}** vs **{m.away_team}**")
                            c1, c2, c3 = st.columns([2, 1, 2])
                            h = c1.number_input(m.home_team, min_value=0, max_value=20,
                                                value=pred.home_score if pred else 0, label_visibility="collapsed")
                            c2.markdown("<div style='text-align:center;padding-top:8px;font-weight:bold'>-</div>", unsafe_allow_html=True)
                            a = c3.number_input(m.away_team, min_value=0, max_value=20,
                                                value=pred.away_score if pred else 0, label_visibility="collapsed")
                            if st.form_submit_button("Guardar", use_container_width=True):
                                if h == a:
                                    st.error("No puede haber empate en eliminatorias.")
                                else:
                                    if pred:
                                        pred.home_score = h
                                        pred.away_score = a
                                    else:
                                        db.add(Prediction(user_id=user_id, match_id=m.id, home_score=h, away_score=a))
                                    db.commit()
                                    st.success("Guardado.")
                                    st.rerun()
        st.divider()
    db.close()


# ── Estadísticas del Mundial ──────────────────────────────────────────────────

def compute_group_standings(db):
    """Calcula la tabla de posiciones de cada grupo a partir de los partidos jugados."""
    standings = {}
    for group_name, teams in GROUPS.items():
        table = {t: {"PJ": 0, "G": 0, "E": 0, "P": 0, "GF": 0, "GC": 0, "DG": 0, "Pts": 0} for t in teams}
        matches = db.query(Match).filter_by(stage="Grupos", group=group_name, status="jugado").all()
        for m in matches:
            h, a = m.home_score, m.away_score
            ht, at = m.home_team, m.away_team
            if ht not in table or at not in table:
                continue
            table[ht]["PJ"] += 1; table[at]["PJ"] += 1
            table[ht]["GF"] += h; table[ht]["GC"] += a
            table[at]["GF"] += a; table[at]["GC"] += h
            if h > a:
                table[ht]["G"] += 1; table[ht]["Pts"] += 3
                table[at]["P"] += 1
            elif h < a:
                table[at]["G"] += 1; table[at]["Pts"] += 3
                table[ht]["P"] += 1
            else:
                table[ht]["E"] += 1; table[ht]["Pts"] += 1
                table[at]["E"] += 1; table[at]["Pts"] += 1
        for t in table:
            table[t]["DG"] = table[t]["GF"] - table[t]["GC"]
        sorted_teams = sorted(
            table.items(),
            key=lambda x: (-x[1]["Pts"], -x[1]["DG"], -x[1]["GF"], x[0])
        )
        standings[group_name] = sorted_teams
    return standings


def page_mundial_stats():
    db = get_db()
    st.title("🌍 Estadísticas del Mundial")

    played_matches = db.query(Match).filter_by(status="jugado").all()
    total_played = len(played_matches)
    group_played = [m for m in played_matches if m.stage == "Grupos"]
    ko_played = [m for m in played_matches if m.stage != "Grupos"]

    # ── Métricas generales ────────────────────────────────────────────────────
    total_goals = sum((m.home_score or 0) + (m.away_score or 0) for m in played_matches)
    avg_goals = round(total_goals / total_played, 2) if total_played else 0
    total_group_matches = db.query(Match).filter_by(stage="Grupos").count()
    total_ko_matches = sum(KNOCKOUT_SLOTS.values())

    c1, c2, c3, c4, c5 = st.columns(5)
    c1.metric("Partidos jugados", f"{total_played} / {total_group_matches + total_ko_matches}")
    c2.metric("Goles totales", total_goals)
    c3.metric("Promedio goles/partido", avg_goals)
    c4.metric("Partidos de grupos", len(group_played))
    c5.metric("Partidos eliminatorios", len(ko_played))

    if not played_matches:
        st.info("⏳ El torneo aún no comenzó. Las estadísticas se actualizarán al iniciarse los partidos.")
        db.close()
        return

    st.divider()

    # ── Tabs principales ──────────────────────────────────────────────────────
    tab_groups, tab_results, tab_teams, tab_records = st.tabs([
        "🏟️ Tabla de grupos",
        "📋 Resultados",
        "⚽ Equipos",
        "🏅 Récords",
    ])

    # ── Tabla de grupos ───────────────────────────────────────────────────────
    with tab_groups:
        standings = compute_group_standings(db)
        group_names = sorted(GROUPS.keys())

        # Mostrar de a 3 grupos por fila
        for i in range(0, len(group_names), 3):
            cols = st.columns(3)
            for col, gname in zip(cols, group_names[i:i+3]):
                with col:
                    st.markdown(f"#### Grupo {gname}")
                    rows = standings[gname]
                    # Header
                    h = st.columns([4, 1, 1, 1, 1, 1, 1, 1])
                    for hcol, label in zip(h, ["Equipo","PJ","G","E","P","GF","GC","Pts"]):
                        hcol.markdown(f"<small><b>{label}</b></small>", unsafe_allow_html=True)

                    for pos, (team, s) in enumerate(rows):
                        r = st.columns([4, 1, 1, 1, 1, 1, 1, 1])
                        # Color: verde top 2, amarillo 3ro, rojo 4to
                        if pos < 2:
                            color = "#22c55e"
                            prefix = "🟢 "
                        elif pos == 2:
                            color = "#eab308"
                            prefix = "🟡 "
                        else:
                            color = "#ef4444"
                            prefix = "🔴 "
                        r[0].markdown(
                            f"<span style='color:{color};font-size:0.85rem'>{prefix}{team}</span>",
                            unsafe_allow_html=True
                        )
                        for rcol, val in zip(r[1:], [s["PJ"],s["G"],s["E"],s["P"],s["GF"],s["GC"],s["Pts"]]):
                            weight = "bold" if rcol == r[7] else "normal"
                            rcol.markdown(f"<span style='font-size:0.85rem;font-weight:{weight}'>{val}</span>", unsafe_allow_html=True)
                    st.markdown("")

        st.caption("🟢 Clasificado · 🟡 Posible repechaje · 🔴 Eliminado (proyección según resultados actuales)")

    # ── Resultados ────────────────────────────────────────────────────────────
    with tab_results:
        stage_filter = st.selectbox("Filtrar por etapa", ["Todos"] + ["Grupos"] + KNOCKOUT_ROUNDS)
        group_filter = st.selectbox("Filtrar por grupo", ["Todos"] + sorted(GROUPS.keys())) if stage_filter in ("Todos", "Grupos") else None

        filtered = played_matches
        if stage_filter != "Todos":
            filtered = [m for m in filtered if m.stage == stage_filter]
        if group_filter and group_filter != "Todos":
            filtered = [m for m in filtered if m.group == group_filter]

        if not filtered:
            st.info("No hay partidos jugados con ese filtro.")
        else:
            for m in filtered:
                total_m = (m.home_score or 0) + (m.away_score or 0)
                badge = "🔥" if total_m >= 5 else ""
                label = f"Gr.{m.group}" if m.group else m.stage
                cols = st.columns([1, 3, 2, 3, 1])
                cols[0].caption(label)
                cols[1].markdown(f"<div style='text-align:right'>{m.home_team}</div>", unsafe_allow_html=True)
                cols[2].markdown(
                    f"<div style='text-align:center;font-weight:bold;font-size:1.1rem'>"
                    f"{m.home_score} - {m.away_score}</div>",
                    unsafe_allow_html=True
                )
                cols[3].markdown(m.away_team)
                cols[4].markdown(badge)

    # ── Estadísticas por equipo ───────────────────────────────────────────────
    with tab_teams:
        team_stats = {}
        for m in group_played:
            for team, gf, gc in [(m.home_team, m.home_score, m.away_score),
                                  (m.away_team, m.away_score, m.home_score)]:
                if team not in team_stats:
                    team_stats[team] = {"PJ":0,"G":0,"E":0,"P":0,"GF":0,"GC":0,"Pts":0}
                s = team_stats[team]
                s["PJ"] += 1; s["GF"] += gf; s["GC"] += gc
                if gf > gc: s["G"] += 1; s["Pts"] += 3
                elif gf == gc: s["E"] += 1; s["Pts"] += 1
                else: s["P"] += 1
        for s in team_stats.values():
            s["DG"] = s["GF"] - s["GC"]

        if not team_stats:
            st.info("Sin datos aún.")
        else:
            sort_by = st.selectbox("Ordenar por", ["Pts", "GF", "DG", "G"])
            sorted_teams = sorted(team_stats.items(), key=lambda x: -x[1][sort_by])

            header = st.columns([3,1,1,1,1,1,1,1,1])
            for hc, lbl in zip(header, ["Equipo","PJ","G","E","P","GF","GC","DG","Pts"]):
                hc.markdown(f"**{lbl}**")
            st.divider()
            for team, s in sorted_teams:
                row = st.columns([3,1,1,1,1,1,1,1,1])
                row[0].markdown(team)
                for rc, v in zip(row[1:], [s["PJ"],s["G"],s["E"],s["P"],s["GF"],s["GC"],s["DG"],s["Pts"]]):
                    rc.markdown(str(v))

    # ── Récords del torneo ────────────────────────────────────────────────────
    with tab_records:
        if not group_played:
            st.info("Sin datos aún.")
        else:
            col1, col2 = st.columns(2)

            with col1:
                st.markdown("#### 🔥 Partido con más goles")
                top_match = max(group_played, key=lambda m: (m.home_score or 0) + (m.away_score or 0))
                total = (top_match.home_score or 0) + (top_match.away_score or 0)
                st.metric(
                    f"{top_match.home_team} vs {top_match.away_team}",
                    f"{top_match.home_score} - {top_match.away_score}",
                    f"{total} goles"
                )

                st.markdown("#### ⚽ Mayor goleada")
                top_diff = max(group_played, key=lambda m: abs((m.home_score or 0) - (m.away_score or 0)))
                diff = abs((top_diff.home_score or 0) - (top_diff.away_score or 0))
                st.metric(
                    f"{top_diff.home_team} vs {top_diff.away_team}",
                    f"{top_diff.home_score} - {top_diff.away_score}",
                    f"Diferencia: {diff}"
                )

                st.markdown("#### 🤝 Empates")
                draws = [m for m in group_played if m.home_score == m.away_score]
                st.metric("Total de empates", len(draws))

            with col2:
                if team_stats:
                    st.markdown("#### 🏹 Mejor ataque")
                    best_attack = max(team_stats.items(), key=lambda x: x[1]["GF"])
                    st.metric(best_attack[0], f"{best_attack[1]['GF']} goles a favor")

                    st.markdown("#### 🛡️ Mejor defensa")
                    best_defense = min(
                        [(t, s) for t, s in team_stats.items() if s["PJ"] > 0],
                        key=lambda x: (x[1]["GC"], -x[1]["PJ"])
                    )
                    st.metric(best_defense[0], f"{best_defense[1]['GC']} goles en contra")

                    st.markdown("#### 📈 Más goleador")
                    top_scorer_team = max(team_stats.items(), key=lambda x: x[1]["GF"])
                    avg = round(top_scorer_team[1]["GF"] / max(top_scorer_team[1]["PJ"], 1), 1)
                    st.metric(top_scorer_team[0], f"{avg} goles/partido en promedio")

                    st.markdown("#### 🔴 Más derrotas")
                    worst = max(team_stats.items(), key=lambda x: x[1]["P"])
                    st.metric(worst[0], f"{worst[1]['P']} derrota(s)")

    db.close()


# ── Tabla ─────────────────────────────────────────────────────────────────────

def page_leaderboard():
    db = get_db()
    st.title("📊 Tabla de Posiciones")
    played = db.query(Match).filter_by(status="jugado").count()
    st.caption(f"{played} partidos jugados hasta ahora.")

    leaderboard = get_leaderboard(db)
    if not leaderboard:
        st.info("Aún no hay participantes.")
        db.close()
        return

    medals = {1: "🥇", 2: "🥈", 3: "🥉"}
    my_id = st.session_state["user_id"]

    header = st.columns([1, 4, 2, 2, 2, 2])
    header[0].markdown("**#**")
    header[1].markdown("**Jugador**")
    header[2].markdown("**Puntos**")
    header[3].markdown("**Exactos 🎯**")
    header[4].markdown("**Resultados ✓**")
    header[5].markdown("**Pronósticos**")
    st.divider()

    for r in leaderboard:
        is_me = r["user"].id == my_id
        cols = st.columns([1, 4, 2, 2, 2, 2])
        cols[0].markdown(medals.get(r["pos"], str(r["pos"])))
        name_str = f"**{r['user'].name}** ← vos" if is_me else r["user"].name
        cols[1].markdown(name_str)
        cols[2].markdown(f"**{r['total']}**")
        cols[3].markdown(str(r["exact"]))
        cols[4].markdown(str(r["result"]))
        cols[5].markdown(str(r["n"]))

    st.divider()
    st.caption("Desempate: más exactos → más resultados → orden de registro.")
    db.close()


# ── Admin ─────────────────────────────────────────────────────────────────────

def page_admin():
    st.title("⚙️ Panel de Admin")

    if not st.session_state.get("is_admin"):
        with st.form("admin_auth"):
            pwd = st.text_input("Contraseña de administrador", type="password")
            if st.form_submit_button("Ingresar"):
                if pwd == ADMIN_PASSWORD:
                    db = get_db()
                    user = db.query(User).get(st.session_state["user_id"])
                    user.is_admin = True
                    db.commit()
                    db.close()
                    st.session_state["is_admin"] = True
                    st.rerun()
                else:
                    st.error("Contraseña incorrecta.")
        return

    db = get_db()
    st.success("✅ Sesión de admin activa.")

    # ── Sincronización automática ──────────────────────────────────────────────
    st.subheader("🔄 Sincronización automática de resultados")
    col1, col2 = st.columns([2, 1])
    col1.markdown(
        "Trae los resultados de los últimos 10 días desde **ESPN** (sin API key) "
        "y actualiza los puntos de todos los participantes automáticamente."
    )
    if col2.button("🔄 Sincronizar ahora", use_container_width=True, type="primary"):
        with st.spinner("Consultando ESPN..."):
            result = sync_results(None, db)
        if not result["ok"]:
            st.error(f"❌ {result['error']}")
        else:
            st.success(
                f"✅ Listo — **{result['updated']}** partido(s) actualizado(s), "
                f"{result['skipped']} ya estaban cargados."
            )
            if result["not_found"]:
                st.warning(
                    f"⚠️ {len(result['not_found'])} partido(s) de ESPN no coincidieron con la DB "
                    f"(pueden ser de otras competencias): "
                    + ", ".join(result["not_found"][:5])
                )
            if result["updated"] > 0:
                st.rerun()

    st.divider()

    stage_opts = ["Grupos"] + KNOCKOUT_ROUNDS
    stage = st.selectbox("Etapa", stage_opts)

    if stage == "Grupos":
        group = st.selectbox("Grupo", sorted(GROUPS.keys()))
        matches = db.query(Match).filter_by(stage="Grupos", group=group).all()
    else:
        matches = db.query(Match).filter_by(stage=stage).order_by(Match.slot).all()

    st.divider()

    for m in matches:
        with st.expander(
            f"{'✅' if m.status == 'jugado' else '⏳'} {m.home_team} vs {m.away_team}"
            + (f" — {m.home_score}-{m.away_score}" if m.status == 'jugado' else ""),
            expanded=(m.status != "jugado"),
        ):
            # Editar equipos (solo eliminatorias)
            if stage != "Grupos":
                with st.form(f"teams_{m.id}"):
                    c1, c2 = st.columns(2)
                    ht = c1.text_input("Equipo local", value=m.home_team)
                    at = c2.text_input("Equipo visitante", value=m.away_team)
                    if st.form_submit_button("Actualizar equipos"):
                        m.home_team = ht.strip() or m.home_team
                        m.away_team = at.strip() or m.away_team
                        db.commit()
                        st.success("Equipos actualizados.")
                        st.rerun()
                st.divider()

            # Cargar resultado
            if m.status != "jugado":
                with st.form(f"result_{m.id}"):
                    c1, c2, c3 = st.columns([2, 2, 2])
                    rh = c1.number_input(f"Goles {m.home_team}", min_value=0, max_value=20, value=0)
                    ra = c2.number_input(f"Goles {m.away_team}", min_value=0, max_value=20, value=0)
                    if c3.form_submit_button("✅ Cargar resultado", use_container_width=True, type="primary"):
                        m.home_score = rh
                        m.away_score = ra
                        m.status = "jugado"
                        db.commit()
                        recalculate(db)
                        st.success(f"Resultado cargado: {m.home_team} {rh}-{ra} {m.away_team}")
                        st.rerun()
            else:
                st.markdown(f"**Resultado:** {m.home_team} **{m.home_score} - {m.away_score}** {m.away_team}")
                if st.button(f"🔄 Resetear resultado", key=f"reset_{m.id}"):
                    m.home_score = None
                    m.away_score = None
                    m.status = "pendiente"
                    for p in m.predictions:
                        p.points = 0
                    db.commit()
                    st.warning("Resultado reseteado.")
                    st.rerun()

    db.close()


# ── Navegación ────────────────────────────────────────────────────────────────

def main():
    if "user_id" not in st.session_state:
        page_login()
        return

    with st.sidebar:
        st.markdown(f"### 🏆 Prode Mundial 2026")
        st.markdown(f"👤 **{st.session_state['user_name']}**")
        st.divider()
        pages = ["Dashboard", "Pronósticos", "Eliminatorias", "Tabla", "Mundial 🌍"]
        if st.session_state.get("is_admin"):
            pages.append("Admin ⚙️")
        else:
            pages.append("Admin")
        icons = {"Dashboard": "🏠", "Pronósticos": "✏️", "Eliminatorias": "🗂️", "Tabla": "📊", "Mundial 🌍": "🌍", "Admin": "⚙️", "Admin ⚙️": "⚙️"}
        if "page" not in st.session_state:
            st.session_state["page"] = "Dashboard"
        for p in pages:
            if st.button(f"{icons.get(p, '')} {p}", use_container_width=True,
                         type="primary" if st.session_state["page"] == p else "secondary"):
                st.session_state["page"] = p
                st.rerun()
        st.divider()
        if st.button("🚪 Salir", use_container_width=True):
            st.session_state.clear()
            st.rerun()

    page = st.session_state.get("page", "Dashboard")
    if page == "Dashboard":
        page_dashboard()
    elif page == "Pronósticos":
        page_predictions()
    elif page == "Eliminatorias":
        page_bracket()
    elif page == "Tabla":
        page_leaderboard()
    elif page == "Mundial 🌍":
        page_mundial_stats()
    elif page in ("Admin", "Admin ⚙️"):
        page_admin()


if __name__ == "__main__":
    main()
