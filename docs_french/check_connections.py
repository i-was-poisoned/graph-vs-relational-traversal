########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de
# scripts/check_connections.py. Il n'est PAS destiné à être exécuté dans
# le cadre du pipeline du projet — il se trouve dans docs_french/ car son
# but est d'enseigner, pas de s'exécuter. Le script réel et « propre »
# (sans tous ces commentaires) est scripts/check_connections.py.
#
# Ce fichier suppose que vous avez déjà lu les copies annotées
# précédentes — les imports, les fonctions, les f-strings, `with`, main()
# et la garde __name__ ne sont PAS réexpliqués depuis zéro ici. Ce
# fichier se concentre sur ce qui est NOUVEAU dans check_connections.py :
# les premiers paquets EXTERNES du projet (psycopg et neo4j), la lecture
# des mots de passe depuis des VARIABLES D'ENVIRONNEMENT, la connexion à
# un serveur de base de données, et la gestion des erreurs avec
# try/except pour qu'un échec ne masque pas l'autre vérification.
#
# Comment il est censé être lancé — toujours via run.sh :
#     ./run.sh scripts/check_connections.py
# run.sh active .venv (pour que `import psycopg` / `import neo4j`
# fonctionnent) et charge secrets.sh (pour que PGPASSWORD /
# NEO4J_PASSWORD existent). Ce script hérite des deux. Voir
# project-notes.md, section « Installation des logiciels », étape 4.
########################################################################

"""Check that Python can reach both of the project's databases.

Connects to PostgreSQL and to Neo4j with the passwords taken from the
environment (PGPASSWORD and NEO4J_PASSWORD, loaded from secrets.sh by run.sh)
and prints each server's version. Exits with an error if either one fails.

Usage:
    ./run.sh scripts/check_connections.py
"""

# ---------------------------------------------------------------------
# import os, import sys
#
# Ce sont deux modules de la bibliothèque standard (fournis avec Python).
#   os   — « operating system » (système d'exploitation). Ici, on utilise
#          seulement os.environ : un objet qui se comporte comme un
#          dictionnaire et contient les VARIABLES D'ENVIRONNEMENT dont ce
#          processus a hérité du terminal (ou de run.sh). C'est ainsi que
#          les mots de passe arrivent jusqu'à Python sans jamais être
#          écrits dans le code.
#   sys  — « system ». Ici, on utilise seulement sys.exit(), qui arrête
#          le programme et indique à celui qui l'a lancé s'il a réussi
#          (voir main()).
# ---------------------------------------------------------------------
import os
import sys

# ---------------------------------------------------------------------
# import psycopg / from neo4j import GraphDatabase
#
# Ce sont les premiers paquets EXTERNES du projet : ils ne sont pas
# fournis avec Python, ils ont été installés dans .venv avec `pip install
# -r requirements.txt`. Si .venv n'est pas activé, ces deux lignes
# échouent avec « ModuleNotFoundError » — l'une des raisons de toujours
# passer par run.sh.
#
# La ligne vide entre les deux groupes d'imports est une convention :
# d'abord les imports de la bibliothèque standard, puis les paquets
# externes.
#
#   psycopg         — le connecteur PostgreSQL.
#   GraphDatabase   — le point d'entrée du connecteur Neo4j ; on n'a
#                     besoin que de ce seul nom du paquet `neo4j`, d'où
#                     `from neo4j import ...` au lieu de `import neo4j`.
# ---------------------------------------------------------------------
import psycopg
from neo4j import GraphDatabase

# ---------------------------------------------------------------------
# Paramètres de connexion, sous forme de constantes en haut du fichier
# (même idée que DEFAULT_FILE dans les scripts précédents) : un seul
# endroit où regarder si quelque chose change un jour.
#
# POSTGRES_SETTINGS est un dictionnaire dont les clés sont exactement les
# noms qu'attend la fonction connect() de psycopg :
#   host="localhost"     la base de données tourne sur ce même ordinateur
#   dbname="gharchive"   la base de données créée à l'étape 1
#   user="postgres"      le superutilisateur créé par l'installateur
# Il n'y a volontairement AUCUN mot de passe ici : voir check_postgres().
#
# NEO4J_URI = "neo4j://localhost:7687"
#   L'adresse du serveur Neo4j : protocole neo4j://, cet ordinateur,
#   port 7687 (le port « Bolt » pour les programmes ; 7474 est celui du
#   navigateur).
# NEO4J_USER = "neo4j" — l'utilisateur Neo4j par défaut.
# ---------------------------------------------------------------------
POSTGRES_SETTINGS = {"host": "localhost", "dbname": "gharchive", "user": "postgres"}
NEO4J_URI = "neo4j://localhost:7687"
NEO4J_USER = "neo4j"


# ---------------------------------------------------------------------
# def check_postgres() -> None:
#
# psycopg.connect(**POSTGRES_SETTINGS)
#   `**` DÉPAQUETTE un dictionnaire en arguments nommés, donc c'est
#   exactement la même chose que d'écrire :
#       psycopg.connect(host="localhost", dbname="gharchive", user="postgres")
#
# Où est le mot de passe ? PGPASSWORD est un nom de variable
# d'environnement standard que la bibliothèque cliente de PostgreSQL
# (utilisée en interne par psycopg) cherche d'elle-même. Comme run.sh l'a
# chargée depuis secrets.sh, elle est déjà dans l'environnement de ce
# processus — le code n'y touche jamais.
#
# `with ... as conn:` — même schéma que `with open(...) as f:` dans les
# scripts précédents : la connexion est fermée automatiquement à la fin
# du bloc, même si quelque chose se passe mal à l'intérieur.
#
# conn.execute("SELECT version();") envoie une requête SQL au serveur.
# .fetchone() récupère la première (ici, la seule) ligne de la réponse,
# sous forme de tuple ; [0] prend sa première (seule) colonne — le texte
# de la version.
# ---------------------------------------------------------------------
def check_postgres() -> None:
    # psycopg lit le mot de passe dans PGPASSWORD tout seul.
    with psycopg.connect(**POSTGRES_SETTINGS) as conn:
        version = conn.execute("SELECT version();").fetchone()[0]
    print(f"PostgreSQL OK: {version}")


