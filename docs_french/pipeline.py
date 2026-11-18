########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/pipeline.py.
# Il n'est PAS destiné à être exécuté dans le cadre du pipeline du projet — il
# se trouve dans docs_french/ car son but est d'enseigner, pas de s'exécuter.
# Le script réel et « propre » (sans tous ces commentaires) est
# scripts/pipeline.py.
#
# Ce fichier suppose que vous avez déjà lu les scripts annotés précédents —
# download_gharchive.py (fetch_gz), extract_csv.py (extract, write_all),
# load_postgres.py et load_neo4j.py (load), et check_connections.py.
# pipeline.py est le premier script qui ne fait pas lui-même un travail :
# il COORDONNE les autres. Ce qui est NOUVEAU ici relève surtout des
# bonnes pratiques de l'ingénierie des données : manipuler des dates et
# des heures en UTC (datetime, timedelta, timezone), importer nos propres
# scripts comme MODULES, la JOURNALISATION (logging) dans un fichier, un
# FICHIER DE VERROU pour que deux exécutions ne se chevauchent jamais, la
# création IDEMPOTENTE des bases de données, un try/except/finally autour
# de toute une exécution, et des CODES DE SORTIE pour un planificateur.
#
# NOUVEAU DANS CETTE VERSION — le mode --scheduled (« une fois par jour,
# tout seul ») : already_ran_today(), servers_not_ready(),
# skip_scheduled_run(), et deux petits FICHIERS D'ÉTAT
# (last_success_date.txt, scheduled_status.txt). Également nouveaux :
# `date` (un jour sans heure), la date locale par rapport à la date UTC,
# les DÉLAIS DE CONNEXION (timeouts), et les annotations de type comme
# `str | None` (« un str, ou None »).
#
# POURQUOI IL EXISTE — le projet comporte DEUX sortes de données :
#   1. des données FIXES pour la recherche : l'heure figée du benchmark
#      dans les bases « gharchive », plus les heures que VOUS choisissez,
#      chargées à la main avec build_hours.py dans leurs propres bases
#      « gharchive-... » (voir docs_french/build_hours.py). Jamais
#      modifiées automatiquement, pour que les mesures puissent toujours
#      être répétées sur les mêmes données ;
#   2. ce PIPELINE EN DIRECT : une fenêtre glissante de 24 heures dans des
#      bases SÉPARÉES appelées « gharchive24h », reconstruites une fois
#      par jour.
#
# COMMENT IL DÉMARRE — le Planificateur de tâches de Windows lance
#     ./run.sh scripts/pipeline.py --scheduled
# à l'ouverture de votre session, puis toutes les 15 minutes, de façon
# CACHÉE (sans fenêtre) via `conhost.exe --headless`. La plupart de ces
# démarrages n'ont rien à faire (l'exécution du jour a déjà réussi, ou
# Neo4j Desktop n'est pas encore ouvert) et s'arrêtent en une fraction de
# seconde — voir skip_scheduled_run(). Pour l'instant, le pipeline
# automatique est REPORTÉ : la phase de recherche utilise les données
# fixes du point 1. Le code reste prêt pour le jour où il sera activé.
########################################################################

"""Live pipeline: rebuild the "gharchive24h" databases from a rolling 24-hour window.

This is the project's second process, separate from the frozen benchmark data in
the "gharchive" databases (which it never touches). Each run:

    1. works out the window: the last WINDOW_HOURS complete UTC hours, shifted
       LAG_HOURS into the past (default: 24 hours, ending 24 hours ago), so that
       every hour in it has surely been published by GH Archive;
    2. downloads only the hours it doesn't have yet, and deletes those that have
       left the window;
    3. extracts the CSV files from the window's hours (extract_csv.py);
    4. rebuilds PostgreSQL and Neo4j from those same CSVs (load_postgres.py,
       load_neo4j.py), in the "gharchive24h" database on both sides;
    5. writes what happened to logs/pipeline.log.

If anything fails before loading (a missing hour, a database that isn't
running), the databases keep the previous window: nothing is half-replaced.
It runs on its own, once a day: Windows Task Scheduler starts it with --scheduled
every 15 minutes, and it only does the work if today's run hasn't succeeded yet
and both servers are answering (see README, step 6). It never asks anything.

Usage:
    ./run.sh scripts/pipeline.py
    ./run.sh scripts/pipeline.py --dry-run
    ./run.sh scripts/pipeline.py --window-hours 6 --lag-hours 2
    ./run.sh scripts/pipeline.py --scheduled     # what Task Scheduler runs
"""

# ---------------------------------------------------------------------
# Imports de la bibliothèque standard
#   logging   NOUVEAU : écrire des messages horodatés dans un fichier et
#             à l'écran (voir setup_logging()).
#   datetime, timedelta, timezone   NOUVEAU : des dates/heures et des
#             calculs sur celles-ci (voir compute_window()).
#   date      NOUVEAU : un JOUR du calendrier, sans heure (par ex.
#             2026-11-12). date.today() est la date du jour selon
#             l'horloge de VOTRE ordinateur (heure locale, pas UTC) —
#             utilisée par le mode --scheduled pour décider « l'exécution
#             du jour a-t-elle déjà eu lieu ? » (voir already_ran_today()).
#   os        pour os.getpid() et os.environ (comme dans
#             check_connections.py).
#   argparse, sys, time, Path : déjà expliqués dans les scripts
#             précédents.
# ---------------------------------------------------------------------
import argparse
import logging
import os
import sys
import time
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

