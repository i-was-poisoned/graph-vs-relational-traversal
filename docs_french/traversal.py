########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/traversal.py.
# Il n'est PAS destiné à être exécuté — il se trouve dans docs_french/ car
# son but est d'enseigner, pas de s'exécuter. Le fichier réel et
# « propre » (sans tous ces commentaires) est scripts/traversal.py. (Le
# fichier réel ne s'exécute pas seul non plus : c'est un MODULE de
# requêtes partagées, importé par choose_starts.py et measure.py.)
#
# Ce fichier suppose que vous avez déjà lu les copies annotées
# précédentes :
#   check_connections.py   psycopg, le driver Neo4j, os.environ,
#                          try/except
#   load_postgres.py       les tables actor, repo, actor_repo, leurs
#                          index, time.perf_counter()
#   load_neo4j.py          les bases de Cypher (MATCH, motifs,
#                          $paramètres), database_=
#   test_integration.py    la traversée à 2 sauts écrite comme une
#                          AUTO-JOINTURE SQL et comme un motif Cypher
#   pipeline.py            sql.SQL / sql.Identifier, autocommit=True
#   profile_schema.py      la RÉCURSIVITÉ (une fonction qui s'appelle
#                          elle-même)
#   drop_databases.py      la copie la plus récente, même style
#
# Ce qui est NOUVEAU ici — c'est le CŒUR de la recherche :
#   - le nombre d'acteurs « à un saut » pour chaque acteur (utilisé pour
#     choisir les points de départ), en SQL (une auto-jointure + GROUP BY)
#     et en Cypher ;
#   - la traversée MESURÉE : « combien d'acteurs peut-on atteindre en au
#     plus N sauts ? », écrite comme une CTE RÉCURSIVE SQL (WITH
#     RECURSIVE) et en DEUX versions Cypher : « paths » (un MOTIF DE
#     CHEMIN QUANTIFIÉ ( ... ){1,N}) et « levels » (niveau par niveau
#     comme le SQL, avec CALL { ... }, UNWIND, collect() et des listes) ;
#   - sql_joins() / cypher_hops() : combien de jointures / de relations
#     représente une profondeur de chaque côté ;
#   - une LIMITE DE TEMPS sur chaque requête (statement_timeout /
#     Query(timeout=)) ;
#   - une @dataclass (Outcome) pour renvoyer un résultat dans un seul
#     objet bien rangé ;
#   - demander à chaque base COMBIEN DE TRAVAIL elle a fait : EXPLAIN
#     (ANALYZE, BUFFERS) dans PostgreSQL et PROFILE dans Neo4j, transformés
#     en chiffres comparables : les Mo de pages de 8 ko traitées, et les
#     Mo de mémoire utilisée.
#
# La question de recherche : à partir de quelle PROFONDEUR de traversée,
# et avec quelle quantité de DONNÉES, Neo4j (une base de données orientée
# graphe) commence-t-il à battre PostgreSQL (une base relationnelle) ? Ce
# fichier contient l'unique question posée aux deux, écrite une seule
# fois, pour que les deux scripts qui l'utilisent posent exactement la
# même chose.
#
# Comment le fichier réel est utilisé (jamais directement : measure.py
# l'importe, tout comme choose_starts.py, que measure.py appelle) :
#     ./run.sh scripts/measure.py --database <name> ...
########################################################################

"""The research queries, the same question asked to PostgreSQL (SQL) and to Neo4j (Cypher).

Used by choose_starts.py and measure.py; it isn't run by itself.

Two questions:

* ONE_HOP: for every actor, how many distinct OTHER actors share at least one
  repo with it ("reached in one hop"), and how many distinct repos it touched.
  This chooses the starting actors.

* REACH: from one starting actor, how many distinct other actors can be
  reached in at most N hops, one hop being actor -> repo -> actor. This is the
  traversal that is measured.

Both databases must give exactly the same numbers; measure.py checks it every time.
"""

# ---------------------------------------------------------------------
# os, time, psycopg, GraphDatabase, sql, load_neo4j : tous déjà vus.
#
# NOUVEAU :
#   from dataclasses import dataclass
#       un DÉCORATEUR qui écrit à votre place les parties fastidieuses
#       d'une petite classe (voir Outcome plus bas).
#   from neo4j import ... Query
#       une enveloppe autour d'une chaîne Cypher qui peut emporter des
#       OPTIONS avec elle ; ici, l'option est une limite de temps (voir
#       run_neo4j_reach()).
# ---------------------------------------------------------------------
import os
import time
from dataclasses import dataclass

import psycopg
from neo4j import GraphDatabase, Query
from psycopg import sql

import load_neo4j

# ---------- ONE_HOP: used to choose the starting actors ----------

