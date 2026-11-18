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
#                             try/except et lever FileNotFoundError
#   - extract_csv.py          csv.writer, open(..., newline=""),
#                             mkdir(parents=True), sorted(...), les
#                             ensembles (sets)
#   - load_neo4j.py           csv.DictReader,
#                             driver.execute_query(..., database_=...)
#   - check_connections.py    les connexions psycopg / neo4j, `with`,
#                             sys.exit
#   - pipeline.py             RawDescriptionHelpFormatter
#   - traversal.py            les deux requêtes de parcours, l'objet
#                             Outcome (status / seconds / count / error),
#                             les délais (timeouts), EXPLAIN (ANALYZE,
#                             BUFFERS) et PROFILE
#   - choose_starts.py        comment les 20 acteurs de départ sont
#                             choisis, RESULTS_DIR et
#                             results/<database>/starts.csv
#
# Ce qui est NOUVEAU ici — c'est le script qui produit réellement les
# chiffres de la recherche, donc la plupart des explications portent sur
# l'art de MESURER ÉQUITABLEMENT :
#   - l'exécution 0, la « première exécution » : ce n'est pas un résultat
#     (elle inclut la préparation du plan de requête), mais elle sert à
#     vérifier que les deux côtés donnent le MÊME comptage ;
#   - des répétitions chronométrées qui ALTERNENT le côté qui passe en
#     premier ;
#   - noter à quel point l'ordinateur était occupé (psutil) à côté de
#     chaque exécution ;
#   - arrêter les profondeurs plus grandes pour un côté dès qu'il manque
#     de temps ;
#   - conditions.json : versions, réglages de mémoire et tailles,
#     enregistrés pour que les résultats puissent être lus plus tard dans
#     leur contexte ;
#   - flush(), un dossier de sortie par date et heure (csv.DictWriter est
#     expliqué dans docs_french/choose_starts.py ; un rappel figure plus
#     bas).
#
# Comment il est censé être lancé — normalement via research.sh, qui lance
# choose_starts.py, puis ce script, puis analyze.py :
#     ./research.sh --database gharchive-2026-08-27-12-6h
# ou seul, via run.sh (qui charge .venv et les mots de passe) :
#     ./run.sh scripts/measure.py --database gharchive-2026-08-27-12-6h
########################################################################

"""Measure the traversal in PostgreSQL and Neo4j, from the chosen starting actors.

For every starting actor (results/<database>/starts.csv, from choose_starts.py)
and every depth from 1 to --max-depth, it:

    1. runs the traversal once on each side, not timed as a result ("first run":
       it includes preparing the query plan), and checks that BOTH SIDES GIVE
       THE SAME COUNT;
    2. runs it --repeats more times, alternating which side goes first, so that
       anything else happening on the computer affects both sides alike; each
       run records its time, its answer, whether it finished, failed or ran out
       of time (--timeout), and how busy the computer was (CPU and memory);
    3. runs it once more with EXPLAIN (ANALYZE, BUFFERS) / PROFILE, to record
       the work done inside each database.

If a side runs out of time at some depth, the deeper depths are skipped for that
side and actor (they can only be slower). The conditions (versions, memory
settings, data size) are saved too, so every result can be read later in context.

Everything goes to results/<database>/<date-time>/:
    conditions.json   versions, settings, sizes, options used
    runs.csv          one line per timed run
    work.csv          one line per actor, depth and side: the database's own figures

Usage:
    ./run.sh scripts/measure.py --database gharchive-2026-08-27-12-6h
    ./run.sh scripts/measure.py --database ... --max-depth 4 --repeats 5 --timeout 60
"""

# ---------------------------------------------------------------------
# Imports de la bibliothèque standard. Déjà rencontrés : argparse, csv,
# json, sys, Path. Les nouveaux :
#   platform  — décrit l'ordinateur et Python lui-même : nom du
#               processeur, système d'exploitation, version de Python.
#               Utilisé dans conditions().
#   datetime  — la date et l'heure actuelles : datetime.now(). Utilisé
#               pour nommer le dossier de sortie et pour dater
#               conditions.json.
# ---------------------------------------------------------------------
import argparse
import csv
import json
import platform
import sys
from datetime import datetime
from pathlib import Path

# ---------------------------------------------------------------------
# import psutil
#
# Un paquet EXTERNE (installé depuis requirements.txt, comme psycopg et
# neo4j) : « process and system utilities » (utilitaires pour les
# processus et le système). Il lit à quel point l'ordinateur est occupé
# — utilisation du processeur (CPU), mémoire utilisée, nombre de
# processeurs, mémoire totale.
#
# Pourquoi un benchmark en a-t-il besoin ? Le portable sert aussi à
# d'autres choses pendant que la mesure tourne (un navigateur, une
# analyse antivirus, les mises à jour de Windows...). Si une exécution a
# été lente parce que l'ordinateur était occupé, on veut le VOIR à côté
# du temps, au lieu d'en accuser la base de données.
# ---------------------------------------------------------------------
import psutil

