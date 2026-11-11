########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de tests/test_integration.py.
# Il n'est PAS destiné à être exécuté — il se trouve dans docs_french/ car son
# but est d'enseigner. Le fichier réel et « propre » (sans tous ces
# commentaires) est tests/test_integration.py, et c'est celui-là que pytest
# trouve et lance.
#
# Ce fichier suppose que vous avez déjà lu docs_french/test_extract_csv.py
# (comment on écrit un test avec pytest : test_, assert, fixtures) ainsi que
# docs_french/load_postgres.py et docs_french/load_neo4j.py (les chargeurs
# testés ici). Il se concentre sur ce qui est NOUVEAU.
#
# Test UNITAIRE ou test d'INTÉGRATION ?
#   - Un test unitaire vérifie UNE pièce, seule, sans rien d'externe
#     (par exemple is_bot("dependabot[bot]")).
#   - Un test d'intégration vérifie que PLUSIEURS pièces fonctionnent
#     ENSEMBLE, avec de VRAIS serveurs : ici, des événements -> extract_csv
#     -> fichiers CSV -> load_postgres et load_neo4j -> les deux bases.
# Les deux s'écrivent avec pytest ; ce qui change, c'est ce qu'il y a
# DANS le test : ici, de vraies bases de données.
########################################################################

"""Integration tests: load the same tiny data set into real PostgreSQL and Neo4j databases.

These tests need both servers running, so they're kept apart from the unit tests
(marker "integration") and don't run with a plain "python -m pytest".

Run with:
    ./run.sh -m pytest -m integration      # locally (passwords from secrets.sh)

The databases used are a separate test database on each side, never the
benchmark's "gharchive" or the pipeline's "gharchive24h":
    TEST_POSTGRES_DATABASE   default "gharchivetest" (created if missing)
    TEST_NEO4J_DATABASE      default "gharchivetest" (created if missing; in CI
                             "neo4j", the only database Neo4j Community allows)
"""

# json, os, Path : déjà vus. time sert ici à ATTENDRE Neo4j (voir
# wait_for_neo4j plus bas).
import json
import os
import time
from pathlib import Path

# psycopg (PostgreSQL), pytest et le pilote Neo4j : les mêmes que dans les
# chargeurs. On a besoin de pytest lui-même ici (et pas seulement de la
# commande) parce qu'on utilise pytest.mark et pytest.fixture.
import psycopg
import pytest
from neo4j import GraphDatabase
# sql : l'outil de psycopg pour construire du SQL en sécurité quand une
# partie de la requête est un NOM (de table, de base…), pas une valeur.
# Expliqué plus bas, dans ensure_test_databases.
from psycopg import sql

# Les trois scripts testés ensemble. Python les trouve grâce à la ligne
# `pythonpath = scripts` de pytest.ini (voir docs_french/test_extract_csv.py).
import extract_csv
import load_neo4j
import load_postgres

# ---------------------------------------------------------------------
# pytestmark : un nom SPÉCIAL que pytest reconnaît. Le marqueur qu'on y
# met s'applique à TOUS les tests du fichier d'un coup, sans avoir à
# écrire @pytest.mark.integration au-dessus de chacun.
#
# Avec `addopts = -m "not integration"` dans pytest.ini, un simple
# `python -m pytest` les ignore (« deselected ») ; il faut taper
# `python -m pytest -m integration` pour les lancer.
# ---------------------------------------------------------------------
pytestmark = pytest.mark.integration

