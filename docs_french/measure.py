########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/measure.py.
# Il n'est PAS destiné à être exécuté — il se trouve dans docs_french/ car
# son but est d'enseigner, pas de s'exécuter. Le script réel et « propre »
# (sans tous ces commentaires) est scripts/measure.py.
#
# Lisez d'abord ces copies annotées ; ce qu'elles expliquent n'est PAS
# répété ici :
#   - download_gharchive.py   argparse, Path, main() et la garde __name__,
#                             try/except et le lancement d'erreurs
#   - extract_csv.py          le module csv, open(..., newline=""),
#                             mkdir(parents=True, exist_ok=True), sorted(...),
#                             les ensembles (sets)
#   - load_neo4j.py           csv.DictReader, driver.execute_query(..., database_=...)
#   - check_connections.py    les connexions psycopg / neo4j, `with`, sys.exit
#   - pipeline.py             RawDescriptionHelpFormatter
#   - build_hours.py          datetime, timedelta, strptime, et la façon dont
#                             les bases sont NOMMÉES (gharchive-<date>-<heure>[-<n>h])
#   - summarize_data.py       les compréhensions de dictionnaire, la largeur
#                             des colonnes dans les f-strings
#   - test_build_hours.py     lambda, iter() et next()
#   - traversal.py            les requêtes de parcours (SQL, Cypher « paths »
#                             et « levels »), l'objet Outcome (status /
#                             seconds / count / error), les délais maximum,
#                             et les chiffres de TRAVAIL (données traitées,
#                             mémoire) tirés de EXPLAIN (ANALYZE, BUFFERS)
#                             et de PROFILE
#   - choose_starts.py        comment les 20 acteurs de départ sont choisis
#                             (choose_in_both), statistics.median
#
# Ce qui est NOUVEAU ici — c'est le script qui produit vraiment les
# chiffres de la recherche, donc la plupart des explications portent sur
# la façon de MESURER ÉQUITABLEMENT et sur le fichier de résultats :
#   - UN fichier CSV par mesure, results/<base>_<date>_<heure>.csv.
#     Une ligne = une question à laquelle les deux bases répondent
#     (csv.DictWriter) ;
#   - sa disposition en trois parties : les colonnes du test, puis un bloc
#     PostgreSQL et un bloc Neo4j aux colonnes IDENTIQUES, puis la
#     comparaison ;
#   - les quatre choses comparées : les données traitées, le temps,
#     l'espace (mémoire et disque) et la puissance de calcul (les secondes
#     de CPU des processus SERVEURS des bases, mesurées avec psutil) ;
#   - le module `re` : lire la fenêtre de temps des données dans le nom de
#     la base ;
#   - la « première exécution » : ce n'est pas un résultat, mais elle sert
#     à vérifier que TOUS les côtés donnent le MÊME nombre ;
#   - des répétitions chronométrées qui font TOURNER le côté qui passe en
#     premier ;
#   - la médiane, « fiable », et qui a été « le plus rapide » (et combien
#     de fois plus) ;
#   - l'arrêt des profondeurs plus grandes pour un côté dès qu'il manque
#     de temps ;
#   - la réutilisation des acteurs de départ du dernier CSV de la même base
#     (--new-starts pour les choisir à nouveau).
#
# Comment il est censé être lancé — normalement via research.sh, qui
# vérifie les connexions, demande quelle base utiliser, puis lance ce
# script :
#     ./research.sh --database gharchive-2026-10-08-9-24h
# ou seul, via run.sh (qui charge .venv et les mots de passe) :
#     ./run.sh scripts/measure.py --database gharchive-2026-10-08-9-24h
########################################################################

"""Measure the traversal in PostgreSQL and Neo4j, and write the results to ONE CSV file.

Every measurement (every analysis) writes its own file,
results/<database>_<date>_<time>.csv. One line of it = one question answered
by both databases: "from this starting actor, at this depth, in this volume of
data, how many actors are reached?". First the test, then PostgreSQL's figures
and Neo4j's figures side by side, with the same columns. Every column is
explained in the README ("What is measured, and why").

For the database given, it:

    1. chooses the 20 starting actors (choose_starts.py), or reuses the ones
       in the latest CSV of that database, so a repeated measurement
       starts from the same actors;
    2. for every actor and every depth from 1 to --max-depth:
       a. runs the traversal once on each side ("first run": it includes
          preparing the query) and checks that ALL sides give the same count;
       b. runs it --repeats more times, changing which side goes first each
          time, recording the time and the CPU used by each database server;
       c. runs it once more with EXPLAIN (ANALYZE, BUFFERS) / PROFILE, for the
          data read and the memory used inside each database;
    3. writes one line per actor, depth and Cypher version, and prints a summary.

If a side runs out of time at some depth, the deeper depths are skipped for that
side and actor (they can only be slower); their lines say so.

Usage:
    ./run.sh scripts/measure.py --database gharchive-2026-10-08-9-24h
    ./run.sh scripts/measure.py --database ... --max-depth 4 --repeats 5 --timeout 60 --cypher both
"""

# ---------------------------------------------------------------------
# Imports de la bibliothèque standard. Déjà vus : argparse, csv,
# statistics, sys, datetime, timedelta, Path.
# Un nouveau :
#   re  — les EXPRESSIONS RÉGULIÈRES : des motifs qui décrivent la forme
#         d'un texte (voir NAME et data_window() plus bas).
# ---------------------------------------------------------------------
import argparse
import csv
import re
import statistics
import sys
from datetime import datetime, timedelta
from pathlib import Path

# ---------------------------------------------------------------------
# import psutil
#
# Un paquet EXTERNE (installé depuis requirements.txt, comme psycopg et
# neo4j) : « process and system utilities » (outils pour les processus et
# le système). Il sait lister les programmes (PROCESSUS) qui tournent sur
# l'ordinateur, dire combien de temps de processeur chacun a utilisé, et
# à quel point l'ordinateur entier est occupé.
#
# Pourquoi un banc d'essai a-t-il besoin de cela ? Deux raisons :
#   - la PUISSANCE DE CALCUL : combien de CPU chaque SERVEUR de base de
#     données a dépensé pour une requête (voir server_processes() et
#     cpu_seconds() plus bas) ;
#   - l'ÉQUITÉ : l'ordinateur portable sert aussi à d'autres choses
#     pendant la mesure (un navigateur, un antivirus, les mises à jour de
#     Windows...). Si une exécution a été lente parce que l'ordinateur
#     était occupé, on veut le VOIR, au lieu d'en accuser la base.
# ---------------------------------------------------------------------
import psutil

# ---------------------------------------------------------------------
# import choose_starts / import traversal
#
# Les PROPRES scripts du projet, importés comme des paquets (cela
# fonctionne parce qu'ils sont tous dans le même dossier scripts/). Ce
# script réutilise :
#   choose_starts.choose_in_both                       les acteurs de départ
#   traversal.connect_postgres / connect_neo4j
#   traversal.run_postgres_reach / run_neo4j_reach     un parcours chronométré
#   traversal.postgres_work / neo4j_work               les chiffres de travail
#   traversal.sql_joins / cypher_hops / CYPHER_VERSIONS
# Tous sont expliqués dans docs_french/traversal.py et
# docs_french/choose_starts.py.
# ---------------------------------------------------------------------
import choose_starts
import traversal

# ---------------------------------------------------------------------
# RESULTS_DIR — le dossier des fichiers de résultats : <projet>/results
#
# (Même recette avec Path que PROJECT_DIR dans load_postgres.py.) Chaque
# mesure y écrit UN fichier CSV, nommé d'après la base et le moment où la
# mesure a commencé (voir results_file()), par exemple
#     results/gharchive-2026-10-08-9-24h_2026-11-19_14-05-31.csv
# Un seul fichier contient tout ce qui concerne une mesure, et une
# nouvelle mesure ne touche jamais une mesure précédente. (Les versions
# précédentes écrivaient plusieurs fichiers par mesure — exécutions,
# travail, par acteur, résumé — ce qui s'est révélé trop difficile à
# lire.)
# ---------------------------------------------------------------------
RESULTS_DIR = Path(__file__).resolve().parent.parent / "results"