# ---------------------------------------------------------------------
# import choose_starts / import traversal
#
# Les PROPRES scripts du projet, importés comme des paquets (cela
# fonctionne parce qu'ils sont tous dans le même dossier scripts/). Ce
# script réutilise :
#   choose_starts.RESULTS_DIR            le dossier results/
#   traversal.connect_postgres / connect_neo4j
#   traversal.run_postgres_reach / run_neo4j_reach     un parcours
#                                                      chronométré
#   traversal.postgres_work / neo4j_work               les chiffres de
#                                                      travail
# Tous sont expliqués dans docs_french/traversal.py et
# docs_french/choose_starts.py.
# ---------------------------------------------------------------------
import choose_starts
import traversal

# ---------------------------------------------------------------------
# Les noms de colonnes des deux fichiers CSV qu'écrit ce script.
#
# RUN_FIELDS — runs.csv, UNE LIGNE PAR EXÉCUTION :
#   actor_id, group    quel acteur de départ (groupe « top » ou
#                      « median »)
#   depth              combien de sauts
#   system             "postgresql" ou "neo4j"
#   run                0 pour la première exécution (pas un résultat),
#                      puis 1, 2, ...
#   status             "ok", "timeout" ou "error"
#   seconds            combien de temps cela a pris, mesuré depuis Python
#   count              la réponse : combien d'acteurs ont été atteints
#   machine_cpu_percent, machine_memory_percent
#                      à quel point tout l'ordinateur était occupé juste
#                      avant l'exécution
#   error              le message d'erreur, s'il y en a un
#
# WORK_FIELDS — work.csv, les chiffres que chaque BASE DE DONNÉES donne
# sur son propre travail (d'après EXPLAIN / PROFILE, voir
# docs_french/traversal.py) :
#   server_ms                         le temps mesuré à l'intérieur du
#                                     serveur
#   blocks_from_memory / from_disk    PostgreSQL : pages de données
#                                     trouvées dans sa mémoire ou lues sur
#                                     le disque
#   temp_blocks_written               PostgreSQL : déversées dans des
#                                     fichiers temporaires parce que
#                                     work_mem était trop petit
#   db_hits                           Neo4j : son unité de « travail
#                                     effectué »
#   page_cache_hits / misses          Neo4j : même idée que les blocs de
#                                     PostgreSQL
#   memory_bytes                      Neo4j : la mémoire utilisée par la
#                                     requête
#
# Garder les listes de colonnes sous forme de constantes garantit que
# l'en-tête et les lignes ne peuvent jamais diverger (voir csv.DictWriter
# dans main()).
#
# SYSTEMS — les deux côtés, sous forme de tuple, toujours dans cet ordre.
# ---------------------------------------------------------------------
RUN_FIELDS = ["actor_id", "group", "depth", "system", "run", "status", "seconds", "count",
              "machine_cpu_percent", "machine_memory_percent", "error"]
WORK_FIELDS = ["actor_id", "group", "depth", "system", "server_ms", "blocks_from_memory", "blocks_from_disk",
               "temp_blocks_written", "db_hits", "page_cache_hits", "page_cache_misses", "memory_bytes"]
SYSTEMS = ("postgresql", "neo4j")


# ---------------------------------------------------------------------
# def run_order(repeat) — QUEL CÔTÉ PASSE EN PREMIER
#
# Pourquoi alterner ? Tout ce qui change pendant la mesure touche celui
# qui tourne à ce moment-là : vous ouvrez un onglet du navigateur,
# l'antivirus se réveille, le portable chauffe et ralentit, Windows écrit
# sur le disque... Si PostgreSQL passait TOUJOURS en premier, chacune de
# ces perturbations tomberait du même côté, à la même position. Alterner
# les répartit pour qu'elles touchent les deux côtés de la même façon, et
# qu'aucun n'ait d'avantage systématique (par exemple « le second à
# tourner trouve toujours les données déjà dans la mémoire du système
# d'exploitation »).
#
# repeat % 2 — `%` est le RESTE d'une division : 1 % 2 vaut 1, 2 % 2 vaut
# 0, 3 % 2 vaut 1... donc `repeat % 2 == 1` signifie « repeat est
# impair ».
#
# SYSTEMS[::-1] — un découpage (slice) avec un pas de -1 donne le tuple
# À L'ENVERS : ("neo4j", "postgresql").
#
# `A if condition else B` — un if/else sur une ligne qui donne une
# VALEUR : A quand la condition est vraie, B sinon.
#
# -> tuple[str, str] : la fonction renvoie un tuple de deux chaînes.
# tests/test_research.py vérifie cette fonction
# (docs_french/test_research.py).
# ---------------------------------------------------------------------
def run_order(repeat: int) -> tuple[str, str]:
    # Repetition 1: PostgreSQL first; repetition 2: Neo4j first; and so on.
    return SYSTEMS if repeat % 2 == 1 else SYSTEMS[::-1]