# ---------------------------------------------------------------------
# os.environ.get("NOM", "défaut") : lit une variable d'environnement, et
# si elle n'existe pas, renvoie la valeur par défaut au lieu de planter
# (contrairement à os.environ["NOM"], qui lève une KeyError).
# Ainsi :
#   - sur votre ordinateur, sans rien faire : "gharchivetest" des deux côtés ;
#   - dans la CI, ci.yml définit TEST_NEO4J_DATABASE=neo4j (Neo4j
#     Community n'autorise qu'une base utilisateur, nommée "neo4j").
# ---------------------------------------------------------------------
POSTGRES_DATABASE = os.environ.get("TEST_POSTGRES_DATABASE", "gharchivetest")
NEO4J_DATABASE = os.environ.get("TEST_NEO4J_DATABASE", "gharchivetest")
# Les bases du projet que ces tests ne doivent JAMAIS toucher (chaque
# chargement VIDE la base avant de la remplir). Un ensemble (set) entre
# accolades, pour tester rapidement « ce nom est-il dedans ? ».
PROTECTED_DATABASES = {"gharchive", "gharchive24h"}

# ---------------------------------------------------------------------
# Les données de test : 8 événements inventés, avec seulement les champs
# que lit extract_csv.py. Ils réunissent TOUS les cas difficiles connus :
#   - Ana (1) et Bea (2) travaillent toutes les deux sur le repo 10 :
#     elles sont donc à 2 sauts (acteur -> repo -> acteur) ;
#   - Bea -> repo 20 apparaît DEUX fois : paire répétée, une seule connexion ;
#   - Carl (3) change de login ("carl" puis "carl-dev") : on doit garder
#     le plus récent ;
#   - dependabot[bot] : un bot, à exclure ;
#   - Dan (4) avec "repo": {} : repo vide, à ignorer.
# ---------------------------------------------------------------------
# Ana (1) and Bea (2) both work on repo 10; Bea also on 20; Carl (3) only on 30.
# Plus the known hard cases: a bot, an empty repo, a repeated pair and a renamed login.
EVENTS = [
    {"actor": {"id": 1, "login": "ana"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:00:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:01:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 20, "name": "bea/tool"}, "created_at": "2026-08-27T15:02:00Z"},
    {"actor": {"id": 2, "login": "bea"}, "repo": {"id": 20, "name": "bea/tool"}, "created_at": "2026-08-27T15:03:00Z"},
    {"actor": {"id": 3, "login": "carl"}, "repo": {"id": 30, "name": "carl/notes"}, "created_at": "2026-08-27T15:04:00Z"},
    {"actor": {"id": 3, "login": "carl-dev"}, "repo": {"id": 30, "name": "carl/notes"}, "created_at": "2026-08-27T15:05:00Z"},
    {"actor": {"id": 9, "login": "dependabot[bot]"}, "repo": {"id": 10, "name": "ana/project"}, "created_at": "2026-08-27T15:06:00Z"},
    {"actor": {"id": 4, "login": "dan"}, "repo": {}, "created_at": "2026-08-27T15:07:00Z"},
]
# Ce qu'on attend dans LES DEUX bases, sous forme d'ensembles de tuples
# (une ligne = un tuple). Pourquoi des ENSEMBLES ? Parce qu'une base de
# données ne garantit aucun ordre sans ORDER BY : comparer des ensembles
# vérifie « mêmes lignes », quel que soit l'ordre.
EXPECTED_ACTORS = {(1, "ana"), (2, "bea"), (3, "carl-dev")}
EXPECTED_REPOS = {(10, "ana/project"), (20, "bea/tool"), (30, "carl/notes")}
EXPECTED_PAIRS = {(1, 10), (2, 10), (2, 20), (3, 30)}