# ---------------------------------------------------------------------
# LES COLONNES D'UN CSV DE RÉSULTATS — TROIS PARTIES
#
# L'utilisateur a demandé cette disposition : d'abord les informations du
# TEST, puis un tableau PostgreSQL et un tableau Neo4j côte à côte, avec
# les MÊMES colonnes, pour qu'on puisse lire chaque base seule ET les
# comparer colonne par colonne (pg_time_s à côté de... la même place dans
# le bloc Neo4j : neo4j_time_s).
#
# 1. TEST_COLUMNS — quelles données, quand, et quelle question :
#   measured_at          le moment où la mesure a commencé (le même pour
#                        toutes ses lignes, pour pouvoir combiner des
#                        fichiers plus tard)
#   database             la base mesurée
#   data_from_utc, data_to_utc, volume_hours
#                        la fenêtre de temps des données, lue dans le nom
#                        de la base (voir data_window())
#   graph_actors, graph_repos, graph_connections
#                        la taille du graphe (identique des deux côtés :
#                        vérifié dans graph_facts())
#   start_group, start_rank, start_actor_id, start_login, start_reach_1_hop
#                        l'acteur de départ (venant de choose_starts.py)
#   depth                le nombre de sauts
#   cypher_version       la version Cypher que cette ligne compare au SQL :
#                        « paths » ou « levels » (docs_french/traversal.py)
#   actors_reached       la réponse, si tous les côtés sont d'accord
#   answers_match        yes / no / unknown (personne n'a terminé)
#   runs, timeout_s      le nombre d'exécutions chronométrées, et le délai
#                        maximum
#
# 2. SIDE_COLUMNS — la même liste, utilisée DEUX FOIS : une fois avec le
#    préfixe « pg_ », une fois avec « neo4j_ ». Les quatre choses
#    comparées sont ici :
#   joins_or_hops        la quantité de chemin parcouru pour une
#                        profondeur : des JOIN en SQL, des relations
#                        suivies en Cypher (2 par profondeur, voir
#                        traversal.sql_joins / cypher_hops)
#   status               finished / timeout / error / skipped (...)
#   time_s               le TEMPS : la MÉDIANE des exécutions
#                        chronométrées, en secondes
#   first_run_s          la première exécution (pendant laquelle la
#                        requête est préparée)
#   data_processed_mb    les DONNÉES TRAITÉES : les Mo de pages de 8 Ko
#                        touchées (une page utilisée deux fois compte deux
#                        fois)
#   data_from_disk_mb    la partie lue sur le disque
#   memory_mb            l'ESPACE : la mémoire utilisée par la requête
#   temp_disk_mb         l'ESPACE : les fichiers temporaires sur disque
#                        (PostgreSQL seulement ; la colonne reste VIDE pour
#                        Neo4j, qui n'a pas d'équivalent)
#   database_mb          l'ESPACE : la taille de toute la base sur le disque
#   cpu_s                la PUISSANCE DE CALCUL : les secondes de CPU
#                        utilisées par le serveur de la base (médiane des
#                        exécutions chronométrées)
#   cores_used           cpu_s / time_s : combien de cœurs du processeur
#                        ont été occupés en moyenne (2.0 = deux cœurs
#                        pendant tout le temps)
#   reliable             yes / no, pour CE côté (voir side_summary())
#
# 3. COMPARISON_COLUMNS — à la fin :
#   faster, times_faster qui a été le plus rapide, et combien de fois plus
#                        (compare())
#
# COLUMNS — la liste complète, dans l'ordre, collée avec `+` (liste +
# liste = une liste plus longue). [f"pg_{c}" for c in SIDE_COLUMNS] est
# une compréhension de liste qui met le préfixe devant chaque nom :
# "pg_status", "pg_time_s"... Les parenthèses ( ... ) autour de
# l'expression lui permettent de continuer sur la ligne suivante.
#
# Garder les colonnes dans des constantes garantit que l'en-tête et les
# lignes ne peuvent jamais être en désaccord (voir csv.DictWriter dans
# main()) et que chaque fichier a les mêmes colonnes ; de plus,
# tests/test_research.py vérifie la forme en trois parties.
# ---------------------------------------------------------------------
# The columns of every results CSV, in order: first the test (which data, when, which question),
# then two blocks with THE SAME columns, one for PostgreSQL ("pg_...") and one for Neo4j
# ("neo4j_..."), and at the end the comparison. Their meaning is explained in the README.
TEST_COLUMNS = [
    "measured_at", "database", "data_from_utc", "data_to_utc", "volume_hours",
    "graph_actors", "graph_repos", "graph_connections",
    "start_group", "start_rank", "start_actor_id", "start_login", "start_reach_1_hop",
    "depth", "cypher_version", "actors_reached", "answers_match", "runs", "timeout_s",
]
SIDE_COLUMNS = [
    "joins_or_hops", "status", "time_s", "first_run_s", "data_processed_mb", "data_from_disk_mb",
    "memory_mb", "temp_disk_mb", "database_mb", "cpu_s", "cores_used", "reliable",
]
COMPARISON_COLUMNS = ["faster", "times_faster"]
COLUMNS = (TEST_COLUMNS + [f"pg_{c}" for c in SIDE_COLUMNS] + [f"neo4j_{c}" for c in SIDE_COLUMNS]
           + COMPARISON_COLUMNS)

# ---------------------------------------------------------------------
# Les deux seuils « pas fiable » (utilisés dans side_summary()) :
#   BUSY_CPU      l'ordinateur entier au-dessus de 80 % de CPU pendant une
#                 exécution : la base a dû partager le processeur.
#   NOISY_SPREAD  l'exécution chronométrée la plus lente a duré plus de 3
#                 fois plus longtemps que la plus rapide : quelque chose a
#                 perturbé les exécutions.
#
# NAME — une EXPRESSION RÉGULIÈRE (le module `re`)
#
# Une expression régulière est un petit langage de motifs qui décrit la
# FORME d'un texte. re.compile(...) prépare le motif une seule fois, pour
# pouvoir l'utiliser de nombreuses fois. r"..." est une chaîne BRUTE
# (« raw ») : les barres obliques inverses restent telles qu'on les a
# tapées (sinon Python essaierait d'interpréter \d lui-même).
#
#   ^ ... $                 le début et la fin du texte : le nom ENTIER
#                           doit correspondre, pas seulement un morceau
#   gharchive-              exactement ces caractères
#   (\d{4}-\d{2}-\d{2})     \d = un chiffre ; {4} = exactement 4 chiffres.
#                           Donc « 2026-10-08 ». Les parenthèses forment un
#                           GROUPE : la partie trouvée est conservée, comme
#                           groupe 1.
#   -(\d{1,2})              un tiret, puis 1 ou 2 chiffres : l'heure
#                           (groupe 2)
#   (?:-(\d+)h)?            (?: ... ) est un groupe qui n'est PAS conservé,
#                           il sert seulement à regrouper « -<n>h » ; le ?
#                           qui suit rend tout ce groupe FACULTATIF. À
#                           l'intérieur, \d+ = un chiffre ou plus, conservé
#                           comme groupe 3.
# Donc « gharchive-2026-10-08-9-24h » et « gharchive-2026-10-08-23 »
# correspondent tous les deux (le second sans groupe 3). Les noms sont
# ceux que fabrique build_hours.py (database_name(), voir
# docs_french/build_hours.py).
# (C'est la même idée que [[ =~ ]] en bash, dans docs_french/research.sh.)
# ---------------------------------------------------------------------
BUSY_CPU = 80.0       # computer CPU above this (percent) during a run: not reliable
NOISY_SPREAD = 3.0    # slowest run more than 3 times the fastest: not reliable
NAME = re.compile(r"^gharchive-(\d{4}-\d{2}-\d{2})-(\d{1,2})(?:-(\d+)h)?$")


# ---------- which data ----------

