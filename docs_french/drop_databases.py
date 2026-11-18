########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de
# scripts/drop_databases.py. Il n'est PAS destiné à être exécuté — il se
# trouve dans docs_french/ car son but est d'enseigner, pas de
# s'exécuter. Le script réel et « propre » (sans tous ces commentaires)
# est scripts/drop_databases.py.
#
# Ce fichier suppose que vous avez déjà lu les copies annotées
# précédentes, en particulier check_connections.py (psycopg, le driver
# Neo4j, execute_query, os.environ, sys.exit, try/except) et pipeline.py
# (autocommit=True, le catalogue pg_database, sql.SQL + sql.Identifier,
# la base « system » où Neo4j gère les bases de données, CREATE DATABASE
# ... WAIT). Ces points ne sont PAS réexpliqués depuis zéro ici.
#
# Ce qui est NOUVEAU dans ce fichier :
#   - l'opération DANGEREUSE, DROP DATABASE, des deux côtés, et les
#     RÈGLES DE SÉCURITÉ qui l'entourent : une liste d'autorisation
#     explicite (« gharchive* ») et une liste d'interdiction (les bases
#     propres aux serveurs), vérifiées À L'INTÉRIEUR même des fonctions de
#     suppression, avant toute connexion ;
#   - demander à l'utilisateur de CONFIRMER en tapant un mot, avec input() ;
#   - DROP DATABASE ... WITH (FORCE) (PostgreSQL) et
#     DROP DATABASE `x` IF EXISTS DESTROY DATA WAIT (Neo4j) ;
#   - VÉRIFIER ensuite qu'il ne reste rien, au lieu de faire confiance au
#     fait que les suppressions ont fonctionné.
#
# POURQUOI IL EXISTE : chaque volume de données de la recherche (1 heure,
# 6 heures, 12 heures, 1 jour, ...) est sa propre paire de bases de
# données, appelée « gharchive-<date>-<heure>-<n>h », construite par
# build_hours.py. Elles s'accumulent. Ce script les supprime toutes d'un
# coup, pour recommencer les mesures à partir d'un état propre. Les
# fichiers téléchargés dans data/ sont conservés, donc reconstruire une
# base de données ne demande jamais de nouveau téléchargement.
#
# Lancez-le via run.sh (il a besoin de PGPASSWORD et NEO4J_PASSWORD) :
#     ./run.sh scripts/drop_databases.py
########################################################################

"""Delete every database this project created, in PostgreSQL and in Neo4j.

A project database is one called "gharchive" or whose name starts with
"gharchive": gharchive, gharchive24h, gharchive-<date>-<hour>..., gharchivetest.
The databases that come with the servers ("postgres" in PostgreSQL, "neo4j"
and "system" in Neo4j) are never touched, and neither are the downloaded
files in data/ (so nothing has to be downloaded again to rebuild a database).

It shows what it found and asks you to type "delete" before deleting
anything. Afterwards it checks that no project database is left on either side.
This can't be undone.

Usage:
    ./run.sh scripts/drop_databases.py
"""

# ---------------------------------------------------------------------
# os, sys, psycopg, GraphDatabase : expliqués dans check_connections.py.
# `from psycopg import sql` : les outils pour construire du texte SQL en
# toute sécurité (sql.SQL, sql.Identifier), expliqués dans pipeline.py
# (ensure_databases).
#
# `import load_neo4j` / `import pipeline` : nos PROPRES scripts importés
# comme modules (expliqué dans pipeline.py). De load_neo4j, on réutilise
# seulement les constantes NEO4J_URI et NEO4J_USER (pour que l'adresse
# soit écrite à UN SEUL endroit), et de pipeline la fonction utilitaire
# servers_not_ready() (voir main()).
# ---------------------------------------------------------------------
import os
import sys

import psycopg
from neo4j import GraphDatabase
from psycopg import sql

import load_neo4j
import pipeline

