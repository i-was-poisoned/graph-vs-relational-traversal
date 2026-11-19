########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de
# scripts/choose_starts.py. Il n'est PAS destiné à être exécuté — il se
# trouve dans docs_french/ car son but est d'enseigner, pas de
# s'exécuter. Le script réel et « propre » (sans tous ces commentaires)
# est scripts/choose_starts.py.
#
# Lisez d'abord ces copies annotées ; ce qu'elles expliquent n'est PAS
# répété ici :
#   - download_gharchive.py   argparse, Path, main() et la garde __name__,
#                             lever une erreur
#   - extract_csv.py          sorted(...)
#   - load_neo4j.py           database_=
#   - summarize_data.py       les compréhensions de dictionnaire, les
#                             largeurs de colonnes dans les f-strings
#   - pipeline.py             RawDescriptionHelpFormatter
#   - drop_databases.py       neo4j_databases() / postgres_databases()
#   - traversal.py            SQL_ONE_HOP / CYPHER_ONE_HOP (ce que
#                             signifient « reached » et « repos »),
#                             connect_postgres/neo4j
#
# Ce qui est NOUVEAU ici :
#   - POURQUOI les acteurs de départ sont CHOISIS PAR UNE RÈGLE, et
#     quelle est cette règle ;
#   - trier avec une fonction CLÉ qui renvoie un TUPLE, et des nombres
#     négatifs pour trier certaines parties du plus grand au plus petit ;
#   - statistics.median() et « le plus proche de la médiane » ;
#   - lambda (une fonction d'une ligne, sans nom) ;
#   - faire le choix dans les DEUX bases et refuser de continuer si elles
#     ne sont pas d'accord (choose_in_both(), raise RuntimeError) ;
#   - les options action="store_true" et parser.error().
#
# Ce fichier est désormais surtout une BIBLIOTHÈQUE : measure.py
# l'importe et appelle choose_in_both() quand il a besoin d'acteurs de
# départ. Les acteurs choisis ne sont plus enregistrés dans un fichier à
# part : ils sont écrits dans chaque ligne du fichier CSV de la mesure,
# dans results/, et une mesure ultérieure de la même base les reprend
# dans son CSV le plus récent (voir previous_starts dans
# docs_french/measure.py).
#
# POURQUOI CHOISIR LES ACTEURS DE DÉPART ? La traversée mesurée (REACH
# dans traversal.py) part d'UN acteur. L'identité de cet acteur change
# tout : depuis un acteur très connecté, la profondeur 2 peut déjà
# atteindre une grande partie du graphe ; depuis un acteur discret,
# presque rien. Si on choisissait les acteurs à la main (« celui-ci a
# l'air intéressant »), les résultats pourraient être faussés — même sans
# le vouloir. Le choix est donc fait par une RÈGLE fixe, écrite ici, qui
# donne la même réponse à chaque fois :
#   - 10 acteurs « top » : les plus connectés (le cas le plus difficile) ;
#   - 10 acteurs « median » : des acteurs typiques (le cas habituel).
#
# Comment il est lancé seul (research.sh le fait pour construire son
# menu des bases) :
#     ./run.sh scripts/choose_starts.py --list-databases
########################################################################

"""Choose the starting actors for the measurements, the same on both sides.

For every actor it counts, in PostgreSQL and in Neo4j:
    reached = distinct other actors that share at least one repo with it (one hop)
    repos   = distinct repos it touched
and then picks two groups of 10:

    top     the 10 that reach the most actors in one hop
    median  the 10 whose "reached" is closest to the median, among the actors
            that reach at least one other actor (those that reach nobody are
            only a single JOIN, and tell nothing about traversals)

Ties are broken by more repos, then by the smaller id, so the choice never
changes. Both databases must give exactly the same 20 actors (with the same
numbers); otherwise the measurement doesn't start.

measure.py uses choose_in_both(). The chosen actors are saved as part of every
line of the measurement's CSV in results/, so a measurement repeated another
day reuses them.

Usage (only to list the databases that can be measured; research.sh uses it):
    ./run.sh scripts/choose_starts.py --list-databases
"""

