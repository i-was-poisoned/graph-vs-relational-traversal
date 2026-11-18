########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/build_hours.py.
# Il n'est PAS destiné à être exécuté dans le cadre du pipeline du projet — il
# se trouve dans docs_french/ car son but est d'enseigner, pas de s'exécuter.
# Le script réel et « propre » (sans tous ces commentaires) est
# scripts/build_hours.py.
#
# Lisez d'abord ces copies annotées ; ce qu'elles expliquent n'est PAS
# répété ici :
#   download_gharchive.py   fetch_gz(), try/except, `raise ... from`
#   extract_csv.py          extract(), write_all()
#   load_postgres.py,
#   load_neo4j.py           load(), et les vérifications de comptage
#                           (OK / MISMATCH)
#   check_connections.py    la connexion aux deux serveurs, les mots de
#                           passe
#   pipeline.py             importer nos propres scripts comme modules,
#                           hour_file_name(), sql.Identifier, CREATE
#                           DATABASE ... WAIT, servers_not_ready()
#   test_integration.py     `while True:`, les records de Neo4j
#
# CE QUE C'EST — le PROCESSUS MANUEL. La recherche se demande à partir de
# quelle profondeur de parcours et de quel volume de données Neo4j
# commence à battre PostgreSQL ; elle a donc besoin des MÊMES données
# fixes dans les deux bases, à plusieurs tailles (1 heure, 3 heures, 24
# heures...). Ce script construit l'un de ces jeux de données à la
# demande : VOUS choisissez les heures, il les met dans une base de
# données qui leur est propre, des deux côtés. (Le pipeline automatique de
# 24 heures, pipeline.py, est reporté pour l'instant : la phase de
# recherche utilise des données construites avec ce script.)
#
# Ce qui est NOUVEAU ici :
#   - poser des questions au clavier avec input(), et VALIDER les
#     réponses (redemander jusqu'à ce qu'elles soient valides) ;
#   - lever nos propres erreurs (raise ValueError) avec des messages
#     lisibles ;
#   - lire une date à partir d'un texte (datetime.strptime) ;
#   - passer une FONCTION en paramètre pour que les tests puissent
#     remplacer le clavier ;
#   - supprimer et recréer toute une base de données (DROP DATABASE ...
#     WITH (FORCE), CREATE OR REPLACE DATABASE), derrière une
#     VÉRIFICATION DE SÉCURITÉ sur le nom, puis PROUVER qu'elle est vide
#     avant de charger ;
#   - EOFError / KeyboardInterrupt (pas de clavier, ou Ctrl+C).
# Ses messages sont volontairement BAVARDS : chaque étape dit ce qu'elle va
# faire et ce qu'elle a fait, pour que vous puissiez la suivre sans ouvrir
# le code.
#
# Comment le vrai script se lance (il demande le reste) :
#     ./run.sh scripts/build_hours.py
# run.sh active .venv et charge les mots de passe depuis secrets.sh ; ce
# script ne contient ni ne demande jamais de mot de passe.
########################################################################

"""Build a database from GH Archive hours that you choose, on both sides.

The benchmark's fixed hour lives in the "gharchive" databases and never
changes. This script lets you load other data to compare with it: it asks
which date, starting hour and number of consecutive hours you want, then

    1. downloads those hours to data/hours/ (hours already there are reused);
    2. extracts the CSV files from them (extract_csv.py), into
       data/hours/csv/<database name>/;
    3. empties the database named after the hours, in PostgreSQL and in Neo4j:
       it deletes it (if it exists) and creates it again, then checks that both
       sides really are empty, and stops if they aren't;
           1 hour  from 2026-08-27 15:00 UTC -> "gharchive-2026-08-27-15"
           3 hours from 2026-08-27 15:00 UTC -> "gharchive-2026-08-27-15-3h"
    4. loads the CSVs into both (load_postgres.py, load_neo4j.py).

Each choice gets its own database, so "gharchive" and "gharchive24h" are never
touched. Loading the same choice again empties and rebuilds only its own databases.

Usage (it asks the rest; press Enter to keep the value in brackets):
    ./run.sh scripts/build_hours.py
"""

# ---------------------------------------------------------------------
# Imports : tous déjà vus. `date` (un jour sans heure) est expliqué dans
# la copie annotée de pipeline.py, comme datetime/timedelta/timezone.
# Remarque : pas d'argparse ici — ce script POSE DES QUESTIONS au lieu
# de prendre des options.
# ---------------------------------------------------------------------
import os
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import psycopg
from neo4j import GraphDatabase
from psycopg import sql