# Petite fonction auxiliaire : crée un pilote Neo4j avec les mêmes réglages
# que load_neo4j.py (même adresse, même utilisateur, même variable de mot
# de passe). Dans la CI, l'authentification est désactivée, donc la valeur
# du mot de passe est ignorée.
def neo4j_driver():
    return GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=(load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"]))


# ---------------------------------------------------------------------
# wait_for_neo4j : une BOUCLE D'ATTENTE avec délai maximal.
#
# Dans la CI, le conteneur Neo4j démarre en même temps que les étapes,
# mais met quelques secondes à accepter les connexions. Au lieu d'échouer
# tout de suite, on réessaie toutes les 2 secondes, pendant 90 secondes
# au plus.
#
# time.monotonic() : une horloge qui ne fait qu'avancer (elle ne recule
# pas si quelqu'un change l'heure de l'ordinateur) ; parfaite pour
# mesurer un délai. deadline = « maintenant + 90 secondes ».
# ---------------------------------------------------------------------
def wait_for_neo4j(timeout_seconds: int = 90) -> None:
    # In CI the Neo4j container takes a few seconds to start accepting connections.
    deadline = time.monotonic() + timeout_seconds
    # while True : une boucle « infinie » dont on sort par return (succès)
    # ou par raise (abandon).
    while True:
        # try / except : « essaie ceci ; si une erreur arrive, fais cela ».
        try:
            with neo4j_driver() as driver:
                driver.verify_connectivity()
            # Connexion réussie : on sort de la fonction.
            return
        except Exception:
            # Délai dépassé : `raise` tout seul RELANCE l'erreur qu'on vient
            # d'attraper, pour que le test échoue avec le vrai message.
            if time.monotonic() > deadline:
                raise
            # Sinon, on patiente 2 secondes et on recommence.
            time.sleep(2)


# ---------------------------------------------------------------------
# ensure_test_databases : crée les bases de test si elles n'existent pas.
# ---------------------------------------------------------------------
def ensure_test_databases() -> None:
    # On se connecte à la base "postgres" (elle existe toujours) pour
    # pouvoir CRÉER une autre base. autocommit=True est obligatoire :
    # PostgreSQL refuse CREATE DATABASE à l'intérieur d'une transaction,
    # et psycopg en ouvre une par défaut.
    #
    # **load_postgres.POSTGRES_SETTINGS « déplie » le dictionnaire
    # {"host": "localhost", "user": "postgres"} en arguments nommés.
    with psycopg.connect(**load_postgres.POSTGRES_SETTINGS, dbname="postgres", autocommit=True) as conn:
        # pg_database : la table système qui liste les bases. %s est un
        # paramètre (une VALEUR), passé à part : jamais collé dans le texte.
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (POSTGRES_DATABASE,)).fetchone() is None:
            # Un NOM de base ne peut pas être un paramètre %s. On construit
            # donc la requête avec sql.SQL et sql.Identifier, qui met le nom
            # entre guillemets correctement : impossible d'injecter du SQL
            # par le nom.
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(POSTGRES_DATABASE)))
    # "neo4j" always exists; any other name needs CREATE DATABASE (Enterprise Edition only).
    # Côté Neo4j : la commande s'envoie à la base "system". IF NOT EXISTS
    # évite l'erreur si elle existe déjà ; WAIT attend qu'elle soit prête.
    # Dans la CI (Community), on utilise "neo4j", qui existe déjà : pas de
    # CREATE DATABASE, que Community ne connaît pas.
    if NEO4J_DATABASE != "neo4j":
        with neo4j_driver() as driver:
            driver.execute_query(f"CREATE DATABASE `{NEO4J_DATABASE}` IF NOT EXISTS WAIT", database_="system")


# Charge les CSV dans les deux bases et renvoie un tuple de deux booléens :
# (PostgreSQL correspond à ses CSV ?, Neo4j correspond à ses CSV ?).
# Ce sont exactement les fonctions load() qu'utilise la pipeline.
def load_both(csv_dir: Path) -> tuple[bool, bool]:
    return load_postgres.load(csv_dir, POSTGRES_DATABASE), load_neo4j.load(csv_dir, NEO4J_DATABASE)


# Lance une requête SQL et renvoie ses lignes sous forme d'ENSEMBLE de
# tuples. fetchall() renvoie déjà une liste de tuples ; set(...) la
# transforme en ensemble.
def postgres_rows(query: str) -> set[tuple]:
    with psycopg.connect(**load_postgres.POSTGRES_SETTINGS, dbname=POSTGRES_DATABASE) as conn:
        return set(conn.execute(query).fetchall())