# ---------------------------------------------------------------------
# NOUVEAU : `import statistics` — un module de la bibliothèque standard
# avec les indicateurs statistiques habituels (moyenne, médiane, ...).
# Seule statistics.median() est utilisée.
#
# `import drop_databases` / `import traversal` : nos propres scripts,
# utilisés comme modules. drop_databases fournit les fonctions qui listent
# les bases du projet ; traversal fournit les requêtes et les connexions.
# (csv, sys et Path ne sont plus nécessaires : rien n'est enregistré dans
# un fichier ici, et un désaccord est LEVÉ comme une erreur pour
# measure.py.)
# ---------------------------------------------------------------------
import argparse
import statistics
import time

import drop_databases
import traversal

# GROUP_SIZE = 10 : la taille de chaque groupe (top, median).
GROUP_SIZE = 10


# ---------------------------------------------------------------------
# def ranking_key(actor) -> tuple:  — COMMENT TRIER, ET POURQUOI UN TUPLE
#
# Chaque acteur est un dictionnaire comme
#     {"actor_id": 19, "login": "brynary", "reached": 340, "repos": 12}
# sorted(..., key=ranking_key) appelle ranking_key sur chaque acteur et
# trie les acteurs selon ce qu'elle renvoie.
#
# Python compare les TUPLES élément par élément, de gauche à droite,
# comme les mots d'un dictionnaire : les premiers éléments décident ;
# c'est seulement s'ils sont ÉGAUX que les deuxièmes éléments décident ;
# et ainsi de suite. Un seul tuple exprime donc « trier par ceci, puis
# par cela, puis par cela ».
#
# sorted() trie toujours du PETIT au GRAND. Pour obtenir « le PLUS
# atteint en premier », l'astuce est un signe MOINS : -340 est plus petit
# que -12, donc l'acteur qui en atteint 340 passe avant celui qui en
# atteint 12. Même chose pour repos. L'id n'est PAS rendu négatif : c'est
# le PLUS PETIT id qui l'emporte.
#
# Exemple, trois acteurs :
#     A : reached 50, repos 3, id 7   -> clé (-50, -3, 7)
#     B : reached 50, repos 5, id 9   -> clé (-50, -5, 9)
#     C : reached 80, repos 1, id 4   -> clé (-80, -1, 4)
#   ordre trié : C (-80 est le plus petit), puis B (égalité sur -50, et
#   -5 < -3), puis A.
#
# POURQUOI CES DÉPARTAGES ? Beaucoup d'acteurs ont le même compte
# « reached ». Sans départage, savoir lesquels d'entre eux entrent dans
# le top 10 pourrait dépendre de l'ordre dans lequel la base a renvoyé
# les lignes — et PostgreSQL et Neo4j les renvoient dans des ordres
# différents. Avec le départage, l'ordre est TOTAL : deux acteurs
# différents ne peuvent jamais avoir la même clé (les id sont uniques),
# donc le résultat est toujours le même. « Plus de repos » vient en
# premier parce que c'est un nombre qui a du sens (plus de points de
# départ pour le parcours) ; l'id est la règle finale, arbitraire mais
# fixe. (Un départage naturel serait « plus d'événements », mais le
# nombre d'événements n'est pas stocké dans les bases — seules les
# paires acteur-repo le sont.)
# ---------------------------------------------------------------------
def ranking_key(actor: dict) -> tuple:
    # Most reached first; ties: more repos first; then the smaller id.
    return (-actor["reached"], -actor["repos"], actor["actor_id"])


# Le groupe top : tout trier selon la clé et garder les `size` premiers.
# [:size] est une tranche (slice) : les éléments 0 à size-1.
# `size: int = GROUP_SIZE` est une valeur par défaut, pour que les tests
# puissent demander un groupe plus petit.
def pick_top(actors: list[dict], size: int = GROUP_SIZE) -> list[dict]:
    return sorted(actors, key=ranking_key)[:size]


