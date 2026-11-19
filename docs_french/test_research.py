########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de tests/test_research.py.
# Il n'est PAS destiné à être exécuté — il se trouve dans docs_french/ car
# son but est d'enseigner, pas de s'exécuter (pytest ne cherche des tests
# que dans tests/, comme l'indique pytest.ini). Le fichier réel et
# « propre » (sans tous ces commentaires) est tests/test_research.py.
#
# Lisez d'abord ces fichiers ; ce qu'ils expliquent n'est PAS répété ici :
#   - docs_french/test_extract_csv.py   les bases de pytest (le nom test_,
#                                       assert, comment lancer les tests)
#   - docs_french/test_pipeline.py      les petites fonctions d'aide dans
#                                       un fichier de tests, les arguments
#                                       nommés
#   - les trois scripts testés : docs_french/choose_starts.py,
#     docs_french/traversal.py et docs_french/measure.py
#
# Ce qui est NOUVEAU ici : pytest.raises (vérifier qu'une fonction REFUSE
# une mauvaise entrée), tester qu'un résultat ne dépend PAS de l'ordre
# des données d'entrée, et deux FIXTURES de pytest, tmp_path et
# monkeypatch (dans le dernier test). Les tests servent aussi de
# description précise, et exécutable, des règles de la recherche : quels
# acteurs sont choisis, à quoi ressemblent les textes Cypher, dans quel
# ordre les côtés tournent, comment les chiffres d'un côté sont résumés,
# qui compte comme le plus rapide, et la forme et le nom des fichiers CSV
# de résultats.
#
# Son rôle dans le projet : vérifier la logique propre aux scripts de la
# recherche — les parties qui n'ont besoin d'aucune base de données —
# pour qu'une erreur dans une règle soit repérée en une seconde, et non
# après des heures de mesure.
#
# Comment lancer les vrais tests :   python -m pytest
########################################################################

"""Unit tests for the research scripts' own logic (no network, no databases).

choose_starts.py (which actors), traversal.py (the query texts) and
measure.py (the order of the sides, the data window, the comparison).

Run with:  python -m pytest
"""

# Cette fois, on importe pytest lui-même (les fichiers de tests précédents
# n'en avaient pas besoin) : uniquement pour pytest.raises, dans les tests
# de traversal plus bas.
import pytest

# ---------------------------------------------------------------------
# Les fonctions testées. `from measure import ...` fonctionne parce que
# pytest.ini ajoute scripts/ au chemin de recherche de Python
# (pythonpath = scripts). Ce sont toutes des fonctions PURES — de
# simples données en entrée, de simples données en sortie — elles peuvent
# donc être testées sans que PostgreSQL ni Neo4j ne tournent. Outcome (le
# résultat d'une exécution, docs_french/traversal.py) est importé pour
# fabriquer de fausses exécutions.
# ---------------------------------------------------------------------
from choose_starts import choose, pick_median, pick_top
from measure import compare, data_window, run_order, side_summary, sides
from traversal import Outcome, cypher_hops, cypher_reach, sql_joins


# ---------------------------------------------------------------------
# Une fonction d'aide (pas un test : pas de préfixe test_) qui construit
# un faux acteur sous forme de dictionnaire, avec les mêmes clés que les
# vrais (voir choose_starts.py) :
#   reached   combien d'autres acteurs il atteint en un saut
#   repos     avec combien de dépôts il a interagi
# `login=None` + `login or f"user{actor_id}"` : si aucun login n'est
# donné, en inventer un (« user7 »). `or` donne le côté droit quand le
# gauche vaut None.
# ---------------------------------------------------------------------
def actor(actor_id, reached, repos, login=None):
    return {"actor_id": actor_id, "login": login or f"user{actor_id}", "reached": reached, "repos": repos}


# ---------- choose_starts: the top group ----------