# ---------------------------------------------------------------------
# SQL_ONE_HOP — pour CHAQUE acteur : combien d'autres il atteint en un
# saut (« reached »), et combien de repos il a touchés (« repos »).
#
# QU'EST-CE QU'UN SAUT ? acteur -> repo -> un autre acteur. Deux acteurs
# sont à un saut l'un de l'autre s'ils partagent au moins un repo. (Dans
# test_integration.py, ce même parcours s'appelait « 2 sauts » parce
# qu'on comptait chaque flèche ; dans la recherche, UN SAUT = un pas
# d'acteur à acteur = deux flèches.)
#
# WITH nom AS (...)  — une CTE (« Common Table Expression », expression
# de table commune) : un résultat temporaire nommé, qu'on peut ensuite
# utiliser comme une table dans le reste de la requête. Ici, il y en a
# deux, séparées par une virgule : reach et degree. C'est simplement une
# façon d'écrire une grosse requête en morceaux lisibles.
#
# reach — l'AUTO-JOINTURE (expliquée dans test_integration.py) :
#   actor_repo apparaît deux fois, sous les noms a1 (« l'acteur pour qui
#   on compte ») et a2 (« les autres »). `a2.repo_id = a1.repo_id`
#   associe chaque ligne de a1 à toutes les lignes du même repo ;
#   `a2.actor_id <> a1.actor_id` (<> signifie « différent de ») retire
#   l'acteur lui-même.
#   GROUP BY a1.actor_id produit UNE ligne de résultat par acteur ; le
#   comptage se fait à l'intérieur de chaque groupe.
#   count(DISTINCT a2.actor_id) : quelqu'un qui partage TROIS repos avec
#   a1 apparaît dans trois lignes jointes, mais doit être compté une
#   seule fois.
#
#   Petit exemple. actor_repo contient (1,R), (2,R), (2,S), (3,S) :
#     acteur 1 : partage R avec 2                   -> reached 1
#     acteur 2 : partage R avec 1, S avec 3         -> reached 2
#     acteur 3 : partage S avec 2                   -> reached 1
#
# degree — le nombre de repos de l'acteur (« degré » est le terme de la
#   théorie des graphes pour « combien d'arêtes touchent ce nœud »).
#   count(*) par acteur suffit : la clé primaire (actor_id, repo_id)
#   garantit que chaque paire n'apparaît qu'une fois.
#
# Le SELECT final met les morceaux côte à côte :
#   JOIN degree d USING (actor_id)   USING (col) = « joindre SUR la
#                                    colonne de ce nom dans les deux
#                                    tables ».
#   JOIN actor a ON a.id = ...       pour récupérer le login, à afficher.
#
# Remarque : un acteur qui ne partage aucun repo avec personne n'a pas de
# ligne dans `reach` (l'auto-jointure ne trouve rien pour lui), donc il
# n'apparaît tout simplement pas dans la réponse. La version Cypher se
# comporte de la même façon.
#
# Cette requête s'exécute sur TOUTE la table, donc elle est lourde sur
# les grosses bases — c'est pourquoi elle ne tourne qu'au moment où les
# acteurs de départ sont CHOISIS. Les acteurs choisis sont écrits dans
# chaque ligne du fichier CSV de la mesure, dans results/, et les mesures
# suivantes de la même base les reprennent dans le plus récent (voir
# previous_starts dans docs_french/measure.py).
# ---------------------------------------------------------------------
SQL_ONE_HOP = """
WITH reach AS (
    SELECT a1.actor_id, count(DISTINCT a2.actor_id) AS reached
    FROM actor_repo a1
    JOIN actor_repo a2 ON a2.repo_id = a1.repo_id AND a2.actor_id <> a1.actor_id
    GROUP BY a1.actor_id
), degree AS (
    SELECT actor_id, count(*) AS repos FROM actor_repo GROUP BY actor_id
)
SELECT r.actor_id, a.login, r.reached, d.repos
FROM reach r
JOIN degree d USING (actor_id)
JOIN actor a ON a.id = r.actor_id
"""

# ---------------------------------------------------------------------
# CYPHER_ONE_HOP — la même question en Cypher.
#
# MATCH (a:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
#   Le parcours à un saut DESSINÉ sous forme de motif (vu dans
#   test_integration.py) : a pointe vers un repo, et b pointe vers le même
#   repo. Sans point de départ fixé, Neo4j cherche ce motif pour CHAQUE
#   acteur a.
# WHERE a <> b       comme le « pas l'acteur lui-même » du SQL.
#
# WITH a, count(DISTINCT b) AS reached
#   En Cypher, WITH est un « tuyau » entre deux parties d'une requête :
#   seul ce qui est listé continue. Mettre un agrégat (count) à côté de
#   `a` REGROUPE par a — Cypher n'a pas de mot-clé GROUP BY : tout ce qui
#   n'est pas un agrégat sert de clé de regroupement. Donc : une ligne par
#   acteur, avec son compte.
#
# MATCH (a)-[:INTERACTED_WITH]->(r:Repo)
#   Deuxième étape, en repartant de chaque a : ses repos.
# RETURN a.id AS actor_id, a.login AS login, reached, count(r) AS repos
#   Là encore, un agrégat (count(r)) regroupe par tout le reste du
#   RETURN. count(r) compte des arêtes ; le chargeur a créé une arête par
#   paire acteur-repo, donc c'est le nombre de repos. Les noms après AS
#   sont les MÊMES que les noms de colonnes du SQL, pour que
#   choose_starts.py puisse comparer les deux réponses clé par clé.
# ---------------------------------------------------------------------
CYPHER_ONE_HOP = """
MATCH (a:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
WHERE a <> b
WITH a, count(DISTINCT b) AS reached
MATCH (a)-[:INTERACTED_WITH]->(r:Repo)
RETURN a.id AS actor_id, a.login AS login, reached, count(r) AS repos
"""

# ---------- REACH: the measured traversal ----------