# psycopg et GraphDatabase : les deux connecteurs de bases de données
# (voir check_connections.py). `sql` est l'outil de psycopg pour
# construire du SQL en toute sécurité quand un NOM (et non une valeur)
# doit figurer dans la requête — voir ensure_databases().
import psycopg
from neo4j import GraphDatabase
from psycopg import sql

# ---------------------------------------------------------------------
# import download_gharchive, extract_csv, load_neo4j, load_postgres
#
# NOUVEAU : importer NOS PROPRES scripts. Chaque fichier .py est aussi un
# MODULE que d'autres fichiers Python peuvent importer. Quand on exécute
# scripts/pipeline.py, Python cherche les imports dans le dossier où se
# trouve le script (scripts/), il y trouve donc les autres scripts.
#
# Importer un script exécute son code de premier niveau (constantes,
# définitions de fonctions) mais PAS son main() : c'est exactement à
# cela que sert la garde `if __name__ == "__main__":` en bas de chaque
# script. Le pipeline récupère donc leurs fonctions —
# download_gharchive.fetch_gz(), extract_csv.extract(),
# load_postgres.load()... — sans les exécuter comme des programmes. C'est
# de la RÉUTILISATION : le pipeline ne copie pas leur code, donc le
# benchmark et le pipeline utilisent toujours exactement la même logique.
# ---------------------------------------------------------------------
import download_gharchive
import extract_csv
import load_neo4j
import load_postgres

# ---------------------------------------------------------------------
# Où se trouvent les choses. Tout ce qui est sous data/ et logs/ est
# ignoré par git :
#   data/live/raw/               les fichiers horaires .json.gz de la
#                                fenêtre
#   data/live/csv/               les trois CSV des bases de 24 heures
#   data/live/pipeline.lock      n'existe que pendant une exécution
#   data/live/current_window.txt la dernière fenêtre chargée avec succès
#   logs/pipeline.log            l'historique de chaque exécution
# Les fichiers du benchmark (data/2026-08-27-15.json, data/csv/) et ceux
# de build_hours.py (data/hours/) sont séparés et jamais touchés.
# ---------------------------------------------------------------------
PROJECT_DIR = Path(__file__).resolve().parent.parent
LIVE_DIR = PROJECT_DIR / "data" / "live"
RAW_DIR = LIVE_DIR / "raw"
CSV_DIR = LIVE_DIR / "csv"
LOCK_FILE = LIVE_DIR / "pipeline.lock"
WINDOW_FILE = LIVE_DIR / "current_window.txt"
LOG_FILE = PROJECT_DIR / "logs" / "pipeline.log"
# ---------------------------------------------------------------------
# Deux FICHIERS D'ÉTAT, utilisés seulement par le mode --scheduled.
# Chacun contient une seule ligne et est ÉCRASÉ à chaque fois (ce n'est
# pas un historique — l'historique, c'est le journal) :
#   last_success_date.txt   la date de la dernière exécution réussie,
#                           par ex. « 2026-11-12 ». C'est la MÉMOIRE du
#                           pipeline entre deux démarrages : chaque
#                           démarrage est un tout nouveau processus Python
#                           qui ne se souvient de rien, donc « ai-je déjà
#                           tourné aujourd'hui ? » doit être noté dans un
#                           fichier.
#   scheduled_status.txt    ce qu'a trouvé le DERNIER démarrage, par ex.
#                           « 2026-11-12 10:15 (your time): Neo4j isn't
#                           answering (...); will try again at the next
#                           check » ou « ... run SUCCEEDED ». Comme la
#                           tâche tourne de façon cachée, c'est le moyen
#                           le plus rapide de voir ce qu'elle fait.
# ---------------------------------------------------------------------
# --scheduled only: the local date of the last successful run, and what the last attempt found.
LAST_SUCCESS_FILE = LIVE_DIR / "last_success_date.txt"
SCHEDULED_STATUS_FILE = LIVE_DIR / "scheduled_status.txt"

# ---------------------------------------------------------------------
# DEFAULT_DATABASE = "gharchive24h"
#   Pas "gharchive_24h" : les noms de bases de données Neo4j ne peuvent
#   contenir que des lettres, des chiffres, des points et des tirets —
#   pas de tirets bas. Le même nom est utilisé des deux côtés, comme
#   pour le « gharchive » du benchmark.
# DEFAULT_WINDOW_HOURS / DEFAULT_LAG_HOURS — 24 heures de données, se
#   terminant il y a 24 heures (voir compute_window()). Les deux peuvent
#   être modifiés depuis la ligne de commande.
# STALE_LOCK_HOURS — l'âge à partir duquel un fichier de verrou est
#   considéré comme abandonné (voir acquire_lock()).
# ---------------------------------------------------------------------
DEFAULT_DATABASE = "gharchive24h"  # Neo4j doesn't allow "_" in database names
DEFAULT_WINDOW_HOURS = 24
DEFAULT_LAG_HOURS = 24
STALE_LOCK_HOURS = 3