# ---------------------------------------------------------------------
# Nos propres scripts, importés comme MODULES (voir la copie annotée de
# pipeline.py). Il réutilise le téléchargeur, l'extracteur et les deux
# chargeurs — exactement le même code que pour le benchmark et le
# pipeline, donc chaque jeu de données est construit de la même façon —
# ainsi que deux fonctions de pipeline.py lui-même : hour_file_name() et
# servers_not_ready().
# ---------------------------------------------------------------------
import download_gharchive
import extract_csv
import load_neo4j
import load_postgres
import pipeline

# ---------------------------------------------------------------------
# Constantes :
#   HOURS_DIR   data/hours/ — où vont les téléchargements et les CSV de
#               ce script (ignoré par git comme le reste de data/).
#               Séparé des fichiers du benchmark et de data/live/ (ceux
#               du pipeline).
#   FIRST_DATE  la date la plus ancienne qu'il accepte. date(2015, 1, 1)
#               est un objet `date` : année, mois, jour.
#   MAX_HOURS   le nombre maximal d'heures qu'il accepte d'un coup :
#               168 = 7 x 24, une semaine.
# ---------------------------------------------------------------------
HOURS_DIR = Path(__file__).resolve().parent.parent / "data" / "hours"
# GH Archive's events have had today's format since 2015; older files use another one.
FIRST_DATE = date(2015, 1, 1)
# A week. More would take very long to load and need a lot of memory in Neo4j.
MAX_HOURS = 168


# ---------------------------------------------------------------------
# def parse_date(text) -> date:
#
# La première de trois petites fonctions de VALIDATION : chacune
# transforme ce que vous avez tapé (un str) en une vraie valeur, ou LÈVE
# une ValueError avec un message compréhensible par une personne.
#
# raise ValueError("...")
#   NOUVEAU : lever NOTRE PROPRE erreur. Jusqu'ici, on ne faisait
#   qu'attraper des erreurs levées par d'autres. ValueError est le type
#   habituel de Python pour « bon type, mauvaise valeur ». Le texte
#   devient le message de l'erreur, et ask_hours() se contente de
#   l'afficher (voir plus bas). Une fonction, deux rôles : dire si la
#   réponse est valide ET pourquoi elle ne l'est pas.
#
# text.strip() enlève les espaces et la fin de ligne autour du texte,
# donc une réponse « "   " » compte comme vide. `not ""` vaut True (une
# chaîne vide est « falsy », c'est-à-dire considérée comme fausse), donc
# `if not text.strip():` signifie « si rien n'a été tapé ».
#
# datetime.strptime(text, "%Y-%m-%d")
#   « STRing Parse TIME » (analyser une date dans une chaîne) : l'inverse
#   du formatage f"{day:%Y-%m-%d}" vu dans pipeline.py — il LIT une date
#   écrite selon ce modèle. Si le texte ne correspond pas (mauvais ordre,
#   mois 13...), il lève une ValueError. Il renvoie un datetime (à
#   minuit) ; .date() ne garde que le jour.
#
# except ValueError: raise ValueError(...) from None
#   Le message propre à strptime (« time data '27/08/2026' does not match
#   format '%Y-%m-%d' ») est juste mais obscur ; on l'attrape donc et on
#   en lève un plus clair. `from None` masque l'erreur d'origine :
#   contrairement à `from error` (voir download_gharchive.py), elle ne
#   contient rien d'utile à garder, et l'utilisateur ne doit voir que
#   notre message.
#
# day < FIRST_DATE — les dates se comparent comme des nombres : la plus
# ancienne < la plus récente.
# ---------------------------------------------------------------------
def parse_date(text: str) -> date:
    # "2026-08-27" -> date(2026, 8, 27); anything else raises ValueError with a readable message.
    if not text.strip():
        raise ValueError("Please type a date, like 2026-08-27 (year-month-day)")
    try:
        day = datetime.strptime(text.strip(), "%Y-%m-%d").date()
    except ValueError:
        raise ValueError(f"'{text}' isn't a date like 2026-08-27 (year-month-day)") from None
    if day < FIRST_DATE:
        raise ValueError(f"Dates before {FIRST_DATE} use an older GH Archive format; choose a later one")
    return day