# La même chose pour Neo4j. **params récupère les arguments nommés
# (par exemple id=1) dans un dictionnaire, envoyé comme paramètres $id.
# Un « record » Neo4j est une ligne de résultat ; record.values() donne
# ses valeurs dans l'ordre du RETURN, qu'on transforme en tuple : ainsi
# les résultats Neo4j ont la même forme que ceux de PostgreSQL et on peut
# les comparer directement.
def neo4j_rows(query: str, **params) -> set[tuple]:
    with neo4j_driver() as driver:
        records, _, _ = driver.execute_query(query, params, database_=NEO4J_DATABASE)
    return {tuple(record.values()) for record in records}


# ---------------------------------------------------------------------
# FIXTURES avec scope="module".
#
# Par défaut, une fixture est préparée À NOUVEAU pour chaque test. Ici,
# ce serait lent (charger les deux bases six fois). scope="module" veut
# dire : une seule fois pour tout le FICHIER ; les six tests reçoivent
# le même résultat.
#
# tmp_path_factory : la version de tmp_path utilisable dans une fixture
# de portée "module" (tmp_path, lui, est propre à chaque test).
# mktemp("integration") crée un dossier temporaire neuf.
# ---------------------------------------------------------------------
@pytest.fixture(scope="module")
def csv_dir(tmp_path_factory) -> Path:
    # Safety guard: these tests empty the databases they load into.
    # Le garde-fou : si quelqu'un a mis "gharchive" ou "gharchive24h" dans
    # les variables d'environnement, le test s'arrête ICI, avant de toucher
    # quoi que ce soit. Le texte après la virgule est le message affiché.
    # {POSTGRES_DATABASE!r} : !r affiche la valeur avec ses guillemets.
    assert POSTGRES_DATABASE not in PROTECTED_DATABASES, f"refusing to use {POSTGRES_DATABASE!r}"
    assert NEO4J_DATABASE not in PROTECTED_DATABASES, f"refusing to use {NEO4J_DATABASE!r}"

    # On écrit les 8 événements (une ligne JSON par événement), puis on
    # lance la VRAIE extraction et la VRAIE écriture des CSV.
    folder = tmp_path_factory.mktemp("integration")
    events_file = folder / "events.json"
    events_file.write_text("".join(json.dumps(event) + "\n" for event in EVENTS), encoding="utf-8")
    actors, repos, pairs, _ = extract_csv.extract([events_file])
    extract_csv.write_all(folder, actors, repos, pairs)

    # Avant de charger : Neo4j doit répondre, et les bases de test exister.
    wait_for_neo4j()
    ensure_test_databases()
    return folder


# Une fixture peut DÉPENDRE d'une autre : il suffit de mettre son nom en
# paramètre. Ici, `loaded` reçoit le dossier préparé par `csv_dir`.
# pytest les prépare dans le bon ordre : d'abord csv_dir, puis loaded.
@pytest.fixture(scope="module")
def loaded(csv_dir) -> tuple[bool, bool]:
    # Loaded once and shared by the tests below, which only read.
    return load_both(csv_dir)


# Test 1 : les deux chargements renvoient True (leurs comptages
# correspondent aux CSV). Le tuple (True, True) est « déballé » dans deux
# variables.
def test_both_loads_match_their_csv_files(loaded):
    postgres_ok, neo4j_ok = loaded
    assert postgres_ok
    assert neo4j_ok


# Tests 2 à 4 : les deux bases contiennent EXACTEMENT les mêmes lignes,
# et ce sont celles attendues. Le paramètre `loaded` n'est pas utilisé
# dans le corps : on le demande seulement pour que le chargement soit
# fait AVANT le test.
def test_both_databases_hold_the_same_actors(loaded):
    assert postgres_rows("SELECT id, login FROM actor") == EXPECTED_ACTORS
    assert neo4j_rows("MATCH (a:Actor) RETURN a.id, a.login") == EXPECTED_ACTORS


