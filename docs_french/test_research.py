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
#   - les quatre scripts testés : docs_french/choose_starts.py,
#     docs_french/measure.py, docs_french/traversal.py et
#     docs_french/analyze.py
#
# Ce qui est NOUVEAU ici : pytest.raises (vérifier qu'une fonction REFUSE
# une mauvaise entrée), et tester qu'un résultat ne dépend PAS de l'ordre
# des données d'entrée. Les tests servent aussi de description précise,
# et exécutable, des règles de la recherche : quels acteurs sont choisis,
# dans quel ordre les côtés tournent, et comment les temps sont résumés.
#
# Son rôle dans le projet : vérifier la logique propre aux scripts de la
# recherche — les parties qui n'ont besoin d'aucune base de données —
# pour qu'une erreur dans une règle soit repérée en une seconde, et non
# après des heures de mesure.
#
# Comment lancer les vrais tests :   python -m pytest
########################################################################

"""Unit tests for the research scripts' own logic (no network, no databases).

choose_starts.py (which actors), measure.py (the alternating order),
traversal.py (the Cypher text) and analyze.py (the summaries).

Run with:  python -m pytest
"""

# Cette fois, on importe pytest lui-même (les fichiers de tests précédents
# n'en avaient pas besoin) : uniquement pour pytest.raises, dans les tests
# de traversal plus bas.
import pytest

# ---------------------------------------------------------------------
# Les fonctions testées. `from analyze import ...` fonctionne parce que
# pytest.ini ajoute scripts/ au chemin de recherche de Python
# (pythonpath = scripts). Ce sont toutes des fonctions PURES — de
# simples données en entrée, de simples données en sortie — elles peuvent
# donc être testées sans que PostgreSQL ni Neo4j ne tournent.
# ---------------------------------------------------------------------
from analyze import summarise_actor, summary
from choose_starts import choose, pick_median, pick_top
from measure import run_order
from traversal import cypher_reach


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
# choose() réunit les deux groupes, sous forme des lignes de starts.csv.
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


# ---------- measure: alternating order ----------

# La règle d'équité de measure.py (voir docs_french/measure.py,
# run_order) : répétitions impaires, PostgreSQL d'abord ; répétitions
# paires, Neo4j d'abord.
def test_run_order_alternates_which_side_goes_first():
    assert run_order(1) == ("postgresql", "neo4j")
    assert run_order(2) == ("neo4j", "postgresql")
    assert run_order(3) == ("postgresql", "neo4j")


# ---------- traversal: the Cypher text ----------

# cypher_reach(3) doit contenir le motif de longueur variable {1,3}
# (« de 1 à 3 sauts ») et le paramètre $start. `"..." in text` vaut True
# si le morceau apparaît n'importe où dans le texte.
def test_cypher_reach_writes_the_depth_into_the_pattern():
    assert "{1,3}" in cypher_reach(3)
    assert "$start" in cypher_reach(3)


# ---------------------------------------------------------------------
# pytest.raises — TESTER QUE QUELQUE CHOSE ÉCHOUE
#
# Parfois, le bon comportement EST une erreur : une profondeur de 0 n'a
# pas de sens, et cypher_reach doit la refuser avec une ValueError plutôt
# que de construire une requête cassée.
#     with pytest.raises(ValueError):
#         <code>
# signifie « le code à l'intérieur doit lever une ValueError ». S'il le
# fait, pytest l'attrape et le test RÉUSSIT. S'il ne lève rien (ou une
# erreur d'un autre type), le test ÉCHOUE.
# ---------------------------------------------------------------------
def test_cypher_reach_refuses_depth_zero():
    with pytest.raises(ValueError):
        cypher_reach(0)


# ---------- analyze ----------

# ---------------------------------------------------------------------
# Une fonction d'aide qui construit une ligne de runs.csv telle que
# csv.DictReader la donnerait : chaque valeur est du TEXTE (str(...)),
# exactement comme dans le vrai fichier. Les valeurs par défaut décrivent
# une exécution ordinaire qui a fini : statut « ok », réponse « 7 », CPU
# à 10 %.
# ---------------------------------------------------------------------
def run(run_number, seconds, status="ok", count="7", cpu="10"):
    return {"run": str(run_number), "seconds": str(seconds), "status": status, "count": count,
            "machine_cpu_percent": cpu}


# ---------------------------------------------------------------------
# L'exécution 0 a pris 9 s (la première exécution, pendant laquelle le
# plan est préparé). Si elle était comptée, le max serait 9.0 et la
# médiane 0.35. En l'ignorant : les exécutions chronométrées sont 0.2,
# 0.4, 0.3 -> médiane 0.3, min 0.2, max 0.4, trois finies, et la réponse
# 7 (désormais un nombre, plus du texte).
# ---------------------------------------------------------------------
def test_summary_of_an_actor_ignores_the_first_run():
    result = summarise_actor([run(0, 9.0), run(1, 0.2), run(2, 0.4), run(3, 0.3)])
    assert result["median_s"] == 0.3 and result["min_s"] == 0.2 and result["max_s"] == 0.4
    assert result["finished"] == 3 and result["count"] == 7


# Seulement l'exécution 0, et elle a dépassé le délai (donc measure.py a
# sauté les répétitions) : le timeout doit quand même être compté, et il
# n'y a aucun temps.
def test_summary_of_an_actor_counts_timeouts():
    result = summarise_actor([run(0, 60, "timeout", "")])
    assert result["timeouts"] == 1 and result["median_s"] is None


# ---------------------------------------------------------------------
# Les deux règles de « bruit » (voir docs_french/analyze.py), plus un cas
# qui ne doit PAS être bruité :
#   0.1 s et 0.5 s            écart de 5x, au-dessus de 3x -> bruité
#   0.1 s deux fois, CPU 95 % ordinateur occupé, au-dessus de 80 %
#                                                         -> bruité
#   0.1 s et 0.12 s           1.2x, CPU 10 %              -> pas bruité
# `assert not x` — réussit quand x vaut False.
# ---------------------------------------------------------------------
def test_noisy_when_spread_is_large_or_computer_busy():
    assert summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.5)])["noisy"]          # 5x spread
    assert summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.1, cpu="95")])["noisy"]  # busy
    assert not summarise_actor([run(0, 1), run(1, 0.1), run(2, 0.12)])["noisy"]


# ---------------------------------------------------------------------
# Le rapport phare : médiane de PostgreSQL 0.4 s, de Neo4j 0.1 s, même
# groupe et même profondeur -> 0.4 / 0.1 = 4.0, « PostgreSQL 4 fois plus
# lent » (Neo4j plus rapide). Les lignes imitent la sortie de
# per_actor(). by_system : les lignes du résumé dans un dictionnaire dont
# la clé est le côté, pour prendre celle de PostgreSQL.
# ---------------------------------------------------------------------
def test_group_summary_gives_postgresql_vs_neo4j():
    rows = [
        {"group": "top", "actor_id": 1, "depth": 2, "system": "postgresql", "median_s": 0.4, "timeouts": 0,
         "errors": 0, "noisy": False},
        {"group": "top", "actor_id": 1, "depth": 2, "system": "neo4j", "median_s": 0.1, "timeouts": 0,
         "errors": 0, "noisy": False},
    ]
    by_system = {r["system"]: r for r in summary(rows)}
    assert by_system["postgresql"]["postgresql_vs_neo4j"] == 4.0