# ---------------------------------------------------------------------
# SQL_REACH — une CTE RÉCURSIVE
#
# La question : en partant d'UN acteur, combien d'autres acteurs
# distincts peut-on atteindre en AU PLUS N sauts ? Avec de simples JOIN,
# il faudrait une paire de JOIN de plus par saut, donc une requête
# différente pour chaque profondeur. Une CTE RÉCURSIVE écrit « un saut de
# plus » UNE SEULE FOIS et laisse PostgreSQL le répéter.
#
# WITH RECURSIVE reach(actor_id, depth) AS ( <ancre> UNION <partie récursive> )
#   reach est une table que PostgreSQL construit pas à pas ; chaque ligne
#   est (un acteur trouvé, à quelle profondeur).
#
#   1. L'ANCRE (la partie avant UNION) s'exécute UNE SEULE FOIS et donne
#      la ligne de départ :
#          SELECT %(start)s::bigint, 0      -> (acteur de départ, profondeur 0)
#      %(start)s est un PARAMÈTRE NOMMÉ : psycopg le remplit à partir du
#      dictionnaire {"start": ..., "depth": ...} passé avec la requête, en
#      toute sécurité (sans coller de texte). ::bigint est une
#      CONVERSION de type (« traiter ceci comme un BIGINT »), pour que la
#      colonne de l'ancre ait le même type que actor_repo.actor_id.
#
#   2. LA PARTIE RÉCURSIVE (après UNION) fait référence à reach
#      ELLE-MÊME. Elle s'exécute uniquement sur les lignes produites par
#      l'étape PRÉCÉDENTE, et ses nouvelles lignes deviennent l'entrée de
#      l'étape suivante :
#          FROM reach r                                     les acteurs trouvés à l'étape précédente
#          JOIN actor_repo ar1 ON ar1.actor_id = r.actor_id leurs repos
#          JOIN actor_repo ar2 ON ar2.repo_id = ar1.repo_id tous ceux qui sont sur ces repos
#          SELECT ar2.actor_id, r.depth + 1                 = trouvés un saut plus loin
#      (Ces deux jointures sont exactement l'auto-jointure à un saut
#      vue plus haut ; les deux index construits par load_postgres.py —
#      actor_id en premier, et repo_id — servent les deux sens.)
#
#   3. Elle S'ARRÊTE quand une étape ne produit aucune nouvelle ligne.
#
#   Exemple, start = 1, avec (1,R), (2,R), (2,S), (3,S) et N = 2 :
#     ancre    -> (1, 0)
#     étape 1  -> (1, 1), (2, 1)              le repo R de 1 a les acteurs 1 et 2
#     étape 2  -> (1, 2), (2, 2), (3, 2)      depuis 1 et 2 : repos R, S
#     arrêt (profondeur 2 = N)
#   Compte final : acteurs distincts sauf 1 -> {2, 3} -> 2.
#
# POURQUOI UNION ET PAS UNION ALL ? UNION jette toute ligne qui est un
# DOUBLON exact d'une ligne déjà trouvée. Comme une ligne est (acteur,
# profondeur), un acteur atteint par 50 chemins différents à la
# profondeur 2 n'est gardé qu'UNE FOIS à la profondeur 2. Chaque niveau
# contient donc au plus une ligne par acteur — jamais une ligne par
# CHEMIN. C'est important : le nombre de chemins explose avec la
# profondeur (chaque repo populaire les multiplie), le nombre d'acteurs,
# lui, ne le peut pas.
# (Cela ne retire PAS de la profondeur 2 un acteur trouvé à la
# profondeur 1, car (2, 1) et (2, 2) sont des lignes différentes. C'est
# pourquoi le SELECT final utilise DISTINCT.)
#
# POURQUOI LA LIMITE DE PROFONDEUR (WHERE r.depth < %(depth)s) ? Deux
# raisons :
#   - c'est le N de la question (« en au plus N sauts ») ;
#   - sans elle, la requête ne se TERMINERAIT JAMAIS : chaque étape
#     ajoute depth + 1, donc chaque ligne est nouvelle (une profondeur
#     différente), et le graphe contient des cycles
#     (A -> repo -> B -> repo -> A...). C'est la limite qui l'arrête.
#
# La dernière ligne : count(DISTINCT actor_id) sur tous les niveaux, sans
# l'acteur de départ lui-même (<> %(start)s).
# ---------------------------------------------------------------------
# Level by level: each row is (actor, depth). UNION drops a row already found at that
# depth, so every level holds at most one row per actor, never one row per path.
SQL_REACH = """
WITH RECURSIVE reach(actor_id, depth) AS (
    SELECT %(start)s::bigint, 0
    UNION
    SELECT ar2.actor_id, r.depth + 1
    FROM reach r
    JOIN actor_repo ar1 ON ar1.actor_id = r.actor_id
    JOIN actor_repo ar2 ON ar2.repo_id  = ar1.repo_id
    WHERE r.depth < %(depth)s
)
SELECT count(DISTINCT actor_id) FROM reach WHERE actor_id <> %(start)s
"""

# ---------------------------------------------------------------------
# DEUX VERSIONS CYPHER DE LA MÊME QUESTION — POURQUOI ?
#
# Les premières mesures n'utilisaient que la version « paths » ci-dessous,
# et sur 24 heures de données elle a EXPLOSÉ à la profondeur 5-6 (elle a
# dépassé le temps imparti) alors que le SQL, non. Était-ce à cause de la
# BASE DE DONNÉES, ou à cause de la FAÇON dont la requête Cypher était
# ÉCRITE ? Pour départager les deux, la même question est aussi posée
# d'une seconde manière, « levels », qui suit la stratégie du SQL :
#   paths    la façon naturelle de Neo4j : décrire le parcours comme un
#            motif.
#   levels   la stratégie niveau par niveau du SQL, écrite en Cypher.
# Si « levels » reste rapide là où « paths » explose, le problème venait
# de la façon d'écrire la requête, pas de Neo4j lui-même. measure.py
# mesure les deux (ou une seule, avec --cypher) et écrit une ligne du CSV
# de résultats par version ; les deux doivent donner exactement le compte
# du SQL.
#
# CYPHER_VERSIONS = ("paths", "levels") : les deux noms, dans un tuple,
# utilisés par measure.py (les choix de --cypher) et vérifiés par
# cypher_reach().
# ---------------------------------------------------------------------
# Two ways of asking the same question in Cypher (both must give the SQL's count):
#
# "paths"   A quantified path pattern: the group in brackets (one hop, actor -> repo ->
#           actor) is repeated from 1 to N times. Neo4j follows every PATH and removes
#           repeated actors only at the end, so the work grows with the number of paths.
# "levels"  Level by level, like the SQL: each step starts from the actors found in the
#           step before (the "frontier") and keeps only actors never seen before.
#
# N can't be a query parameter, so it's written into the text.
CYPHER_VERSIONS = ("paths", "levels")