# ---------------------------------------------------------------------
# log = logging.getLogger("pipeline")
#
# Un LOGGER (journaliseur) est un objet qui écrit des messages avec un
# NIVEAU, indiquant l'importance de chacun :
#   log.info("...")       progression normale (« Window: ... »,
#                         « Status: ... »)
#   log.warning("...")    quelque chose d'inhabituel, mais l'exécution
#                         continue
#   log.error("...")      quelque chose s'est mal passé
#   log.exception("...")  une erreur, plus la trace complète (traceback)
#                         de l'exception en cours de traitement
# Par rapport à print(), chaque message reçoit un horodatage et un niveau,
# et peut aller à plusieurs endroits à la fois (ici : un fichier et
# l'écran).
# ---------------------------------------------------------------------
log = logging.getLogger("pipeline")


# ---------------------------------------------------------------------
# def setup_logging() -> None:
#
# Configure OÙ vont les messages et à QUOI ils ressemblent :
#
#   Formatter("%(asctime)s UTC  %(levelname)-7s  %(message)s", ...)
#     chaque ligne devient par ex.
#     2026-10-22 12:44:14 UTC  INFO     Window: 2026-10-20 12:00 -> ...
#   formatter.converter = time.gmtime
#     écrire les heures en UTC au lieu de l'heure locale de l'ordinateur
#     — la même horloge que celle des noms de fichiers de GH Archive, pour
#     que le journal et la fenêtre puissent être comparés directement (le
#     Portugal a une heure d'avance sur l'UTC en été, et cette heure
#     sèmerait sinon la confusion).
#   FileHandler(LOG_FILE)    ajouter chaque message à logs/pipeline.log
#   StreamHandler(sys.stdout) et l'afficher aussi à l'écran
#
# Les handlers (gestionnaires) sont placés sur le logger RACINE
# (logging.getLogger() sans nom), le parent de tous les loggers. Les
# messages de n'importe quel logger « remontent » jusqu'à lui, donc
# l'avertissement qu'extract_csv.py écrit avec son propre logger (par ex.
# « Skipped 2 event(s) without an actor or repo id ») aboutit dans le
# même fichier.
#
# logging.getLogger("neo4j").setLevel(logging.WARNING)
#   Le pilote Neo4j a son propre logger et signale des notifications
#   INFORMATIVES du serveur au niveau INFO. La première vraie exécution en
#   a affiché une longue (« server has caught up ») juste après CREATE
#   DATABASE — sans danger, mais c'est du bruit. Ceci ne garde que les
#   avertissements et les erreurs du pilote.
# ---------------------------------------------------------------------
def setup_logging() -> None:
    LOG_FILE.parent.mkdir(parents=True, exist_ok=True)
    # Log times in UTC, like GH Archive's file names, so the window and the log line up.
    formatter = logging.Formatter("%(asctime)s UTC  %(levelname)-7s  %(message)s", "%Y-%m-%d %H:%M:%S")
    formatter.converter = time.gmtime
    # Handlers go on the root logger, so warnings from the other scripts (e.g. extract_csv)
    # end up in the same log file.
    root = logging.getLogger()
    for handler in (logging.FileHandler(LOG_FILE, encoding="utf-8"), logging.StreamHandler(sys.stdout)):
        handler.setFormatter(formatter)
        root.addHandler(handler)
    root.setLevel(logging.INFO)
    # The Neo4j driver logs informational server notifications (e.g. "server has caught up"
    # after CREATE DATABASE); only its warnings and errors belong in this log.
    logging.getLogger("neo4j").setLevel(logging.WARNING)


# ---------------------------------------------------------------------
# def compute_window(now, window_hours, lag_hours) -> list[datetime]:
#
# Détermine QUELLES HEURES contient la fenêtre. Un `datetime` est une
# date et une heure ensemble ; un `timedelta` est une durée, et on peut
# l'ajouter à un datetime ou l'en soustraire (« cette heure moins 24
# heures »).
#
# Étape par étape, avec now = 2026-10-22 11:15 UTC et les valeurs par
# défaut :
#   now.replace(minute=0, second=0, microsecond=0)
#       -> 2026-10-22 11:00   (arrondir VERS LE BAS au début de l'heure)
#   - timedelta(hours=lag_hours)        (24)
#       -> end   = 2026-10-21 11:00   la fenêtre SE TERMINE ici
#   end - timedelta(hours=window_hours) (24)
#       -> start = 2026-10-20 11:00   la fenêtre COMMENCE ici
#   [start + timedelta(hours=i) for i in range(24)]
#       -> 2026-10-20 11:00, 12:00, ..., 2026-10-21 10:00   (24 heures)
#
# Chaque élément est le DÉBUT d'un fichier horaire : le dernier, 10:00,
# couvre 10:00-11:00, donc la fenêtre se termine exactement à 11:00.
# L'heure `end` elle-même n'est PAS incluse.
#
# Pourquoi ce décalage : GH Archive publie chaque heure un peu après sa
# fin, et parfois plus tard. Terminer la fenêtre il y a un jour garantit
# que chacune de ses heures a forcément été publiée. Le décalage est un
# paramètre (--lag-hours), il pourra donc être réduit plus tard.
#
# `now` est un paramètre (au lieu de lire l'horloge à l'intérieur) pour
# que la fonction puisse être TESTÉE avec n'importe quelle heure, comme
# dans l'exemple ci-dessus.
# ---------------------------------------------------------------------
def compute_window(now: datetime, window_hours: int, lag_hours: int) -> list[datetime]:
    # Example (24 h, lag 24 h): now 2026-10-22 11:15 UTC -> hours 2026-10-20 11:00 ... 2026-10-21 10:00,
    # i.e. the window 2026-10-20 11:00 -> 2026-10-21 11:00.
    end = now.replace(minute=0, second=0, microsecond=0) - timedelta(hours=lag_hours)
    start = end - timedelta(hours=window_hours)
    return [start + timedelta(hours=i) for i in range(window_hours)]