# Le groupe top, ce sont « les acteurs qui en atteignent le plus
# d'autres », du plus grand au plus petit.
def test_top_is_ordered_by_actors_reached():
    actors = [actor(1, 2, 1), actor(2, 9, 1), actor(3, 5, 1)]
    # La compréhension de liste ne garde que les identifiants, pour
    # comparer l'ORDRE : 9 atteints (id 2), puis 5 (id 3), puis 2 (id 1).
    assert [a["actor_id"] for a in pick_top(actors, size=3)] == [2, 3, 1]


# Les égalités doivent être départagées par une règle fixe, sinon le
# choix pourrait changer d'une exécution à l'autre (ou entre PostgreSQL et
# Neo4j).
def test_top_tie_is_broken_by_more_repos_then_smaller_id():
    actors = [actor(30, 5, 1), actor(20, 5, 4), actor(10, 5, 1)]
    # same "reached": 20 has more repos; then 10 before 30 (smaller id)
    assert [a["actor_id"] for a in pick_top(actors, size=3)] == [20, 10, 30]


# Sans size=..., la taille de groupe par défaut (10) s'applique.
def test_top_keeps_only_ten():
    actors = [actor(i, i, 1) for i in range(1, 30)]
    assert len(pick_top(actors)) == 10


# ---------- choose_starts: the median group ----------

# Le groupe « median », ce sont les acteurs TYPIQUES : ceux dont le
# « reached » est le plus proche de la médiane. Les acteurs qui
# n'atteignent personne (reached = 0) sont d'abord écartés : lancer un
# parcours à partir d'eux ne mesurerait rien.
def test_median_leaves_out_actors_that_reach_nobody():
    actors = [actor(1, 0, 1), actor(2, 0, 1), actor(3, 2, 1), actor(4, 2, 1), actor(5, 2, 1)]
    chosen = pick_median(actors, exclude=set(), size=3)
    # Une compréhension d'ENSEMBLE { } — l'ordre n'a pas d'importance ici,
    # seulement quels identifiants ont été choisis. Comparer deux
    # ensembles ne tient pas compte de l'ordre.
    assert {a["actor_id"] for a in chosen} == {3, 4, 5}


def test_median_takes_the_closest_to_the_median():
    # reached 1..9 -> median 5; closest: 5, then 4 and 6 (tie: more repos first, then id)
    actors = [actor(i, i, 1) for i in range(1, 10)]
    # La position 5 de la liste (en comptant à partir de 0) est l'acteur
    # d'id 6. Il est remplacé par le même acteur avec 3 dépôts, pour qu'il
    # gagne l'égalité contre l'id 4 (tous deux sont à 1 de la médiane).
    actors[5] = actor(6, 6, 3)
    chosen = pick_median(actors, exclude=set(), size=3)
    assert [a["actor_id"] for a in chosen] == [5, 6, 4]


# exclude= les identifiants déjà dans le groupe top : un acteur n'est
# jamais dans les deux.
def test_median_never_repeats_a_top_actor():
    actors = [actor(i, 3, 1) for i in range(1, 6)]
    chosen = pick_median(actors, exclude={1, 2}, size=5)
    assert {a["actor_id"] for a in chosen} == {3, 4, 5}


# ---------------------------------------------------------------------
# choose() réunit les deux groupes, sous forme d'une liste de lignes.
# ["top"] * 10 + ["median"] * 10 — `*` répète une liste, `+` en relie
# deux : dix « top » suivis de dix « median ». Les rangs repartent de 1
# dans chaque groupe : rows[0] est le premier acteur top, rows[10] le
# premier median. Avec reached = 1..30, l'acteur qui en atteint le plus
# est l'id 30.
# ---------------------------------------------------------------------
def test_choose_gives_groups_and_ranks():
    rows = choose([actor(i, i, 1) for i in range(1, 31)])
    assert [r["group"] for r in rows] == ["top"] * 10 + ["median"] * 10
    assert rows[0]["rank"] == 1 and rows[0]["actor_id"] == 30
    assert rows[10]["rank"] == 1