# ---------------------------------------------------------------------
# SERVER_DATABASES — une LISTE D'INTERDICTION, écrite sous forme
# d'ENSEMBLE ({...}).
#
# Ce sont les bases de données fournies avec les serveurs eux-mêmes :
#   PostgreSQL  postgres (celle par défaut, à laquelle on se connecte),
#               template0 et template1 (les « moules » à partir desquels
#               toute nouvelle base est copiée). Supprimer un modèle
#               casse CREATE DATABASE.
#   Neo4j       neo4j (la base par défaut) et system (où Neo4j garde ses
#               utilisateurs et la liste des bases — la supprimer
#               casserait tout le serveur).
#
# Aucune d'elles ne commence par « gharchive », donc le test sur le nom
# ci-dessous les écarterait déjà. La liste d'interdiction est un SECOND
# filet de sécurité, indépendant : la « défense en profondeur ». Avec une
# opération destructrice, on veut deux verrous, pour qu'une seule erreur
# dans une seule règle ne suffise pas à provoquer une catastrophe.
#
# On utilise un ensemble parce que la seule question posée est « ce nom
# est-il DEDANS ? », à laquelle un ensemble répond instantanément.
# ---------------------------------------------------------------------
# Names that may never be deleted, whatever they look like.
SERVER_DATABASES = {"postgres", "template0", "template1", "neo4j", "system"}


# ---------------------------------------------------------------------
# def is_project_database(name) -> bool:
#
# LA règle de tout le script, en une ligne : un nom est une base du
# projet s'il COMMENCE PAR « gharchive » (une LISTE D'AUTORISATION par
# préfixe) ET n'est pas dans la liste d'interdiction. str.startswith()
# renvoie True ou False.
#
# Pourquoi un préfixe et pas une liste fixe de noms ? Parce que les bases
# par volume ont des noms qui changent avec la date et la taille, par ex.
# « gharchive-2026-08-27-15-6h » ; un préfixe les attrape toutes, et rien
# d'autre. Notez que c'est « commence par », pas « contient » :
# « mygharchive » ne correspondrait PAS, donc une base qui mentionne
# simplement le mot est en sécurité.
#
# C'est une fonction PURE (aucun serveur en jeu), donc on peut la tester
# unitairement sans aucune base de données : c'est ce que fait
# tests/test_drop_databases.py.
# ---------------------------------------------------------------------
def is_project_database(name: str) -> bool:
    # gharchive, gharchive24h, gharchive-..., gharchivetest; nothing else.
    return name.startswith("gharchive") and name not in SERVER_DATABASES


# ---------------------------------------------------------------------
# def project_databases(names) -> list[str]:
#
# Filtre une liste de noms pour ne garder que ceux du projet, et les
# trie. `name for name in names if ...` est une EXPRESSION GÉNÉRATRICE :
# une compréhension de liste sans les crochets, passée directement à
# sorted(), qui renvoie une nouvelle LISTE triée. Le tri rend la liste
# affichée facile à lire et identique d'une exécution à l'autre.
#
# Elle aussi est pure : postgres_databases() et neo4j_databases() y font
# passer toutes les deux leur réponse brute, donc c'est la MÊME règle qui
# décide des deux côtés.
# ---------------------------------------------------------------------
def project_databases(names: list[str]) -> list[str]:
    # The project's databases among all the names a server reports, sorted.
    return sorted(name for name in names if is_project_database(name))


# ---------------------------------------------------------------------
# def postgres_databases() -> list[str]:
#
# Demande à PostgreSQL toutes les bases qu'il possède. Elle se connecte à
# « postgres » (toujours présente) et lit pg_database, le catalogue des
# bases de PostgreSQL (vu dans pipeline.py) ; la colonne datname est le
# nom. fetchall() renvoie une liste de tuples à une colonne, par ex.
# [("postgres",), ("gharchive",), ...] ; row[0] en extrait le nom.
#
# Notez que le `return` est EN DEHORS du `with` : la connexion est déjà
# fermée quand le filtrage a lieu. Plus rien n'en a besoin.
# ---------------------------------------------------------------------
def postgres_databases() -> list[str]:
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres") as conn:
        rows = conn.execute("SELECT datname FROM pg_database").fetchall()
    return project_databases([row[0] for row in rows])