# ---------------------------------------------------------------------
# def hour_file_name(hour) -> str:
#
# f"{hour:%Y-%m-%d}" formate le datetime avec un modèle de date :
#   %Y année (2026), %m mois (10), %d jour (20)  ->  "2026-10-20"
# hour.hour est simplement l'heure sous forme de nombre (5), donc sans
# zéro initial — exactement comme GH Archive nomme ses fichiers :
# 2026-10-20-5.json.gz.
# ---------------------------------------------------------------------
def hour_file_name(hour: datetime) -> str:
    # Same naming as GH Archive: UTC hour without a leading zero, e.g. 2026-10-20-5.json.gz
    return f"{hour:%Y-%m-%d}-{hour.hour}.json.gz"


# ---------------------------------------------------------------------
# def acquire_lock() -> bool:
#
# Un FICHIER DE VERROU empêche deux exécutions de travailler en même
# temps. Le Planificateur de tâches lance le pipeline toutes les 15
# minutes ; si une exécution durait plus longtemps (un téléchargement
# lent, une grande fenêtre), le démarrage suivant pourrait commencer
# pendant que le premier est encore en train de charger — et les deux
# videraient et rempliraient les mêmes bases de données en même temps.
# (Quelqu'un qui le lancerait à la main pendant une exécution planifiée
# causerait le même problème.)
#
#   - Pas de fichier de verrou ?          -> le créer et continuer (True).
#   - Verrou âgé de moins de 3 h ?        -> une autre exécution est en
#                                            cours : ne pas démarrer
#                                            (False).
#   - Verrou âgé de plus de 3 h ?         -> une exécution précédente a
#                                            planté sans le supprimer
#                                            (verrou « périmé ») : le
#                                            supprimer, journaliser un
#                                            avertissement, et continuer.
#
# LOCK_FILE.stat().st_mtime est le moment où le fichier a été écrit pour
# la dernière fois (en secondes depuis 1970) ; time.time() est
# maintenant, dans la même unité, donc la différence divisée par 3600 est
# son âge en heures. Le contenu du fichier (l'identifiant du processus et
# l'heure de démarrage) n'est là que pour qui le consulte à la main.
# ---------------------------------------------------------------------
def acquire_lock() -> bool:
    # If a previous run is still going (or crashed without cleaning up), don't start a second one.
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    if LOCK_FILE.exists():
        age_hours = (time.time() - LOCK_FILE.stat().st_mtime) / 3600
        if age_hours < STALE_LOCK_HOURS:
            return False
        log.warning("Removing stale lock file (%.1f hours old)", age_hours)
        LOCK_FILE.unlink()
    LOCK_FILE.write_text(f"pid {os.getpid()} started {datetime.now(timezone.utc):%Y-%m-%d %H:%M:%S} UTC\n")
    return True


# ---------------------------------------------------------------------
# def sync_raw_files(hours) -> None:
#
# Fait en sorte que data/live/raw/ contienne EXACTEMENT les fichiers
# horaires de la fenêtre :
#
#   1. wanted = l'ensemble des noms de fichiers qui doivent être là.
#   2. Tout fichier du dossier qui n'est pas voulu (une heure sortie de
#      la fenêtre, ou un « .part » restant d'un téléchargement
#      interrompu) est supprimé. RAW_DIR.iterdir() liste le contenu du
#      dossier.
#   3. missing = les heures de la fenêtre dont le fichier n'est pas
#      encore là, et seules celles-ci sont téléchargées, avec
#      download_gharchive.fetch_gz().
#
# Ainsi, la première exécution télécharge les 24 heures, et chaque
# exécution suivante ne télécharge que la nouvelle heure et supprime
# celle qui est sortie — c'est ce qui rend l'exécution horaire peu
# coûteuse.
#
# log.info("%d of %d ...", a, b, c) — logging remplit les emplacements %d
# avec les arguments supplémentaires, dans l'ordre (%d = nombre entier).
# ---------------------------------------------------------------------
def sync_raw_files(hours: list[datetime]) -> None:
    RAW_DIR.mkdir(parents=True, exist_ok=True)
    wanted = {hour_file_name(hour) for hour in hours}

    for path in RAW_DIR.iterdir():
        if path.name not in wanted:
            path.unlink()
            log.info("Removed %s (outside the window)", path.name)

    missing = [hour for hour in hours if not (RAW_DIR / hour_file_name(hour)).exists()]
    log.info("%d of %d hour files already present; downloading %d", len(hours) - len(missing), len(hours), len(missing))
    for hour in missing:
        download_gharchive.fetch_gz(f"{hour:%Y-%m-%d}", hour.hour, RAW_DIR)