# ---------------------------------------------------------------------
# TESTER QUE L'ORDRE DES DONNÉES D'ENTRÉE N'A PAS D'IMPORTANCE
#
# Les acteurs viennent d'une requête sur une base de données, et les
# bases de données ne promettent aucun ordre particulier des lignes. Si
# le choix en dépendait, la même base pourrait donner des acteurs de
# départ différents d'un jour à l'autre. Le test donne donc à choose() les
# mêmes acteurs dans deux ordres opposés et exige exactement le même
# résultat. `i % 7` et `i % 3` (des restes) créent volontairement
# beaucoup d'égalités, pour mettre à l'épreuve la règle de départage.
# ---------------------------------------------------------------------
def test_choose_is_the_same_whatever_the_input_order():
    # PostgreSQL and Neo4j return rows in different orders; the choice must not depend on it.
    actors = [actor(i, i % 7, i % 3) for i in range(1, 50)]
    assert choose(actors) == choose(list(reversed(actors)))


# ---------- traversal: the query texts ----------

# cypher_reach(3, "paths") doit contenir le motif de longueur variable
# {1,3} (« de 1 à 3 sauts ») et le paramètre $start. `"..." in text` vaut
# True si le morceau apparaît n'importe où dans le texte.
def test_cypher_paths_writes_the_depth_into_the_pattern():
    assert "{1,3}" in cypher_reach(3, "paths")
    assert "$start" in cypher_reach(3, "paths")


# ---------------------------------------------------------------------
# La version « levels » colle une ÉTAPE par saut (voir
# docs_french/traversal.py). text.count("morceau") dit combien de fois
# le morceau apparaît : profondeur 4 -> exactement 4 sous-requêtes CALL.
# Le second assert vérifie que l'étape écarte bien les acteurs déjà vus,
# et que le départ est toujours un paramètre.
# ---------------------------------------------------------------------
def test_cypher_levels_has_one_step_per_hop():
    query = cypher_reach(4, "levels")
    assert query.count("CALL (seen, frontier)") == 4
    assert "NOT b IN seen" in query and "$start" in query


# ---------------------------------------------------------------------
# pytest.raises — TESTER QUE QUELQUE CHOSE ÉCHOUE
#
# Parfois, le bon comportement EST une erreur : une profondeur de 0 n'a
# pas de sens, et cypher_reach doit la refuser avec une ValueError plutôt
# que de construire une requête cassée. De même pour un nom de version
# qu'elle ne connaît pas.
#     with pytest.raises(ValueError):
#         <code>
# signifie « le code à l'intérieur doit lever une ValueError ». S'il le
# fait, pytest l'attrape et le test RÉUSSIT. S'il ne lève rien (ou une
# erreur d'un autre type), le test ÉCHOUE. Chaque bloc `with` vérifie UN
# SEUL appel : la première erreur termine son bloc.
# ---------------------------------------------------------------------
def test_cypher_refuses_depth_zero_and_unknown_versions():
    with pytest.raises(ValueError):
        cypher_reach(0)
    with pytest.raises(ValueError):
        cypher_reach(2, "shortcut")


# Un saut = 2 jointures en SQL, 2 relations en Cypher : profondeur 3 -> 6
# de chaque (les colonnes joins_or_hops du CSV de résultats).
def test_joins_and_hops_are_two_per_depth():
    assert sql_joins(3) == 6 and cypher_hops(3) == 6


# ---------- measure ----------

# --cypher both -> PostgreSQL et les deux versions Cypher ; --cypher
# levels -> PostgreSQL et cette version seulement. PostgreSQL vient
# toujours en premier.
def test_sides_are_postgresql_then_the_cypher_versions():
    assert sides("both") == ["postgresql", "neo4j-paths", "neo4j-levels"]
    assert sides("levels") == ["postgresql", "neo4j-levels"]