# ---------------------------------------------------------------------
# def pick_median(actors, exclude, size) -> list[dict]:  — LES ACTEURS TYPIQUES
#
# 1. reaching = seulement les acteurs avec reached >= 1. Un acteur qui
#    n'atteint personne donne une traversée qui s'arrête immédiatement
#    (une seule recherche) : elle ne mesurerait rien d'intéressant. (En
#    pratique, les requêtes ONE_HOP écartent déjà ces acteurs ; cette
#    ligne rend la règle explicite et sûre quelle que soit l'entrée.)
#    S'il ne reste personne (une base vide), il n'y a pas de médiane :
#    on renvoie [].
#
# 2. statistics.median(...) : trier les nombres et prendre celui du
#    MILIEU (avec un nombre pair de valeurs, la moyenne des deux du
#    milieu, donc cela peut valoir par ex. 3.5). Pourquoi la médiane et
#    pas la moyenne ? Les données sont très ASYMÉTRIQUES : la plupart des
#    acteurs en atteignent une poignée d'autres, quelques bots et projets
#    populaires en atteignent des milliers. Ces quelques-uns tirent la
#    moyenne très vers le haut, si bien que « la moyenne » ne décrirait
#    personne ; la médiane, c'est l'acteur au milieu de la file — un
#    acteur vraiment typique.
#
# 3. candidates = tous ceux de `reaching` SAUF les acteurs de `exclude`
#    (le groupe top). Sur une petite base, les deux groupes pourraient se
#    chevaucher ; un acteur mesuré deux fois sous deux étiquettes
#    fausserait les deux groupes. `exclude` est un ensemble, donc
#    `not in exclude` est instantané.
#
# 4. La clé de tri, avec une LAMBDA :
#        lambda a: (abs(a["reached"] - median),) + ranking_key(a)
#    `lambda a: <expression>` est une toute petite fonction sans nom :
#    elle prend a et renvoie l'expression. Pratique quand la fonction ne
#    sert qu'une fois, ici même. Ce qu'elle renvoie :
#      abs(...)            la DISTANCE à la médiane (abs = valeur
#                          absolue : 3 au-dessus et 3 en dessous comptent
#                          tous les deux pour 3).
#      (x,)                un tuple à UN élément (c'est la virgule qui en
#                          fait un tuple).
#      + ranking_key(a)    `+` entre des tuples les COLLE bout à bout :
#                          (2,) + (-5, -3, 7) -> (2, -5, -3, 7).
#    Donc : le plus proche de la médiane d'abord ; à distance égale, les
#    mêmes départages que pour le groupe top (plus de reached, plus de
#    repos, plus petit id). Puis [:size] garde les 10 plus proches.
# ---------------------------------------------------------------------
def pick_median(actors: list[dict], exclude: set[int], size: int = GROUP_SIZE) -> list[dict]:
    # Only actors that reach someone; the median of their "reached"; then the closest ones,
    # with the same tie-break. Actors already in the top group are left out.
    reaching = [a for a in actors if a["reached"] >= 1]
    if not reaching:
        return []
    median = statistics.median(a["reached"] for a in reaching)
    candidates = [a for a in reaching if a["actor_id"] not in exclude]
    return sorted(candidates, key=lambda a: (abs(a["reached"] - median),) + ranking_key(a))[:size]