# ---------------------------------------------------------------------
# def ensure_databases(database) -> None:
#
# S'assure que la base de données cible existe des DEUX côtés, en la
# créant seulement si elle n'existe pas. C'est l'IDEMPOTENCE : l'exécuter
# une fois ou dix fois donne le même résultat, donc la toute première
# exécution s'installe toute seule, et une base de données supprimée par
# erreur est simplement recréée par l'exécution suivante.
#
# PostgreSQL :
#   - Se connecte à la base « postgres », toujours présente (on ne peut
#     pas créer une base de données tout en y étant connecté).
#   - autocommit=True : CREATE DATABASE ne peut pas s'exécuter dans une
#     transaction.
#   - pg_database est le catalogue des bases de données de PostgreSQL :
#     le SELECT demande « y en a-t-il une avec ce nom ? ». %s est un
#     PARAMÈTRE : psycopg insère la valeur en toute sécurité.
#   - Un NOM de base de données ne peut pas être passé en paramètre, il
#     est donc construit avec
#     sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)),
#     qui met correctement le nom entre guillemets au lieu de coller du
#     texte brut dans le SQL.
#
# Neo4j :
#   CREATE DATABASE `gharchive24h` IF NOT EXISTS WAIT
#     IF NOT EXISTS  ne fait rien si elle existe déjà
#     WAIT           ne rend la main qu'une fois la nouvelle base en ligne
#   Elle est envoyée à la base « system », où Neo4j gère les bases de
#   données et les utilisateurs. (Créer des bases supplémentaires
#   nécessite l'Enterprise Edition de Neo4j — celle incluse dans Neo4j
#   Desktop.)
#
# C'est aussi une VÉRIFICATION PRÉALABLE : elle est appelée avant tout
# chargement, donc si l'un des serveurs est arrêté, l'exécution échoue
# ici, avant que quoi que ce soit n'ait été vidé.
# ---------------------------------------------------------------------
def ensure_databases(database: str) -> None:
    # Also a pre-flight check: if either server isn't reachable, stop before changing anything.
    with psycopg.connect(host="localhost", user="postgres", dbname="postgres", autocommit=True) as conn:
        if conn.execute("SELECT 1 FROM pg_database WHERE datname = %s", (database,)).fetchone() is None:
            conn.execute(sql.SQL("CREATE DATABASE {}").format(sql.Identifier(database)))
            log.info("Created PostgreSQL database %s", database)

    auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
    with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth) as driver:
        driver.verify_connectivity()
        driver.execute_query(f"CREATE DATABASE `{database}` IF NOT EXISTS WAIT", database_="system")


# ---------------------------------------------------------------------
# def run(window_hours, lag_hours, database, dry_run) -> bool:
#
# Une exécution complète, étape par étape, chacune chronométrée et
# journalisée :
#   1. calculer la fenêtre à partir de l'heure UTC actuelle ;
#   2. (simulation, dry run : seulement lister les fichiers et
#      s'arrêter — rien ne change) ;
#   3. synchroniser les fichiers horaires (télécharger ce qui manque) ;
#   4. extraire les CSV, en réutilisant les fonctions d'extract_csv ;
#   5. s'assurer que les deux bases de données existent (et que les deux
#      serveurs répondent) ;
#   6. charger PostgreSQL, puis Neo4j, en réutilisant les chargeurs, avec
#      le nom de la base de données transmis ;
#   7. si les deux chargements correspondent à leurs CSV, enregistrer la
#      fenêtre dans current_window.txt — et, pour la vraie base
#      « gharchive24h », la date du jour dans last_success_date.txt (voir
#      plus bas).
# Renvoie True seulement si les vérifications des deux chargements sont
# OK.
#
# L'ORDRE est délibéré : tout ce qui peut échouer sans dommage
# (téléchargement, extraction, connexion) se passe AVANT qu'une base de
# données ne soit vidée. S'il manque une heure ou qu'un serveur est
# arrêté, les bases de données gardent la fenêtre précédente.
#
# hours[-1] + timedelta(hours=1) est la FIN de la fenêtre : le début de
# la dernière heure plus une heure.
# ---------------------------------------------------------------------
def run(window_hours: int, lag_hours: int, database: str, dry_run: bool) -> bool:
    hours = compute_window(datetime.now(timezone.utc), window_hours, lag_hours)
    window = f"{hours[0]:%Y-%m-%d %H:00} -> {hours[-1] + timedelta(hours=1):%Y-%m-%d %H:00} UTC"
    log.info("Window: %s (%d hours, lag %d h), database %s", window, window_hours, lag_hours, database)

    if dry_run:
        for hour in hours:
            present = (RAW_DIR / hour_file_name(hour)).exists()
            log.info("  %s  %s", hour_file_name(hour), "present" if present else "to download")
        return True

    run_start = time.perf_counter()

    step = time.perf_counter()
    sync_raw_files(hours)
    log.info("Download step done in %.1f s", time.perf_counter() - step)

    step = time.perf_counter()
    files = [RAW_DIR / hour_file_name(hour) for hour in hours]
    actors, repos, pairs, skipped_bot_events = extract_csv.extract(files)
    extract_csv.write_all(CSV_DIR, actors, repos, pairs)
    log.info("Extracted %d actors, %d repos, %d connections (%d bot events skipped) in %.1f s",
             len(actors), len(repos), len(pairs), skipped_bot_events, time.perf_counter() - step)

    ensure_databases(database)

    step = time.perf_counter()
    postgres_ok = load_postgres.load(CSV_DIR, database)
    log.info("PostgreSQL load %s in %.1f s", "OK" if postgres_ok else "MISMATCH", time.perf_counter() - step)

    step = time.perf_counter()
    neo4j_ok = load_neo4j.load(CSV_DIR, database)
    log.info("Neo4j load %s in %.1f s", "OK" if neo4j_ok else "MISMATCH", time.perf_counter() - step)

    if postgres_ok and neo4j_ok:
        WINDOW_FILE.write_text(f"{window}\n{len(actors)} actors, {len(repos)} repos, {len(pairs)} connections\n")
        # -------------------------------------------------------------
        # Retenir « l'exécution du jour a réussi » — mais seulement quand
        # c'est la VRAIE base de données qui a été reconstruite. Une
        # exécution de test comme --database gharchivetest ne doit pas
        # faire croire à la tâche planifiée que le travail du jour est
        # fait.
        #
        # date.today() est la date LOCALE (le calendrier de votre
        # ordinateur), volontairement, même si tout le reste ici est en
        # UTC : « une fois par jour » s'entend de votre point de vue. Vers
        # minuit, les deux peuvent différer — à 00:30 à Madrid en hiver,
        # c'est encore la veille en UTC — et une date UTC ferait
        # « changer de jour » l'exécution quotidienne à une heure locale
        # bizarre.
        #
        # f"{date.today():%Y-%m-%d}" la formate en « 2026-11-12 » (le même
        # modèle de date que dans hour_file_name()) ; "\n" termine la
        # ligne.
        # -------------------------------------------------------------
        if database == DEFAULT_DATABASE:
            # Your computer's date, not UTC: "once a day" means once per day of yours.
            LAST_SUCCESS_FILE.write_text(f"{date.today():%Y-%m-%d}\n")
    log.info("Run finished in %.1f s", time.perf_counter() - run_start)
    return postgres_ok and neo4j_ok