# ---------------------------------------------------------------------
# La règle d'équité de measure.py (voir docs_french/measure.py,
# run_order) : les côtés TOURNENT, pour que chaque répétition commence
# par un côté différent. Avec trois côtés, la répétition 4 revient au
# point de départ (la rotation a fait un tour complet) ; avec deux côtés,
# ils alternent simplement.
# ---------------------------------------------------------------------
def test_run_order_changes_which_side_goes_first():
    three = ["postgresql", "neo4j-paths", "neo4j-levels"]
    assert run_order(three, 1) == three
    assert run_order(three, 2) == ["neo4j-paths", "neo4j-levels", "postgresql"]
    assert run_order(three, 4) == three
    assert run_order(["postgresql", "neo4j-paths"], 2) == ["neo4j-paths", "postgresql"]


# ---------------------------------------------------------------------
# data_window lit la fenêtre de temps des données dans le NOM de la base :
#   ...-2026-10-08-9-24h   à partir de 09:00, 24 heures -> se termine le
#                          lendemain à 09:00
#   ...-2026-10-08-23      pas de partie « -<n>h » : UNE heure, de 23:00 à
#                          00:00 le lendemain (la date change aussi)
#   gharchive24h           pas un nom que build_hours.py fabrique : des
#                          valeurs vides, pas un plantage
# ---------------------------------------------------------------------
def test_data_window_is_read_from_the_database_name():
    assert data_window("gharchive-2026-10-08-9-24h") == ("2026-10-08 09:00", "2026-10-09 09:00", 24)
    assert data_window("gharchive-2026-10-08-23") == ("2026-10-08 23:00", "2026-10-09 00:00", 1)
    assert data_window("gharchive24h") == ("", "", None)


# Une fonction d'aide : les deux clés que compare() lit sur un côté qui a
# fini.
def finished(time_s):
    return {"status": "finished", "time_s": time_s}


# PostgreSQL 0.4 s, Neo4j 0.1 s -> Neo4j, 0.4 / 0.1 = 4 fois plus rapide.
# Et dans l'autre sens : 0.5 / 0.1 = 5 fois, PostgreSQL plus rapide.
def test_compare_says_who_was_faster_and_how_many_times():
    assert compare(finished(0.4), finished(0.1), 60) == ("neo4j", 4.0)
    assert compare(finished(0.1), finished(0.5), 60) == ("postgresql", 5.0)


# ---------------------------------------------------------------------
# Quand un côté n'a pas fini, son temps est inconnu — mais il vaut au
# moins la limite de temps. Donc times_faster = limite / le temps de
# l'autre côté est un MINIMUM (« au moins 30 fois »). Quand aucun des
# deux n'a fini : « neither » (aucun), et pas de nombre du tout (None).
# ---------------------------------------------------------------------
def test_compare_with_a_timeout_gives_a_minimum():
    # Neo4j didn't finish in 60 s: PostgreSQL was at least 60 / 2 = 30 times faster.
    assert compare(finished(2.0), {"status": "timeout"}, 60) == ("postgresql", 30.0)
    assert compare({"status": "timeout"}, {"status": "skipped (timed out at a smaller depth)"}, 60) == ("neither", None)


# ---------------------------------------------------------------------
# Une fonction d'aide qui construit une exécution chronométrée telle que
# timed_run() de measure.py la renvoie : l'Outcome
# (docs_french/traversal.py), les secondes de CPU utilisées par le
# serveur de base de données, et le niveau d'occupation de tout
# l'ordinateur. Les valeurs par défaut décrivent une exécution
# ordinaire : 0.1 s de CPU, ordinateur à 10 %.
# ---------------------------------------------------------------------
def run(seconds, cpu_s=0.1, machine_cpu=10.0):
    return {"outcome": Outcome("ok", seconds, 7), "cpu_s": cpu_s, "machine_cpu": machine_cpu}