# ---------------------------------------------------------------------
# def machine_load() — À QUEL POINT L'ORDINATEUR EST OCCUPÉ EN CE MOMENT
#
# psutil.cpu_percent(interval=0.2)
#   Observe le processeur pendant 0,2 seconde et renvoie la part utilisée,
#   en pourcentage (0-100), en comptant TOUS les programmes, pas
#   seulement le nôtre. L'intervalle est nécessaire : « l'utilisation du
#   CPU » n'a de sens que sur une période de temps. 0,2 s est assez court
#   pour ne pas trop ralentir la mesure.
#
# psutil.virtual_memory().percent
#   La part de la mémoire de l'ordinateur (RAM) qui est utilisée, en
#   pourcentage.
#
# Elle est appelée juste AVANT chaque exécution chronométrée (voir
# measure_actor()), pour que chaque ligne de runs.csv dise à quel point
# l'ordinateur était occupé à ce moment-là. analyze.py signale ensuite
# comme « bruitées » les exécutions où le CPU dépassait 80 %.
# ---------------------------------------------------------------------
def machine_load() -> tuple[float, float]:
    # CPU use of the whole computer over a short moment, and memory in use (percent).
    return psutil.cpu_percent(interval=0.2), psutil.virtual_memory().percent


# ---------------------------------------------------------------------
# def read_starts(database) — lire les acteurs de départ
#
# starts.csv a été écrit par choose_starts.py (voir
# docs_french/choose_starts.py). S'il n'est pas là, mesurer n'a aucun
# sens ; la fonction lève donc FileNotFoundError avec un message qui dit
# quoi lancer d'abord. L'erreur est attrapée tout en bas du fichier (dans
# la garde __name__) et affichée proprement, sans longue trace d'erreur.
#
# {**row, "actor_id": int(row["actor_id"])}
#   csv.DictReader donne chaque valeur sous forme de TEXTE. `**row` copie
#   toutes les paires clé/valeur de row dans un NOUVEAU dictionnaire, puis
#   "actor_id": ... vient après et REMPLACE cette seule clé par un vrai
#   entier. Même idée que `**` qui dépaquette un dictionnaire en arguments
#   nommés dans check_connections.py, mais utilisé à l'intérieur d'un
#   dictionnaire { }. Tout le reste (group, rank, login, reached) reste du
#   texte — ce n'est qu'affiché.
# ---------------------------------------------------------------------
def read_starts(database: str) -> list[dict]:
    path = choose_starts.RESULTS_DIR / database / "starts.csv"
    if not path.exists():
        raise FileNotFoundError(f"{path} doesn't exist: run choose_starts.py --database {database} first")
    with open(path, encoding="utf-8") as f:
        return [{**row, "actor_id": int(row["actor_id"])} for row in csv.DictReader(f)]