# ---------------------------------------------------------------------
# parse_args() : les options du pipeline. Toutes ont une valeur par
# défaut, donc le planificateur peut le lancer sans aucune option.
#   --window-hours   la taille de la fenêtre (par ex. 6 pour un test
#                    rapide)
#   --lag-hours      à quelle distance dans le passé elle se termine
#   --database       quelle base de données reconstruire des deux côtés
#   --dry-run        afficher seulement le plan (un DRAPEAU, comme l'était
#                    --exclude-bots)
#   --scheduled      NOUVEAU : un autre drapeau, celui que passe le
#                    Planificateur de tâches. Il ajoute les vérifications
#                    « y a-t-il quelque chose à faire ? » de
#                    skip_scheduled_run() avant l'exécution (voir main()).
#                    Lancé à la main sans lui, le pipeline s'exécute
#                    toujours.
# formatter_class=RawDescriptionHelpFormatter conserve les sauts de ligne
# de la docstring quand --help l'affiche.
#
# Remarquez le texte help= de --scheduled : deux chaînes littérales côte
# à côte ("... run " "already ...") sont COLLÉES en une seule par Python.
# C'est une façon de couper un long texte sur deux lignes sans signe +.
# ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--window-hours", type=int, default=DEFAULT_WINDOW_HOURS,
                         help=f"How many hours the window covers (default: {DEFAULT_WINDOW_HOURS})")
    parser.add_argument("--lag-hours", type=int, default=DEFAULT_LAG_HOURS,
                         help=f"How far back the window ends, in hours (default: {DEFAULT_LAG_HOURS})")
    parser.add_argument("--database", default=DEFAULT_DATABASE,
                         help=f"Database to rebuild on both sides (default: {DEFAULT_DATABASE})")
    parser.add_argument("--dry-run", action="store_true",
                         help="Only show the window and which files would be downloaded; change nothing")
    parser.add_argument("--scheduled", action="store_true",
                         help="For Task Scheduler, which starts it every 15 minutes: do nothing if today's run "
                              "already succeeded, or if PostgreSQL or Neo4j isn't answering yet")
    return parser.parse_args()


