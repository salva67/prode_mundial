# Equipos y grupos del Mundial 2026
# Fuente: Sorteo oficial FIFA, 5 de diciembre de 2025 — Washington D.C.

GROUPS = {
    "A": ["México", "Sudáfrica", "Corea del Sur", "República Checa"],
    "B": ["Canadá", "Bosnia y Herzegovina", "Qatar", "Suiza"],
    "C": ["Brasil", "Marruecos", "Haití", "Escocia"],
    "D": ["Estados Unidos", "Paraguay", "Australia", "Turquía"],
    "E": ["Alemania", "Curazao", "Costa de Marfil", "Ecuador"],
    "F": ["Países Bajos", "Japón", "Suecia", "Túnez"],
    "G": ["Bélgica", "Egipto", "Irán", "Nueva Zelanda"],
    "H": ["España", "Cabo Verde", "Arabia Saudita", "Uruguay"],
    "I": ["Francia", "Senegal", "Iraq", "Noruega"],
    "J": ["Argentina", "Argelia", "Austria", "Jordania"],
    "K": ["Portugal", "RD Congo", "Uzbekistán", "Colombia"],
    "L": ["Inglaterra", "Croacia", "Ghana", "Panamá"],
}

def generate_group_matches():
    matches = []
    match_id = 1
    for group, teams in GROUPS.items():
        combos = [
            (teams[0], teams[1]),
            (teams[2], teams[3]),
            (teams[0], teams[2]),
            (teams[1], teams[3]),
            (teams[0], teams[3]),
            (teams[1], teams[2]),
        ]
        for home, away in combos:
            matches.append({
                "id": match_id,
                "stage": "Grupos",
                "group": group,
                "home_team": home,
                "away_team": away,
            })
            match_id += 1
    return matches

GROUP_MATCHES = generate_group_matches()

KNOCKOUT_ROUNDS = [
    "Octavos de Final",
    "Cuartos de Final",
    "Semifinal",
    "Tercer Puesto",
    "Final",
]

KNOCKOUT_SLOTS = {
    "Octavos de Final": 16,
    "Cuartos de Final": 8,
    "Semifinal": 4,
    "Tercer Puesto": 1,
    "Final": 1,
}
