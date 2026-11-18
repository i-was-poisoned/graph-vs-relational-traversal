########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/analyze.py.
# Il n'est PAS destiné à être exécuté — il se trouve dans docs_french/ car
# son but est d'enseigner, pas de s'exécuter. Le script réel et « propre »
# (sans tous ces commentaires) est scripts/analyze.py.
#
# Lisez d'abord ces copies annotées ; ce qu'elles expliquent n'est PAS
# répété ici :
#   - download_gharchive.py   argparse, Path, main() et la garde __name__
#   - extract_csv.py          open(..., newline=""), sorted(...), les
#                             ensembles (sets)
#   - load_neo4j.py           csv.DictReader
#   - summarize_data.py       collections.defaultdict (l'idée de base)
#   - pipeline.py             RawDescriptionHelpFormatter
#   - measure.py              ce que contient runs.csv (l'exécution 0, les
#                             exécutions chronométrées, le statut, la
#                             charge de la machine), csv.DictWriter,
#                             lambda, les compréhensions de dictionnaire,
#                             `**` à l'intérieur d'un dictionnaire, et
#                             l'organisation de results/ en un dossier par
#                             date et heure
#
# Ce qui est NOUVEAU ici — transformer une pile d'exécutions chronométrées
# en quelques chiffres dignes de confiance :
#   - la MÉDIANE (et pourquoi pas la moyenne), le minimum et le maximum ;
#   - ignorer l'exécution 0 ;
#   - signaler les exécutions BRUITÉES (écart supérieur à 3x, ou
#     ordinateur au-dessus de 80 % de CPU) ;
#   - regrouper des lignes par une clé tuple avec defaultdict(list) ;
#   - le RAPPORT PostgreSQL / Neo4j (au-dessus de 1 : Neo4j plus rapide) ;
#   - results/all_databases.csv, pour comparer côte à côte des VOLUMES de
#     données.
#
# Comment il est censé être lancé — normalement comme dernière étape de
# research.sh :
#     ./research.sh --database gharchive-2026-08-27-12-6h
# ou seul, via run.sh :
#     ./run.sh scripts/analyze.py --database gharchive-2026-08-27-12-6h
#     ./run.sh scripts/analyze.py --all
# (Il n'a besoin d'aucune connexion à une base de données : il ne lit que
# des fichiers CSV.)
########################################################################

"""Summarise the measurements made by measure.py.

For one database, it reads its latest measurement (results/<database>/<date-time>/)
and writes, in that same folder:

    per_actor.csv   for every actor, depth and side: median, minimum and maximum
                    time of the timed runs, how many finished, timed out or
                    failed, the answer, and a warning if the runs were noisy
    summary.csv     the same per group (top / median) and depth: the median over
                    the actors, and how many times slower PostgreSQL was than
                    Neo4j (above 1: Neo4j faster; below 1: PostgreSQL faster)

It also rebuilds results/all_databases.csv: one line per database, group, depth
and side, from the latest measurement of every database, to compare volumes.

A run is "noisy" if its slowest timed run took more than NOISY_SPREAD times its
fastest, or if the computer was very busy (CPU above BUSY_CPU %) during it.

Usage:
    ./run.sh scripts/analyze.py --database gharchive-2026-08-27-12-6h
    ./run.sh scripts/analyze.py --all
"""

# ---------------------------------------------------------------------
# statistics — un module de la bibliothèque standard avec les indicateurs
# de synthèse habituels (moyenne, médiane, écart-type...). Seule
# statistics.median() est utilisée ici.
#
# defaultdict — voir docs_french/summarize_data.py. Ici, il est utilisé
# sous la forme defaultdict(list) : un dictionnaire où une clé absente
# commence par une LISTE VIDE, donc `grouped[key].append(x)` fonctionne
# même la première fois qu'une clé apparaît.
#
# Pas de psycopg, pas de neo4j : ce script ne lit que les fichiers CSV
# qu'a écrits measure.py.
# ---------------------------------------------------------------------
import argparse
import csv
import statistics
from collections import defaultdict
from pathlib import Path