# ---------------------------------------------------------------------
# CYPHER_REACH_PATHS — « paths » : un MOTIF DE CHEMIN QUANTIFIÉ (Neo4j 5.9 et plus)
#
# Une fois le formatage Python ci-dessous appliqué, la requête se lit
# (pour N = 3) :
#
#   MATCH (a:Actor {id: $start})
#         ((:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(:Actor)){1,3}
#         (b:Actor)
#   WHERE b <> a
#   RETURN count(DISTINCT b)
#
#   (a:Actor {id: $start})   le départ : le nœud Actor dont la propriété
#                            id vaut le paramètre $start.
#   ( ...un saut... ){1,3}   la partie entre parenthèses est UN saut
#                            (acteur -> repo <- acteur), et {1,3} est un
#                            QUANTIFICATEUR : « répéter ceci de 1 à 3
#                            fois », comme {1,3} dans une expression
#                            régulière. Le dernier acteur d'une
#                            répétition est le premier de la suivante, et
#                            le tout premier est `a` lui-même.
#   (b:Actor)                l'acteur où le chemin se termine.
#   count(DISTINCT b)        combien d'acteurs d'arrivée différents.
#
# Comparez avec le SQL : le saut est dessiné une fois puis répété,
# exactement comme la partie récursive de la CTE — mais la façon de
# penser est différente. Le MATCH de Cypher cherche des CHEMINS (dans un
# même chemin, une même arête ne peut pas servir deux fois) et DISTINCT
# ne retire les acteurs d'arrivée répétés qu'à la FIN ; le SQL retire les
# répétitions à CHAQUE niveau. Les deux donnent le même ensemble
# d'acteurs, mais ici le travail grandit avec le nombre de CHEMINS, et ce
# nombre se multiplie à chaque saut (chaque repo populaire ouvre des
# dizaines de nouveaux chemins) : c'est ce qui a explosé à la profondeur
# 5-6 sur 24 heures de données.
#
# POURQUOI LA PROFONDEUR EST ÉCRITE DANS LE TEXTE : Cypher n'accepte
# qu'un nombre littéral dans {1,N}, pas un $paramètre. La requête est
# donc un MODÈLE, et str.format() de Python y écrit le nombre (voir
# cypher_reach()). Dans un modèle de format, {depth} est un trou à
# remplir, et une accolade DOUBLÉE {{ ou }} signifie « une vraie
# accolade, pas un trou ». Ainsi :
#   {{id: $start}}      devient   {id: $start}
#   {{1,{depth}}}       devient   {1,3}       (avec depth=3)
# $start reste un paramètre normal, rempli par le driver.
# ---------------------------------------------------------------------
CYPHER_REACH_PATHS = """
MATCH (a:Actor {{id: $start}})
      ((:Actor)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(:Actor)){{1,{depth}}}
      (b:Actor)
WHERE b <> a
RETURN count(DISTINCT b)
"""

# ---------------------------------------------------------------------
# « levels » : TROIS MORCEAUX, COLLÉS ENSEMBLE PAR cypher_reach()
#
# L'idée est celle du SQL : garder deux LISTES d'acteurs et avancer d'un
# niveau à la fois.
#   seen       tous les acteurs trouvés jusqu'ici (le départ compris)
#   frontier   les acteurs trouvés au DERNIER niveau seulement : le saut
#              suivant part d'eux, et pas à nouveau de tout le monde
# Pour la profondeur 3, la requête est START + STEP + STEP + STEP + END.
#
# CYPHER_LEVELS_START
#   MATCH (start:Actor {id: $start})     trouver l'acteur de départ.
#   WITH [start] AS seen, [start] AS frontier
#       [x] est une LISTE Cypher à un élément. WITH transmet les deux
#       listes au reste de la requête (WITH : voir CYPHER_ONE_HOP plus
#       haut).
#   Il n'y a pas de .format() sur ce morceau, donc les accolades restent
#   simples.
# ---------------------------------------------------------------------
CYPHER_LEVELS_START = """
MATCH (start:Actor {id: $start})
WITH [start] AS seen, [start] AS frontier
"""

# ---------------------------------------------------------------------
# CYPHER_LEVELS_STEP — UN saut, répété une fois par niveau
#
# CALL (seen, frontier) { ... }
#   Une SOUS-REQUÊTE : une petite requête exécutée à l'intérieur de la
#   grande. Les parenthèses après CALL indiquent quelles variables de
#   l'extérieur elle a le droit d'utiliser (ici, les deux listes). Son
#   RETURN renvoie son résultat à la requête extérieure. (C'est un autre
#   usage de CALL que `CALL dbms.components()` dans check_connections.py,
#   qui appelle une procédure intégrée.)
#
# À l'intérieur :
#   UNWIND frontier AS a      une ligne par acteur de la frontière
#                             (UNWIND : docs_french/load_neo4j.py).
#   MATCH (a)-...->(:Repo)<-...-(b:Actor)
#                             le saut unique, depuis chacun de ces
#                             acteurs.
#   WITH DISTINCT b           garder chaque acteur trouvé UNE SEULE FOIS,
#                             quel que soit le nombre de chemins qui y
#                             mènent — comme le UNION du SQL. C'est LA
#                             différence avec « paths » : les répétitions
#                             sont retirées à chaque niveau, pas seulement
#                             à la fin.
#   WHERE NOT b IN seen       `x IN liste` vaut True si x est dans la
#                             liste : écarter les acteurs déjà trouvés à
#                             un niveau précédent.
#   RETURN collect(b) AS next collect() est un agrégat (comme count) qui
#                             rassemble les valeurs de toutes les lignes
#                             en UNE SEULE liste : les nouveaux acteurs de
#                             ce niveau.
#
# Après la sous-requête :
#   WITH seen + next AS seen, next AS frontier
#       `+` entre deux listes les RELIE : seen grandit des nouveaux
#       acteurs, et les nouveaux acteurs deviennent la frontière suivante.
#
# Python répète ensuite ce texte `depth` fois (voir cypher_reach()). Si
# un niveau ne trouve personne de nouveau, next est une liste vide et les
# étapes suivantes n'ajoutent simplement rien.
# ---------------------------------------------------------------------
CYPHER_LEVELS_STEP = """
CALL (seen, frontier) {
    UNWIND frontier AS a
    MATCH (a)-[:INTERACTED_WITH]->(:Repo)<-[:INTERACTED_WITH]-(b:Actor)
    WITH DISTINCT b
    WHERE NOT b IN seen
    RETURN collect(b) AS next
}
WITH seen + next AS seen, next AS frontier
"""