# ---------------------------------------------------------------------
# def parse_hour(text) -> int:
#
# text.strip().isdigit()
#   True seulement si le texte est fait de chiffres 0-9 et de rien
#   d'autre. « 15 » passe ; « -1 », « 3pm » et « 1.5 » ne passent pas.
#   C'est vérifié AVANT int(text), donc int() ne reçoit jamais un texte
#   qu'il ne sait pas convertir.
#
# 0 <= int(text) <= 23
#   Une comparaison EN CHAÎNE : Python la lit comme
#   « 0 <= int(text) and int(text) <= 23 » — la notation habituelle en
#   mathématiques.
#
# `A or B` dans la condition : si le texte n'est pas fait de chiffres,
# `or` sait déjà que la réponse est True et n'évalue même pas la seconde
# partie.
#
# Les heures sont en UTC car GH Archive nomme ses fichiers en UTC (voir
# la copie annotée de pipeline.py, compute_window()).
# ---------------------------------------------------------------------
def parse_hour(text: str) -> int:
    # "15" -> 15. GH Archive hours are UTC, 0 to 23.
    if not text.strip():
        raise ValueError("Please type an hour from 0 to 23 (UTC)")
    if not text.strip().isdigit() or not 0 <= int(text) <= 23:
        raise ValueError(f"'{text}' isn't an hour from 0 to 23 (UTC)")
    return int(text)


# Même idée pour le nombre d'heures : de 1 à MAX_HOURS. Il n'y a pas de
# vérification « vide » ici, car une réponse vide n'arrive jamais jusqu'à
# cette fonction : elle est remplacée par « 1 » dans ask_hours() (la seule
# question qui a une valeur par défaut).
def parse_count(text: str) -> int:
    # "3" -> 3 consecutive hours, from 1 to MAX_HOURS.
    if not text.strip().isdigit() or not 1 <= int(text) <= MAX_HOURS:
        raise ValueError(f"'{text}' isn't a number of hours from 1 to {MAX_HOURS}")
    return int(text)


# ---------------------------------------------------------------------
# def chosen_hours(day, hour, count) -> list[datetime]:
#
# Transforme les trois réponses en liste d'heures, sous la même forme que
# compute_window() dans pipeline.py : un datetime UTC par fichier
# horaire. Elle construit le premier à partir de l'année, du mois et du
# jour de `day` plus l'heure, puis ajoute 0, 1, 2... heures avec
# timedelta. Comme c'est du calcul sur des datetime, dépasser 23:00 fait
# passer tout seul au jour suivant (et au mois, et à l'année).
# ---------------------------------------------------------------------
def chosen_hours(day: date, hour: int, count: int) -> list[datetime]:
    # Example: 2026-08-27, 23, 2 -> 2026-08-27 23:00 and 2026-08-28 00:00 (crossing midnight is fine).
    first = datetime(day.year, day.month, day.day, hour, tzinfo=timezone.utc)
    return [first + timedelta(hours=i) for i in range(count)]


# ---------------------------------------------------------------------
# def hours_are_published(hours, now) -> bool:
#
# Refuse les heures que GH Archive ne peut pas encore avoir (des heures
# récentes, ou le futur), AVANT d'essayer de les télécharger. Avec
# now = 15:20 UTC :
#   l'heure en cours commence    15:00
#   moins une heure entière   -> 14:00   la FIN la plus tardive permise
#   12:00 + 2 heures finit à     14:00   -> acceptées
#   13:00 + 2 heures finit à     15:00   -> refusées (trop récentes)
# last_end = le début de la dernière heure + 1 heure (comme dans run() de
# pipeline.py). `now` est un paramètre, pour que les tests puissent
# utiliser une heure fixe (voir docs_french/test_build_hours.py).
# ---------------------------------------------------------------------
def hours_are_published(hours: list[datetime], now: datetime) -> bool:
    # GH Archive publishes each hour's file a little after the hour ends. Accept the hours only
    # if the last one ended at least one full hour before the current hour began.
    last_end = hours[-1] + timedelta(hours=1)
    return last_end <= now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=1)


# ---------------------------------------------------------------------
# def database_name(hours) -> str:
#
# Chaque choix d'heures reçoit SA PROPRE base de données, nommée d'après
# les heures, pour que les jeux de données ne se mélangent jamais et que
# le nom dise ce qu'il y a dedans :
#   1 heure    -> "gharchive-2026-08-27-15"
#   3 heures   -> "gharchive-2026-08-27-15-3h"
# Le nom commence toujours par « gharchive- » (avec un tiret) : c'est ce
# préfixe que vérifie may_be_emptied(), et il ne peut jamais être égal à
# « gharchive » ni à « gharchive24h ». Des tirets, pas des tirets bas :
# Neo4j interdit « _ » dans les noms de bases de données (voir
# DEFAULT_DATABASE dans pipeline.py).
#
# `X if condition else Y` (déjà vu) : le nom simple pour 1 heure, le nom
# suivi de « -<nombre>h » sinon.
# ---------------------------------------------------------------------
def database_name(hours: list[datetime]) -> str:
    # Neo4j allows letters, digits, dots and dashes in database names (not "_"), so dashes it is.
    # The hour has no leading zero, like GH Archive's file names.
    name = f"gharchive-{hours[0]:%Y-%m-%d}-{hours[0].hour}"
    return name if len(hours) == 1 else f"{name}-{len(hours)}h"