import choose_starts

# ---------------------------------------------------------------------
# Les deux seuils pour qualifier une mesure de « bruitée » (peu fiable) :
#
#   NOISY_SPREAD = 3.0   l'exécution chronométrée la plus lente a pris
#                        plus de 3 fois le temps de la plus rapide. La
#                        même requête sur les mêmes données devrait
#                        prendre à peu près le même temps à chaque fois ;
#                        un écart de 3x signifie que quelque chose d'autre
#                        s'en est mêlé.
#   BUSY_CPU = 80.0      le CPU de l'ordinateur dépassait 80 % juste avant
#                        une exécution (machine_cpu_percent, venant de
#                        measure.py) : d'autres programmes se disputaient
#                        le processeur.
#
# Une ligne bruitée est quand même gardée et résumée — elle est seulement
# SIGNALÉE, pour que vous sachiez quels chiffres traiter avec prudence (ou
# mesurer de nouveau).
# ---------------------------------------------------------------------
NOISY_SPREAD = 3.0
BUSY_CPU = 80.0
SYSTEMS = ("postgresql", "neo4j")


# ---------------------------------------------------------------------
# def latest_measurement(database) — le dossier de résultats le plus
# récent
#
# folder.glob("*") liste tout ce qui se trouve dans results/<database>/.
# Seuls les dossiers qui contiennent un runs.csv sont des mesures
# (starts.csv se trouve aussi là, et n'en est pas une).
#
# sorted(...) — les noms de dossiers sont des dates comme
# 2026-11-18_14-05-31, donc l'ordre alphabétique EST l'ordre
# chronologique ; measurements[-1] est la plus récente.
#
# `... if folder.exists() else []` — si la base n'a jamais été mesurée,
# le dossier peut ne pas exister du tout : on utilise alors une liste
# vide au lieu d'échouer. Dans les deux cas, une liste vide donne un
# message FileNotFoundError clair.
# \" à l'intérieur d'une chaîne "..." est un vrai caractère guillemet
# double.
# ---------------------------------------------------------------------
def latest_measurement(database: str) -> Path:
    folder = choose_starts.RESULTS_DIR / database
    measurements = sorted(p for p in folder.glob("*") if (p / "runs.csv").exists()) if folder.exists() else []
    if not measurements:
        raise FileNotFoundError(f"No measurement of \"{database}\" yet: run measure.py --database {database}")
    return measurements[-1]


# Toutes les lignes de runs.csv, sous forme de liste de dictionnaires (les
# valeurs sont du TEXTE).
def read_runs(folder: Path) -> list[dict]:
    with open(folder / "runs.csv", encoding="utf-8") as f:
        return list(csv.DictReader(f))