# CYPHER_LEVELS_END — size(liste) est son nombre d'éléments. `seen`
# contient tous les acteurs atteints, PLUS le départ lui-même, d'où le
# - 1 : le même nombre que le compte du SQL (qui laisse le départ de côté
# avec <> %(start)s).
CYPHER_LEVELS_END = """
RETURN size(seen) - 1
"""


# ---------------------------------------------------------------------
# def cypher_reach(depth, version="paths") -> str:
#
# Construit le texte Cypher pour une profondeur et une version.
#   version: str = "paths"   une valeur PAR DÉFAUT : cypher_reach(3)
#                            désigne toujours la version « paths ».
#
# Comme la profondeur va dans le TEXTE de la requête (et non dans un
# paramètre sûr), elle est d'abord vérifiée : {1,0} n'aurait aucun sens,
# donc une profondeur inférieure à 1 lève une ValueError au lieu
# d'envoyer une requête cassée.
#
#   "paths"    remplit le modèle avec str.format() (voir plus haut).
#   "levels"   colle les morceaux : START, puis STEP `depth` fois, puis
#              END. `texte * 3` RÉPÈTE une chaîne : "ab" * 3 == "ababab".
#   toute autre valeur : une ValueError. {version!r} dans une f-string
#              affiche la valeur avec repr(), c'est-à-dire AVEC ses
#              guillemets ('shortcut'), pour que le message montre
#              clairement ce qui a été reçu.
# tests/test_research.py vérifie les trois cas.
# ---------------------------------------------------------------------
def cypher_reach(depth: int, version: str = "paths") -> str:
    if depth < 1:
        raise ValueError("depth must be at least 1")
    if version == "paths":
        return CYPHER_REACH_PATHS.format(depth=depth)
    if version == "levels":
        return CYPHER_LEVELS_START + CYPHER_LEVELS_STEP * depth + CYPHER_LEVELS_END
    raise ValueError(f"unknown Cypher version {version!r}: use one of {CYPHER_VERSIONS}")


# ---------------------------------------------------------------------
# sql_joins(depth) / cypher_hops(depth) — « COMBIEN DE MARCHE » REPRÉSENTE
# UNE PROFONDEUR
#
# Deux petits nombres écrits sur chaque ligne du CSV de résultats, pour
# qu'un lecteur voie ce que signifie une profondeur de chaque côté :
#   sql_joins     un saut = actor_repo joint deux fois (acteur -> ses
#                 repos, repo -> ses acteurs) ; la partie récursive
#                 s'exécute une fois par saut. Profondeur 3 -> 6
#                 jointures.
#   cypher_hops   un saut = deux relations INTERACTED_WITH suivies
#                 (acteur -> repo, repo <- acteur). Profondeur 3 -> 6.
# Les deux valent 2 x la profondeur : le même parcours, compté dans les
# unités propres à chaque base. (Testé dans tests/test_research.py.)
# ---------------------------------------------------------------------
def sql_joins(depth: int) -> int:
    # Each hop of the recursive part joins actor_repo twice (actor -> repo, repo -> actor),
    # and the recursive part runs once per hop.
    return 2 * depth


def cypher_hops(depth: int) -> int:
    # Each hop follows two relationships: (actor)-[:INTERACTED_WITH]->(repo)<-[:INTERACTED_WITH]-(actor).
    return 2 * depth


# ---------- running a query, with a time limit, on either side ----------

# ---------------------------------------------------------------------
# @dataclass  class Outcome — le résultat d'UNE exécution chronométrée.
#
# Une classe (expliquée dans summarize_data.py) a normalement besoin
# d'une méthode __init__ qui recopie chaque argument dans self.
# @dataclass est un DÉCORATEUR (la ligne en @ juste au-dessus d'une
# classe ou d'une fonction, qui lui ajoute un comportement) : à partir de
# la liste des champs annotés ci-dessous, il ÉCRIT ce __init__ à votre
# place, ainsi qu'un affichage lisible (__repr__) et une comparaison ==.
# Ainsi, Outcome("ok", 0.42, 1234) crée un objet avec .status = "ok",
# .seconds = 0.42, .count = 1234 et .error = "".
#
# Les champs :
#   status   "ok", "timeout" ou "error" — un seul mot, facile à compter
#            ensuite.
#   seconds  le temps mesuré depuis Python (voir run_postgres_reach()).
#   count    la réponse ; `int | None` = un int, ou None quand la requête
#            ne s'est pas terminée (il n'existe donc pas de réponse —
#            None, et pas 0, car 0 serait une vraie réponse, fausse).
#   error    = "" est une valeur PAR DÉFAUT : on peut l'omettre, comme en
#            cas de succès. Les champs avec une valeur par défaut doivent
#            venir après ceux qui n'en ont pas.
#
# Pourquoi une dataclass et pas un tuple ? outcome.status se lit mieux
# que outcome[0], et une erreur dans un nom de champ provoque une
# erreur, pas une mauvaise position silencieuse.
# ---------------------------------------------------------------------
@dataclass
class Outcome:
    status: str            # "ok", "timeout" or "error"
    seconds: float         # wall-clock time seen from Python
    count: int | None      # the answer (None if it didn't finish)
    error: str = ""        # the error message, if any


# ---------------------------------------------------------------------
# Deux fonctions utilitaires de connexion, pour que les détails de
# connexion se trouvent à un seul endroit.
#
# connect_postgres : autocommit=True (vu dans pipeline.py), ici pour une
# nouvelle raison : chaque requête est sa propre transaction. Si l'une
# d'elles est annulée par la limite de temps, une transaction normale
# resterait « interrompue » (aborted) et refuserait toutes les commandes
# suivantes sur cette connexion ; avec autocommit, la mesure suivante
# peut simplement continuer. L'indication `-> psycopg.Connection` nomme
# le type renvoyé.
#
# connect_neo4j : le même driver que dans check_connections.py, avec
# l'adresse et l'utilisateur réutilisés depuis load_neo4j.py.
# ---------------------------------------------------------------------
def connect_postgres(database: str) -> psycopg.Connection:
    return psycopg.connect(host="localhost", user="postgres", dbname=database, autocommit=True)