# ---------------------------------------------------------------------
# def neo4j_databases(driver) -> list[str]:
#
# La même question pour Neo4j, posée à la base « system » (database_=
# est expliqué dans load_neo4j.py) :
#   SHOW DATABASES          la commande de Neo4j qui liste ses bases.
#   YIELD name              ne garde que la colonne « name » de cette
#                           liste (elle en a beaucoup : status, address,
#                           role...).
#   RETURN DISTINCT name    une ligne par nom. Dans un cluster, la même
#                           base peut apparaître une fois par serveur ;
#                           DISTINCT n'en garde qu'un exemplaire.
# .records est la liste des lignes de la réponse ; record["name"] lit une
# colonne par son nom, comme un dictionnaire.
#
# Contrairement à postgres_databases(), elle reçoit le driver en
# PARAMÈTRE au lieu de créer le sien : main() ouvre UN SEUL driver et le
# réutilise pour toutes les étapes Neo4j (un driver est plus lourd à
# créer qu'une connexion psycopg).
# ---------------------------------------------------------------------
def neo4j_databases(driver) -> list[str]:
    records = driver.execute_query("SHOW DATABASES YIELD name RETURN DISTINCT name", database_="system").records
    return project_databases([record["name"] for record in records])


# ---------------------------------------------------------------------
# def drop_postgres(name) -> None:
#
# 1. LA GARDE vient en premier, avant toute connexion :
#      if not is_project_database(name): raise ValueError(...)
#    `raise` arrête la fonction avec une erreur (raise a été expliqué
#    dans download_gharchive.py). ValueError est l'erreur standard de
#    Python pour « le type convient mais la VALEUR n'est pas
#    acceptable ». Comme la vérification se trouve dans la fonction de
#    suppression elle-même, aucun appelant — le main() d'aujourd'hui ou un
#    futur script — ne peut jamais supprimer « postgres » à travers elle,
#    même par erreur. Le fichier de tests vérifie exactement cela.
#    Dans le message, \' est une apostrophe ÉCHAPPÉE : la chaîne est
#    écrite entre apostrophes '...', donc l'apostrophe de « isn't » a
#    besoin d'une barre oblique inverse.
#
# 2. La connexion utilise autocommit=True parce que DROP DATABASE, comme
#    CREATE DATABASE, ne peut pas s'exécuter dans une transaction (voir
#    pipeline.py). Elle se connecte à « postgres » : on ne peut pas
#    supprimer la base à laquelle on est connecté.
#
# 3. Le SQL :  DROP DATABASE IF EXISTS "name" WITH (FORCE)
#      DROP DATABASE   supprime la base et tous ses fichiers.
#      IF EXISTS       pas d'erreur si elle a déjà disparu (juste un
#                      avertissement).
#      WITH (FORCE)    (PostgreSQL 13+) ferme d'abord toutes les autres
#                      connexions à cette base. Sans cela, un onglet
#                      pgAdmin ouvert sur cette base fait échouer le DROP
#                      avec « database is being accessed by other users ».
#    sql.Identifier(name) met le nom entre guillemets doubles :
#    nécessaire ici car des noms comme « gharchive-2026-08-27-15 »
#    contiennent des tirets, que SQL lirait sinon comme des signes moins.
# ---------------------------------------------------------------------
def drop_postgres(name: str) -> None:
    if not is_project_database(name):
        raise ValueError(f'Refusing to delete "{name}": it isn\'t a project database')
    print(f'Deleting the PostgreSQL database "{name}" ...')
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        # WITH (FORCE) first closes other connections to it (e.g. pgAdmin), which would block the DROP.
        conn.execute(sql.SQL("DROP DATABASE IF EXISTS {} WITH (FORCE)").format(sql.Identifier(name)))
    print(f'The PostgreSQL database "{name}" has been deleted.')