# ---------------------------------------------------------------------
# def already_ran_today(last_success, today) -> bool:
#
# Répond à « l'exécution du jour a-t-elle déjà réussi ? », à partir de :
#   last_success   le TEXTE de last_success_date.txt, par ex.
#                  "2026-11-12\n", ou None si le fichier n'existe pas
#                  encore (jamais exécuté) ;
#   today          la date du jour.
#
# `str | None` est une annotation de type qui signifie « un str OU
# None ». Le `|` se lit « ou ». Ce n'est qu'une note pour le lecteur
# (Python ne la fait pas respecter), mais elle prévient que la fonction
# doit gérer None.
#
# Comment elle décide, de gauche à droite :
#   last_success is not None   — si c'EST None, `and` s'arrête ici même
#                                et la réponse est False. (Cela évite
#                                aussi d'appeler .strip() sur None, ce
#                                qui serait une erreur.)
#   last_success.strip()       — enlève le "\n" (et les éventuels espaces)
#                                aux extrémités, donc "2026-11-12\n"
#                                devient "2026-11-12" ;
#   == f"{today:%Y-%m-%d}"     — le compare avec la date du jour écrite de
#                                la même façon.
#
# Pourquoi est-elle si petite et séparée ? C'est une fonction PURE : elle
# reçoit le texte du fichier et la date en PARAMÈTRES, au lieu de lire
# elle-même le fichier et l'horloge. On peut donc la TESTER avec
# n'importe quelle date, sans fichiers — pour la même raison que
# compute_window() reçoit `now` en paramètre (voir
# docs_french/test_pipeline.py).
# ---------------------------------------------------------------------
def already_ran_today(last_success: str | None, today: date) -> bool:
    # last_success is the text of LAST_SUCCESS_FILE (None if it doesn't exist yet).
    return last_success is not None and last_success.strip() == f"{today:%Y-%m-%d}"


# ---------------------------------------------------------------------
# def servers_not_ready() -> str | None:
#
# Demande aux deux serveurs « êtes-vous là ? », de la façon la moins
# coûteuse possible, et répond par :
#   None                 les deux ont répondu — prêt à travailler ;
#   un court texte       la RAISON pour laquelle l'un n'a pas répondu
#                        (par ex. « Neo4j isn't answering (...) »).
# Renvoyer « le problème, ou None s'il n'y en a pas » est un schéma
# courant : l'appelant vérifie `if reason is not None:` et a le message
# tout prêt à afficher.
#
# C'est le même genre de connexion que dans check_connections.py, avec
# deux différences :
#   - DÉLAIS (timeouts) : connect_timeout=5 (psycopg) et
#     connection_timeout=5 (Neo4j) abandonnent au bout de 5 secondes.
#     Quand un serveur ne tourne pas, la vérification doit échouer
#     RAPIDEMENT, pas rester bloquée — elle est répétée toutes les 15
#     minutes en arrière-plan.
#   - Les exceptions sont ATTRAPÉES et transformées en message au lieu
#     d'arrêter le programme : ici, un serveur qui ne répond pas est une
#     situation normale (par ex. vous n'avez pas encore ouvert Neo4j
#     Desktop), pas une erreur.
#
# « SELECT 1 » est la plus petite requête SQL possible : elle prouve
# simplement que la connexion fonctionne. verify_connectivity() fait de
# même pour Neo4j (voir check_connections.py).
#
# Le mot de passe : celui de PostgreSQL vient tout seul de PGPASSWORD,
# celui de Neo4j est lu dans os.environ — exactement comme dans
# check_connections.py. Les deux viennent de secrets.sh via run.sh ;
# aucun n'est jamais écrit dans le code.
#
# build_hours.py réutilise cette fonction comme son « étape 0 » (voir
# docs_french/build_hours.py).
# ---------------------------------------------------------------------
def servers_not_ready() -> str | None:
    # Returns None if both servers answer, or a short reason if one doesn't (it isn't running yet).
    try:
        with psycopg.connect(host="localhost", user="postgres", dbname="postgres", connect_timeout=5) as conn:
            conn.execute("SELECT 1")
    except Exception:
        return "PostgreSQL isn't answering"
    try:
        auth = (load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"])
        with GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=auth, connection_timeout=5) as driver:
            driver.verify_connectivity()
    except Exception:
        return "Neo4j isn't answering (is Neo4j Desktop open, with the instance started?)"
    return None


# ---------------------------------------------------------------------
# def skip_scheduled_run() -> bool:
#
# La BARRIÈRE du mode --scheduled. Renvoie True si ce démarrage ne doit
# rien faire, False si la vraie exécution doit avoir lieu. Deux raisons
# de sauter, vérifiées dans cet ordre :
#   1. l'exécution du jour a déjà réussi  -> rien à faire avant demain ;
#   2. un serveur ne répond pas           -> réessayer dans 15 minutes.
# La vérification peu coûteuse (lire un fichier d'une ligne) vient en
# premier, donc la plupart du temps les serveurs ne sont même pas
# contactés.
#
# Ligne par ligne :
#   X if condition else Y   (déjà vu) — lire le texte du fichier s'il
#       existe, sinon None, que already_ran_today() sait gérer.
#   reason += "; will try ..."   `+=` ajoute du texte à la FIN d'une
#       chaîne ("a" += "b" donne "ab"). Fait seulement si reason n'est pas
#       None — ajouter quelque chose à None serait une erreur.
#   if reason is None: return False   rien n'empêche l'exécution.
#   Sinon : écrire UNE ligne dans scheduled_status.txt (write_text
#       remplace tout le fichier, qui montre donc toujours la DERNIÈRE
#       vérification), l'afficher aussi, et renvoyer True.
#
# datetime.now() SANS timezone.utc donne l'heure LOCALE de votre
# ordinateur — d'où « (your time) » dans le texte. Ce fichier est fait
# pour être lu par vous, donc l'heure locale est plus claire ; le journal
# continue d'utiliser l'UTC.
#
# POURQUOI ELLE S'EXÉCUTE AVANT setup_logging() : elle peut être appelée
# jusqu'à 96 fois par jour (toutes les 15 minutes) et ne trouve presque
# jamais rien à faire. Si chacune de ces vérifications écrivait dans
# logs/pipeline.log, les vraies exécutions seraient noyées sous des
# milliers de lignes « rien à faire ». Les vérifications se contentent
# donc d'écraser leur fichier d'état d'une ligne, et le journal ne reçoit
# que les vraies exécutions.
# ---------------------------------------------------------------------
def skip_scheduled_run() -> bool:
    # Runs before logging is set up, so the frequent "nothing to do" checks don't fill
    # logs/pipeline.log: their result only goes to SCHEDULED_STATUS_FILE (overwritten each time).
    last_success = LAST_SUCCESS_FILE.read_text() if LAST_SUCCESS_FILE.exists() else None
    if already_ran_today(last_success, date.today()):
        reason = "today's run already succeeded; nothing to do"
    else:
        reason = servers_not_ready()
        if reason is not None:
            reason += "; will try again at the next check"
    if reason is None:
        return False
    LIVE_DIR.mkdir(parents=True, exist_ok=True)
    SCHEDULED_STATUS_FILE.write_text(f"{datetime.now():%Y-%m-%d %H:%M} (your time): {reason}\n")
    print(reason)
    return True