# ---------------------------------------------------------------------
# def describe(hours) -> str:
#
# Un résumé lisible pour les messages. La petite astuce à la fin :
#   's' * (len(hours) > 1)
# Une comparaison donne True ou False, et dans un calcul True compte pour
# 1 et False pour 0. Une chaîne multipliée par 1 reste elle-même ;
# multipliée par 0, elle donne "". Le « s » du pluriel n'est donc ajouté
# que s'il y a plus d'une heure : « 1 hour », « 3 hours ».
# ---------------------------------------------------------------------
def describe(hours: list[datetime]) -> str:
    # e.g. "2026-08-27 15:00 -> 2026-08-27 18:00 UTC (3 hours)"
    end = hours[-1] + timedelta(hours=1)
    return f"{hours[0]:%Y-%m-%d %H:00} -> {end:%Y-%m-%d %H:00} UTC ({len(hours)} hour{'s' * (len(hours) > 1)})"


# ---------------------------------------------------------------------
# def ask_hours(now, ask=input) -> list[datetime] | None:
#
# input("question") — NOUVEAU : affiche la question, attend que vous
# tapiez quelque chose et appuyiez sur Entrée, et renvoie ce que vous avez
# tapé sous forme de str (sans l'Entrée). Appuyer seulement sur Entrée
# renvoie "".
#
# ask=input — une FONCTION comme valeur par défaut d'un paramètre. Les
# fonctions sont des valeurs comme les autres (voir la boucle
# (name, check) de check_connections.py), donc la fonction est appelée
# via le nom `ask`. Normalement, ask EST input (le clavier). Un test passe
# à la place sa propre fonction, qui renvoie des réponses toutes prêtes —
# ainsi ask_hours() peut être testée sans que personne ne tape rien (voir
# docs_french/test_build_hours.py).
# Remarque : `input`, et non `input()` — on passe la fonction elle-même,
# on ne l'appelle pas.
#
# La boucle de questions (`while True:` est expliqué dans
# test_integration.py) :
#   - chaque réponse passe directement par sa fonction parse_... ; la
#     première qui lève une ValueError saute à `except` ;
#   - `except ValueError as error: print(error)` affiche le message
#     lisible que nous avons écrit dans la fonction parse_ ;
#   - `continue` — revenir en HAUT de la boucle : les trois questions
#     sont reposées ;
#   - la même chose se produit si les heures ne sont pas encore publiées.
#
# ask("How many consecutive hours [1]: ") or "1"
#   LA SEULE VALEUR PAR DÉFAUT. `A or B` donne A si A est « truthy »
#   (considéré comme vrai), sinon B. Une réponse vide "" est falsy, donc
#   appuyer sur Entrée donne "1". Le « [1] » dans la question est la
#   façon habituelle d'indiquer la valeur par défaut.
#
# La DATE et l'HEURE n'ont volontairement AUCUNE valeur par défaut :
# Entrée seule redemande simplement (« Please type a date... »). Une date
# par défaut permettrait de charger, en appuyant sur Entrée, des données
# que personne n'a vraiment choisies — et ensuite de mesurer la mauvaise
# chose sans s'en rendre compte.
#
# La CONFIRMATION : elle montre exactement ce qui va être chargé et dans
# quelle base de données, et prévient qu'une base existante portant ce
# nom est d'abord vidée. La réponse est nettoyée avec .strip().lower()
# (sans espaces, en minuscules, donc « Y » entouré d'espaces devient
# « y ») et comparée avec `in` à un TUPLE de réponses acceptées : Entrée
# seule (""), y/yes, et s/si/sí pour qui répond en portugais ou en
# espagnol. Toute autre réponse (par ex. « n ») renvoie None, ce qui dit
# à main() « rien à faire ».
#
# Le type de retour `list[datetime] | None` : une liste d'heures, OU None
# (l'annotation `|` est expliquée dans la copie annotée de pipeline.py).
# ---------------------------------------------------------------------
def ask_hours(now: datetime, ask=input) -> list[datetime] | None:
    # Asks for the date, the first hour and how many hours until all are valid, then asks for
    # confirmation. Returns None if the answer to the confirmation is "n".
    # "ask" is input() unless a test replaces it.
    # The date and the hour have no default: they must always be typed, so data is never
    # loaded for a date nobody chose. Only the number of hours has one (Enter = 1).
    while True:
        try:
            day = parse_date(ask("Date (UTC, e.g. 2026-08-27): "))
            hour = parse_hour(ask("First hour (UTC, 0-23): "))
            count = parse_count(ask("How many consecutive hours [1]: ") or "1")
        except ValueError as error:
            print(error)
            continue
        hours = chosen_hours(day, hour, count)
        if not hours_are_published(hours, now):
            print("GH Archive hasn't published all those hours yet: "
                  "the last one must end at least an hour before the current hour.")
            continue

        answer = ask(f'Load {describe(hours)} into "{database_name(hours)}"? '
                     "(if that database already exists, it's emptied first) [Y/n]: ")
        return hours if answer.strip().lower() in ("", "y", "yes", "s", "si", "sí") else None