# ---------------------------------------------------------------------
# def data_window(database) -> tuple[str, str, int | None]:
#
# Transforme le nom d'une base en la fenêtre de temps de ses données, par
# exemple
#   "gharchive-2026-10-08-9-24h" -> ("2026-10-08 09:00", "2026-10-09 09:00", 24)
#
# NAME.match(database) essaie le motif sur le texte : il donne un objet
# MATCH (correspondance) si le texte a cette forme, ou None sinon. Un nom
# qui ne correspond pas (créé à la main, par exemple) n'est pas une
# erreur : les trois colonnes restent vides ("", "", None).
#
# match.group(1), (2), (3) — le texte trouvé par chaque groupe conservé.
# Un groupe FACULTATIF qui n'a rien trouvé donne None, donc
#   int(match.group(3) or 1)    pas de partie « -<n>h » -> 1 heure.
# Les valeurs sont du TEXTE : int(...) les transforme en nombres.
#
# datetime.strptime(date, "%Y-%m-%d") lit la date (build_hours.py), à
# minuit ; + timedelta(hours=hour) l'avance jusqu'à l'heure de début ;
# ajouter encore `hours` heures donne la fin. strftime("%Y-%m-%d %H:%M")
# les réécrit sous forme de texte. Les heures de GH Archive sont en UTC,
# d'où les noms de colonnes en _utc.
# ---------------------------------------------------------------------
def data_window(database: str) -> tuple[str, str, int | None]:
    # build_hours.py names each database after its data: gharchive-<date>-<hour>[-<n>h].
    match = NAME.match(database)
    if not match:
        return "", "", None
    date, hour, hours = match.group(1), int(match.group(2)), int(match.group(3) or 1)
    begin = datetime.strptime(date, "%Y-%m-%d") + timedelta(hours=hour)
    end = begin + timedelta(hours=hours)
    return begin.strftime("%Y-%m-%d %H:%M"), end.strftime("%Y-%m-%d %H:%M"), hours


# ---------------------------------------------------------------------
# def folder_size_mb(path) -> float | None:  — la taille d'un dossier sur le disque
#
#   path.is_dir()          ce dossier existe-t-il ? Sinon : None (inconnu).
#   path.rglob("*")        tous les fichiers et dossiers qu'il CONTIENT, à
#                          n'importe quelle profondeur (le « r » veut dire
#                          récursif).
#   f.is_file()            garder les fichiers (les dossiers n'ont pas de
#                          taille propre).
#   f.stat().st_size       la taille d'un fichier, en octets.
#   sum(...) / 1024 ** 2   le tout additionné, en Mo.
# Utilisé pour la taille de la base Neo4j (graph_facts()).
# ---------------------------------------------------------------------
def folder_size_mb(path: Path) -> float | None:
    if not path.is_dir():
        return None
    return sum(f.stat().st_size for f in path.rglob("*") if f.is_file()) / 1024 ** 2


# ---------------------------------------------------------------------
# def graph_facts(conn, driver, database) -> dict:  — LES DONNÉES, ET UNE VÉRIFICATION
#
# Rassemble les chiffres qui sont les mêmes pour toutes les lignes de
# cette mesure : la taille du graphe, et celle de chaque base sur le
# disque.
#
# count = lambda q: ... — une fonction d'une seule ligne (lambda :
# test_build_hours.py) qui exécute un comptage Cypher et renvoie le
# nombre (records[0][0] : la première colonne de la première ligne).
#
# Du côté PostgreSQL : les trois tables sont comptées, et
# pg_database_size(current_database()) — la taille en octets de toute la
# base sur le disque (tables ET index), / 1024 ** 2 -> Mo.
#
# LES MÊMES DONNÉES DES DEUX CÔTÉS : les comptages Neo4j (acteurs, dépôts,
# connexions) sont mis dans un tuple et comparés à ceux de PostgreSQL.
# S'ils diffèrent, les deux bases ne contiennent pas le même graphe, et
# comparer leur vitesse n'aurait aucun sens : on lève RuntimeError, qui
# est attrapée tout en bas du fichier (rien n'est mesuré).
#
# LA TAILLE DE NEO4J SUR LE DISQUE : Neo4j n'a pas de pg_database_size.
# Ses bases sont des dossiers sous le répertoire de données du serveur,
# donc le script demande au serveur où il se trouve (SHOW SETTINGS ...
# 'server.directories.data', dans la base spéciale « system ») et mesure
# le dossier <data>/databases/<database> avec folder_size_mb(). `if
# records else None` : si le paramètre ne peut pas être lu, la taille
# reste inconnue. (Cela fonctionne parce que Neo4j Desktop tourne sur le
# même ordinateur.)
#
# Les clés "pg_database_mb" et "neo4j_database_mb" sont exactement les
# noms des colonnes des deux blocs, donc elles vont directement dans
# chaque ligne.
# ---------------------------------------------------------------------
def graph_facts(conn, driver, database: str) -> dict:
    count = lambda q: driver.execute_query(q, database_=database).records[0][0]
    facts = {
        "graph_actors": conn.execute("SELECT count(*) FROM actor").fetchone()[0],
        "graph_repos": conn.execute("SELECT count(*) FROM repo").fetchone()[0],
        "graph_connections": conn.execute("SELECT count(*) FROM actor_repo").fetchone()[0],
        "pg_database_mb": conn.execute("SELECT pg_database_size(current_database())").fetchone()[0] / 1024 ** 2,
    }
    neo4j = (count("MATCH (a:Actor) RETURN count(a)"), count("MATCH (r:Repo) RETURN count(r)"),
             count("MATCH ()-[c:INTERACTED_WITH]->() RETURN count(c)"))
    if neo4j != (facts["graph_actors"], facts["graph_repos"], facts["graph_connections"]):
        raise RuntimeError(f"The two databases don't hold the same data: PostgreSQL "
                           f"{facts['graph_actors']}/{facts['graph_repos']}/{facts['graph_connections']}, "
                           f"Neo4j {neo4j[0]}/{neo4j[1]}/{neo4j[2]} (actors/repos/connections)")
    # Neo4j's size on disk: the database's folder under the server's data directory.
    records = driver.execute_query("SHOW SETTINGS YIELD name, value WHERE name = 'server.directories.data' "
                                   "RETURN value", database_="system").records
    facts["neo4j_database_mb"] = folder_size_mb(Path(records[0]["value"]) / "databases" / database) if records else None
    return facts


# ---------- the CPU used by each database server ----------

# ---------------------------------------------------------------------
# def server_processes(system) -> list[psutil.Process]:  — TROUVER LES SERVEURS
#
# La PUISSANCE DE CALCUL est mesurée sur le SERVEUR de la base, pas sur
# Python : les serveurs sont des programmes séparés (des PROCESSUS) qui
# tournent sur le même ordinateur.
#   PostgreSQL   tourne sous forme de PLUSIEURS processus appelés postgres
#                (un principal, un par connexion, et des processus
#                auxiliaires). Tous comptent.
#   Neo4j        tourne sous forme d'UN seul programme Java (java.exe).
#                Mais d'autres programmes Java peuvent aussi tourner, donc
#                le processus n'est gardé que si sa LIGNE DE COMMANDE (le
#                programme et ses arguments, process.cmdline()) mentionne
#                neo4j.
#
# psutil.process_iter(["name"]) parcourt tous les processus de
# l'ordinateur, avec leur nom déjà lu (process.info["name"]).
# `(... or "").lower()` : un nom absent devient "", et lower() fait que la
# comparaison ignore les majuscules. name.startswith("postgres") vaut True
# pour « postgres » comme pour « postgres.exe ».
#
# try / except (psutil.Error, OSError): pass — certains processus
# appartiennent à Windows ou à un autre utilisateur, et les interroger
# est REFUSÉ ; d'autres se terminent pendant qu'on les examine. Ceux-là
# sont simplement ignorés (`pass` = ne rien faire). Un tuple de classes
# d'erreur attrape n'importe laquelle d'entre elles.
# ---------------------------------------------------------------------
def server_processes(system: str) -> list[psutil.Process]:
    # PostgreSQL runs as several postgres processes; Neo4j as one Java process.
    found = []
    for process in psutil.process_iter(["name"]):
        name = (process.info["name"] or "").lower()
        try:
            if system == "postgresql" and name.startswith("postgres"):
                found.append(process)
            elif system == "neo4j" and name.startswith("java") and "neo4j" in " ".join(process.cmdline()).lower():
                found.append(process)
        except (psutil.Error, OSError):
            pass
    return found