# ---------------------------------------------------------------------
# def main() -> None:
#
# 0. NOUVEAU — BARRIÈRE PLANIFIÉE : avec --scheduled (et sans --dry-run),
#    demander d'abord à skip_scheduled_run() ; s'il n'y a rien à faire,
#    s'arrêter aussitôt avec sys.exit(0) — un succès, car « rien à
#    faire » est normal. Cela se passe AVANT setup_logging(), donc ces
#    sorties rapides ne touchent jamais le journal (voir
#    skip_scheduled_run()).
# 1. GARDE-FOU : refuser de toucher à « gharchive », la base figée du
#    benchmark — même si quelqu'un tape --database gharchive par erreur.
# 2. VERROU : si une autre exécution est en cours, sauter celle-ci.
#    sys.exit(0) (succès) volontairement : sauter une exécution est
#    normal, ce n'est pas une erreur.
# 3. try / except / finally :
#      try      exécuter tout le pipeline ;
#      except   si QUOI QUE CE SOIT lève une exception, la journaliser
#               avec sa trace complète (log.exception) et marquer
#               l'exécution comme échouée, au lieu de planter sans
#               laisser de trace dans le journal ;
#      finally  s'exécute dans TOUS les cas, succès ou échec : supprimer
#               le fichier de verrou, pour que l'exécution suivante ne
#               soit pas bloquée.
# 4. NOUVEAU — avec --scheduled, écrire le RÉSULTAT de l'exécution dans
#    scheduled_status.txt, pour que le fichier dise toujours ce qu'a fait
#    le dernier démarrage : sauté, réussi ou échoué.
# 5. CODE DE SORTIE : sys.exit(0) en cas de succès, sys.exit(1) en cas
#    d'échec. Utile quand vous le lancez à la main ou depuis un autre
#    script. MAIS : le « Résultat de la dernière exécution » du
#    Planificateur de tâches affiche toujours 0x0 ici, même après un
#    échec, car le lanceur caché (conhost.exe --headless) ne transmet pas
#    le code de sortie. C'est pour cela qu'existe le fichier d'état de
#    l'étape 4 : c'est là qu'un échec planifié devient visible.
# ---------------------------------------------------------------------
def main() -> None:
    args = parse_args()
    # Étape 0. `and` s'évalue de gauche à droite et s'arrête au premier
    # False, donc skip_scheduled_run() (qui peut contacter les serveurs)
    # n'est appelée que si --scheduled a été donné et que ce n'est pas un
    # dry run.
    if args.scheduled and not args.dry_run and skip_scheduled_run():
        sys.exit(0)
    setup_logging()

    if args.database == "gharchive":
        log.error("Refusing to rebuild 'gharchive': that database holds the frozen benchmark data")
        sys.exit(1)
    if not args.dry_run and not acquire_lock():
        log.warning("Another pipeline run is still in progress; skipping this one")
        sys.exit(0)

    try:
        ok = run(args.window_hours, args.lag_hours, args.database, args.dry_run)
    except Exception:
        log.exception("Run FAILED; the databases keep their previous contents unless a load had already started")
        ok = False
    finally:
        if not args.dry_run:
            LOCK_FILE.unlink(missing_ok=True)

    log.info("Status: %s", "SUCCESS" if ok else "FAILURE")
    # Étape 4 : le résultat, à votre heure locale, pour qui ouvre
    # data/live/scheduled_status.txt. En cas d'échec, il renvoie au
    # journal, où log.exception() a écrit tous les détails.
    if args.scheduled and not args.dry_run:
        outcome = "run SUCCEEDED" if ok else "run FAILED (see logs/pipeline.log); will try again at the next check"
        SCHEDULED_STATUS_FILE.write_text(f"{datetime.now():%Y-%m-%d %H:%M} (your time): {outcome}\n")
    sys.exit(0 if ok else 1)


# Voir la copie annotée de download_gharchive.py pour la garde __name__ —
# ici, elle compte doublement : c'est aussi elle qui permet à D'AUTRES
# scripts d'importer les fonctions d'un script sans exécuter son main().
if __name__ == "__main__":
    main()