# ---------------------------------------------------------------------
# def may_be_emptied(name) -> bool:
#
# La VÉRIFICATION DE SÉCURITÉ avant de supprimer quoi que ce soit. Ce
# script supprime des bases de données entières, il doit donc lui être
# impossible de supprimer la mauvaise. La règle tient en une ligne :
# seulement les noms qui commencent par « gharchive- ».
# str.startswith(prefix) vaut True si le texte commence par ce préfixe.
#   "gharchive"             -> False (pas de tiret) le benchmark figé
#   "gharchive24h"          -> False               celle du pipeline
#   "gharchivetest"         -> False               celle des tests
#                                                  d'intégration
#   "neo4j", "postgres", "system" -> False         celles des serveurs
#   "gharchive-2026-08-27-15" -> True              créée par ce script
# Gardée comme une toute petite fonction séparée pour pouvoir être testée
# à part.
# ---------------------------------------------------------------------
def may_be_emptied(name: str) -> bool:
    # Only databases made by this script may be deleted: never "gharchive" (the frozen
    # benchmark), "gharchive24h" (the pipeline's) or anything else on the servers.
    return name.startswith("gharchive-")


# ---------------------------------------------------------------------
# def recreate_databases(name) -> None:
#
# Vide la base de données des deux côtés en la SUPPRIMANT puis en la
# RECRÉANT. Les chargeurs vident déjà leurs propres tables et nœuds (voir
# load_postgres.py et load_neo4j.py), mais recréer toute la base est plus
# sûr : rien d'avant ne survit, pas même quelque chose que les chargeurs
# ne connaissent pas.
#
# PREMIÈRE LIGNE : la vérification de sécurité, AVANT de se connecter à
# quoi que ce soit. Si le nom n'est pas autorisé, elle lève une
# ValueError et absolument rien ne se passe.
#
# PostgreSQL (connexion à la base « postgres » avec autocommit=True, la
# recherche dans pg_database et sql.Identifier : tout comme dans
# ensure_databases() de la copie annotée de pipeline.py) :
#   - `exists` vaut True ou False : `... is not None` transforme « une
#     ligne, ou None » en oui/non.
#   - DROP DATABASE "name" WITH (FORCE) — NOUVEAU : supprime la base de
#     données et TOUTES ses données. PostgreSQL refuse de supprimer une
#     base à laquelle quelqu'un est connecté (pgAdmin, par exemple) ;
#     WITH (FORCE) ferme d'abord ces connexions.
#   - CREATE DATABASE "name" — une nouvelle base, vide.
#   - Les messages sont écrits f'...' (entre apostrophes simples) pour
#     pouvoir contenir des "guillemets doubles" autour du nom. Pour y
#     mettre une apostrophe, comme dans doesn\'t, on l'écrit \' — une
#     apostrophe ÉCHAPPÉE : elle fait partie du texte, ce n'est pas la fin
#     de la chaîne.
#
# Neo4j (dans la base « system », où les bases de données sont gérées) :
#   - SHOW DATABASES YIELD name WHERE name = $name RETURN name
#     liste les bases de données portant ce nom : une ligne si elle
#     existe, aucune sinon. $name est un PARAMÈTRE de requête (voir
#     load_neo4j.py), rempli par name=name. Sa valeur est une VALEUR, donc
#     un paramètre fonctionne ici.
#   - .records — le résultat contient les lignes dans son attribut
#     .records ; c'est la même liste que `records, _, _ = ...` déballe
#     ailleurs. Une liste vide est falsy, donc `if records:` signifie
#     « elle existe ».
#   - CREATE OR REPLACE DATABASE `name` WAIT — NOUVEAU : une seule
#     commande qui supprime la base si elle existe et la recrée
#     (Enterprise Edition, celle incluse dans Neo4j Desktop). WAIT ne rend
#     la main qu'une fois la base en ligne. Ici, le nom ne peut pas être
#     un paramètre (c'est un NOM, pas une valeur), il est donc mis dans
#     le texte entre accents graves (backticks) — ce qui n'est acceptable
#     que parce que may_be_emptied() l'a déjà vérifié.
# Les `if records:` avant et après ne servent qu'à choisir les bons
# messages.
# ---------------------------------------------------------------------
def recreate_databases(name: str) -> None:
    # Deleting the whole database and creating it again is the surest way to empty it:
    # nothing from before survives (tables, rows, nodes, relationships, constraints).
    if not may_be_emptied(name):
        raise ValueError(f'Refusing to empty "{name}": build_hours.py only empties databases named gharchive-...')

    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        exists = conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (name,)).fetchone() is not None
        if exists:
            print(f'Deleting the PostgreSQL database "{name}" and all its data ...')
            # WITH (FORCE) first closes other connections to it (e.g. pgAdmin), which would block the DROP.
            conn.execute(sql.SQL("DROP DATABASE {} WITH (FORCE)").format(sql.Identifier(name)))
            print(f'The PostgreSQL database "{name}" has been deleted.')
        else:
            print(f'The PostgreSQL database "{name}" doesn\'t exist yet: nothing to delete.')
        print(f'Creating the PostgreSQL database "{name}" (empty) ...')
        conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(name)))
        print(f'The PostgreSQL database "{name}" has been created.')

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        records = driver.execute_query("SHOW DATABASES YIELD name WHERE name = $name RETURN name",
                                       name=name, database_="system").records
        if records:
            print(f'Deleting the Neo4j database "{name}" and all its data, then creating it again (empty) ...')
        else:
            print(f'The Neo4j database "{name}" doesn\'t exist yet: nothing to delete. Creating it (empty) ...')
        # CREATE OR REPLACE = delete it if it exists, then create it (Enterprise Edition only).
        # WAIT: don't return until the new database is online.
        driver.execute_query(f"CREATE OR REPLACE DATABASE `{name}` WAIT", database_="system")
        if records:
            print(f'The Neo4j database "{name}" has been deleted and created again.')
        else:
            print(f'The Neo4j database "{name}" has been created.')