# ---------------------------------------------------------------------
# def choose(actors) -> list[dict]:  — les deux groupes, sous forme d'une liste de lignes
#
# exclude={a["actor_id"] for a in top} : une COMPRÉHENSION D'ENSEMBLE
# (accolades, sans clé: valeur) — l'ensemble des id du groupe top.
#
# La double boucle construit une ligne par acteur choisi :
#   for group, members in (("top", top), ("median", median)):
#       parcourt deux paires (nom, liste), pour que le même code traite
#       les deux.
#   for rank, actor in enumerate(members, start=1):
#       enumerate (peek_data.py) avec start=1 : rangs 1..10, et non 0..9.
#
# La ligne elle-même :
#   {"group": group, "rank": rank, **{k: actor[k] for k in (...)}}
#   {k: actor[k] for k in (...)} est une compréhension de dictionnaire
#   (summarize_data.py) qui recopie ces quatre clés depuis l'acteur. `**`
#   À L'INTÉRIEUR d'un dictionnaire littéral dépaquette les clés et
#   valeurs de ce dictionnaire dans le nouveau (le même `**` que pour les
#   arguments nommés dans check_connections.py). Résultat, par ex. :
#   {"group": "top", "rank": 1, "actor_id": 19, "login": "...",
#    "reached": 340, "repos": 12}. measure.py les recopie dans les
#   colonnes start_... du CSV de résultats (start_group, start_rank,
#   start_actor_id, start_login, start_reach_1_hop).
# ---------------------------------------------------------------------
def choose(actors: list[dict]) -> list[dict]:
    top = pick_top(actors)
    median = pick_median(actors, exclude={a["actor_id"] for a in top})
    rows = []
    for group, members in (("top", top), ("median", median)):
        for rank, actor in enumerate(members, start=1):
            rows.append({"group": group, "rank": rank, **{k: actor[k] for k in ("actor_id", "login", "reached", "repos")}})
    return rows


# ---------------------------------------------------------------------
# Obtenir les comptes de chaque base, sous la MÊME forme : une liste de
# dictionnaires avec les clés actor_id, login, reached, repos.
#
# postgres_actors : fetchall() donne des tuples dans l'ordre des colonnes
# du SELECT (actor_id, login, reached, repos), transformés en
# dictionnaires selon leur position.
#
# neo4j_actors : un record Neo4j connaît déjà les noms de ses colonnes
# (les noms après AS de CYPHER_ONE_HOP, choisis identiques à ceux du
# SQL), donc dict(r) donne directement le même dictionnaire.
#
# Les lignes reviennent dans un ordre QUELCONQUE des deux côtés — ce qui
# ne pose pas de problème, car choose() les trie selon un ordre total
# (voir ranking_key).
# ---------------------------------------------------------------------
def postgres_actors(database: str) -> list[dict]:
    with traversal.connect_postgres(database) as conn:
        rows = conn.execute(traversal.SQL_ONE_HOP).fetchall()
    return [{"actor_id": r[0], "login": r[1], "reached": r[2], "repos": r[3]} for r in rows]


def neo4j_actors(database: str) -> list[dict]:
    with traversal.connect_neo4j() as driver:
        records = driver.execute_query(traversal.CYPHER_ONE_HOP, database_=database).records
    return [dict(r) for r in records]