# ---------------------------------------------------------------------
# La première exécution a pris 9 s (le plan est en cours de
# préparation). Elle est rapportée dans first_run_s, mais PAS utilisée
# pour le temps : les exécutions chronométrées sont 0.2, 0.4, 0.3 s ->
# médiane 0.3. Leurs secondes de CPU sont 0.1, 0.4, 0.3 -> médiane 0.3,
# et cores_used = 0.3 / 0.3 = 1.0 (un cœur occupé pendant toute
# l'exécution). Les chiffres de travail ({"memory_mb": 1.5}) sont
# recopiés tels quels.
# ---------------------------------------------------------------------
def test_side_summary_uses_the_median_and_ignores_the_first_run():
    summary = side_summary(Outcome("ok", 9.0, 7), [run(0.2), run(0.4, 0.4), run(0.3, 0.3)], {"memory_mb": 1.5}, "finished")
    assert summary["time_s"] == 0.3 and summary["first_run_s"] == 9.0
    assert summary["cpu_s"] == 0.3 and summary["cores_used"] == 1.0
    assert summary["memory_mb"] == 1.5


# ---------------------------------------------------------------------
# Les deux règles « pas fiable » (voir side_summary dans
# docs_french/measure.py), plus un cas qui ne doit être ni l'un ni
# l'autre :
#   0.1 s et 0.5 s            écart de 5x, au-dessus de 3x  -> noisy
#                                                    (bruité)
#   0.1 s deux fois, CPU 95 % ordinateur occupé, au-dessus de 80 %
#                                                 -> busy (occupé)
#   0.1 s et 0.12 s           1.2x, CPU 10 %                -> calme
# `assert not x` — réussit quand x vaut False.
# ---------------------------------------------------------------------
def test_side_summary_flags_noisy_or_busy_runs():
    assert side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.5)], {}, "finished")["noisy"]          # 5x spread
    assert side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.1, machine_cpu=95)], {}, "finished")["busy"]
    calm = side_summary(Outcome("ok", 1, 7), [run(0.1), run(0.12)], {}, "finished")
    assert not calm["noisy"] and not calm["busy"]


# ---------------------------------------------------------------------
# LA FORME D'UN CSV DE RÉSULTATS
#
# L'utilisateur a demandé cette disposition : d'abord les informations
# du test, puis un bloc PostgreSQL et un bloc Neo4j avec les MÊMES
# colonnes, côte à côte, puis la comparaison. Ce test garantit que la
# disposition ne peut pas dériver :
#
# 1. from measure import ... À L'INTÉRIEUR de la fonction : un import
#    peut s'écrire n'importe où ; ici, il garde ces trois noms à côté du
#    seul test qui en a besoin.
#
# 2. COLUMNS[:len(TEST_COLUMNS)] == TEST_COLUMNS
#    Les premières colonnes sont exactement celles du test, dans l'ordre.
#
# 3. pg = [c[len("pg_"):] for c in COLUMNS if c.startswith("pg_")]
#    Chaque colonne qui commence par « pg_ », avec ce préfixe coupé
#    (c[3:] = le texte à partir de la position 3 : « pg_time_s » ->
#    « time_s »). Pareil pour « neo4j_ ». `pg == neo4j == SIDE_COLUMNS`
#    est une comparaison EN CHAÎNE : les deux doivent être égales à
#    SIDE_COLUMNS, donc les deux blocs contiennent les mêmes colonnes
#    DANS LE MÊME ORDRE.
#
# 4. Le dernier assert vérifie que les blocs sont côte à côte : la
#    première colonne Neo4j vient JUSTE APRÈS la dernière colonne
#    PostgreSQL (sa position, .index(), est plus grande de un), donc
#    aucune autre colonne ne se glisse entre les deux.
# ---------------------------------------------------------------------
def test_results_columns_are_the_test_then_two_identical_blocks():
    from measure import COLUMNS, SIDE_COLUMNS, TEST_COLUMNS
    assert COLUMNS[:len(TEST_COLUMNS)] == TEST_COLUMNS
    pg = [c[len("pg_"):] for c in COLUMNS if c.startswith("pg_")]
    neo4j = [c[len("neo4j_"):] for c in COLUMNS if c.startswith("neo4j_")]
    assert pg == neo4j == SIDE_COLUMNS
    assert COLUMNS.index("neo4j_" + SIDE_COLUMNS[0]) == COLUMNS.index("pg_" + SIDE_COLUMNS[-1]) + 1