# ---------------------------------------------------------------------
# def drop_neo4j(driver, name) -> None:
#
# D'abord la même garde, puis la commande d'administration de Cypher,
# envoyée à la base « system » :
#   DROP DATABASE `name`   les ACCENTS GRAVES `...` encadrent un nom en
#                          Cypher (le même rôle que les guillemets doubles
#                          en SQL) ; nécessaires pour les tirets des noms.
#   IF EXISTS              pas d'erreur si elle a déjà disparu.
#   DESTROY DATA           supprime aussi ses fichiers de données.
#                          (L'autre option, DUMP DATA, en enregistrerait
#                          d'abord une copie — ce qu'on ne veut pas : les
#                          données peuvent toujours être reconstruites à
#                          partir de data/.)
#   WAIT                   ne rend la main qu'une fois la suppression
#                          terminée, pour que la vérification de l'étape 3
#                          de main() voie l'état final (le même WAIT que
#                          dans CREATE DATABASE).
#
# Ici, le nom est collé dans le texte avec une f-string, parce que Cypher
# n'accepte pas non plus un nom de base en $paramètre. Ce n'est
# acceptable que parce que la garde ci-dessus vient de vérifier le nom.
# ---------------------------------------------------------------------
def drop_neo4j(driver, name: str) -> None:
    if not is_project_database(name):
        raise ValueError(f'Refusing to delete "{name}": it isn\'t a project database')
    print(f'Deleting the Neo4j database "{name}" ...')
    # DESTROY DATA: delete its files too. WAIT: don't return until it's gone.
    driver.execute_query(f"DROP DATABASE `{name}` IF EXISTS DESTROY DATA WAIT", database_="system")
    print(f'The Neo4j database "{name}" has been deleted.')