# ---------------------------------------------------------------------
# def choose_in_both(database) -> list[dict]:  — LE MÊME CHOIX, FAIT DEUX FOIS
#
# C'est ce que measure.py appelle. Le choix est fait DEUX FOIS, de façon
# indépendante : une fois à partir des comptes de PostgreSQL, une fois à
# partir de ceux de Neo4j. Chacun prend un moment sur une grosse base,
# donc le temps est affiché (perf_counter : load_postgres.py ; :.1f = une
# décimale). La première f-string utilise des guillemets simples '...'
# pour pouvoir contenir des guillemets "doubles" ; deux chaînes écrites
# l'une à côté de l'autre sont collées en une seule.
#
# LES DEUX BASES DOIVENT ÊTRE D'ACCORD
#
# in_postgres != in_neo4j compare les deux LISTES de dictionnaires
# élément par élément : même longueur, même ordre, et chaque
# dictionnaire égal (mêmes clés, mêmes valeurs). La moindre différence —
# un autre acteur, ou le même acteur avec un autre compte — signifie que
# les deux bases ne contiennent pas les mêmes données, et comparer leurs
# vitesses n'aurait aucun sens. Donc rien n'est mesuré.
#
# differences : une compréhension de liste qui ne garde que les paires
# qui diffèrent (zip : test_pipeline.py), chacune écrite sur deux lignes,
# celle de PostgreSQL au-dessus de celle de Neo4j ("\n" est un retour à
# la ligne à l'intérieur du texte).
#
# raise RuntimeError(...) — au lieu d'afficher un message et d'appeler
# elle-même sys.exit(1), la fonction LÈVE une erreur (raise :
# download_gharchive.py). RuntimeError est l'erreur générale de Python
# pour « quelque chose s'est mal passé pendant l'exécution ». Une
# fonction de bibliothèque ne devrait pas arrêter tout le programme de
# son propre chef : elle signale le problème, et c'est l'appelant qui
# décide. measure.py attrape RuntimeError tout en bas de son code,
# affiche le message (les différences y sont ajoutées avec "\n".join) et
# se termine avec 1.
#
# Elles sont d'accord : renvoyer la liste de PostgreSQL (de toute façon
# égale à celle de Neo4j).
# ---------------------------------------------------------------------
def choose_in_both(database: str) -> list[dict]:
    # The same choice made in each database; they must agree, or nothing is measured.
    print(f'Choosing the starting actors: counting, for every actor of "{database}", '
          "how many actors it reaches in one hop ...")
    begin = time.perf_counter()
    in_postgres = choose(postgres_actors(database))
    print(f"  PostgreSQL done in {time.perf_counter() - begin:.1f} s.")
    begin = time.perf_counter()
    in_neo4j = choose(neo4j_actors(database))
    print(f"  Neo4j done in {time.perf_counter() - begin:.1f} s.")
    if in_postgres != in_neo4j:
        differences = [f"  PostgreSQL {p}\n  Neo4j      {n}" for p, n in zip(in_postgres, in_neo4j) if p != n]
        raise RuntimeError("The two databases DON'T choose the same actors; nothing was measured.\n"
                           + "\n".join(differences))
    return in_postgres


# ---------------------------------------------------------------------
# def existing_databases() -> list[str]:
#
# Une base ne peut être mesurée que si elle existe sur les DEUX serveurs
# (une construction a pu échouer à mi-chemin). Ceci garde les noms
# PostgreSQL (déjà filtrés et triés par drop_databases) qui sont AUSSI
# dans l'ensemble Neo4j : une INTERSECTION, écrite sous forme de
# compréhension de liste pour conserver l'ordre trié. Utilisé par
# --list-databases (research.sh lit cette liste).
# ---------------------------------------------------------------------
def existing_databases() -> list[str]:
    # Project databases that exist on BOTH servers (the only ones that can be measured).
    with traversal.connect_neo4j() as driver:
        in_neo4j = set(drop_databases.neo4j_databases(driver))
    return [name for name in drop_databases.postgres_databases() if name in in_neo4j]


def main() -> None:
    # -----------------------------------------------------------------
    # Les options de la ligne de commande : il n'en reste qu'une.
    #   --list-databases   action="store_true" crée un INTERRUPTEUR
    #                      MARCHE/ARRÊT qui ne prend pas de valeur : False
    #                      s'il est absent, True s'il est écrit. (argparse
    #                      transforme le tiret en tiret bas :
    #                      args.list_databases.)
    # Le texte d'aide est réparti sur deux lignes à l'intérieur des
    # parenthèses, ce que Python permet.
    #
    # Sans --list-databases, il n'y a rien à faire (choisir les acteurs
    # est désormais le travail de measure.py), donc parser.error("...")
    # affiche la ligne d'utilisation et le message, et arrête le
    # programme avec le code de sortie 2 — comme les propres erreurs
    # d'argparse.
    #
    # Avec : afficher les noms, un par ligne ("\n".join). research.sh lit
    # cette sortie pour construire son menu (voir docs_french/research.sh).
    # -----------------------------------------------------------------
    parser = argparse.ArgumentParser(description=__doc__, formatter_class=argparse.RawDescriptionHelpFormatter)
    parser.add_argument("--list-databases", action="store_true",
                        help="Print the project databases that exist on both servers, one per line")
    args = parser.parse_args()
    if not args.list_databases:
        parser.error("the only option is --list-databases (measure.py chooses the actors)")
    print("\n".join(existing_databases()))


# La garde __name__ : download_gharchive.py.
if __name__ == "__main__":
    main()
