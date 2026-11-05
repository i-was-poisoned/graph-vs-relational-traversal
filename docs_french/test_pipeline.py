########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de tests/test_pipeline.py.
# Il n'est PAS destiné à être exécuté — il se trouve dans docs_french/ car son
# but est d'enseigner. Le fichier réel et « propre » (sans tous ces
# commentaires) est tests/test_pipeline.py.
#
# Ce fichier suppose que vous avez déjà lu docs_french/test_extract_csv.py —
# les bases de pytest qui y sont expliquées (le nom test_, assert, les
# fonctions d'aide, les fixtures) ne sont PAS réexpliquées ici. Les
# fonctions testées (compute_window, hour_file_name) sont expliquées dans
# docs_french/pipeline.py.
#
# Son rôle dans le projet : vérifier les deux calculs « invisibles » de la
# pipeline. Si la fenêtre était décalée d'une heure ou si un nom de fichier
# était faux, la pipeline ne planterait pas forcément : elle chargerait
# simplement les mauvaises heures, ou recevrait des 404.
########################################################################

"""Unit tests for the pure functions of scripts/pipeline.py (no network, no databases).

Run with:  python -m pytest
"""

# datetime, timedelta, timezone : déjà expliqués dans docs_french/pipeline.py.
# timedelta est une DURÉE (par exemple timedelta(hours=1) = une heure) ;
# soustraire deux datetime donne un timedelta.
from datetime import datetime, timedelta, timezone

# ---------------------------------------------------------------------
# On n'importe que les deux fonctions « pures » de pipeline.py : elles
# calculent un résultat à partir de leurs paramètres, sans Internet, sans
# base de données et sans fichiers.
#
# Importer pipeline importe aussi psycopg et neo4j (pipeline.py en a
# besoin), mais sans se connecter à rien : aucune base n'est contactée
# tant qu'on n'appelle pas les fonctions qui s'y connectent.
# ---------------------------------------------------------------------
from pipeline import compute_window, hour_file_name


# ---------------------------------------------------------------------
# utc : une petite fonction d'aide pour écrire les dates plus court.
# utc(2026, 10, 22, 11, 15) au lieu de
# datetime(2026, 10, 22, 11, 15, tzinfo=timezone.utc).
# `minute: int = 0` : par défaut, une heure pile.
# Toutes les dates du projet sont en UTC, comme les fichiers GH Archive.
# ---------------------------------------------------------------------
def utc(year: int, month: int, day: int, hour: int, minute: int = 0) -> datetime:
    return datetime(year, month, day, hour, minute, tzinfo=timezone.utc)


# ---------- compute_window ----------

# ---------------------------------------------------------------------
# Le test reprend exactement l'exemple écrit dans le README et dans le
# commentaire de compute_window : s'il échoue un jour, c'est soit que le
# code a changé, soit que la documentation ne dit plus la vérité.
#
# window_hours=24, lag_hours=24 : des arguments NOMMÉS. On pourrait écrire
# compute_window(..., 24, 24), mais avec les noms, on voit lequel est la
# fenêtre et lequel est le décalage.
#
# hours[0] : la première heure de la liste ; hours[-1] : la DERNIÈRE (un
# indice négatif compte depuis la fin).
# ---------------------------------------------------------------------
def test_compute_window_readme_example():
    # At 2026-10-22 11:15 UTC the window is 2026-10-20 11:00 -> 2026-10-21 11:00:
    # 24 hour files, the first starting at 11:00 and the last at 10:00 the next day.
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    assert len(hours) == 24
    assert hours[0] == utc(2026, 10, 20, 11)
    assert hours[-1] == utc(2026, 10, 21, 10)


# ---------------------------------------------------------------------
# NOUVEAU : zip(hours, hours[1:]) pour comparer chaque élément au suivant.
#
# hours[1:] est la même liste sans son premier élément. zip avance dans
# les deux listes en même temps et donne des paires :
#     (heure 0, heure 1), (heure 1, heure 2), ... (heure 22, heure 23)
# Chaque paire est déballée dans `earlier` (la plus tôt) et `later`.
#
# Pour chaque paire, on vérifie que l'écart est exactement d'une heure :
# pas de trou, pas de doublon. Un assert dans une boucle fait échouer le
# test dès la première paire fausse.
# ---------------------------------------------------------------------
def test_compute_window_hours_are_consecutive():
    hours = compute_window(utc(2026, 10, 22, 11, 15), window_hours=24, lag_hours=24)
    for earlier, later in zip(hours, hours[1:]):
        assert later - earlier == timedelta(hours=1)


# ---------------------------------------------------------------------
# Un autre cas : une heure PILE (12:00:00, sans minutes) et d'autres
# réglages, pour vérifier que la fonction n'est pas « collée » à 24 h.
#
# [utc(2026, 10, 22, h) for h in range(4, 10)] : une compréhension de
# liste. range(4, 10) donne 4, 5, 6, 7, 8, 9 (le 10 est exclu), donc la
# liste attendue est 04:00, 05:00, ... 09:00 — six heures.
# ---------------------------------------------------------------------
def test_compute_window_exactly_on_the_hour():
    # 12:00:00 sharp, 6-hour window, 2-hour lag -> ends at 10:00, so hours 04:00 ... 09:00.
    hours = compute_window(utc(2026, 10, 22, 12), window_hours=6, lag_hours=2)
    assert hours == [utc(2026, 10, 22, h) for h in range(4, 10)]


# ---------- hour_file_name ----------

# Le piège du format GH Archive : l'heure est écrite SANS zéro devant.
# C'est le cas qui a servi d'exemple d'échec dans project-notes.md.
def test_hour_file_name_has_no_leading_zero():
    # GH Archive writes "-5", not "-05": a wrong name would mean a 404 on every early hour.
    assert hour_file_name(utc(2026, 10, 20, 5)) == "2026-10-20-5.json.gz"


# Une heure à deux chiffres : rien à enlever, rien à ajouter.
def test_hour_file_name_two_digit_hour():
    assert hour_file_name(utc(2026, 10, 20, 23)) == "2026-10-20-23.json.gz"


# Minuit : l'heure 0 doit donner "-0", pas "-00" ni une chaîne vide.
def test_hour_file_name_midnight():
    assert hour_file_name(utc(2026, 10, 21, 0)) == "2026-10-21-0.json.gz"