# ---------------------------------------------------------------------
# def cpu_seconds(processes) -> dict[int, float]:
#
# Pour chaque processus, le temps de CPU qu'il a utilisé DEPUIS SON
# DÉMARRAGE :
#   cpu.user     les secondes que le processeur a passées à exécuter son
#                propre code
#   cpu.system   les secondes passées par Windows à travailler pour lui
#                (lire des fichiers...)
# La somme est rangée sous l'identifiant du processus (pid : « process
# id », un numéro qui identifie un programme en cours d'exécution).
#
# Une seule lecture ne veut rien dire en soi ; timed_run() la fait AVANT
# et APRÈS une requête, et la différence est ce que la requête a coûté.
# Un processus qui s'est terminé (ou qui refuse) est ignoré.
# ---------------------------------------------------------------------
def cpu_seconds(processes: list[psutil.Process]) -> dict[int, float]:
    times = {}
    for process in processes:
        try:
            cpu = process.cpu_times()
            times[process.pid] = cpu.user + cpu.system
        except (psutil.Error, OSError):
            pass
    return times


# ---------- running ----------

# ---------------------------------------------------------------------
# def sides(cypher) -> list[str]:  — CE QUI EST MESURÉ
#
# Un « côté » est une façon de répondre à la question :
#   "postgresql"     le SQL
#   "neo4j-paths"    Cypher, version « paths »
#   "neo4j-levels"   Cypher, version « levels »
# --cypher both donne les trois ; --cypher levels donne PostgreSQL et
# seulement cette version. (cypher,) est un tuple d'un seul élément (c'est
# la virgule qui en fait un tuple), donc les deux branches donnent quelque
# chose sur quoi boucler.
# ---------------------------------------------------------------------
def sides(cypher: str) -> list[str]:
    # The "sides" measured: PostgreSQL and one or two Cypher versions.
    versions = traversal.CYPHER_VERSIONS if cypher == "both" else (cypher,)
    return ["postgresql"] + [f"neo4j-{v}" for v in versions]


# ---------------------------------------------------------------------
# def run_order(all_sides, repeat) -> list[str]:  — QUEL CÔTÉ PASSE EN PREMIER
#
# Pourquoi changer l'ordre ? Tout ce qui change pendant la mesure touche
# celui qui s'exécute à ce moment-là : vous ouvrez un onglet du
# navigateur, l'antivirus se réveille, l'ordinateur portable chauffe et
# ralentit, Windows écrit sur le disque... Si PostgreSQL passait
# TOUJOURS en premier, chacune de ces perturbations tomberait sur le même
# côté, à la même position. Faire tourner l'ordre les répartit pour
# qu'elles touchent tous les côtés de la même façon, et aucun n'obtient
# d'avantage systématique (par exemple, « celui qui passe en deuxième
# trouve toujours les données déjà dans la mémoire du système
# d'exploitation »).
#
# LA ROTATION, avec trois côtés [A, B, C] :
#   repeat 1 -> shift 0 -> [A, B, C]
#   repeat 2 -> shift 1 -> [B, C, A]
#   repeat 3 -> shift 2 -> [C, A, B]
#   repeat 4 -> shift 0 -> [A, B, C] de nouveau
# `%` est le RESTE d'une division : (repeat - 1) % 3 donne 0, 1, 2, 0...
# all_sides[shift:] + all_sides[:shift] — deux TRANCHES (slices) collées :
# de la position `shift` jusqu'à la fin, puis le début jusqu'à `shift`.
# tests/test_research.py vérifie cette fonction (docs_french/test_research.py).
# ---------------------------------------------------------------------
def run_order(all_sides: list[str], repeat: int) -> list[str]:
    # Repetition 1 starts with the first side, repetition 2 with the second, and so on, so
    # anything else happening on the computer affects every side alike.
    shift = (repeat - 1) % len(all_sides)
    return all_sides[shift:] + all_sides[:shift]


# ---------------------------------------------------------------------
# def run_once(side, ...) — un parcours sur UN seul côté
#
# Un petit aiguillage pour que le reste du code puisse simplement dire
# « exécute-le sur ce côté » sans se soucier de quel côté il s'agit. Les
# deux fonctions renvoient un Outcome (status, seconds, count, error) :
# voir docs_french/traversal.py.
#
# side.split("-", 1)[1] — découpe le texte au PREMIER « - » seulement (le
# 1), et prend le deuxième morceau : "neo4j-levels" -> ["neo4j", "levels"]
# -> "levels", la version Cypher.
# ---------------------------------------------------------------------
def run_once(side: str, conn, driver, database: str, start: int, depth: int, timeout: int):
    if side == "postgresql":
        return traversal.run_postgres_reach(conn, start, depth, timeout)
    return traversal.run_neo4j_reach(driver, database, start, depth, timeout, side.split("-", 1)[1])


# ---------------------------------------------------------------------
# def timed_run(...) -> dict:  — UNE EXÉCUTION CHRONOMÉTRÉE, AVEC SON CPU
#
# 1. psutil.cpu_percent(interval=0.2) — observe le processeur pendant
#    0,2 s et renvoie la part utilisée, en pourcentage, en comptant TOUS
#    les programmes. Mesuré juste AVANT l'exécution (impossible pendant :
#    la fonction attend ses 0,2 s avant de répondre). Cela indique à quel
#    point l'ordinateur était occupé.
#
# 2. procs = les processus serveurs de ce côté ("neo4j-paths" et
#    "neo4j-levels" utilisent tous les deux le serveur Neo4j).
#    `A if condition else B` : un if/else sur une seule ligne qui donne
#    une valeur.
#
# 3. Secondes de CPU AVANT, l'exécution, secondes de CPU APRÈS. Le temps
#    de l'exécution elle-même est mesuré dans run_once() (l'Outcome), donc
#    les lectures du CPU ne s'y ajoutent pas.
#
# 4. used = le CPU que le serveur a dépensé pour cette exécution : pour
#    chaque processus, après moins avant, le tout additionné. `if pid in
#    before` : un processus apparu entre-temps n'a pas de « avant » et est
#    laissé de côté. `if procs else None` : si aucun processus serveur n'a
#    été trouvé, le CPU est INCONNU (None — pas 0, qui serait une vraie
#    valeur, et fausse).
#
# Remarque : cela compte TOUT ce que le serveur a fait pendant
# l'exécution, donc la recherche suppose que rien d'autre n'utilise les
# bases à ce moment-là.
# ---------------------------------------------------------------------
def timed_run(side, processes, conn, driver, database, start, depth, timeout) -> dict:
    machine_cpu = psutil.cpu_percent(interval=0.2)
    procs = processes["postgresql" if side == "postgresql" else "neo4j"]
    before = cpu_seconds(procs)
    outcome = run_once(side, conn, driver, database, start, depth, timeout)
    after = cpu_seconds(procs)
    used = sum(after[pid] - before[pid] for pid in after if pid in before) if procs else None
    return {"outcome": outcome, "cpu_s": used, "machine_cpu": machine_cpu}


# ---------------------------------------------------------------------
# def work_figures(...) -> dict:  — LES CHIFFRES DE TRAVAIL D'UN CÔTÉ
#
# Une exécution supplémentaire, où l'on demande cette fois à la base de
# rapporter ce qu'elle a fait : EXPLAIN (ANALYZE, BUFFERS) dans
# PostgreSQL, PROFILE dans Neo4j (expliqués dans
# docs_french/traversal.py). Elle renvoie un dictionnaire comme
#   {"data_processed_mb": ..., "data_from_disk_mb": ..., "memory_mb": ...}
# (plus "temp_disk_mb" pour PostgreSQL). Elle est séparée des exécutions
# chronométrées parce que recueillir ces chiffres coûte lui-même du temps.
#
# try / except : si le recueil des chiffres échoue, cela ne vaut pas la
# peine de perdre toute la mesure : un dictionnaire vide laisse ces
# colonnes vides, et une courte note est affichée. str(error)[:80] — les
# 80 premiers caractères du message (une TRANCHE du texte). end=" " fait
# continuer la ligne à l'écran.
# ---------------------------------------------------------------------
def work_figures(side, conn, driver, database, start, depth, timeout) -> dict:
    try:
        if side == "postgresql":
            return traversal.postgres_work(conn, start, depth, timeout)
        return traversal.neo4j_work(driver, database, start, depth, timeout, side.split("-", 1)[1])
    except Exception as error:
        print(f"(no work figures for {side}: {str(error)[:80]})", end=" ")
        return {}