# ---------------------------------------------------------------------
# def summarise_actor(runs) — UN acteur, UNE profondeur, UN côté -> une
# ligne
#
# `runs` contient les lignes de runs.csv pour cette combinaison :
# l'exécution 0 plus les exécutions chronométrées 1..5. Rappelez-vous que
# chaque valeur est du texte, d'où int(...) et float(...).
# ---------------------------------------------------------------------
def summarise_actor(runs: list[dict]) -> dict:
    # -----------------------------------------------------------------
    # timed — seulement les exécutions 1, 2, 3... : l'exécution 0 est
    # IGNORÉE pour les temps. Elle inclut un travail unique (préparer le
    # plan de requête — environ 5 s pour la première requête d'une forme
    # nouvelle dans Neo4j — et charger les données en mémoire), elle
    # décrirait donc « la première fois », pas le parcours. Voir
    # docs_french/measure.py, étape 1.
    #
    # ok — les temps (sous forme de nombres) des exécutions chronométrées
    # qui ont FINI. Une exécution qui a dépassé le délai a aussi un
    # « seconds » (le temps jusqu'à son arrêt), mais ce n'est pas un vrai
    # temps et il ne doit pas être mélangé aux autres.
    # -----------------------------------------------------------------
    # runs: the lines of ONE actor, depth and side. Run 0 is the first run: not a result.
    timed = [r for r in runs if int(r["run"]) >= 1]
    ok = [float(r["seconds"]) for r in timed if r["status"] == "ok"]
    # -----------------------------------------------------------------
    # statuses — les « ok » / « timeout » / « error » des exécutions
    # chronométrées, pour les compter plus bas. `A or B` donne A si A
    # n'est pas vide, sinon B : quand il n'y a AUCUNE exécution
    # chronométrée (le côté avait déjà manqué de temps à l'exécution 0,
    # donc measure.py a sauté les répétitions), on se rabat sur le statut
    # de l'exécution 0, pour que le timeout apparaisse quand même dans les
    # comptes.
    #
    # counts — un ENSEMBLE (set) des réponses données par les exécutions
    # qui ont fini. Un ensemble ne garde chaque valeur qu'une fois : si
    # chaque exécution a dit 1234, l'ensemble est {1234}. Plus d'une
    # valeur voudrait dire que la même requête a donné des réponses
    # différentes — un bug. (r["count"] != "" : une cellule vide est
    # ignorée.)
    #
    # busy — any(...) vaut True si AU MOINS UN élément vaut True. Pour
    # chaque exécution chronométrée : y a-t-il un chiffre de CPU
    # (`r[...] and` : une cellule vide est falsy, donc float("") n'est
    # jamais tenté) et dépasse-t-il BUSY_CPU ?
    #
    # spread — la plus lente / la plus rapide. N'a de sens qu'avec au
    # moins 2 exécutions finies, et sans diviser par 0 ; sinon None
    # (« pas d'écart dont on puisse parler »).
    # -----------------------------------------------------------------
    statuses = [r["status"] for r in timed] or [r["status"] for r in runs]
    counts = {int(r["count"]) for r in runs if r["status"] == "ok" and r["count"] != ""}
    busy = any(r["machine_cpu_percent"] and float(r["machine_cpu_percent"]) > BUSY_CPU for r in timed)
    spread = (max(ok) / min(ok)) if len(ok) >= 2 and min(ok) > 0 else None
    # -----------------------------------------------------------------
    # La ligne pour per_actor.csv.
    #
    # median_s — LA MÉDIANE, PAS LA MOYENNE. On trie les temps et on prend
    # celui du milieu (avec un nombre pair de valeurs, la moyenne des deux
    # du milieu). Pourquoi pas la moyenne ? Parce que les perturbations
    # d'un benchmark ne rendent jamais les exécutions que PLUS LENTES,
    # jamais plus rapides : une seule exécution touchée par une analyse
    # antivirus, par ex. 0,30, 0,31, 0,29, 0,30, 3,00 s, tire la moyenne
    # jusqu'à 0,84 s — un temps qu'aucune exécution n'a réellement pris —
    # alors que la médiane reste à 0,30 s. La médiane ignore quelques
    # valeurs aberrantes.
    #
    # min_s / max_s — l'exécution finie la plus rapide et la plus lente :
    # elles montrent à quel point les exécutions s'écartent autour de la
    # médiane.
    #
    # `... if ok else None` — sans aucune exécution finie, il n'y a aucun
    # temps ; None devient une cellule vide dans le CSV.
    #
    # statuses.count("ok") — list.count(x) compte combien d'éléments sont
    # égaux à x.
    #
    # count — next(iter(counts)) sort la valeur unique de l'ensemble (un
    # ensemble n'a pas de [0] : iter() le parcourt, next() prend le
    # premier élément). Seulement quand il y a exactement UNE réponse ;
    # sinon None, qu'analyse() signale par un avertissement.
    #
    # noisy — True si l'ordinateur était occupé OU si l'écart dépassait
    # 3x. bool(...) garantit que la valeur est exactement True/False.
    # -----------------------------------------------------------------
    return {
        "median_s": statistics.median(ok) if ok else None,
        "min_s": min(ok) if ok else None,
        "max_s": max(ok) if ok else None,
        "finished": statuses.count("ok"),
        "timeouts": statuses.count("timeout"),
        "errors": statuses.count("error"),
        "count": next(iter(counts)) if len(counts) == 1 else None,
        "noisy": bool(busy or (spread is not None and spread > NOISY_SPREAD)),
    }


