########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de
# tests/test_drop_databases.py. Il n'est PAS destiné à être exécuté — il
# se trouve dans docs_french/ car son but est d'enseigner, pas de
# s'exécuter (pytest ne cherche les tests que dans tests/, comme le dit
# pytest.ini). Le fichier réel et « propre » (sans tous ces commentaires)
# est tests/test_drop_databases.py.
#
# Lisez d'abord docs_french/test_extract_csv.py (les bases de pytest :
# les noms test_, assert, comment lancer les tests) et
# docs_french/drop_databases.py (le script testé). Ils ne sont PAS
# répétés ici. Ce fichier se concentre sur ce qui est NOUVEAU : vérifier
# qu'une fonction LÈVE une erreur, avec pytest.raises(), et tester des
# RÈGLES DE SÉCURITÉ — ce qui ne doit JAMAIS arriver — plutôt que ce qui
# devrait arriver.
#
# Son rôle dans le projet : drop_databases.py supprime des bases de
# données définitivement. Ces tests prouvent, sans aucun serveur en
# marche, que sa règle sur les noms accepte toutes les sortes de bases du
# projet, rejette les bases propres aux serveurs (et celles qui leur
# ressemblent), et que les fonctions de suppression refusent une base de
# serveur AVANT même d'essayer de se connecter.
#
# Lancez les vrais tests avec :
#     python -m pytest
########################################################################

"""Unit tests for the safety rules of scripts/drop_databases.py (no network, no databases).

Run with:  python -m pytest
"""

# `import pytest` : nécessaire ici (contrairement à certains fichiers de
# tests précédents) car on utilise directement l'un de ses outils :
# pytest.raises (voir le dernier test).
import pytest

# Les quatre fonctions testées. is_project_database et project_databases
# sont pures. drop_postgres et drop_neo4j toucheraient normalement un
# serveur — mais seulement APRÈS leur garde, et c'est la garde qu'on
# teste ici.
from drop_databases import drop_neo4j, drop_postgres, is_project_database, project_databases


# ---------------------------------------------------------------------
# Un test pour chaque CÔTÉ de la règle : ce qui doit être accepté, et ce
# qui doit être refusé. Une boucle sur un tuple de noms vérifie plusieurs
# cas en un seul test. (Le tuple est réparti sur deux lignes ; entre
# parenthèses, Python laisse une ligne se poursuivre librement.)
# Les noms couvrent toutes les formes utilisées par le projet : la base
# du benchmark, celle des 24 heures en direct, une base par heure, une
# base par volume (« -6h ») et celle du test d'intégration.
# ---------------------------------------------------------------------
def test_project_databases_are_recognised():
    for name in ("gharchive", "gharchive24h", "gharchive-2026-08-27-15", "gharchive-2026-08-27-15-6h",
                 "gharchivetest"):
        assert is_project_database(name)


# Les bases propres aux serveurs, plus deux SOSIES : « myothers » (un nom
# sans rapport) et « archive » (contient une partie du mot mais ne
# commence pas par « gharchive »). `assert not ...` affirme que le
# résultat est False.
def test_server_databases_are_never_project_databases():
    for name in ("postgres", "template0", "template1", "neo4j", "system", "myothers", "archive"):
        assert not is_project_database(name)


# Une liste mélangée, telle qu'un serveur la renverrait, sans ordre
# particulier. Comparer avec == à la LISTE attendue vérifie à la fois le
# filtrage ET l'ordre. Notez que l'ordre est ALPHABÉTIQUE, caractère par
# caractère : « - » vient avant « 2 » dans la table des caractères, donc
# « gharchive-2026... » est classé avant « gharchive24h ».
def test_project_databases_picks_only_the_project_ones_sorted():
    names = ["postgres", "gharchive24h", "template1", "gharchive", "neo4j", "gharchive-2026-11-09-9-5h"]
    assert project_databases(names) == ["gharchive", "gharchive-2026-11-09-9-5h", "gharchive24h"]


# ---------------------------------------------------------------------
# NOUVEAU : pytest.raises — tester que quelque chose ÉCHOUE
#
#     with pytest.raises(ValueError, match="Refusing to delete"):
#         drop_postgres("postgres")
#
# se lit : « le code à l'intérieur de ce bloc `with` DOIT lever une
# ValueError dont le message contient 'Refusing to delete' ».
#   - Si c'est le cas, l'erreur est interceptée et le test continue
#     (il réussit).
#   - Si AUCUNE erreur n'est levée, le test ÉCHOUE (« DID NOT RAISE »).
#   - Si une erreur DIFFÉRENTE est levée, ou si le message ne correspond
#     pas, le test échoue aussi.
# match= est une expression régulière recherchée dans le message ; des
# mots simples comme ceux-ci signifient juste « contient ce texte ».
#
# Pourquoi cela prouve que la garde vient EN PREMIER : aucun serveur ne
# tourne pendant les tests unitaires. Si drop_postgres essayait de se
# connecter avant de vérifier le nom, il lèverait plutôt une erreur de
# connexion psycopg — une erreur différente, donc le test échouerait. Et
# drop_neo4j reçoit None au lieu d'un driver : s'il atteignait un jour
# driver.execute_query(...), il planterait avec une AttributeError.
# Obtenir exactement une ValueError montre que rien n'a été exécuté
# au-delà de la garde.
# ---------------------------------------------------------------------
def test_drop_refuses_server_databases_before_connecting_to_anything():
    # The check comes first, so this fails safely even with no server running.
    with pytest.raises(ValueError, match="Refusing to delete"):
        drop_postgres("postgres")
    with pytest.raises(ValueError, match="Refusing to delete"):
        drop_neo4j(None, "neo4j")