# ---------------------------------------------------------------------
# def conditions(...) — LES CONDITIONS DE LA MESURE
#
# Un temps comme « 0,8 s » ne veut pas dire grand-chose tout seul. Il
# dépend des versions des logiciels, de la quantité de mémoire que chaque
# base de données était AUTORISÉE à utiliser, de la taille des données,
# de l'ordinateur. Cette fonction rassemble tout cela dans un
# dictionnaire, que main() enregistre sous le nom conditions.json à côté
# des résultats. Des mois plus tard, les chiffres peuvent encore être lus
# dans leur contexte (« ceci a été mesuré avec les 128 MB de
# shared_buffers par défaut de PostgreSQL »).
#
# Remarque : les réglages sont NOTÉS, pas modifiés. Les deux bases
# tournent avec leurs valeurs par défaut d'installation ; le but est de
# savoir quelles elles étaient.
# ---------------------------------------------------------------------
def conditions(conn, driver, database: str, args: argparse.Namespace) -> dict:
    # -----------------------------------------------------------------
    # Les réglages de PostgreSQL, lus avec la commande SQL `SHOW <nom>` :
    #   shared_buffers        la mémoire propre à PostgreSQL pour les
    #                         pages de données (128MB par défaut — c'est
    #                         peu ; le cache de fichiers du système
    #                         d'exploitation aide en plus)
    #   work_mem              la mémoire par étape de tri / de hachage
    #                         avant de déverser dans des fichiers
    #                         temporaires sur le disque (4MB par défaut)
    #   effective_cache_size  ce que le planificateur de requêtes SUPPOSE
    #                         être en cache au total (4GB par défaut) ;
    #                         cela n'influence que le choix des plans
    #   max_parallel_workers_per_gather
    #                         combien de processus supplémentaires une
    #                         requête peut utiliser (2 par défaut)
    #   jit                   compiler des parties des grosses requêtes en
    #                         code machine (activé par défaut)
    #
    # f"SHOW {name}" construit le texte SQL avec une f-string. Ce n'est
    # sûr ICI que parce que les noms viennent de notre propre tuple fixe
    # ci-dessus, jamais d'un utilisateur (voir docs_french/traversal.py au
    # sujet de sql.Literal).
    #
    # {name: ... for name in settings} est une COMPRÉHENSION DE
    # DICTIONNAIRE : comme une compréhension de liste, mais elle construit
    # un dictionnaire, une paire clé: valeur par élément.
    # -----------------------------------------------------------------
    settings = ("shared_buffers", "work_mem", "effective_cache_size", "max_parallel_workers_per_gather", "jit")
    postgres = {name: conn.execute(f"SHOW {name}").fetchone()[0] for name in settings}
    # La version du serveur, la taille de toute la base sur le disque en
    # octets (pg_database_size de la base à laquelle on est connecté), et
    # le nombre de lignes de chacune des trois tables.
    postgres["version"] = conn.execute("SHOW server_version").fetchone()[0]
    postgres["database_size_bytes"] = conn.execute("SELECT pg_database_size(current_database())").fetchone()[0]
    postgres["rows"] = {t: conn.execute(f"SELECT count(*) FROM {t}").fetchone()[0] for t in ("actor", "repo", "actor_repo")}

    # -----------------------------------------------------------------
    # Les réglages de mémoire de Neo4j, lus avec la commande Cypher SHOW
    # SETTINGS :
    #   server.memory.heap.initial_size / max_size
    #                         le « tas » (heap) Java : la mémoire pour
    #                         exécuter les requêtes
    #   server.memory.pagecache.size
    #                         la mémoire de Neo4j pour les pages de
    #                         données (l'équivalent de shared_buffers dans
    #                         PostgreSQL)
    #   dbms.memory.transaction.total.max
    #                         le plafond de mémoire utilisée par toutes
    #                         les requêtes à la fois
    # Les réglages du serveur se trouvent dans la base spéciale « system »,
    # d'où database_="system". `.records` est la liste des lignes du
    # résultat (la première des trois choses que renvoie execute_query,
    # voir check_connections.py).
    #
    # Le texte de la requête est coupé en plusieurs morceaux "..." :
    # Python colle en une seule les chaînes écrites les unes à côté des
    # autres.
    # -----------------------------------------------------------------
    records = driver.execute_query(
        "SHOW SETTINGS YIELD name, value WHERE name IN ['server.memory.heap.initial_size', "
        "'server.memory.heap.max_size', 'server.memory.pagecache.size', 'dbms.memory.transaction.total.max'] "
        "RETURN name, value", database_="system").records
    neo4j = {r["name"]: r["value"] for r in records}
    # La version, comme dans check_connections.py ; `AS v` nomme la
    # colonne. .records[0] est la première (et seule) ligne.
    version = driver.execute_query("CALL dbms.components() YIELD versions, edition RETURN versions[0] AS v, edition",
                                   database_="system").records[0]
    neo4j["version"] = f"{version['v']} {version['edition']}"
    # -----------------------------------------------------------------
    # count = lambda q: ...
    #
    # Une LAMBDA est une toute petite fonction sans nom, écrite sur une
    # ligne :
    #     lambda q: <expression>
    # est la même chose que
    #     def count(q):
    #         return <expression>
    # Ici, elle évite de répéter trois fois le long appel
    # execute_query(...). records[0][0] est la première colonne de la
    # première ligne : le nombre.
    #
    # Les trois comptages sont l'équivalent, dans le graphe, des trois
    # tables, pour que conditions.json puisse montrer que les deux côtés
    # contiennent les mêmes données.
    # -----------------------------------------------------------------
    count = lambda q: driver.execute_query(q, database_=database).records[0][0]
    neo4j["rows"] = {"actors": count("MATCH (a:Actor) RETURN count(a)"),
                     "repos": count("MATCH (r:Repo) RETURN count(r)"),
                     "connections": count("MATCH ()-[c:INTERACTED_WITH]->() RETURN count(c)")}

    # -----------------------------------------------------------------
    # Le tableau complet, sous forme d'un seul dictionnaire imbriqué (des
    # dictionnaires dans un dictionnaire), que json.dumps() peut
    # transformer tel quel en fichier.
    #   started      datetime.now().isoformat(timespec="seconds") donne la
    #                date et l'heure sous forme de texte, par ex.
    #                « 2026-11-18T14:05:31 »
    #   options      ce qu'on a demandé à la mesure de faire
    #   machine      nom du processeur, nombre de processeurs LOGIQUES
    #                (cœurs, en comptant l'hyper-threading), mémoire
    #                totale en Go (octets / 1024**3, `**` signifiant « à la
    #                puissance » ; arrondi à une décimale), système
    #                d'exploitation et version de Python
    # -----------------------------------------------------------------
    return {
        "database": database,
        "started": datetime.now().isoformat(timespec="seconds"),
        "options": {"max_depth": args.max_depth, "repeats": args.repeats, "timeout_s": args.timeout},
        "machine": {"cpu": platform.processor(), "logical_cpus": psutil.cpu_count(),
                    "memory_gb": round(psutil.virtual_memory().total / 1024 ** 3, 1),
                    "os": platform.platform(), "python": platform.python_version()},
        "postgresql": postgres,
        "neo4j": neo4j,
    }