# ---------------------------------------------------------------------
# def per_actor(runs) — REGROUPER les lignes, puis résumer chaque groupe
#
# grouped[(group, actor_id, depth, system)].append(r)
#   La clé est un TUPLE de quatre valeurs : un tuple peut servir de clé
#   de dictionnaire, donc toutes les lignes ayant le même acteur, la même
#   profondeur et le même côté finissent dans la même liste.
#   defaultdict(list) crée cette liste la première fois qu'une clé
#   apparaît. actor_id et depth sont convertis en int pour que le tri
#   place la profondeur 10 après 9 (en texte, "10" < "9").
#
# for (group, actor_id, depth, system), lines in sorted(grouped.items()):
#   .items() donne des paires (clé, valeur) ; le tuple de la clé est
#   DÉBALLÉ en quatre noms directement dans la ligne du for. sorted() les
#   range par groupe, puis par acteur, puis par profondeur, puis par
#   côté.
#
# {..., **summarise_actor(lines)} — les quatre colonnes d'identification,
# puis toutes les colonnes du résumé ajoutées à leur suite (`**` comme
# dans measure.py).
# ---------------------------------------------------------------------
def per_actor(runs: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in runs:
        grouped[(r["group"], int(r["actor_id"]), int(r["depth"]), r["system"])].append(r)
    rows = []
    for (group, actor_id, depth, system), lines in sorted(grouped.items()):
        rows.append({"group": group, "actor_id": actor_id, "depth": depth, "system": system, **summarise_actor(lines)})
    return rows


# ---------------------------------------------------------------------
# def summary(actor_rows) — DES ACTEURS AUX GROUPES
#
# Les 10 acteurs d'un groupe (top ou median) sont combinés en une ligne
# par groupe, profondeur et côté. Même technique de regroupement que
# per_actor(), avec cette fois une clé de trois valeurs (sans actor_id).
# ---------------------------------------------------------------------
def summary(actor_rows: list[dict]) -> list[dict]:
    grouped = defaultdict(list)
    for r in actor_rows:
        grouped[(r["group"], r["depth"], r["system"])].append(r)
    # medians retient la médiane de chaque groupe, pour que le rapport
    # puisse être calculé ensuite, une fois les deux côtés connus.
    medians = {}
    rows = []
    # -----------------------------------------------------------------
    # L'ordre de tri : « top » avant « median », puis par profondeur, puis
    # par côté.
    #
    # Le simple ordre alphabétique mettrait « median » avant « top ». La
    # fonction key construit, pour chaque paire (clé, valeur) kv :
    #     (kv[0][0] != "top",) + kv[0][1:]
    #   kv[0] est le tuple de la clé (group, depth, system) ; kv[0][0] le
    #   groupe. `kv[0][0] != "top"` vaut False pour top, True pour median,
    #   et False se trie avant True. `(x,)` — avec la virgule — est un
    #   tuple d'un seul élément, et `+` le colle à (depth, system). Donc
    #   top vient en premier et, à l'intérieur de chaque groupe, la
    #   profondeur 1, 2, 3...
    # -----------------------------------------------------------------
    for (group, depth, system), lines in sorted(grouped.items(), key=lambda kv: (kv[0][0] != "top",) + kv[0][1:]):
        # -------------------------------------------------------------
        # Le temps du groupe = la MÉDIANE DES MÉDIANES DES ACTEURS, pour
        # la même raison que plus haut : un acteur inhabituel n'entraîne
        # pas tout le groupe. Les acteurs sans exécution finie (median_s
        # vaut None) sont laissés hors du temps, mais toujours comptés
        # dans « actors » — comparez « actors » avec « actors_finished »
        # pour voir combien ont dépassé le délai.
        #
        # sum(r["noisy"] for r in lines) — True compte pour 1 et False
        # pour 0, donc additionner des valeurs True/False compte les
        # acteurs bruités.
        # -------------------------------------------------------------
        times = [r["median_s"] for r in lines if r["median_s"] is not None]
        medians[(group, depth, system)] = statistics.median(times) if times else None
        rows.append({"group": group, "depth": depth, "system": system, "actors": len(lines),
                     "actors_finished": len(times), "median_s": medians[(group, depth, system)],
                     "timeouts": sum(r["timeouts"] for r in lines), "errors": sum(r["errors"] for r in lines),
                     "noisy_actors": sum(r["noisy"] for r in lines)})
    # -----------------------------------------------------------------
    # LE RAPPORT — le chiffre phare de la recherche.
    #
    # postgresql_vs_neo4j = le temps médian de PostgreSQL / le temps
    # médian de Neo4j, pour le même groupe et la même profondeur. C'est
    # « combien de fois PostgreSQL a été plus lent » :
    #     4.0   PostgreSQL a mis 4 fois plus de temps -> Neo4j plus rapide
    #     1.0   pareil
    #     0.25  PostgreSQL a mis un quart du temps -> PostgreSQL plus
    #           rapide
    # Regarder ce chiffre franchir 1 à mesure que la profondeur (ou le
    # volume de données) augmente répond à la question de la recherche :
    # À PARTIR D'OÙ Neo4j commence-t-il à gagner ?
    #
    # La même valeur est écrite sur les lignes des deux côtés (postgresql
    # et neo4j). medians.get(...) donne None si un côté n'a pas de ligne ;
    # `if pg and neo` — seulement quand les deux ont un temps (None, ou un
    # 0 qui ferait échouer la division, donnent None). round(..., 3) :
    # trois décimales.
    # -----------------------------------------------------------------
    for row in rows:
        pg, neo = medians.get((row["group"], row["depth"], "postgresql")), medians.get((row["group"], row["depth"], "neo4j"))
        row["postgresql_vs_neo4j"] = round(pg / neo, 3) if pg and neo else None
    return rows


# ---------------------------------------------------------------------
# def write_csv(rows, path) — une liste de dictionnaires vers un fichier
# CSV
#
# csv.DictWriter (docs_french/measure.py) avec fieldnames=list(rows[0]) :
# list(un_dict) donne ses CLÉS, dans l'ordre où elles ont été ajoutées,
# donc l'en-tête est pris dans la première ligne elle-même. (Rien à
# écrire -> on sort tout de suite, puisqu'il n'y aurait pas de rows[0].)
# writer.writerows(rows) écrit toutes les lignes en un seul appel.
# ---------------------------------------------------------------------
def write_csv(rows: list[dict], path: Path) -> None:
    if not rows:
        return
    with open(path, "w", newline="", encoding="utf-8") as f:
        writer = csv.DictWriter(f, fieldnames=list(rows[0]))
        writer.writeheader()
        writer.writerows(rows)


# ---------------------------------------------------------------------
# def fmt(seconds) — un temps, lisible à l'écran
#
# Deux if/else sur une ligne, enchaînés :  A if cond1 else B if cond2 else C
#   None           -> "-"
#   moins de 1 s   -> en millisecondes : 0.0123 -> "12.3 ms"
#   sinon          -> en secondes :      12.3456 -> "12.35 s"
# Les spécifications de format à l'intérieur des { } : `,` ajoute un
# séparateur de milliers (1,234.5) et `.1f` / `.2f` signifient « 1 / 2
# décimales ».
# ---------------------------------------------------------------------
def fmt(seconds) -> str:
    return "-" if seconds is None else f"{seconds * 1000:,.1f} ms" if seconds < 1 else f"{seconds:,.2f} s"


# ---------------------------------------------------------------------
# def analyse(database) — tout le travail pour UNE base de données
#
# Trouver la mesure la plus récente, résumer par acteur, puis par groupe,
# écrire les deux fichiers CSV à côté de runs.csv, et afficher un
# tableau.
# ---------------------------------------------------------------------
def analyse(database: str) -> list[dict]:
    folder = latest_measurement(database)
    actor_rows = per_actor(read_runs(folder))
    summary_rows = summary(actor_rows)
    write_csv(actor_rows, folder / "per_actor.csv")
    write_csv(summary_rows, folder / "summary.csv")

    # -----------------------------------------------------------------
    # Le tableau à l'écran : une ligne par groupe et profondeur, les deux
    # côtés l'un à côté de l'autre. Largeurs de colonnes : `:<7` complète
    # à 7 caractères, aligné à gauche ; `:>12` complète à 12, aligné à
    # droite (les nombres s'alignent sur la droite).
    #
    # by_key — les lignes du résumé dans un dictionnaire dont la clé est
    # (group, depth, system), pour prendre la ligne PostgreSQL et la ligne
    # Neo4j du même groupe et de la même profondeur.
    # {(..., ...) for r in summary_rows} est une compréhension d'ENSEMBLE :
    # chaque (group, depth) une seule fois. Trié avec « top » en premier,
    # comme dans summary(). .get(..., {}) donne un dictionnaire vide si un
    # côté manque, donc pg.get() / neo.get() plus bas fonctionnent quand
    # même (et donnent None).
    # -----------------------------------------------------------------
    print(f'"{database}" (measurement {folder.name})')
    print(f"  {'group':<7} {'depth':>5}  {'PostgreSQL':>12}  {'Neo4j':>12}  {'PG / Neo4j':>10}  notes")
    by_key = {(r["group"], r["depth"], r["system"]): r for r in summary_rows}
    for group, depth in sorted({(r["group"], r["depth"]) for r in summary_rows}, key=lambda k: (k[0] != "top", k[1])):
        pg, neo = by_key.get((group, depth, "postgresql"), {}), by_key.get((group, depth, "neo4j"), {})
        # La colonne « notes » : les timeouts et les acteurs bruités, par
        # côté, seulement s'il y en a (0 est falsy, donc
        # `if r.get(...)` le saute). `notes += [...]` ajoute les éléments
        # de la seconde liste à la première.
        notes = [f"{s}: {r['timeouts']} timeouts" for s, r in (("PG", pg), ("Neo4j", neo)) if r.get("timeouts")]
        notes += [f"{s}: {r['noisy_actors']} noisy" for s, r in (("PG", pg), ("Neo4j", neo)) if r.get("noisy_actors")]
        ratio = pg.get("postgresql_vs_neo4j")
        # Une f-string À L'INTÉRIEUR d'une f-string : le rapport est
        # d'abord formaté, par ex. « 4.00x », puis ce texte est aligné à
        # droite sur 10 caractères. '; '.join(notes) met les notes sur une
        # ligne, séparées par « ; ».
        print(f"  {group:<7} {depth:>5}  {fmt(pg.get('median_s')):>12}  {fmt(neo.get('median_s')):>12}  "
              f"{'-' if ratio is None else f'{ratio:,.2f}x':>10}  {'; '.join(notes)}")
    # -----------------------------------------------------------------
    # Un avertissement de sécurité : les lignes où des exécutions ont FINI
    # mais n'ont pas donné une seule et même réponse (count vaut None).
    # measure.py vérifie déjà que les deux côtés sont d'accord à
    # l'exécution 0 ; ceci repère une requête qui donnerait des réponses
    # différentes d'une exécution à l'autre. sum(1 for ...) compte les
    # lignes qui correspondent.
    # -----------------------------------------------------------------
    mismatches = sum(1 for r in actor_rows if r["count"] is None and r["finished"])
    if mismatches:
        print(f"  WARNING: {mismatches} actor/depth lines didn't give one single answer")
    print(f"  Written: {folder / 'per_actor.csv'} and {folder / 'summary.csv'}\n")
    # Les lignes du résumé, chacune précédée du nom de la base et du
    # dossier de mesure : les lignes qui vont dans all_databases.csv.
    return [{"database": database, "measurement": folder.name, **r} for r in summary_rows]


def main() -> None:
    # --database NOM : résumer une base. --all : toutes celles mesurées
    # jusqu'ici. action="store_true" fait de --all un interrupteur
    # marche/arrêt (True quand il est donné, False sinon), sans valeur
    # après lui.
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--database", help="Summarise the latest measurement of this database")
    parser.add_argument("--all", action="store_true", help="Summarise every measured database")
    args = parser.parse_args()

    # -----------------------------------------------------------------
    # measured — les noms de toutes les bases qui ont au moins une
    # mesure : les dossiers de results/ (p.is_dir()) contenant un
    # <date-heure>/runs.csv. any(p.glob("*/runs.csv")) vaut True si le
    # motif correspond à au moins un fichier.
    #
    # Avec --database, analyser celle-là ; sans aucune des deux options,
    # parser.error s'arrête avec un message (voir docs_french/measure.py).
    # -----------------------------------------------------------------
    root = choose_starts.RESULTS_DIR
    measured = sorted(p.name for p in root.glob("*") if p.is_dir() and any(p.glob("*/runs.csv"))) if root.exists() else []
    if args.database:
        analyse(args.database)
    elif not args.all:
        parser.error("give --database NAME or --all")

    # -----------------------------------------------------------------
    # results/all_databases.csv — COMPARER LES VOLUMES
    #
    # Chaque volume de données (6 heures, 1 jour, une semaine...) est sa
    # propre base de données (construite par build_hours.py) et est
    # mesuré séparément. Ce fichier met les lignes de résumé de TOUTES ces
    # bases dans un seul tableau, avec une colonne « database », pour que
    # vous puissiez suivre par ex. « groupe top, profondeur 3 » à mesure
    # que le volume augmente, et voir où le rapport franchit 1.
    #
    # Il est reconstruit à chaque fois, même après l'analyse d'une seule
    # base, pour qu'il reflète toujours la mesure la plus récente de
    # chacune.
    #
    # Le corps de la boucle est UNE SEULE instruction coupée sur trois
    # lignes par le `\` à la fin de la première :
    #     all_rows += (analyse(database)) if args.all else (les mêmes
    #                                         lignes, construites en silence)
    # Avec --all, analyse() affiche le tableau de chaque base et écrit ses
    # fichiers. Sinon, les mêmes lignes de résumé sont recalculées sans
    # bruit (pas d'affichage, pas de fichiers par base), uniquement pour
    # remplir all_databases.csv.
    # -----------------------------------------------------------------
    # Always refresh the comparison of all volumes measured so far.
    all_rows = []
    for database in measured:
        all_rows += analyse(database) if args.all else \
            [{"database": database, "measurement": latest_measurement(database).name, **r}
             for r in summary(per_actor(read_runs(latest_measurement(database))))]
    write_csv(all_rows, root / "all_databases.csv")
    if all_rows:
        print(f"Comparison of all {len(measured)} measured database(s): {root / 'all_databases.csv'}")


# La garde __name__ : voir docs_french/download_gharchive.py.
if __name__ == "__main__":
    main()