def test_both_databases_hold_the_same_repos(loaded):
    assert postgres_rows("SELECT id, name FROM repo") == EXPECTED_REPOS
    assert neo4j_rows("MATCH (r:Repo) RETURN r.id, r.name") == EXPECTED_REPOS


def test_both_databases_hold_the_same_connections(loaded):
    assert postgres_rows("SELECT actor_id, repo_id FROM actor_repo") == EXPECTED_PAIRS
    assert neo4j_rows("MATCH (a:Actor)-[:INTERACTED_WITH]->(r:Repo) RETURN a.id, r.id") == EXPECTED_PAIRS


# ---------------------------------------------------------------------
# Test 5 : la même question de TRAVERSÉE à 2 sauts, dans les deux modèles.
# « Qui a travaillé sur un repo où Ana (1) a aussi travaillé ? »
#
# En SQL : une AUTO-JOINTURE (self-join). La même table actor_repo est
# utilisée deux fois, sous deux alias :
#   - mine  = les lignes d'Ana (ses repos) ;
#   - other = les autres lignes qui ont le MÊME repo_id.
# DISTINCT enlève les doublons ; other.actor_id <> 1 exclut Ana elle-même.
#
# En Cypher : on DESSINE le chemin acteur -> repo <- acteur. Les flèches
# suivent les relations, sans jointure explicite : c'est l'adjacence
# sans index du modèle graphe. $id est un paramètre, passé avec id=1.
#
# Avant de mesurer la VITESSE dans le benchmark, il faut être sûr que les
# deux modèles donnent la MÊME réponse : c'est ce que vérifie ce test.
# ---------------------------------------------------------------------
def test_same_traversal_answer_on_both_sides(loaded):
    # Who worked on a repo that Ana (1) also worked on? Two hops: actor -> repo -> actor.
    postgres_answer = postgres_rows("""
        SELECT DISTINCT other.actor_id
        FROM actor_repo AS mine
        JOIN actor_repo AS other ON other.repo_id = mine.repo_id
        WHERE mine.actor_id = 1 AND other.actor_id <> 1
    """)
    neo4j_answer = neo4j_rows("""
        MATCH (:Actor {id: $id})-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(other:Actor)
        WHERE other.id <> $id
        RETURN DISTINCT other.id
    """, id=1)
    # Comparaison ENCHAÎNÉE : a == b == c veut dire (a == b) et (b == c).
    # {(2,)} : un ensemble contenant un tuple d'UN élément (la virgule est
    # obligatoire) : Bea, id 2.
    assert postgres_answer == neo4j_answer == {(2,)}


# ---------------------------------------------------------------------
# Test 6 : l'IDEMPOTENCE. Une opération idempotente donne le même
# résultat qu'on la lance une fois ou plusieurs fois. Chaque chargement
# commence par vider la base, donc un second chargement ne doit RIEN
# dupliquer : toujours 4 connexions, pas 8.
# Ce test dépend aussi de `loaded` : le second chargement arrive bien
# APRÈS le premier.
# ---------------------------------------------------------------------
def test_loading_twice_gives_the_same_result(loaded, csv_dir):
    # Each load starts from empty tables/graph, so a second run must not duplicate anything.
    assert load_both(csv_dir) == (True, True)
    # count(*) renvoie une seule ligne d'une seule valeur : {(4,)}.
    assert postgres_rows("SELECT count(*) FROM actor_repo") == {(len(EXPECTED_PAIRS),)}
    assert neo4j_rows("MATCH ()-[e:INTERACTED_WITH]->() RETURN count(e)") == {(len(EXPECTED_PAIRS),)}