# ---------------------------------------------------------------------
# def databases_are_empty(name) -> bool:
#
# Ne pas supposer, VÉRIFIER : après la recréation, compter ce qu'il y a
# dedans des deux côtés. Tout doit valoir 0.
#
# PostgreSQL : information_schema.tables — NOUVEAU : un catalogue
#   standard (toute base SQL en possède un) qui liste toutes les tables.
#   table_schema = 'public' ne garde que NOS tables (celles de PostgreSQL
#   lui-même sont ailleurs). Cette fois, on se connecte à la nouvelle base
#   elle-même (dbname=name).
#
# Neo4j : trois comptages, dans la nouvelle base (database_=name) :
#   MATCH (n) RETURN count(n)            tous les nœuds
#   MATCH ()-[r]->() RETURN count(r)     toutes les relations
#   SHOW CONSTRAINTS ... count(name)     toutes les contraintes
#                                        (load_neo4j.py en crée deux ;
#                                        une base vide n'en a aucune)
#
# def count(query) à l'intérieur du bloc `with` : une fonction IMBRIQUÉE
# (voir test_extract_csv.py). Elle peut utiliser `driver` car elle est
# définie là où driver existe. Elle évite d'écrire trois fois la même
# longue ligne. .records[0][0] : la première ligne, sa première colonne
# — le nombre.
#
# Le rapport : un dictionnaire {quoi: combien}, parcouru avec .items()
# (des paires clé et valeur). Dans la f-string, :<20 complète le texte à
# 20 caractères, aligné à gauche, et :>3 aligne le nombre à droite sur 3
# caractères (voir summarize_data.py), pour que les lignes forment des
# colonnes bien rangées :
#   PostgreSQL tables      0   empty
#
# all(how_many == 0 for how_many in found.values())
#   all(...) vaut True seulement si CHAQUE élément vaut True (ici : chaque
#   comptage vaut 0). La partie à l'intérieur est une expression
#   GÉNÉRATRICE — comme une compréhension de liste, sans les crochets.
# ---------------------------------------------------------------------
def databases_are_empty(name: str) -> bool:
    # Checks both sides and prints what it finds; True only if everything is 0.
    print(f'Checking that the database "{name}" is empty on both sides ...')
    with psycopg.connect(host="localhost", user="postgres", dbname=name) as conn:
        tables = conn.execute(
            "SELECT count(*) FROM information_schema.tables WHERE table_schema = 'public'").fetchone()[0]

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        def count(query: str) -> int:
            return driver.execute_query(query, database_=name).records[0][0]
        nodes = count("MATCH (n) RETURN count(n)")
        relationships = count("MATCH ()-[r]->() RETURN count(r)")
        constraints = count("SHOW CONSTRAINTS YIELD name RETURN count(name)")

    found = {"PostgreSQL tables": tables, "Neo4j nodes": nodes,
             "Neo4j relationships": relationships, "Neo4j constraints": constraints}
    for what, how_many in found.items():
        print(f"  {what:<20} {how_many:>3}   {'empty' if how_many == 0 else 'NOT EMPTY'}")
    empty = all(how_many == 0 for how_many in found.values())
    if empty:
        print(f'The database "{name}" is empty in PostgreSQL and in Neo4j: ready to load.')
    return empty