# ---------------------------------------------------------------------
# def check_neo4j() -> None:
#
# os.environ["NEO4J_PASSWORD"]
#   Contrairement à PostgreSQL, le connecteur Neo4j ne cherche pas de mot
#   de passe de lui-même : on le lit donc nous-mêmes dans l'environnement
#   et on le lui transmet. os.environ fonctionne comme un dictionnaire :
#   ["NOM"] donne la valeur de la variable.
#
# GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password))
#   Crée un DRIVER (pilote) : l'objet qui gère les connexions au serveur
#   Neo4j. auth= prend un tuple (utilisateur, mot de passe).
#   `with ... as driver:` le ferme automatiquement à la fin.
#
# driver.verify_connectivity()
#   Créer un driver ne se connecte pas encore réellement. Cette ligne
#   force une vraie connexion et authentification, de sorte qu'un
#   mauvais mot de passe ou une base de données arrêtée soit signalé ici
#   même, avec une erreur claire.
#
# driver.execute_query("CALL dbms.components() ...")
#   Envoie une requête Cypher (le langage de requête de Neo4j) — la même
#   que celle utilisée dans Neo4j Browser dans les notes pour voir la
#   version. Elle renvoie trois choses ; `records, _, _ = ...` garde la
#   première (les lignes du résultat) et jette les deux autres. `_` est
#   le nom conventionnel pour « une valeur dont je n'ai pas besoin ».
#
# Chaque record se comporte comme un dictionnaire : record['name'],
# record['versions'], record['edition']. 'versions' est une list, donc
# [0] prend son premier élément.
# ---------------------------------------------------------------------
def check_neo4j() -> None:
    password = os.environ["NEO4J_PASSWORD"]
    with GraphDatabase.driver(NEO4J_URI, auth=(NEO4J_USER, password)) as driver:
        driver.verify_connectivity()
        records, _, _ = driver.execute_query(
            "CALL dbms.components() YIELD name, versions, edition "
            "RETURN name, versions, edition"
        )
    for record in records:
        print(f"Neo4j OK: {record['name']} {record['versions'][0]} ({record['edition']} edition)")


# ---------------------------------------------------------------------
# def main() -> None:
# ---------------------------------------------------------------------
def main() -> None:
    # -----------------------------------------------------------------
    # D'abord, vérifier que les mots de passe sont bien présents.
    #
    # os.environ.get(nom) renvoie None (au lieu d'une erreur) quand la
    # variable n'existe pas — même idée que dict.get() dans
    # profile_schema.py. `not ...` vaut True quand elle est absente OU
    # vide. La compréhension de liste rassemble les noms de celles qui
    # manquent.
    #
    # sys.exit("un texte") arrête le programme, affiche le texte, et
    # signale un ÉCHEC à celui qui l'a lancé. Vérifier cela dès le début
    # donne un message clair (« lancez-le via run.sh ») au lieu d'une
    # erreur d'authentification déroutante plus tard.
    # -----------------------------------------------------------------
    missing = [name for name in ("PGPASSWORD", "NEO4J_PASSWORD") if not os.environ.get(name)]
    if missing:
        sys.exit(f"Missing environment variable(s): {', '.join(missing)}. "
                 "Run this script through run.sh, which loads them from secrets.sh.")

    # -----------------------------------------------------------------
    # try / except — gérer les erreurs sans tout arrêter
    #
    # Normalement, une erreur (une EXCEPTION) arrête le programme sur le
    # champ. Si PostgreSQL échouait, on ne saurait jamais si Neo4j
    # fonctionne. Donc chaque vérification s'exécute dans `try:` ; si
    # elle lève une exception, Python saute à `except Exception as
    # error:` au lieu de s'arrêter, affiche laquelle a échoué et
    # pourquoi, retient que quelque chose a échoué, et la boucle passe à
    # la vérification suivante.
    #
    # La boucle parcourt des paires (nom, fonction). `check` est la
    # fonction elle-même (sans parenthèses), et `check()` l'appelle — les
    # fonctions peuvent être stockées dans des variables et des tuples
    # comme n'importe quelle autre valeur.
    # -----------------------------------------------------------------
    failed = False
    for name, check in (("PostgreSQL", check_postgres), ("Neo4j", check_neo4j)):
        try:
            check()
        except Exception as error:
            print(f"{name} FAILED: {error}")
            failed = True

    # -----------------------------------------------------------------
    # sys.exit(1) — le CODE DE SORTIE
    #
    # Tout programme se termine par un nombre qui indique à celui qui l'a
    # lancé comment cela s'est passé : 0 signifie succès, toute autre
    # valeur signifie échec. Arriver normalement à la fin du script donne
    # 0 ; sys.exit(1) donne 1. D'autres scripts (ou run.sh) peuvent s'en
    # servir pour savoir si la vérification a réussi.
    # -----------------------------------------------------------------
    if failed:
        sys.exit(1)
    print("Both databases are reachable.")


# main() et la garde `if __name__ == "__main__":` : but et mécanisme
# identiques à ceux des autres scripts — voir la copie annotée de
# download_gharchive.py pour l'explication complète.
if __name__ == "__main__":
    main()