def connect_neo4j():
    return GraphDatabase.driver(load_neo4j.NEO4J_URI, auth=(load_neo4j.NEO4J_USER, os.environ["NEO4J_PASSWORD"]))


# ---------------------------------------------------------------------
# def run_postgres_reach(conn, start, depth, timeout_s) -> Outcome:
#
# LA LIMITE DE TEMPS : SET statement_timeout = '60s'
#   Un réglage PostgreSQL pour cette connexion : toute instruction
#   encore en cours au bout de cette durée est ANNULÉE par le serveur
#   lui-même. Les traversées profondes peuvent prendre des heures ; la
#   recherche doit pouvoir dire « ne s'est pas terminée dans la limite »
#   au lieu d'attendre indéfiniment.
#   SET n'accepte pas de paramètre %s, donc la valeur est construite avec
#   sql.Literal(...), qui la met correctement entre apostrophes : '60s'
#   (la famille sql.SQL a été expliquée dans pipeline.py).
#   f"{timeout_s}s" transforme 60 en texte "60s".
#
# LE CHRONOMÉTRAGE : begin = time.perf_counter() juste avant la requête ;
# la différence obtenue ensuite est le temps RÉEL (« wall-clock ») vu
# depuis Python : l'envoi de la requête, le travail du serveur, et le
# retour de la réponse — le temps qu'un UTILISATEUR de la base
# attendrait. measure.py prend la MÉDIANE de plusieurs de ces temps (les
# colonnes time_s du CSV de résultats).
#
# LA REQUÊTE : conn.execute(SQL_REACH, {"start": ..., "depth": ...})
# remplit les trous %(start)s et %(depth)s à partir du dictionnaire.
# fetchone()[0] : l'unique ligne, son unique colonne — le compte.
#
# TROIS FINS POSSIBLES, un Outcome pour chacune :
#   ok        le compte, et le temps.
#   timeout   psycopg.errors.QueryCanceled est l'erreur que PostgreSQL
#             envoie quand statement_timeout annule la requête.
#   error     toute autre erreur de base de données (psycopg.Error est le
#             parent de toutes les erreurs psycopg, QueryCanceled
#             compris).
#   L'ORDRE des lignes `except` compte : Python utilise la première qui
#   correspond, donc le QueryCanceled spécifique doit venir avant son
#   parent psycopg.Error, sinon un dépassement de temps serait étiqueté
#   « error ».
#   str(error).strip() : le message sous forme de texte, sans le retour à
#   la ligne final.
# ---------------------------------------------------------------------
def run_postgres_reach(conn: psycopg.Connection, start: int, depth: int, timeout_s: int) -> Outcome:
    conn.execute(sql.SQL("SET statement_timeout = {}").format(sql.Literal(f"{timeout_s}s")))
    begin = time.perf_counter()
    try:
        count = conn.execute(SQL_REACH, {"start": start, "depth": depth}).fetchone()[0]
        return Outcome("ok", time.perf_counter() - begin, count)
    except psycopg.errors.QueryCanceled as error:
        return Outcome("timeout", time.perf_counter() - begin, None, str(error).strip())
    except psycopg.Error as error:
        return Outcome("error", time.perf_counter() - begin, None, str(error).strip())


# ---------------------------------------------------------------------
# def run_neo4j_reach(driver, database, start, depth, timeout_s, version="paths") -> Outcome:
#
# Le même travail, côté Neo4j. `version` indique quelle version Cypher
# exécuter (« paths » ou « levels », voir cypher_reach()) ; measure.py
# la transmet.
#
# driver.session(database=database)
#   Jusqu'ici, on utilisait driver.execute_query(), un raccourci en un
#   seul appel. Une SESSION est la forme longue : une « conversation »
#   avec une base, ouverte avec `with` (pour qu'elle soit fermée
#   ensuite), dans laquelle session.run() envoie une requête. On en a
#   besoin à cause du point suivant.
#
# Query(cypher_reach(depth, version), timeout=timeout_s)
#   Enveloppe le texte de la requête avec une LIMITE DE TEMPS en
#   secondes. Le SERVEUR Neo4j arrête la transaction de la requête une
#   fois la limite dépassée — l'équivalent de statement_timeout.
#   start=start est la valeur de $start.
#
# .single()[0] : la réponse doit être exactement UN record (sinon
# single() proteste) ; [0] est sa première colonne, le compte.
#
# Le `except` est large (Exception) exprès, comme le dit le commentaire :
# selon le moment et la version du driver, un dépassement de temps
# arrive sous forme de classes d'erreurs différentes. La décision se fait
# donc sur le MESSAGE :
#   "timeout" in str(error).lower()   le mot est-il dans le message ?
#                                     (lower() pour que « Timeout » et
#                                     « TIMEOUT » correspondent aussi)
#   X if condition else Y             une EXPRESSION CONDITIONNELLE : un
#                                     if/else sur une ligne qui donne une
#                                     valeur.
# [:300] ne garde que les 300 premiers caractères d'un message
# potentiellement énorme.
# ---------------------------------------------------------------------
def run_neo4j_reach(driver, database: str, start: int, depth: int, timeout_s: int, version: str = "paths") -> Outcome:
    begin = time.perf_counter()
    try:
        with driver.session(database=database) as session:
            count = session.run(Query(cypher_reach(depth, version), timeout=timeout_s), start=start).single()[0]
        return Outcome("ok", time.perf_counter() - begin, count)
    except Exception as error:   # the driver raises different classes for a timeout
        status = "timeout" if "timeout" in str(error).lower() or "timed out" in str(error).lower() else "error"
        return Outcome(status, time.perf_counter() - begin, None, str(error).strip()[:300])