# ---------------------------------------------------------------------
# def build(hours) -> bool:
#
# Tout le travail, en étapes numérotées qui sont affichées comme des
# titres (« == 0. ... », « == 1. ... ») ; le "\n" au début de chacune
# affiche d'abord une ligne vide, pour séparer les étapes à l'écran.
# Renvoie True seulement si les comptages des deux chargements
# correspondent à leurs CSV.
#
# Étape 0 — D'ABORD LES DEUX SERVEURS. pipeline.servers_not_ready() (voir
#   la copie annotée de pipeline.py) donne None ou la raison. C'est
#   vérifié avant de télécharger ou de supprimer quoi que ce soit : si
#   Neo4j était arrêté, l'étape 3 viderait PostgreSQL puis échouerait sur
#   Neo4j, laissant les deux côtés DIFFÉRENTS — la seule chose qu'une
#   comparaison ne peut pas se permettre.
#
# Étape 1 — TÉLÉCHARGER seulement ce qui manque : un fichier horaire déjà
#   présent dans data/hours/ est réutilisé (des jeux de données qui
#   partagent des heures partagent les fichiers).
#   download_gharchive.fetch_gz() est le même téléchargeur que d'habitude,
#   avec ses nouvelles tentatives ; il lève une erreur si GH Archive n'a
#   pas une heure. files.append(path) rassemble les chemins pour
#   l'étape 2.
#
# Étape 2 — EXTRAIRE avec extract_csv.extract() et write_all() (bots
#   exclus), dans data/hours/csv/<nom de la base>/ : chaque jeu de données
#   garde ses propres CSV.
#
# Étape 3 — VIDER : recréer la base des deux côtés, puis PROUVER qu'elle
#   est vide. Si elle ne l'est pas, s'arrêter avec False : rien n'est
#   chargé par-dessus d'anciennes données.
#
# Étapes 4 et 5 — CHARGER avec les mêmes chargeurs que pour le benchmark,
#   en passant le nom de la base. Chacun renvoie True si ses comptages
#   correspondent aux CSV (OK) et False sinon (MISMATCH ; le chargeur a
#   déjà affiché quel comptage est faux).
#
# Le RÉSUMÉ reprend l'essentiel sur une ligne : quelles heures, combien
#   d'acteurs / de dépôts / de connexions, et OK ou MISMATCH de chaque
#   côté. (Plusieurs f-strings côte à côte sont collées en une seule,
#   comme vu dans parse_args() de pipeline.py.)
# ---------------------------------------------------------------------
def build(hours: list[datetime]) -> bool:
    name = database_name(hours)
    csv_dir = HOURS_DIR / "csv" / name

    # Before changing anything: if one server isn't answering, stop now. Otherwise one side
    # could be emptied while the other can't be, leaving the two databases different.
    print("\n== 0. Check that both servers are answering")
    print("Connecting to PostgreSQL (localhost:5432) and Neo4j (localhost:7687) ...")
    problem = pipeline.servers_not_ready()
    if problem is not None:
        print(f"{problem}. Nothing was changed.")
        return False
    print("Both servers are answering.")

    print(f"\n== 1. Download {len(hours)} hour file(s) from GH Archive to {HOURS_DIR}")
    files = []
    for hour in hours:
        path = HOURS_DIR / pipeline.hour_file_name(hour)
        if path.exists():
            print(f"{path.name} is already on this computer: no need to download it again.")
        else:
            download_gharchive.fetch_gz(f"{hour:%Y-%m-%d}", hour.hour, HOURS_DIR)
        files.append(path)
    print(f"All {len(files)} hour file(s) are ready.")

    print("\n== 2. Extract actors, repos and connections into CSV files")
    print(f"Reading the events in {len(files)} file(s) (bots are left out) ...")
    actors, repos, pairs, skipped_bot_events = extract_csv.extract(files)
    print(f"Found {len(actors)} actors, {len(repos)} repos and {len(pairs)} connections "
          f"({skipped_bot_events} bot events skipped).")
    print(f"Writing actors.csv, repos.csv and actor_repo.csv to {csv_dir} ...")
    extract_csv.write_all(csv_dir, actors, repos, pairs)
    print("The CSV files have been written.")

    print(f'\n== 3. Empty the database "{name}" on both sides, and check that it is empty')
    recreate_databases(name)
    if not databases_are_empty(name):
        print(f'The database "{name}" isn\'t empty after being recreated; nothing was loaded.')
        return False

    print(f'\n== 4. Load the data into the PostgreSQL database "{name}"')
    print(f'The data is being loaded into the PostgreSQL database "{name}" ...')
    postgres_ok = load_postgres.load(csv_dir, name)
    if postgres_ok:
        print(f'The data has been loaded into the PostgreSQL database "{name}", and every count matches its CSV file.')
    else:
        print(f'The PostgreSQL database "{name}" was loaded, but some counts DON\'T match their CSV files (MISMATCH above).')

    print(f'\n== 5. Load the data into the Neo4j database "{name}"')
    print(f'The data is being loaded into the Neo4j database "{name}" ...')
    neo4j_ok = load_neo4j.load(csv_dir, name)
    if neo4j_ok:
        print(f'The data has been loaded into the Neo4j database "{name}", and every count matches its CSV file.')
    else:
        print(f'The Neo4j database "{name}" was loaded, but some counts DON\'T match their CSV files (MISMATCH above).')

    print(f'\nSummary: "{name}" holds {describe(hours)}: {len(actors)} actors, {len(repos)} repos '
          f"and {len(pairs)} connections, in PostgreSQL ({'OK' if postgres_ok else 'MISMATCH'}) "
          f"and in Neo4j ({'OK' if neo4j_ok else 'MISMATCH'}).")
    return postgres_ok and neo4j_ok