# ---------------------------------------------------------------------
# def main() -> None:
#
# Quatre étapes numérotées, chacune annoncée par « == n. », pour que la
# sortie se lise comme une liste de contrôle :
#   0. les deux serveurs répondent ?   (sinon on s'arrête, sans avoir
#                                       rien changé)
#   1. trouver les bases du projet     (et les afficher)
#      -> confirmation : l'utilisateur doit taper « delete »
#   2. les supprimer
#   3. vérifier qu'il n'en reste aucune (code de sortie 1 s'il en reste)
# ---------------------------------------------------------------------
def main() -> None:
    # -----------------------------------------------------------------
    # Étape 0. pipeline.servers_not_ready() tente une connexion rapide à
    # chaque serveur (délai de 5 secondes) et renvoie None si les deux
    # répondent, ou une courte phrase disant lequel ne répond pas.
    # `str | None` dans sa signature signifie « une chaîne, ou None ».
    #
    # Vérifier les DEUX avant de toucher à l'UN OU L'AUTRE évite un
    # travail à moitié fait : par ex. les bases PostgreSQL supprimées,
    # puis un plantage parce que Neo4j Desktop n'est pas ouvert, laissant
    # les deux côtés désynchronisés.
    # `is not None` est la bonne façon de tester None (pas `!= None`).
    # -----------------------------------------------------------------
    print("== 0. Check that both servers are answering")
    problem = pipeline.servers_not_ready()
    if problem is not None:
        print(f"{problem}. Nothing was deleted.")
        sys.exit(1)
    print("Both servers are answering.")

    # Un seul driver Neo4j pour toute l'exécution (voir neo4j_databases()).
    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        # -------------------------------------------------------------
        # Étape 1. `a, b = x(), y()` affecte deux variables en une seule
        # ligne (dépaquetage de tuple). Le "\n" au début de la chaîne
        # affiche d'abord une ligne vide, pour séparer les étapes.
        #
        # ', '.join(liste) colle les noms en une seule chaîne, avec ", "
        # entre eux. Si la liste est vide, join donne "" — et
        # `"" or 'none'` donne 'none', parce que `or` renvoie son côté
        # droit quand le gauche est « vide/faux ». Une façon courte
        # d'afficher « none » au lieu de rien.
        #
        # `not in_postgres` : une liste vide compte comme False, donc cela
        # signifie « la liste est vide ». Si les deux sont vides, il n'y a
        # rien à faire, et `return` termine main() normalement (code de
        # sortie 0).
        # -------------------------------------------------------------
        print("\n== 1. Find the project's databases")
        in_postgres, in_neo4j = postgres_databases(), neo4j_databases(driver)
        print(f"PostgreSQL ({len(in_postgres)}): {', '.join(in_postgres) or 'none'}")
        print(f"Neo4j      ({len(in_neo4j)}): {', '.join(in_neo4j) or 'none'}")
        if not in_postgres and not in_neo4j:
            print("\nThere's nothing to delete: both servers are already clean.")
            return

        # -------------------------------------------------------------
        # LA CONFIRMATION
        #
        # input(invite) affiche l'invite et ATTEND que l'utilisateur tape
        # une ligne et appuie sur Entrée ; elle renvoie ce qui a été tapé
        # (sous forme de str).
        #
        # Deux façons dont input() peut échouer au lieu de renvoyer :
        #   EOFError           il n'y a pas de clavier du tout — par ex. le
        #                      script a été lancé par un planificateur, ou
        #                      avec son entrée redirigée depuis un fichier
        #                      vide.
        #   KeyboardInterrupt  l'utilisateur a appuyé sur Ctrl+C.
        # Les deux sont interceptées et traitées comme une réponse vide,
        # c'est-à-dire « non ». (`except (A, B):` intercepte l'un ou
        # l'autre type, comme dans download_gharchive.py.)
        #
        # answer.strip().lower() : strip() retire les espaces et la fin de
        # ligne autour du texte, lower() le met en minuscules, donc
        # " Delete " est accepté aussi. TOUT le reste — « y », « yes »,
        # Entrée seule — arrête le script.
        #
        # Pourquoi un mot entier et pas « o/n » ? Taper « delete » est un
        # acte délibéré : on ne peut pas le faire par réflexe. La
        # suppression n'est JAMAIS le choix par défaut : une seule
        # réponse exacte permet de continuer.
        # -------------------------------------------------------------
        print("\nThese databases and ALL their data will be deleted. This can't be undone.")
        print("(The server databases postgres, neo4j and system, and the files in data/, are kept.)")
        try:
            answer = input('Type "delete" to delete them, or anything else to stop: ')
        except (EOFError, KeyboardInterrupt):
            answer = ""
        if answer.strip().lower() != "delete":
            print("\nNothing was deleted.")
            return

        # Étape 2. Une base à la fois ; chaque fonction de suppression
        # revérifie le nom (la garde), même si ces listes sont déjà
        # filtrées.
        print("\n== 2. Delete them")
        for name in in_postgres:
            drop_postgres(name)
        for name in in_neo4j:
            drop_neo4j(driver, name)

        # -------------------------------------------------------------
        # Étape 3. LA CONFIANCE N'EXCLUT PAS LE CONTRÔLE : on interroge à
        # nouveau les deux serveurs, avec les mêmes fonctions qu'à
        # l'étape 1. Une commande qui « s'est terminée sans erreur » n'est
        # pas la preuve que le résultat est celui qu'on voulait ;
        # interroger à nouveau le serveur, si. S'il reste quelque chose,
        # le code de sortie 1 indique à celui qui a lancé le script qu'il
        # n'a pas entièrement réussi (codes de sortie :
        # check_connections.py).
        # -------------------------------------------------------------
        print("\n== 3. Check that none is left")
        left_postgres, left_neo4j = postgres_databases(), neo4j_databases(driver)
        print(f"PostgreSQL: {', '.join(left_postgres) or 'no project database left'}")
        print(f"Neo4j:      {', '.join(left_neo4j) or 'no project database left'}")
        if left_postgres or left_neo4j:
            print("\nSome databases are still there (see above).")
            sys.exit(1)
        print("\nDone: both servers are clean.")


# main() et la garde `if __name__ == "__main__":` : but et forme
# identiques à ceux de download_gharchive.py. Ici, la garde compte
# vraiment : le fichier de tests IMPORTE ce module, et l'importer ne doit
# jamais déclencher de suppression.
if __name__ == "__main__":
    main()