# ---------- the work done inside each database ----------

# ---------------------------------------------------------------------
# PAGE_MB — UNE PAGE, EN MÉGAOCTETS
#
# Les deux bases stockent leurs données dans des PAGES de taille fixe,
# 8 ko (8192 octets), et gardent en mémoire les pages récemment
# utilisées : PostgreSQL les appelle des « blocks » dans ses « shared
# buffers », Neo4j des « pages » dans son « page cache ». Comme la taille
# des pages est la MÊME, le nombre de pages que chaque côté a touchées
# peut être comparé directement — et converti en mégaoctets, plus faciles
# à se représenter : pages x 8192 / 1024**2 (1 Mo = 1024 x 1024 octets ;
# `**` signifie « puissance »). 8192 / 1048576 = 0.0078125 Mo.
# ---------------------------------------------------------------------
PAGE_MB = 8192 / 1024 ** 2   # both databases read and cache data in pages of 8 KB


# ---------------------------------------------------------------------
# def _postgres_memory_kb(node) -> float:  — LA MÉMOIRE DE LA REQUÊTE, côté PostgreSQL
#
# Un plan PostgreSQL est un ARBRE d'étapes ; chaque nœud peut indiquer
# combien de mémoire son étape a gardée pour elle (PostgreSQL 18 donne
# ces valeurs en ko) :
#   "Maximum Storage"     l'UNION récursive et le parcours de la CTE (les
#                         lignes de `reach` gardées pendant sa
#                         construction) ;
#   "Sort Space Used"     un tri ;
#   "Peak Memory Usage"   une table de hachage (utilisée pour les
#                         jointures et DISTINCT).
# Une étape qui a épuisé la mémoire qui lui est autorisée (work_mem)
# continue sur le DISQUE à la place : alors « Storage » / « Sort Space
# Type » indique « Disk », et cette quantité n'est PAS de la mémoire —
# elle est comptée à part, comme temp_disk_mb (voir postgres_work()).
# `node.get("Storage", "Memory") == "Memory"` : si la clé manque, on
# suppose qu'il s'agit de mémoire.
#
# `node.get(...) or 0` transforme une valeur manquante (None) en 0, et la
# fonction parcourt l'arbre de façon RÉCURSIVE, comme _sum_profile()
# plus bas : la mémoire de ce nœud + la somme sur ses « Plans » (le mot
# de PostgreSQL pour les enfants). Le résultat est la mémoire totale
# utilisée par les étapes, en ko.
# ---------------------------------------------------------------------
def _postgres_memory_kb(node: dict) -> float:
    # The memory each step of the plan kept for itself (PostgreSQL 18 reports it in kB):
    # "Maximum Storage" (recursive union, CTE scan), "Sort Space Used", "Peak Memory Usage"
    # (hash tables). Only what stayed in memory; what went to disk is counted as temp.
    own = 0.0
    if node.get("Storage", "Memory") == "Memory":
        own += node.get("Maximum Storage") or 0
    if node.get("Sort Space Type", "Memory") == "Memory":
        own += node.get("Sort Space Used") or 0
    own += node.get("Peak Memory Usage") or 0
    return own + sum(_postgres_memory_kb(child) for child in node.get("Plans", []))


# ---------------------------------------------------------------------
# def postgres_work(conn, start, depth, timeout_s) -> dict:
#
# Le TEMPS n'est pas la seule chose qui mérite d'être mesurée : il dépend
# de l'ordinateur et de ce qui tourne en même temps. COMBIEN DE TRAVAIL
# la base a fait (combien de données elle a parcourues, combien de
# mémoire il lui a fallu) explique POURQUOI un côté est plus rapide.
# measure.py appelle cette fonction une fois par profondeur, comme une
# exécution supplémentaire APRÈS celles qui sont chronométrées, car
# mesurer le travail ralentit un peu la requête et ne doit pas fausser
# les temps.
#
# EXPLAIN montre le PLAN que PostgreSQL a choisi pour une requête (quel
# index, quelle méthode de jointure...). Les options entre parenthèses :
#   ANALYZE      EXÉCUTER réellement la requête, et donner les vrais
#                chiffres au lieu d'estimations. (Ce n'est pas la même
#                chose que la commande ANALYZE de load_postgres.py, qui
#                met à jour les statistiques.)
#   BUFFERS      donner aussi les BLOCS (pages de 8 ko) utilisés.
#   FORMAT JSON  donner le rapport en JSON, pour que Python puisse lire
#                les chiffres par leur nom au lieu d'analyser du texte.
#
# .fetchone()[0][0] : le rapport est une ligne avec une colonne contenant
# une LISTE JSON (psycopg la transforme en list Python) ; [0] est son
# unique élément, un dictionnaire. plan["Plan"] est le nœud du HAUT de
# l'arbre du plan, c'est-à-dire la dernière étape, dont les chiffres de
# BUFFERS incluent déjà toutes les étapes en dessous (pas besoin de les
# additionner — contrairement à Neo4j plus bas, et contrairement à la
# mémoire, que chaque étape donne pour elle-même).
#
# from_memory, from_disk = A, B — deux variables affectées en une ligne.
#   "Shared Hit Blocks"    les blocs déjà en mémoire.
#   "Shared Read Blocks"   les blocs que PostgreSQL a dû lire dans un
#                          fichier (sur le disque — ou dans le cache de
#                          fichiers de Windows lui-même, ce que
#                          PostgreSQL ne sait pas distinguer).
#
# Les chiffres renvoyés, tous en Mo (ils deviennent les colonnes pg_...
# du CSV de résultats, voir docs_french/measure.py) :
#   data_processed_mb   (hits + reads) x PAGE_MB : toutes les données que
#                       la requête a parcourues. Une page utilisée deux
#                       fois compte deux fois : c'est une mesure du
#                       TRAVAIL, pas de la taille des données.
#   data_from_disk_mb   la partie qu'il a fallu lire dans un fichier.
#   memory_mb           _postgres_memory_kb(top) / 1024 (ko -> Mo).
#   temp_disk_mb        « Temp Written Blocks » : blocs écrits dans des
#                       fichiers TEMPORAIRES parce que le travail ne
#                       tenait pas dans la mémoire autorisée pour une
#                       étape (le réglage work_mem) — par ex. un énorme
#                       résultat intermédiaire de la CTE récursive. Le
#                       signe que la requête dépasse la mémoire. (Neo4j
#                       n'a pas de chiffre équivalent, donc le CSV de
#                       résultats n'a pas de colonne neo4j_temp_disk_mb.)
# La même limite de temps est fixée en premier, car il s'agit d'une
# exécution complète de la requête.
# ---------------------------------------------------------------------
def postgres_work(conn: psycopg.Connection, start: int, depth: int, timeout_s: int) -> dict:
    # EXPLAIN (ANALYZE, BUFFERS) runs the query and reports what it did. The top node's
    # buffer numbers include everything below it.
    conn.execute(sql.SQL("SET statement_timeout = {}").format(sql.Literal(f"{timeout_s}s")))
    query = "EXPLAIN (ANALYZE, BUFFERS, FORMAT JSON) " + SQL_REACH
    plan = conn.execute(query, {"start": start, "depth": depth}).fetchone()[0][0]
    top = plan["Plan"]
    from_memory, from_disk = top.get("Shared Hit Blocks") or 0, top.get("Shared Read Blocks") or 0
    return {
        "data_processed_mb": (from_memory + from_disk) * PAGE_MB,
        "data_from_disk_mb": from_disk * PAGE_MB,
        "memory_mb": _postgres_memory_kb(top) / 1024,
        "temp_disk_mb": (top.get("Temp Written Blocks") or 0) * PAGE_MB,
    }