# ---------------------------------------------------------------------
# def run_once(system, ...) — un parcours d'UN SEUL côté
#
# Un petit aiguillage pour que le reste du code puisse simplement dire
# « lance-le de ce côté » sans se soucier de quel côté il s'agit. Les
# deux fonctions renvoient un Outcome (status, seconds, count, error) :
# voir docs_french/traversal.py.
# ---------------------------------------------------------------------
def run_once(system: str, conn, driver, database: str, start: int, depth: int, timeout: int):
    if system == "postgresql":
        return traversal.run_postgres_reach(conn, start, depth, timeout)
    return traversal.run_neo4j_reach(driver, database, start, depth, timeout)


# ---------------------------------------------------------------------
# def measure_actor(...) — TOUT POUR UN ACTEUR DE DÉPART
#
# Pour les profondeurs 1, 2, 3 ... jusqu'à --max-depth, trois étapes (les
# trois mêmes que dans la docstring en haut). `runs` et `work` sont les
# deux écrivains CSV créés dans main() : cette fonction y écrit ses
# lignes.
# ---------------------------------------------------------------------
def measure_actor(actor: dict, conn, driver, database: str, args, runs: csv.DictWriter, work: csv.DictWriter) -> None:
    # -----------------------------------------------------------------
    # stopped — SAUTER LES PROFONDEURS PLUS GRANDES
    #
    # Un ensemble (set) des côtés qui ont déjà manqué de temps (--timeout)
    # pour cet acteur. Aller un saut plus loin ne peut qu'atteindre PLUS
    # d'acteurs, donc ne peut que prendre plus de temps : si la profondeur
    # 4 n'a pas fini en 60 s, la profondeur 5 non plus. La sauter épargne
    # 60 s x (1 + repeats) d'attente inutile par profondeur. L'AUTRE côté
    # continue, tant qu'il finit à temps.
    # -----------------------------------------------------------------
    stopped = set()   # sides that ran out of time at a smaller depth
    # range(1, args.max_depth + 1) : 1, 2, ..., max_depth (la fin d'un
    # range n'est PAS incluse, d'où le + 1).
    for depth in range(1, args.max_depth + 1):
        # Les côtés encore mesurés. Si les deux se sont arrêtés, il n'y a
        # plus rien à faire pour cet acteur : `break` sort de la boucle.
        active = [s for s in SYSTEMS if s not in stopped]
        if not active:
            break
        # end=" " — afficher sans passer à la ligne, pour que la suite du
        # compte rendu de cette profondeur apparaisse plus tard sur la
        # même ligne.
        # flush=True — l'afficher MAINTENANT. Normalement, Python garde un
        # moment le texte affiché dans une mémoire tampon (buffer) ; sans
        # flush, vous fixeriez une ligne vide pendant une longue exécution
        # sans savoir quelle profondeur est en cours de mesure.
        print(f"  depth {depth}:", end=" ", flush=True)

        # -------------------------------------------------------------
        # ÉTAPE 1 — L'EXÉCUTION 0, LA « PREMIÈRE EXÉCUTION » : PAS UN
        # RÉSULTAT
        #
        # La toute première fois qu'une base de données voit une requête
        # d'une forme nouvelle, elle fait un travail supplémentaire unique
        # avant de l'exécuter : elle analyse le texte et prépare (compile)
        # un PLAN de requête. Neo4j en particulier met quelques secondes
        # (environ 5 s) à planifier la première requête de longueur
        # variable d'une nouvelle profondeur ; ensuite, le plan est gardé
        # dans son cache et réutilisé. La première exécution charge aussi
        # les données en mémoire. Compter ce temps-là mesurerait « la
        # première fois » plutôt que le parcours lui-même.
        #
        # L'exécution 0 est donc écrite dans runs.csv (avec run = 0, et
        # sans charge de la machine : (None, None)) pour mémoire, mais
        # analyze.py l'ignore quand il calcule les temps.
        #
        # Elle SERT pourtant à quelque chose d'important : la VÉRIFICATION
        # DES COMPTAGES. Les deux côtés répondent à « combien d'acteurs
        # sont atteignables » ; si les deux nombres diffèrent, l'une des
        # deux requêtes (ou les données chargées) est fausse, et comparer
        # leur vitesse n'aurait aucun sens.
        #
        # first = {s: run_once(...) for s in active}
        #   Une compréhension de dictionnaire :
        #   {"postgresql": Outcome, "neo4j": Outcome}.
        # -------------------------------------------------------------
        # 1. First run (not a result) and the count check.
        first = {s: run_once(s, conn, driver, database, actor["actor_id"], depth, args.timeout) for s in active}
        for system, outcome in first.items():
            runs.writerow(row(actor, depth, system, 0, outcome, (None, None)))
        # Les comptages des côtés qui ont fini (« ok »). Ce n'est que
        # quand les DEUX ont fini (len(counts) == 2) qu'on peut les
        # comparer. S'ils diffèrent, afficher un message bien visible et
        # `return` : arrêter complètement de mesurer cet acteur (main()
        # continue avec l'acteur suivant).
        counts = {s: o.count for s, o in first.items() if o.status == "ok"}
        if len(counts) == 2 and counts["postgresql"] != counts["neo4j"]:
            print(f"COUNTS DIFFER (PostgreSQL {counts['postgresql']}, Neo4j {counts['neo4j']}); stopping this actor")
            return
        # Un côté dont la première exécution n'a pas fini (timeout ou
        # erreur) est ajouté à `stopped` : pas d'exécutions chronométrées
        # à cette profondeur, ni de profondeurs plus grandes.
        for system, outcome in first.items():
            if outcome.status != "ok":
                stopped.add(system)
        timed = [s for s in active if s not in stopped]

        # -------------------------------------------------------------
        # ÉTAPE 2 — LES RÉPÉTITIONS CHRONOMÉTRÉES
        #
        # Pourquoi répéter ? Un seul temps n'est pas fiable : la même
        # requête peut prendre 0,30 s, puis 0,45 s, puis 0,31 s, selon ce
        # que fait l'ordinateur par ailleurs. Avec plusieurs exécutions,
        # analyze.py peut prendre la MÉDIANE et voir à quel point elles
        # sont dispersées.
        #
        # Répétition 1 : PostgreSQL puis Neo4j ; répétition 2 : Neo4j
        # puis PostgreSQL ; ... (run_order ci-dessus). `if system in
        # timed` saute un côté qui s'est arrêté à l'étape 1.
        #
        # machine_load() est mesurée juste AVANT l'exécution (elle ne peut
        # pas l'être pendant : cpu_percent() attend ses 0,2 s avant de
        # rendre la main), et écrite sur la même ligne de runs.csv. Les
        # 0,2 s ne font pas partie du temps de l'exécution : le chronomètre
        # démarre à l'intérieur de run_once().
        # -------------------------------------------------------------
        # 2. Timed repetitions, alternating which side goes first.
        for repeat in range(1, args.repeats + 1):
            for system in run_order(repeat):
                if system in timed:
                    load = machine_load()
                    outcome = run_once(system, conn, driver, database, actor["actor_id"], depth, args.timeout)
                    runs.writerow(row(actor, depth, system, repeat, outcome, load))

        # -------------------------------------------------------------
        # ÉTAPE 3 — LES CHIFFRES DE TRAVAIL
        #
        # Une exécution supplémentaire par côté, en demandant cette fois à
        # la base de données de rendre compte de ce qu'elle a fait :
        # EXPLAIN (ANALYZE, BUFFERS) dans PostgreSQL, PROFILE dans Neo4j
        # (expliqués dans docs_french/traversal.py). Elle est séparée des
        # exécutions chronométrées car recueillir ces chiffres coûte
        # lui-même du temps.
        #
        # Ces chiffres expliquent les temps : par ex. « Neo4j a fait 2
        # millions de db_hits » ou « PostgreSQL a lu 9 000 blocs sur le
        # disque ».
        #
        # try / except : si le recueil des chiffres échoue, cela ne vaut
        # pas la peine de perdre toute la mesure. figures = {} écrit une
        # ligne avec les colonnes laissées vides, et une courte note est
        # affichée. str(error)[:80] — les 80 premiers caractères du
        # message (un DÉCOUPAGE du texte), pour ne pas en remplir l'écran.
        #
        # {"actor_id": ..., **figures} — `**` copie les clés des chiffres
        # dans la ligne (même idée que dans read_starts()). DictWriter
        # laisse vide toute colonne de WORK_FIELDS que le dictionnaire n'a
        # pas : PostgreSQL n'a pas de db_hits, Neo4j n'a pas de
        # blocks_from_disk.
        # -------------------------------------------------------------
        # 3. The work done inside each database (one extra run each).
        for system in timed:
            try:
                if system == "postgresql":
                    figures = traversal.postgres_work(conn, actor["actor_id"], depth, args.timeout)
                else:
                    figures = traversal.neo4j_work(driver, database, actor["actor_id"], depth, args.timeout)
            except Exception as error:
                figures = {}
                print(f"(no work figures for {system}: {str(error)[:80]})", end=" ")
            work.writerow({"actor_id": actor["actor_id"], "group": actor["group"], "depth": depth,
                           "system": system, **figures})

        # -------------------------------------------------------------
        # Terminer à l'écran la ligne de cette profondeur.
        #
        # counts.get("postgresql", counts.get("neo4j"))
        #   dict.get(clé, défaut) : le comptage de PostgreSQL s'il a fini,
        #   sinon celui de Neo4j (ou None si aucun n'a fini).
        #
        # status : les côtés dont la première exécution n'était PAS
        # « ok », par ex. « neo4j timeout ». ", ".join(...) relie les
        # morceaux par des virgules. Les morceaux sont produits par une
        # EXPRESSION GÉNÉRATRICE — une compréhension de liste sans les
        # [ ], passée directement à join().
        #
        # (f"..." if status else "") n'ajoute la partie entre parenthèses
        # que lorsqu'il y a quelque chose à dire.
        # -------------------------------------------------------------
        shown = counts.get("postgresql", counts.get("neo4j"))
        status = ", ".join(f"{s} {first[s].status}" for s in active if first[s].status != "ok")
        print(f"{shown} actors reached" + (f" ({status})" if status else ""))