# ---------------------------------------------------------------------
# def side_summary(first, runs, work, status) -> dict:  — LES CHIFFRES D'UN CÔTÉ
#
# Transforme les exécutions d'un côté, pour un acteur et une profondeur,
# en valeurs de son bloc de colonnes (time_s, cpu_s, ...).
#
# Un côté qui n'a PAS terminé (timeout, error ou skipped) n'a pas de
# temps : seulement son statut, et le temps de la première exécution s'il
# y en a eu une (`if first else None` : un côté ignoré ne s'est jamais
# exécuté).
#
# Un côté qui a terminé :
#   time_s       statistics.median des exécutions chronométrées. Pourquoi
#                la MÉDIANE et pas la moyenne ? Une seule exécution
#                perturbée (l'antivirus...) peut être 10 fois plus lente ;
#                elle tirerait la moyenne vers le haut, mais ne bouge
#                presque pas la médiane (la valeur du milieu).
#   first_run_s  la première exécution, mise à part : elle comprend la
#                préparation du plan de la requête, donc elle ne fait PAS
#                partie de time_s.
#   cpu_s        la médiane des secondes de CPU (sur les exécutions où on
#                la connaît).
#   cores_used   cpu_s / time_s. Exemple : 0,6 seconde de CPU dans une
#                exécution de 0,3 seconde = 2.0 — en moyenne, deux cœurs
#                du processeur étaient occupés (une base peut travailler
#                sur plusieurs cœurs à la fois). Pas calculé si le CPU est
#                inconnu ou si le temps vaut 0 (une division par zéro
#                ferait planter le programme).
#   **{k: round(v, 3) for k, v in work.items() if v is not None}
#                les chiffres de travail, arrondis à 3 décimales ; `**`
#                les copie dans ce dictionnaire (le même `**` que dans
#                choose_starts.py). Un None (par exemple, Neo4j n'a pas
#                rapporté sa mémoire) est laissé de côté, donc sa colonne
#                reste vide.
#   noisy        l'exécution la plus lente plus de NOISY_SPREAD (3) fois
#                plus longue que la plus rapide. (`if min(times) > 0` :
#                évite de diviser par 0.)
#   busy         any(...) vaut True si au moins UNE exécution a eu
#                l'ordinateur au-dessus de BUSY_CPU (80 %).
#   reliable     "no" si noisy ou busy, sinon "yes" — la colonne du bloc
#                de CE côté. Un « no » ne veut pas dire que le chiffre est
#                faux ; il veut dire : attention, mesurez à nouveau si
#                c'est important.
# round(..., 4) : 4 décimales d'une seconde = un dixième de milliseconde.
# tests/test_research.py vérifie cette fonction.
# ---------------------------------------------------------------------
def side_summary(first, runs: list[dict], work: dict, status: str) -> dict:
    # The figures of one side, for one actor and depth.
    if status != "finished":
        return {"status": status, "first_run_s": round(first.seconds, 4) if first else None}
    times = [r["outcome"].seconds for r in runs]
    cpus = [r["cpu_s"] for r in runs if r["cpu_s"] is not None]
    time_s = statistics.median(times)
    cpu_s = statistics.median(cpus) if cpus else None
    noisy = max(times) / min(times) > NOISY_SPREAD if min(times) > 0 else False
    busy = any(r["machine_cpu"] > BUSY_CPU for r in runs)
    return {
        "status": "finished",
        "time_s": round(time_s, 4),
        "first_run_s": round(first.seconds, 4),
        "cpu_s": round(cpu_s, 4) if cpu_s is not None else None,
        "cores_used": round(cpu_s / time_s, 2) if cpu_s is not None and time_s > 0 else None,
        **{k: round(v, 3) for k, v in work.items() if v is not None},
        "noisy": noisy,
        "busy": busy,
        "reliable": "no" if noisy or busy else "yes",
    }


# ---------------------------------------------------------------------
# def compare(pg, neo, timeout) -> tuple[str, float | None]:  — QUI A ÉTÉ LE PLUS RAPIDE
#
# Donne les deux colonnes de comparaison, faster et times_faster :
#   les deux ont terminé     le plus petit temps gagne ; times_faster = le
#                            temps le plus lent / le plus rapide (0,4 s
#                            contre 0,1 s -> 4.0). En cas d'égalité,
#                            PostgreSQL l'emporte (<=).
#   un seul a terminé        l'autre a pris AU MOINS le délai maximum (il
#                            a été arrêté), donc délai / temps du gagnant
#                            est un MINIMUM : « au moins 30 fois plus
#                            rapide ».
#   aucun n'a terminé        "neither", et pas de nombre.
# Chaque `... if pg["time_s"] else None` évite de diviser par un temps
# de 0.
# ---------------------------------------------------------------------
def compare(pg: dict, neo: dict, timeout: int) -> tuple[str, float | None]:
    # Who was faster, and how many times. If only one side finished, the other took at
    # least the time limit, so "times_faster" is a minimum.
    if pg["status"] == "finished" and neo["status"] == "finished":
        if pg["time_s"] <= neo["time_s"]:
            return "postgresql", round(neo["time_s"] / pg["time_s"], 2) if pg["time_s"] else None
        return "neo4j", round(pg["time_s"] / neo["time_s"], 2) if neo["time_s"] else None
    if pg["status"] == "finished":
        return "postgresql", round(timeout / pg["time_s"], 2) if pg["time_s"] else None
    if neo["status"] == "finished":
        return "neo4j", round(timeout / neo["time_s"], 2) if neo["time_s"] else None
    return "neither", None