# ---------------------------------------------------------------------
# def main() -> None:
#
# 1. DEMANDER. Deux exceptions sont attrapées à la fois (un tuple dans
#    `except`) :
#      EOFError           input() n'a trouvé aucun clavier où lire (« End
#                         Of File », fin de fichier) — par ex. le script a
#                         été lancé par un planificateur ou avec son
#                         entrée redirigée. Il est fait pour être lancé à
#                         la main, donc il s'arrête.
#      KeyboardInterrupt  vous avez appuyé sur Ctrl+C pendant une
#                         question.
#    Dans les deux cas : un court message et le code de sortie 1, au lieu
#    d'une longue trace d'erreur (traceback).
#    Si vous avez répondu « n » à la confirmation, ask_hours() a renvoyé
#    None : « Nothing done. » avec le code de sortie 0 — c'est votre
#    choix, donc ce n'est pas un échec.
# 2. CONSTRUIRE, à l'intérieur d'un try / except Exception : une heure
#    absente de GH Archive, pas d'Internet, une erreur de base de
#    données... tout est signalé en une seule ligne lisible (« Stopped by
#    an error: ... ») au lieu d'une trace d'erreur.
# 3. Une dernière ligne qui dit Done ou NOT done, et le CODE DE SORTIE
#    (0 / 1, voir check_connections.py).
# ---------------------------------------------------------------------
def main() -> None:
    try:
        hours = ask_hours(datetime.now(timezone.utc))
    except (EOFError, KeyboardInterrupt):
        # EOFError: there's no keyboard to answer (this script is meant to be run by hand).
        print("\nNo hours chosen; nothing done.")
        sys.exit(1)
    if hours is None:
        print("Nothing done.")
        sys.exit(0)

    name = database_name(hours)
    try:
        ok = build(hours)
    except Exception as error:
        # e.g. an hour GH Archive doesn't have, no internet, a database error
        print(f"\nStopped by an error: {error}")
        ok = False
    print(f'\n{"Done" if ok else "NOT done (see the messages above)"}: database "{name}".')
    sys.exit(0 if ok else 1)


# La garde __name__ : voir la copie annotée de download_gharchive.py (et
# celle de pipeline.py, pour comprendre pourquoi elle permet aussi aux
# tests d'importer les fonctions de ce fichier sans exécuter main()).
if __name__ == "__main__":
    main()