# ---------------------------------------------------------------------
# UN FICHIER PAR MESURE, ET RÉUTILISER LES DERNIERS ACTEURS
#
# L'utilisateur voulait que chaque analyse laisse exactement UN SEUL
# CSV, facile à ouvrir et à comprendre. Ce test vérifie les deux règles
# qui vont avec : le NOM du fichier, et le fait que les acteurs de
# départ sont pris dans le DERNIER fichier de la base.
#
# FIXTURES — tmp_path et monkeypatch entre les parenthèses
#   Quand une fonction de test a des paramètres portant ces noms
#   spéciaux, pytest les PRÉPARE et les lui passe (une « fixture ») :
#   tmp_path     un nouveau dossier temporaire VIDE (un Path), différent
#                pour chaque test et nettoyé par pytest. Le test peut y
#                écrire des fichiers sans toucher au vrai results/.
#   monkeypatch  un outil pour changer quelque chose TEMPORAIREMENT :
#                monkeypatch.setattr(measure, "RESULTS_DIR", tmp_path)
#                remplace measure.RESULTS_DIR par le dossier temporaire
#                pendant la durée de ce test seulement ; pytest remet la
#                vraie valeur ensuite. Ainsi, results_file() et
#                previous_starts() cherchent dans le dossier temporaire.
#
# Les imports sont écrits à l'intérieur du test : `import measure` (le
# module entier, pour que son RESULTS_DIR puisse être remplacé), csv et
# datetime.
#
# 1. results_file(...) avec 2026-11-19 10:30:00 doit donner le nom
#    « <base>_2026-11-19_10-30-00.csv » (.name : le nom du fichier seul,
#    sans le dossier).
# 2. Dans le dossier encore vide, previous_starts() ne trouve aucun
#    fichier : [].
# 3. Deux faux fichiers de mesure sont écrits avec csv.DictWriter (voir
#    docs_french/measure.py), l'un du 18 novembre avec l'acteur 1, l'autre
#    du 19 novembre avec l'acteur 2. Chacun contient l'en-tête et UNE
#    SEULE ligne ; les colonnes non fournies restent vides.
# 4. previous_starts() doit renvoyer l'acteur du DERNIER fichier
#    seulement : [2]. (Les noms de fichiers se trient dans l'ordre du
#    temps, voir results_file().)
# ---------------------------------------------------------------------
def test_each_measurement_gets_its_own_file_and_reuses_the_latest_actors(tmp_path, monkeypatch):
    import csv
    from datetime import datetime

    import measure
    monkeypatch.setattr(measure, "RESULTS_DIR", tmp_path)
    path = measure.results_file("gharchive-2026-10-08-9-24h", datetime(2026, 11, 19, 10, 30, 0))
    assert path.name == "gharchive-2026-10-08-9-24h_2026-11-19_10-30-00.csv"
    assert measure.previous_starts("gharchive-2026-10-08-9-24h") == []

    for name, actor_id in (("2026-11-18_09-00-00", 1), ("2026-11-19_10-30-00", 2)):
        with open(tmp_path / f"gharchive-2026-10-08-9-24h_{name}.csv", "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=measure.COLUMNS)
            writer.writeheader()
            writer.writerow({"database": "gharchive-2026-10-08-9-24h", "start_group": "top", "start_rank": 1,
                             "start_actor_id": actor_id, "start_login": "x", "start_reach_1_hop": 3})
    # The latest measurement wins.
    assert [a["actor_id"] for a in measure.previous_starts("gharchive-2026-10-08-9-24h")] == [2]