# ---------------------------------------------------------------------
# def row(...) — une ligne de runs.csv, sous forme de dictionnaire
#
# Les clés sont exactement RUN_FIELDS. round(outcome.seconds, 6) garde
# les microsecondes (6 décimales) : au-delà, les chiffres ne sont que du
# bruit. load est le tuple (cpu, mémoire) de machine_load(), ou
# (None, None) pour l'exécution 0 ; load[0] et load[1] prennent ses deux
# valeurs. None est écrit comme une cellule vide dans le CSV.
# ---------------------------------------------------------------------
def row(actor: dict, depth: int, system: str, run: int, outcome, load) -> dict:
    return {"actor_id": actor["actor_id"], "group": actor["group"], "depth": depth, "system": system, "run": run,
            "status": outcome.status, "seconds": round(outcome.seconds, 6), "count": outcome.count,
            "machine_cpu_percent": load[0], "machine_memory_percent": load[1], "error": outcome.error}


def main() -> None:
    # -----------------------------------------------------------------
    # Les options. argparse transforme « --max-depth » en args.max_depth
    # (le tiret devient un tiret bas). required=True : le script refuse de
    # tourner sans --database. type=int convertit le texte en nombre.
    #
    # Les valeurs par défaut (profondeur 6, 5 répétitions, 60 s) sont un
    # compromis : 5 exécutions chronométrées suffisent pour une médiane
    # qui a du sens ; 60 s arrête les exécutions profondes sans espoir
    # sans couper celles qui sont simplement lentes.
    #
    # parser.error("...") affiche l'usage et le message, et arrête le
    # script avec une erreur — la façon standard pour argparse de rejeter
    # une valeur qu'il ne sait pas vérifier tout seul (ici : des nombres
    # inférieurs à 1).
    # -----------------------------------------------------------------
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", required=True, help="The database to measure (same name on both sides)")
    parser.add_argument("--max-depth", type=int, default=6, help="Deepest traversal, in hops (default: 6)")
    parser.add_argument("--repeats", type=int, default=5, help="Timed runs per depth and side (default: 5)")
    parser.add_argument("--timeout", type=int, default=60, help="Seconds before a run is stopped (default: 60)")
    args = parser.parse_args()
    if args.max_depth < 1 or args.repeats < 1 or args.timeout < 1:
        parser.error("--max-depth, --repeats and --timeout must be at least 1")

    # -----------------------------------------------------------------
    # UN DOSSIER DE SORTIE PAR DATE ET HEURE
    #
    # datetime.now().strftime("%Y-%m-%d_%H-%M-%S") formate l'heure
    # actuelle en texte : « %Y » année, « %m » mois, « %d » jour, « %H »
    # heure, « %M » minute, « %S » seconde -> par ex.
    # « 2026-11-18_14-05-31 ». (Pas de « : » car Windows ne l'autorise
    # pas dans les noms de fichiers.)
    #
    # Chaque mesure a son propre dossier, donc mesurer de nouveau la même
    # base n'écrase jamais un résultat antérieur. Comme le nom commence
    # par l'année, trier les noms de dossiers par ordre alphabétique les
    # trie aussi dans l'ordre chronologique — analyze.py s'appuie là-dessus
    # pour trouver le plus récent.
    #
    # mkdir(parents=True) SANS exist_ok=True : si le dossier existait
    # déjà, pour une raison ou une autre, c'est une erreur — volontairement,
    # pour ne jamais mélanger deux exécutions.
    # -----------------------------------------------------------------
    starts = read_starts(args.database)
    out_dir = choose_starts.RESULTS_DIR / args.database / datetime.now().strftime("%Y-%m-%d_%H-%M-%S")
    out_dir.mkdir(parents=True)

    # -----------------------------------------------------------------
    # Deux connexions dans UNE SEULE instruction `with`, séparées par une
    # virgule : les deux sont fermées à la fin, quoi qu'il arrive. Une
    # connexion PostgreSQL et un driver Neo4j sont réutilisés pour toutes
    # les exécutions — ouvrir une nouvelle connexion à chaque exécution
    # ajouterait son propre coût à chaque temps mesuré.
    #
    # json.dumps(info, indent=2) transforme le dictionnaire en texte JSON,
    # indenté de 2 espaces pour qu'il soit facile à lire ;
    # Path.write_text() écrit ce texte dans le fichier en une fois
    # (ouvrir + écrire + fermer).
    # -----------------------------------------------------------------
    with traversal.connect_postgres(args.database) as conn, traversal.connect_neo4j() as driver:
        info = conditions(conn, driver, args.database, args)
        (out_dir / "conditions.json").write_text(json.dumps(info, indent=2), encoding="utf-8")
        # f'...' avec des apostrophes SIMPLES, pour que le texte puisse
        # contenir des guillemets "doubles" autour du nom de la base. Deux
        # f-strings côte à côte sont collées en une seule (voir
        # conditions()). "\n" est un retour à la ligne.
        print(f'Measuring "{args.database}": {len(starts)} starting actors, depths 1-{args.max_depth}, '
              f"{args.repeats} timed runs each, time limit {args.timeout} s")
        print(f"Results: {out_dir}\n")

        # -------------------------------------------------------------
        # csv.DictWriter — écrire des lignes qui sont des DICTIONNAIRES
        # (un rappel ; vu pour la première fois dans
        # docs_french/choose_starts.py)
        #
        # csv.writer (docs_french/extract_csv.py) écrit des listes, où
        # l'ordre des valeurs doit correspondre à l'en-tête, à la main.
        # DictWriter prend fieldnames= (l'en-tête) puis des lignes sous
        # forme de dictionnaires : chaque valeur va dans la colonne du MÊME
        # NOM, quel que soit l'ordre du dictionnaire, et une clé absente
        # donne une cellule vide. C'est le jumeau en écriture de
        # csv.DictReader.
        #   writeheader()   écrit la ligne d'en-tête (les fieldnames)
        #   writerow(dict)  écrit une ligne
        #
        # La ligne `with open(...) as a, \` se termine par une barre
        # oblique inverse : elle FAIT CONTINUER l'instruction sur la ligne
        # suivante (sinon la ligne serait trop longue). Les deux fichiers
        # sont fermés à la fin du bloc.
        # -------------------------------------------------------------
        with open(out_dir / "runs.csv", "w", newline="", encoding="utf-8") as runs_file, \
             open(out_dir / "work.csv", "w", newline="", encoding="utf-8") as work_file:
            runs = csv.DictWriter(runs_file, fieldnames=RUN_FIELDS)
            work = csv.DictWriter(work_file, fieldnames=WORK_FIELDS)
            runs.writeheader()
            work.writeheader()
            # ---------------------------------------------------------
            # enumerate(starts, start=1) numérote les acteurs à partir de
            # 1 (et non de 0) pour l'affichage de la progression
            # « [3/20] ».
            #
            # flush() après chaque acteur — une mesure complète peut
            # prendre des HEURES. Python garde un moment en mémoire les
            # lignes écrites avant qu'elles n'atteignent vraiment le
            # fichier. flush() les pousse dans le fichier tout de suite,
            # donc si quelque chose tourne mal à l'acteur 15 (un plantage,
            # Ctrl+C, le portable qui se met en veille), les résultats des
            # acteurs 1 à 14 sont en sécurité sur le disque et peuvent
            # être analysés.
            # ---------------------------------------------------------
            for number, actor in enumerate(starts, start=1):
                print(f"[{number}/{len(starts)}] {actor['group']} #{actor['rank']}: {actor['login']} "
                      f"(reaches {actor['reached']} in one hop)")
                measure_actor(actor, conn, driver, args.database, args, runs, work)
                runs_file.flush()
                work_file.flush()

    print(f"\nDone. Results in {out_dir}")


# ---------------------------------------------------------------------
# La garde __name__ (voir docs_french/download_gharchive.py), avec un
# ajout : main() tourne à l'intérieur d'un try / except
# FileNotFoundError. Le seul « fichier introuvable » attendu est un
# starts.csv manquant (read_starts()) ; son message dit déjà quoi faire,
# il est donc affiché seul, sans la longue trace d'erreur de Python, et
# sys.exit(1) signale l'échec — ce qui fait s'arrêter research.sh à cet
# endroit (set -e, voir docs_french/research.sh).
# ---------------------------------------------------------------------
if __name__ == "__main__":
    try:
        main()
    except FileNotFoundError as error:
        print(error)
        sys.exit(1)