# ---------------------------------------------------------------------
# def measure_actor(actor, context, args, writer) — TOUT POUR UN ACTEUR DE DÉPART
#
# Pour la profondeur 1, 2, 3 ... jusqu'à --max-depth : les étapes a, b, c
# (les mêmes que dans la docstring en haut du fichier), puis d, qui écrit
# les lignes. `context` est un dictionnaire construit dans main() (les
# connexions, les processus serveurs, les faits), pour que la fonction
# n'ait pas besoin d'une longue liste d'arguments. `writer` est le
# csv.DictWriter du fichier CSV de cette mesure.
#
# stopped — IGNORER LES PROFONDEURS PLUS GRANDES
#   Un dictionnaire {côté : le statut qu'il reçoit aux profondeurs plus
#   grandes}. Aller un saut plus loin ne peut atteindre que PLUS
#   d'acteurs, donc cela ne peut que prendre plus de temps : si la
#   profondeur 4 n'a pas terminé en 60 s, la profondeur 5 ne terminera pas
#   non plus. L'ignorer épargne 60 s x (1 + repeats) d'attente inutile par
#   profondeur. Les AUTRES côtés continuent, tant qu'ils terminent ; les
#   lignes du côté ignoré sont quand même écrites, avec le statut
#   « skipped (...) ».
# ---------------------------------------------------------------------
def measure_actor(actor: dict, context: dict, args, writer: csv.DictWriter) -> None:
    conn, driver, database = context["conn"], context["driver"], args.database
    all_sides = sides(args.cypher)
    stopped = {}   # side -> the status it gets at deeper depths
    # range(1, args.max_depth + 1) : 1, 2, ..., max_depth (la fin d'un
    # range n'est PAS incluse, d'où le + 1).
    for depth in range(1, args.max_depth + 1):
        # Les côtés encore mesurés à cette profondeur.
        active = [s for s in all_sides if s not in stopped]
        # end=" " — afficher sans passer à la ligne, pour que la suite du
        # compte rendu de cette profondeur apparaisse plus tard sur la même
        # ligne.
        # flush=True — l'afficher TOUT DE SUITE. Normalement, Python garde
        # le texte affiché un moment dans une mémoire tampon ; sans flush,
        # on fixerait une ligne vide pendant une longue exécution sans
        # savoir quelle profondeur est en cours de mesure.
        print(f"  depth {depth}:", end=" ", flush=True)

        # -------------------------------------------------------------
        # ÉTAPE a — LA « PREMIÈRE EXÉCUTION » : CE N'EST PAS UN RÉSULTAT
        #
        # La toute première fois qu'une base voit une requête d'une forme
        # nouvelle, elle fait un travail supplémentaire, une seule fois,
        # avant de l'exécuter : elle analyse le texte et prépare (compile)
        # un PLAN de requête. Neo4j en particulier peut mettre quelques
        # secondes à planifier une nouvelle requête ; ensuite, le plan est
        # gardé dans son cache et réutilisé. La première exécution amène
        # aussi les données en mémoire. Compter ce temps-là mesurerait « la
        # première fois » plutôt que le parcours lui-même, donc il est
        # rapporté à part (first_run_s).
        #
        # Elle SERT pourtant à quelque chose d'important : la VÉRIFICATION
        # DU NOMBRE. Chaque côté répond à « combien d'acteurs sont
        # atteignables » ; si les nombres diffèrent, l'une des requêtes (ou
        # les données chargées) est fausse, et comparer leur vitesse
        # n'aurait aucun sens.
        #
        # first = {s: run_once(...) for s in active} — une compréhension
        # de dictionnaire : {"postgresql": Outcome, "neo4j-paths":
        # Outcome...}.
        # counts = {o.count for ...} — un ENSEMBLE (set) des réponses des
        # côtés qui ont terminé : un ensemble garde chaque valeur une seule
        # fois, donc si tous sont d'accord il contient UN seul nombre ;
        # deux nombres ou plus = ils ne sont pas d'accord.
        #
        # Un côté dont la première exécution n'a pas terminé va dans
        # `stopped`, avec le statut que recevront ses profondeurs PLUS
        # GRANDES. (Le `\` en fin de ligne fait continuer l'instruction sur
        # la ligne suivante.)
        # -------------------------------------------------------------
        # a. First run (not a result) and the count check.
        first = {s: run_once(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in active}
        counts = {o.count for o in first.values() if o.status == "ok"}
        for side, outcome in first.items():
            if outcome.status != "ok":
                stopped[side] = "skipped (timed out at a smaller depth)" if outcome.status == "timeout" \
                    else "skipped (failed at a smaller depth)"
        finished = [s for s in active if s not in stopped]

        # -------------------------------------------------------------
        # ÉTAPE b — LES RÉPÉTITIONS CHRONOMÉTRÉES
        #
        # Pourquoi répéter ? Un seul temps n'est pas fiable : la même
        # requête peut prendre 0,30 s, puis 0,45 s, puis 0,31 s, selon ce
        # que fait l'ordinateur à côté. Avec plusieurs exécutions, on peut
        # prendre la MÉDIANE, et voir la dispersion (side_summary()).
        #
        # runs = {s: [] for s in finished} — une liste vide par côté ;
        # chaque exécution chronométrée est ajoutée à la liste de son côté.
        # run_order() fait tourner le côté qui passe en premier à chaque
        # répétition.
        # -------------------------------------------------------------
        # b. Timed repetitions, changing which side goes first.
        runs = {s: [] for s in finished}
        for repeat in range(1, args.repeats + 1):
            for side in run_order(finished, repeat):
                runs[side].append(timed_run(side, context["processes"], conn, driver, database,
                                            actor["actor_id"], depth, args.timeout))

        # ÉTAPE c — les chiffres de travail, une exécution supplémentaire
        # par côté qui a terminé (voir work_figures()).
        # c. The work done inside each database.
        work = {s: work_figures(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in finished}

        # -------------------------------------------------------------
        # Un résumé par côté, selon trois cas :
        #   finished                  tous ses chiffres (side_summary())
        #   dans `first` mais pas ok  il vient de s'exécuter et a échoué :
        #                             son statut (« timeout » ou « error »)
        #                             et son premier temps
        #   absent de `first`         ignoré : il s'était arrêté à une
        #                             profondeur plus petite ; le statut
        #                             enregistré dans `stopped`
        # -------------------------------------------------------------
        summaries = {}
        for side in all_sides:
            if side in finished:
                summaries[side] = side_summary(first[side], runs[side], work[side], "finished")
            elif side in first:
                summaries[side] = side_summary(first[side], [], {}, first[side].status)
            else:
                summaries[side] = side_summary(None, [], {}, stopped[side])

        # -------------------------------------------------------------
        # ÉTAPE d — L'ÉCRITURE DES LIGNES
        #
        # Une ligne par VERSION CYPHER : chaque ligne compare PostgreSQL à
        # une version Cypher, donc les chiffres de PostgreSQL apparaissent
        # sur les deux lignes (les mêmes chiffres, mesurés une seule fois).
        #
        # pg / neo — le résumé, plus joins_or_hops : {**dict, "key": v}
        # copie le dictionnaire et y ajoute une clé. Le SQL compte des
        # jointures, Cypher des relations suivies (traversal.sql_joins /
        # cypher_hops).
        #
        # all_sides[1:] — tous les côtés sauf le premier (PostgreSQL).
        #
        # line = { ... } — les colonnes du TEST :
        #   **context["facts"]   quand, quelles données, la taille du
        #                        graphe, et les tailles des deux bases
        #                        (voir main())
        #   start_...            l'acteur de départ
        #   actors_reached       next(iter(counts)) : le seul nombre de
        #                        l'ensemble (iter + next prennent son
        #                        premier élément : test_build_hours.py),
        #                        ou "" si les côtés ne sont pas d'accord ou
        #                        si personne n'a terminé
        #   answers_match        "yes" (une seule réponse), "no"
        #                        (plusieurs), "unknown" (aucune :
        #                        l'ensemble est vide)
        #   faster, times_faster venant de compare()
        #
        # Puis les deux BLOCS, avec la même boucle pour les deux côtés :
        # pour chaque nom de SIDE_COLUMNS, la colonne « pg_<nom> » (ou
        # « neo4j_<nom> ») reçoit la valeur de ce côté.
        # figures.get(key, "") — une cellule vide si le côté n'a pas cette
        # valeur (temp_disk_mb pour Neo4j, tout sauf le statut pour un côté
        # qui n'a pas terminé). database_mb est sauté ici parce qu'il est
        # déjà venu avec les faits.
        #
        # writer.writerow(line) — une ligne du CSV. DictWriter met chaque
        # valeur dans la colonne du même nom, quel que soit l'ordre du
        # dictionnaire (voir main()).
        # -------------------------------------------------------------
        # d. One line per Cypher version: the test, then PostgreSQL's block, then Neo4j's.
        pg = {**summaries["postgresql"], "joins_or_hops": traversal.sql_joins(depth)}
        for side in all_sides[1:]:
            neo = {**summaries[side], "joins_or_hops": traversal.cypher_hops(depth)}
            faster, times = compare(pg, neo, args.timeout)
            line = {
                **context["facts"],
                "start_group": actor["group"], "start_rank": actor["rank"], "start_actor_id": actor["actor_id"],
                "start_login": actor["login"], "start_reach_1_hop": actor["reached"],
                "depth": depth, "cypher_version": side.split("-", 1)[1],
                "actors_reached": next(iter(counts)) if len(counts) == 1 else "",
                "answers_match": "yes" if len(counts) == 1 else ("no" if counts else "unknown"),
                "runs": args.repeats, "timeout_s": args.timeout,
                "faster": faster, "times_faster": times,
            }
            for prefix, figures in (("pg", pg), ("neo4j", neo)):
                for key in SIDE_COLUMNS:
                    if key != "database_mb":   # the database sizes are already in the facts
                        line[f"{prefix}_{key}"] = figures.get(key, "")
            writer.writerow(line)

        # -------------------------------------------------------------
        # Terminer à l'écran la ligne de cette profondeur.
        #
        # Si les réponses diffèrent, les lignes ont été écrites (avec
        # answers_match = "no", pour que le problème soit visible dans le
        # fichier), et `return` arrête complètement la mesure de cet
        # acteur ; main() passe au suivant. sorted(counts) affiche
        # l'ensemble dans l'ordre.
        #
        # notes : les côtés dont la première exécution n'a PAS été « ok »,
        # par exemple « neo4j-paths timeout ». ", ".join(...) relie les
        # morceaux par des virgules ; les morceaux viennent d'une
        # EXPRESSION GÉNÉRATRICE (drop_databases.py). (f"..." if notes
        # else "") n'ajoute la partie entre parenthèses que s'il y a quelque
        # chose à dire.
        #
        # all(...) — vaut True si CHAQUE côté s'est arrêté : il ne reste
        # plus rien à mesurer pour cet acteur, et `break` sort de la boucle
        # des profondeurs.
        # -------------------------------------------------------------
        if len(counts) > 1:
            print(f"ANSWERS DIFFER {sorted(counts)}; stopping this actor")
            return
        shown = next(iter(counts)) if counts else "?"
        notes = ", ".join(f"{s} {first[s].status}" for s in active if first[s].status != "ok")
        print(f"{shown} actors reached" + (f" ({notes})" if notes else ""))
        if all(s in stopped for s in all_sides):
            break


# ---------- starting actors, and the summary ----------

# ---------------------------------------------------------------------
# def results_file(database, measured_at) -> Path:  — LE FICHIER DE CETTE MESURE
#
# Le nom est la base, « _ », puis le moment où la mesure a commencé. Dans
# la f-string, strftime('%Y-%m-%d_%H-%M-%S') utilise des apostrophes
# SIMPLES parce que la f-string elle-même est entre guillemets doubles.
# Pas de « : » dans l'heure : Windows ne l'autorise pas dans les noms de
# fichiers. Comme le nom commence par l'année, trier les noms par ordre
# alphabétique les trie aussi dans l'ordre du TEMPS — previous_starts()
# compte là-dessus.
# ---------------------------------------------------------------------
def results_file(database: str, measured_at: datetime) -> Path:
    # One file per measurement, named after the database and the moment it started.
    return RESULTS_DIR / f"{database}_{measured_at.strftime('%Y-%m-%d_%H-%M-%S')}.csv"


# ---------------------------------------------------------------------
# def previous_starts(database) -> list[dict]:  — RÉUTILISER LES MÊMES ACTEURS
#
# La recherche compare des mesures entre elles : la même base mesurée à
# nouveau un autre jour doit utiliser les MÊMES 20 acteurs, sinon les
# deux mesures ne seraient pas comparables. Les acteurs ne sont pas
# enregistrés dans un fichier à part : chaque ligne d'un CSV de résultats
# dit déjà de quel acteur elle est partie (les colonnes start_...). Cette
# fonction RELIT donc le DERNIER CSV de cette base et en récupère les
# acteurs.
#
# RESULTS_DIR.glob(f"{database}_*.csv") — tous les fichiers dont le nom
# correspond au motif : `*` signifie « n'importe quels caractères » (ici,
# la date et l'heure). sorted(...) les met dans l'ordre du temps (voir
# results_file()), donc earlier[-1] — le DERNIER élément de la liste —
# est le plus récent. Pas encore de fichier : une liste vide (main()
# choisit alors les acteurs).
#
# csv.DictReader (load_neo4j.py) donne chaque ligne sous forme de
# dictionnaire, avec des valeurs en TEXTE. row.get("database") (plutôt
# que row["database"]) donne None au lieu de planter si un fichier n'a
# pas cette colonne. Le même acteur apparaît sur de nombreuses lignes
# (une par profondeur et par version), donc `seen` (un ensemble
# d'identifiants) garde chaque acteur une seule fois. int(...) retransforme
# les nombres en nombres.
#
# La clé de tri, une lambda qui renvoie un tuple (choose_starts.py) :
#   a["group"] != "top"   False pour « top », True pour « median » ; False
#                         passe avant True, donc le groupe top vient en
#                         premier ;
#   a["rank"]             puis par rang, de 1 à 10.
# ---------------------------------------------------------------------
def previous_starts(database: str) -> list[dict]:
    # The actors used in the latest measurement of this database, in their order.
    # (The date-time in the file names sorts in time order.)
    earlier = sorted(RESULTS_DIR.glob(f"{database}_*.csv"))
    if not earlier:
        return []
    seen, actors = set(), []
    with open(earlier[-1], encoding="utf-8") as f:
        for row in csv.DictReader(f):
            if row.get("database") == database and row["start_actor_id"] not in seen:
                seen.add(row["start_actor_id"])
                actors.append({"group": row["start_group"], "rank": int(row["start_rank"]),
                               "actor_id": int(row["start_actor_id"]), "login": row["start_login"],
                               "reached": int(row["start_reach_1_hop"])})
    return sorted(actors, key=lambda a: (a["group"] != "top", a["rank"]))


# ---------------------------------------------------------------------
# def print_summary(database, path) -> None:  — UN TABLEAU À L'ÉCRAN
#
# Après la mesure, un petit tableau de ce qui vient d'être mesuré. Il
# relit le fichier CSV de cette mesure (`path`) ; chacune de ses lignes
# appartient à cette mesure, donc list(...) les garde toutes.
#
# keys — les différentes combinaisons (groupe, profondeur, version) : une
# compréhension d'ENSEMBLE (chaque combinaison une seule fois), puis
# triée : top avant median (même astuce que dans previous_starts), puis
# par profondeur, puis par version.
#
# Pour chaque combinaison :
#   lines    ses lignes (une par acteur).
#   cells    une cellule par côté : le temps médian des acteurs qui ont
#            TERMINÉ, en millisecondes (* 1000) ; `:,.1f` = un séparateur
#            de milliers et une décimale. « +3t/o » indique que 3 acteurs
#            n'ont pas terminé (délai dépassé ou ignorés). « - » si
#            personne n'a terminé.
#   wins     pour combien d'acteurs chaque côté a été le plus rapide.
#            sum(True, False, True...) compte les valeurs True (True
#            compte pour 1).
# Largeur des colonnes (:<7, :>11) : summarize_data.py.
# ---------------------------------------------------------------------
def print_summary(database: str, path: Path) -> None:
    with open(path, encoding="utf-8") as f:
        rows = list(csv.DictReader(f))
    print(f'\nSummary of "{database}" (median over the actors that finished; t/o = timed out or skipped):')
    print(f"  {'group':<7} {'depth':>5}  {'cypher':<7} {'PostgreSQL':>11} {'Neo4j':>11}  faster (count of actors)")
    keys = sorted({(r["start_group"], int(r["depth"]), r["cypher_version"]) for r in rows},
                  key=lambda k: (k[0] != "top", k[1], k[2]))
    for group, depth, version in keys:
        lines = [r for r in rows if (r["start_group"], int(r["depth"]), r["cypher_version"]) == (group, depth, version)]
        cells = []
        for prefix in ("pg", "neo4j"):
            times = [float(r[f"{prefix}_time_s"]) for r in lines if r[f"{prefix}_status"] == "finished"]
            missing = len(lines) - len(times)
            cell = f"{statistics.median(times) * 1000:,.1f} ms" if times else "-"
            cells.append(cell + (f" +{missing}t/o" if missing else ""))
        wins = {name: sum(r["faster"] == name for r in lines) for name in ("postgresql", "neo4j")}
        print(f"  {group:<7} {depth:>5}  {version:<7} {cells[0]:>11} {cells[1]:>11}  "
              f"PG {wins['postgresql']}, Neo4j {wins['neo4j']}")


def main() -> None:
    # -----------------------------------------------------------------
    # Les options. argparse transforme « --max-depth » en args.max_depth
    # (le tiret devient un tiret bas). required=True : le script refuse de
    # s'exécuter sans --database. type=int convertit le texte en nombre.
    #   --cypher       choices=... : argparse refuse toute autre valeur.
    #                  ("both",) + traversal.CYPHER_VERSIONS colle deux
    #                  tuples : ("both", "paths", "levels").
    #   --new-starts   action="store_true" : un interrupteur MARCHE/ARRÊT
    #                  sans valeur (choose_starts.py).
    #
    # Les valeurs par défaut (profondeur 6, 5 répétitions, 60 s) sont un
    # compromis : 5 exécutions chronométrées suffisent pour une médiane qui
    # a du sens ; 60 s arrêtent les exécutions profondes sans espoir sans
    # couper celles qui sont simplement lentes.
    #
    # parser.error("...") affiche l'usage et le message, et arrête le
    # script avec une erreur — la façon habituelle pour argparse de
    # rejeter une valeur qu'il ne sait pas vérifier tout seul (ici : des
    # nombres inférieurs à 1).
    # -----------------------------------------------------------------
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", required=True, help="The database to measure (same name on both sides)")
    parser.add_argument("--max-depth", type=int, default=6, help="Deepest traversal, in hops (default: 6)")
    parser.add_argument("--repeats", type=int, default=5, help="Timed runs per depth and side (default: 5)")
    parser.add_argument("--timeout", type=int, default=60, help="Seconds before a run is stopped (default: 60)")
    parser.add_argument("--cypher", choices=("both",) + traversal.CYPHER_VERSIONS, default="both",
                        help="Which Cypher version(s) to measure (default: both)")
    parser.add_argument("--new-starts", action="store_true",
                        help="Choose the starting actors again instead of reusing the ones of the latest measurement")
    args = parser.parse_args()
    if args.max_depth < 1 or args.repeats < 1 or args.timeout < 1:
        parser.error("--max-depth, --repeats and --timeout must be at least 1")

    # -----------------------------------------------------------------
    # LES ACTEURS DE DÉPART : réutilisés, ou choisis.
    #
    # `[] if args.new_starts else previous_starts(...)` : avec
    # --new-starts, on fait comme s'il n'y en avait aucun. Une liste vide
    # compte comme False, donc si rien n'a été trouvé,
    # choose_starts.choose_in_both() les choisit (dans les DEUX bases, qui
    # doivent être d'accord — sinon elle lève RuntimeError).
    # \" dans la f-string est un guillemet double « échappé ».
    # -----------------------------------------------------------------
    starts = [] if args.new_starts else previous_starts(args.database)
    if starts:
        print(f"Reusing the {len(starts)} starting actors already measured for \"{args.database}\" (from their latest measurement).")
    else:
        starts = choose_starts.choose_in_both(args.database)
        print(f"Both databases choose the same {len(starts)} actors.")

    # La fenêtre des données (data_window()), et le moment où cette mesure
    # a commencé (datetime.now()), utilisé deux fois :
    #   measured_at   sous forme de texte, "%H:%M:%S" = heures, minutes,
    #                 secondes ; il figure sur chaque ligne du fichier ;
    #   path          le nom du fichier de cette mesure (results_file()).
    data_from, data_to, hours = data_window(args.database)
    started = datetime.now()
    measured_at = started.strftime("%Y-%m-%d %H:%M:%S")
    path = results_file(args.database, started)
    # -----------------------------------------------------------------
    # Deux connexions dans UNE seule instruction `with`, séparées par une
    # virgule : les deux sont fermées à la fin, quoi qu'il arrive. Une
    # seule connexion PostgreSQL et un seul driver Neo4j sont réutilisés
    # pour toutes les exécutions — ouvrir une nouvelle connexion à chaque
    # exécution ajouterait son propre coût à chaque temps mesuré.
    #
    # processes : les processus serveurs de chaque base, trouvés UNE
    # seule fois. Si aucun n'est trouvé (par exemple, le serveur tourne
    # sur un autre ordinateur, ou sous un nom non reconnu), la mesure a
    # quand même lieu : seules les colonnes de CPU restent vides, et une
    # note le signale.
    #
    # context : tout ce dont measure_actor() a besoin, dans un seul
    # dictionnaire.
    #   "facts"   les colonnes du TEST qui sont les mêmes pour chaque
    #             ligne : measured_at, database, la fenêtre des données,
    #             plus graph_facts() (taille du graphe et les deux
    #             database_mb). La compréhension de dictionnaire arrondit
    #             les nombres décimaux (floats : les tailles en Mo) à une
    #             décimale ; isinstance(v, float) vérifie le type
    #             (profile_schema.py) ; les comptages restent tels quels.
    #
    # L'affichage : `:,` ajoute des séparateurs de milliers (1,234,567).
    # Trois f-strings placées côte à côte sont collées en une seule.
    # -----------------------------------------------------------------
    with traversal.connect_postgres(args.database) as conn, traversal.connect_neo4j() as driver:
        facts = graph_facts(conn, driver, args.database)
        processes = {"postgresql": server_processes("postgresql"), "neo4j": server_processes("neo4j")}
        for system, found in processes.items():
            if not found:
                print(f"Note: no {system} server process found on this computer; its CPU columns stay empty.")
        context = {"conn": conn, "driver": driver, "processes": processes,
                   "facts": {"measured_at": measured_at, "database": args.database, "data_from_utc": data_from,
                             "data_to_utc": data_to, "volume_hours": hours,
                             **{k: round(v, 1) if isinstance(v, float) else v for k, v in facts.items()}}}
        print(f'\nMeasuring "{args.database}" ({facts["graph_actors"]:,} actors, {facts["graph_repos"]:,} repos, '
              f'{facts["graph_connections"]:,} connections): {len(starts)} starting actors, depths 1-{args.max_depth}, '
              f"{args.repeats} timed runs each, time limit {args.timeout} s, Cypher: {args.cypher}")

        # -------------------------------------------------------------
        # L'ÉCRITURE DU FICHIER CSV DE CETTE MESURE
        #
        # Le nom du fichier est affiché d'abord, pour que vous sachiez où
        # regarder pendant l'exécution. mkdir(parents=True,
        # exist_ok=True) : crée results/ si nécessaire (extract_csv.py).
        #
        # open(path, "w", ...) — "w" ouvre un NOUVEAU fichier en écriture
        # (un fichier existant du même nom serait vidé ; la date et l'heure
        # dans le nom rendent cela pratiquement impossible).
        #
        # csv.DictWriter — écrire des lignes qui sont des DICTIONNAIRES
        #   csv.writer (docs_french/extract_csv.py) écrit des listes, où
        #   l'ordre des valeurs doit correspondre à l'en-tête, à la main.
        #   DictWriter prend fieldnames= (les noms des colonnes, ici
        #   COLUMNS) puis des lignes sous forme de dictionnaires : chaque
        #   valeur va dans la colonne qui porte le MÊME NOM, quel que soit
        #   l'ordre du dictionnaire, et une clé absente donne une cellule
        #   vide. C'est le jumeau en écriture de csv.DictReader
        #   (load_neo4j.py).
        #     writeheader()    écrit la ligne d'en-tête (les fieldnames)
        #     writerow(dict)   écrit une ligne (dans measure_actor())
        #
        # enumerate(starts, start=1) numérote les acteurs à partir de 1
        # (et non de 0) pour l'affichage de la progression « [3/20] ».
        #
        # f.flush() après chaque acteur — une mesure complète peut durer
        # des HEURES. Python garde les lignes écrites en mémoire un moment
        # avant qu'elles n'arrivent vraiment dans le fichier. flush() les
        # pousse dans le fichier tout de suite, donc si quelque chose se
        # passe mal à l'acteur 15 (un plantage, Ctrl+C, l'ordinateur
        # portable qui se met en veille), les lignes des acteurs 1 à 14
        # sont en sécurité sur le disque.
        # -------------------------------------------------------------
        print(f"Results: {path}")
        RESULTS_DIR.mkdir(parents=True, exist_ok=True)
        with open(path, "w", newline="", encoding="utf-8") as f:
            writer = csv.DictWriter(f, fieldnames=COLUMNS)
            writer.writeheader()
            for number, actor in enumerate(starts, start=1):
                print(f"[{number}/{len(starts)}] {actor['group']} #{actor['rank']}: {actor['login']} "
                      f"(reaches {actor['reached']} in one hop)")
                measure_actor(actor, context, args, writer)
                f.flush()

    # Après les blocs `with` (fichier fermé, connexions fermées) : le
    # tableau à l'écran, et l'endroit où se trouvent les lignes.
    print_summary(args.database, path)
    print(f"\nDone. The results of this measurement are in {path}")


# ---------------------------------------------------------------------
# La garde __name__ (voir docs_french/download_gharchive.py), avec un
# ajout : main() s'exécute dans un try / except, qui attrape DEUX sortes
# d'erreurs, écrites sous forme de tuple (FileNotFoundError,
# RuntimeError) :
#   RuntimeError        les deux bases ne contiennent pas les mêmes
#                       données (graph_facts()) ou ne choisissent pas les
#                       mêmes acteurs (choose_starts.choose_in_both()) ;
#   FileNotFoundError   un fichier manquant.
# Leurs messages disent déjà ce qui ne va pas, donc ils sont affichés
# seuls, sans la longue trace d'erreur (traceback) de Python, et
# sys.exit(1) signale l'échec — ce qui fait s'arrêter research.sh à cet
# endroit (set -e, voir docs_french/research.sh).
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except (FileNotFoundError, RuntimeError) as error:
        print(error)
        sys.exit(1)