# ---------------------------------------------------------------------
# def _sum_profile(node, key) -> int:
#
# Un plan Neo4j est un ARBRE d'étapes (« opérateurs »), chacune étant un
# dictionnaire avec ses propres chiffres et une liste d'« enfants »
# (children, les étapes qui l'alimentent). Contrairement à PostgreSQL,
# chaque étape Neo4j ne donne que SON PROPRE travail, donc le total est
# la somme sur tout l'arbre. Cette fonction le parcourt de façon
# RÉCURSIVE (la récursivité : profile_schema.py) :
#   la valeur de ce nœud  +  la somme de _sum_profile(enfant) pour chaque enfant
# Pour un nœud sans enfants : node.get("children", []) donne une liste
# vide, la somme de rien vaut 0, et la récursion s'arrête là.
# `node.get(key) or 0` transforme une valeur manquante (None) en 0.
# Le tiret bas au début du nom est une convention : « fonction
# utilitaire interne, pas destinée à être utilisée depuis d'autres
# fichiers ».
# ---------------------------------------------------------------------
def _sum_profile(node: dict, key: str) -> int:
    return (node.get(key) or 0) + sum(_sum_profile(child, key) for child in node.get("children", []))


# ---------------------------------------------------------------------
# def neo4j_work(driver, database, start, depth, timeout_s, version="paths") -> dict:
#
# PROFILE devant une requête Cypher = l'EXPLAIN ANALYZE de Neo4j : il
# EXÉCUTE la requête et enregistre, pour chaque étape de son plan, ce
# qu'elle a fait. `version` choisit la version Cypher profilée (voir
# cypher_reach()).
#
# result.consume() lit le résultat jusqu'au bout et renvoie son RÉSUMÉ
# (les métadonnées, pas les lignes). summary.profile est l'arbre du plan
# sous forme de dictionnaire (ou None s'il n'y en a pas, d'où `or {}`).
#
#   hits, misses       Le PAGE CACHE de Neo4j est son équivalent des
#                      shared buffers de PostgreSQL, avec les mêmes pages
#                      de 8 ko : un hit = la page était en mémoire, un
#                      miss = il a fallu la lire sur le disque. Additionnés
#                      sur tout l'arbre.
#   memory             « GlobalMemory » : la mémoire utilisée par TOUTE la
#                      requête, en OCTETS, trouvée dans les arguments de
#                      l'étape du haut. La clé qui contient les arguments
#                      est « args » dans certaines versions du driver et
#                      « arguments » dans d'autres, donc on essaie les
#                      deux (`A or B or {}` = le premier qui n'est pas
#                      vide).
#
# Les chiffres renvoyés — les MÊMES noms que ceux de postgres_work(),
# pour que measure.py puisse traiter les deux côtés de la même façon (les
# colonnes neo4j_...) :
#   data_processed_mb   (hits + misses) x PAGE_MB — directement
#                       comparable à celui de PostgreSQL, puisque les
#                       pages ont la même taille. Une page utilisée deux
#                       fois compte deux fois.
#   data_from_disk_mb   misses x PAGE_MB.
#   memory_mb           octets / 1024**2 -> Mo ; None si Neo4j ne l'a pas
#                       indiqué (`X if condition else None`, une
#                       expression conditionnelle).
# ---------------------------------------------------------------------
def neo4j_work(driver, database: str, start: int, depth: int, timeout_s: int, version: str = "paths") -> dict:
    # PROFILE runs the query and reports, for every step of its plan, the page cache
    # hits/misses; they're added up over the whole plan. GlobalMemory is the memory the
    # whole query used.
    with driver.session(database=database) as session:
        result = session.run(Query("PROFILE " + cypher_reach(depth, version), timeout=timeout_s), start=start)
        summary = result.consume()
    profile = summary.profile or {}
    arguments = profile.get("args") or profile.get("arguments") or {}
    hits, misses = _sum_profile(profile, "pageCacheHits"), _sum_profile(profile, "pageCacheMisses")
    memory = arguments.get("GlobalMemory")
    return {
        "data_processed_mb": (hits + misses) * PAGE_MB,
        "data_from_disk_mb": misses * PAGE_MB,
        "memory_mb": memory / 1024 ** 2 if memory is not None else None,
    }
