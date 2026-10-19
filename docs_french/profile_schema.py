########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/profile_schema.py.
# Il n'est PAS destiné à être exécuté dans le cadre du pipeline du projet — il se
# trouve dans docs_french/ car son but est d'enseigner, pas de s'exécuter. Le
# script réel et « propre » (sans tous ces commentaires) est
# scripts/profile_schema.py.
#
# Ce fichier suppose que vous avez déjà lu docs_french/download_gharchive.py,
# docs_french/peek_data.py, et docs_french/summarize_data.py — argparse,
# Path, les f-strings, les recherches dans des dict imbriqués, Counter,
# .most_common(), main(), et la garde __name__ ne sont PAS réexpliqués
# depuis zéro ici. Ce fichier se concentre sur ce qui est NOUVEAU dans
# profile_schema.py : la RÉCURSION — une fonction qui s'appelle elle-même
# pour explorer une structure imbriquée de forme inconnue et arbitraire.
########################################################################

"""Profile the payload shape of a downloaded GH Archive JSON Lines file.

Reads the full file once and reports, per event type, which `payload`
fields appear, how often, and what Python type they hold, plus any nested
"actor-like" references (dicts with a 'login' key, e.g. a PR's author or
reviewer, distinct from the event's top-level actor) found anywhere inside
the payload. This is ground truth for hand-designing the relational/graph
schema later, since payload shape varies a lot between event types (e.g.
PushEvent vs. PullRequestEvent), and multi-actor connectivity (needed for
an actor-repo-actor traversal) mostly lives in these nested references.

Usage:
    python scripts/profile_schema.py
    python scripts/profile_schema.py --file data/2026-08-27-15.json
    python scripts/profile_schema.py --type PushEvent
"""

# argparse, json, Counter, Path : déjà expliqués dans les trois précédentes
# copies annotées.
import argparse
import json
from collections import Counter
from pathlib import Path

DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# ---------------------------------------------------------------------
# POURQUOI une limite de profondeur existe
#
# find_actor_refs() (ci-dessous) est RÉCURSIVE : elle s'appelle
# elle-même sur tout ce qu'elle trouve imbriqué dans un dict ou une list,
# et les données JSON peuvent s'imbriquer arbitrairement profondément (un
# dict dans une list dans un dict dans une list...). Sans limite, une
# structure suffisamment profonde ou inattendument auto-référentielle
# pourrait faire récurser la fonction indéfiniment, jusqu'à planter avec
# une RecursionError. En pratique, les payloads de GH Archive ne
# descendent que sur quelques niveaux, mais MAX_SEARCH_DEPTH est un
# filet de sécurité peu coûteux dans tous les cas, et il limite aussi le
# travail gaspillé à chercher là où une référence d'acteur ne se
# trouverait de toute façon pas raisonnablement.
# ---------------------------------------------------------------------
MAX_SEARCH_DEPTH = 3


# ---------------------------------------------------------------------
# QU'EST-CE QUE LA RÉCURSIVITÉ ? (une fonction qui s'appelle elle-même)
#
# find_actor_refs(), ci-dessous, appelle find_actor_refs() dans son
# propre corps. C'est ce qu'on appelle la RÉCURSIVITÉ (ou récursion), et
# une fonction qui fait cela est RÉCURSIVE. (Ce n'est pas « imbriquer »
# une fonction : imbriquer veut dire DÉFINIR une fonction à l'intérieur
# d'une autre. Ici, il n'y a qu'une seule fonction, qui S'APPELLE
# simplement elle-même.)
#
# Pourquoi c'est possible : à chaque appel d'une fonction, Python crée
# une copie neuve et séparée de ses paramètres et de ses variables pour
# cet appel. Donc quand find_actor_refs() appelle à nouveau
# find_actor_refs(), le nouvel appel a ses propres `value`, `path` et
# `depth`, et n'écrase pas ceux du premier. Le premier appel attend
# simplement, en pause, que l'appel intérieur lui renvoie sa réponse,
# puis reprend là où il s'était arrêté.
#
# Une analogie : les poupées russes (matriochkas). Pour trouver un mot
# caché quelque part dans un jeu de poupées, les instructions sont les
# mêmes à chaque niveau :
#   « Ouvre la poupée. Si le mot est là, prends-le. Sinon, à chaque
#     poupée que tu trouves dedans, applique CES MÊMES INSTRUCTIONS. »
# Les instructions font référence à elles-mêmes : c'est la récursivité.
#
# Pourquoi on en a besoin ICI : un payload est un dictionnaire qui peut
# contenir des dictionnaires, qui peuvent contenir des listes de
# dictionnaires, et ainsi de suite — et on ne sait pas à l'avance
# combien de niveaux il y a. Une boucle `for` ordinaire ne regarde
# qu'UN niveau. Pour regarder tous les niveaux, sans savoir combien il y
# en a, la fonction s'occupe d'un niveau et se demande à elle-même de
# s'occuper du suivant.
#
# Les deux règles dont a besoin toute fonction récursive :
#   1. Un CAS DE BASE : une situation où elle répond SANS s'appeler
#      elle-même (ici : elle a trouvé un utilisateur, elle est arrivée à
#      une valeur simple comme un texte, ou elle n'a plus de profondeur
#      disponible). Sans cela, elle s'appellerait elle-même à l'infini.
#   2. Chaque appel à elle-même doit se RAPPROCHER d'un cas de base
#      (ici : chaque appel descend d'un niveau dans les données, avec
#      depth - 1).
#
# Pas à pas, avec un petit payload :
#
#     payload = {"action": "created",
#                "issue": {"user": {"login": "luis"}}}
#
#   appel 1 : find_actor_refs(payload, "payload", 3)
#             un dict sans "login" -> regarde chacune de ses valeurs :
#     appel 2 : find_actor_refs("created", "payload.action", 2)
#               un texte -> rien dedans -> renvoie []
#     appel 3 : find_actor_refs({"user": {...}}, "payload.issue", 2)
#               un dict sans "login" -> regarde chacune de ses valeurs :
#       appel 4 : find_actor_refs({"login": "luis"}, "payload.issue.user", 1)
#                 un dict AVEC "login" -> renvoie ["payload.issue.user"]
#               l'appel 3 le récupère et renvoie ["payload.issue.user"]
#   l'appel 1 rassemble [] + ["payload.issue.user"] et renvoie
#   ["payload.issue.user"]
#
# Chaque appel ne s'occupe que d'UN niveau ; les réponses remontent,
# d'appel en appel, jusqu'à ce que le premier ait la liste complète.
# ---------------------------------------------------------------------

# ---------------------------------------------------------------------
# def find_actor_refs(value: object, path: str, depth: int) -> list[str]:
#
# `value: object` — le type déclaré du paramètre est `object`, le type
# le plus général en Python (tout est un `object`). C'est délibéré :
# cette fonction reçoit des morceaux de JSON déjà analysé, qui peuvent
# être un dict, une list, un str, un int, un bool, ou None selon
# l'endroit de la structure où l'on se trouve actuellement — aucun type
# plus spécifique ne couvre tous ces cas, donc `object` est l'annotation
# de type honnête ici.
#
# `path: str` — un fil d'Ariane lisible par un humain indiquant comment
# on est arrivé ici, par ex. "payload.pull_request.user". Construit un
# `.attribut` à la fois au fur et à mesure que la fonction descend plus
# profondément, uniquement pour le rapport affiché final — il ne joue
# aucun rôle dans la logique de recherche elle-même.
#
# `depth: int` — combien de niveaux supplémentaires cet appel est
# autorisé à parcourir avant d'abandonner. Chaque appel récursif passe
# `depth - 1`, décomptant vers la limite de profondeur expliquée
# ci-dessus.
#
# `-> list[str]` — cette fonction renvoie toujours une liste de chaînes
# de chemin (éventuellement vide), quelle que soit la branche ci-dessous
# qui s'exécute réellement.
# ---------------------------------------------------------------------
def find_actor_refs(value: object, path: str, depth: int) -> list[str]:
    # ---------------------------------------------------------------
    # LE CAS DE BASE
    #
    # Toute fonction récursive a besoin d'au moins une condition qui
    # arrête complètement la récursion, sans effectuer d'appel récursif
    # supplémentaire — sinon elle récurserait vraiment indéfiniment.
    # Ici, une fois qu'on est descendu plus profondément que ce que
    # MAX_SEARCH_DEPTH autorise, on renvoie immédiatement une liste vide
    # (rien trouvé) plutôt que de chercher plus loin.
    # ---------------------------------------------------------------
    if depth < 0:
        return []

    # ---------------------------------------------------------------
    # isinstance(value, dict)
    #
    # Vérifie si `value` est (une instance) du type dict. C'est ainsi
    # que la fonction distingue les trois cas qui l'intéressent, puisque
    # le type réel de `value` varie d'un appel à l'autre (voir la
    # remarque sur `object` ci-dessus) : est-ce un dict dans lequel il
    # faut regarder, une list dans laquelle il faut regarder, ou autre
    # chose (un str/int/bool/None) sans rien de plus à explorer ?
    # ---------------------------------------------------------------
    if isinstance(value, dict):
        # ---------------------------------------------------------------
        # value.get("login")
        #
        # `.get(key)` est une recherche dans un dict qui renvoie None au
        # lieu de lever une erreur quand la clé est absente —
        # contrairement à value["login"], qui planterait avec une
        # KeyError sur tout dict qui n'a pas de clé "login" (la plupart
        # d'entre eux, ici). C'est le bon outil chaque fois que
        # l'absence d'une clé est une possibilité normale et attendue,
        # pas un bug.
        #
        # isinstance(..., str) sur le résultat vérifie ensuite que la
        # valeur de login est bien une chaîne de caractères (un vrai nom
        # d'utilisateur) et non, par exemple, None issu d'une clé
        # absente, ou un autre type qu'on ne reconnaîtrait pas comme un
        # nom d'utilisateur.
        #
        # gh-archive-guide.md documente que toute référence à un
        # utilisateur GitHub (le champ `actor` de premier niveau de
        # l'événement, mais aussi les auteurs de PR, les relecteurs, les
        # auteurs de commentaires, etc.) a la forme
        # {"id": ..., "login": "some-user"}. Donc : « est-ce que ce dict
        # a un champ 'login' de type chaîne ? » est un test raisonnable
        # et général pour « est-ce que ce dict est une référence à un
        # utilisateur GitHub ? » — sans avoir à coder en dur chaque nom
        # de champ possible (user/author/assignee/reviewer/owner/...)
        # sous lequel une référence utilisateur pourrait être stockée.
        # ---------------------------------------------------------------
        if isinstance(value.get("login"), str):
            # Une référence trouvée. On renvoie immédiatement — un dict
            # qui ressemble à une référence utilisateur est une
            # « feuille » pour nos besoins ; inutile de continuer à
            # récurser À L'INTÉRIEUR d'un objet utilisateur à la
            # recherche d'encore plus d'utilisateurs imbriqués.
            return [path]

        # ---------------------------------------------------------------
        # Ce dict lui-même n'était pas une référence utilisateur, donc on
        # explore chacune de ses valeurs à la place, au cas où L'UNE
        # D'ELLES en serait une (ou en contiendrait une).
        #
        # `refs = []` puis `refs.extend(...)` dans une boucle, plutôt que
        # `return find_actor_refs(...)` directement dans la boucle : un
        # dict peut avoir de nombreuses clés, et une référence d'acteur
        # pourrait se cacher sous plus d'une d'entre elles (par ex.
        # « assignee » ET « assignees » dans le même payload) — chaque
        # clé doit donc être vérifiée et tous leurs résultats combinés,
        # pas seulement la première correspondance renvoyée
        # immédiatement.
        #
        # `f"{path}.{key}"` prolonge le fil d'Ariane avec le nom de
        # cette clé avant de récurser dans sa valeur — donc si une
        # correspondance est trouvée trois niveaux plus bas, le chemin
        # renvoyé enregistre tout le trajet jusque-là, pas seulement la
        # dernière étape.
        #
        # `depth - 1` — un niveau plus profond, une marge restante en
        # moins.
        # ---------------------------------------------------------------
        refs = []
        for key, sub_value in value.items():
            refs.extend(find_actor_refs(sub_value, f"{path}.{key}", depth - 1))
        return refs

    # ---------------------------------------------------------------
    # isinstance(value, list)
    #
    # Les list apparaissent ici pour des champs comme « assignees » (une
    # liste de dict utilisateur) ou « requested_reviewers ». Notez que
    # le chemin N'EST PAS étendu avec un index (pas de « .0 », « .1 »,
    # ...) en récursant dans les éléments d'une list — chaque élément
    # de, disons, « assignees » est conceptuellement la même sorte de
    # chose (un assigné), donc ils sont rapportés sous un chemin partagé
    # unique plutôt que comme des chemins numérotés séparés.
    # ---------------------------------------------------------------
    if isinstance(value, list):
        refs = []
        for item in value:
            refs.extend(find_actor_refs(item, path, depth - 1))
        return refs

    # ---------------------------------------------------------------
    # Tout le reste (str, int, float, bool, None, ...) n'a rien à
    # l'intérieur à explorer — c'est l'autre cas de base, atteint une
    # fois que la récursion a atteint une valeur simple plutôt qu'un
    # conteneur.
    # ---------------------------------------------------------------
    return []


# ---------------------------------------------------------------------
# EXEMPLE COMPLET : un déroulé de find_actor_refs() du début à la fin
#
# Cet exemple passe par TOUTES les branches de la fonction : un dict
# sans "login", un dict avec "login", une liste, des valeurs simples et
# la limite de profondeur. C'est un payload semblable à celui d'un
# IssuesEvent :
#
#     payload = {
#         "action": "opened",
#         "issue": {
#             "number": 7,
#             "user": {"login": "luis", "id": 1},
#             "assignees": [{"login": "ana"}, {"login": "marta"}],
#             "milestone": {"creator": {"login": "pedro"}}
#         }
#     }
#
# profile() l'appelle ainsi :  find_actor_refs(payload, "payload", 3)
#
# Chaque niveau d'indentation est un appel fait À L'INTÉRIEUR du
# précédent. L'appel extérieur attend, en pause, que l'appel intérieur
# se termine.
#
# APPEL 1 : find_actor_refs(payload, "payload", 3)
#   - depth < 0 ? 3 ne l'est pas -> on continue.
#   - Est-ce un dict ? OUI. A-t-il "login" ? Non (ses clés sont action
#     et issue).
#   - Prépare refs = [] et parcourt ses clés une par une :
#
#   APPEL 2 : find_actor_refs("opened", "payload.action", 2)
#     - C'est du texte : ni dict ni liste -> arrive au `return []`
#       final.
#     - Renvoie [].  L'appel 1 fait refs.extend([]) -> refs = [].
#
#   APPEL 3 : find_actor_refs({...issue...}, "payload.issue", 2)
#     - Est-ce un dict ? OUI. A-t-il "login" ? Non.
#     - Prépare SA PROPRE refs = [] (distincte de celle de l'appel 1) et
#       parcourt ses clés :
#
#     APPEL 4 : find_actor_refs(7, "payload.issue.number", 1)
#       - C'est un nombre : ni dict ni liste -> renvoie [].
#
#     APPEL 5 : find_actor_refs({"login": "luis", "id": 1},
#                               "payload.issue.user", 1)
#       - Un dict avec un "login" texte ("luis") -> TROUVÉ !
#       - Renvoie ["payload.issue.user"] et ne regarde pas plus loin.
#       L'appel 3 a maintenant refs = ["payload.issue.user"].
#
#     APPEL 6 : find_actor_refs([{ana}, {marta}],
#                               "payload.issue.assignees", 1)
#       - Est-ce un dict ? Non. Est-ce une liste ? OUI.
#       - Parcourt chaque élément. Le chemin NE change PAS (pas de .0,
#         .1).
#
#       APPEL 7 : find_actor_refs({"login": "ana"},
#                                 "payload.issue.assignees", 0)
#         - depth = 0 : zéro n'est pas inférieur à zéro -> on continue.
#         - Un dict avec "login" -> renvoie ["payload.issue.assignees"].
#
#       APPEL 8 : find_actor_refs({"login": "marta"},
#                                 "payload.issue.assignees", 0)
#         - Pareil -> renvoie ["payload.issue.assignees"].
#
#       - L'appel 6 renvoie
#         ["payload.issue.assignees", "payload.issue.assignees"].
#
#     APPEL 9 : find_actor_refs({"creator": {...}},
#                               "payload.issue.milestone", 1)
#       - Un dict sans "login" -> parcourt son unique clé :
#
#       APPEL 10 : find_actor_refs({"login": "pedro"},
#                                  "payload.issue.milestone.creator", 0)
#         - depth = 0 -> on continue. Un dict avec "login" ->
#           renvoie ["payload.issue.milestone.creator"].
#
#       - L'appel 9 renvoie ["payload.issue.milestone.creator"].
#
#     - L'appel 3 termine sa boucle et renvoie ses 4 chemins.
#
#   - L'appel 1 fait refs.extend(...) avec ces 4 chemins et renvoie :
#
#     ['payload.issue.user',
#      'payload.issue.assignees',
#      'payload.issue.assignees',
#      'payload.issue.milestone.creator']
#
# QUELLE BRANCHE APPARAÎT DANS QUEL APPEL
#   dict sans "login" -> regarder dedans ........ appels 1, 3 et 9
#   dict AVEC "login" -> return [path] .......... appels 5, 7, 8 et 10
#   liste -> chaque élément, même chemin ........ appel 6
#   valeur simple -> return [] .................. appels 2 et 4
#   depth baisse de 1 à chaque niveau : 3 -> 2 -> 1 -> 0, tout du long
#
# Cela fait 10 appels à la MÊME fonction. Chacun a ses propres value,
# path, depth et refs, et aucun n'écrase les variables d'un autre. Les
# réponses REMONTENT : les appels 7 et 8 répondent à l'appel 6, le 6 au
# 3, et le 3 au 1.
#
# DEUX DÉTAILS DE PLUS
#
# 1. La limite de profondeur en action. Si l'utilisateur était un niveau
#    plus bas :
#
#        deep = {"a": {"b": {"c": {"d": {"login": "x"}}}}}
#        find_actor_refs(deep, "payload", 3)   # -> []
#
#    en arrivant à {"login": "x"}, depth vaudrait déjà -1, et la
#    première vérification (`if depth < 0: return []`) s'arrêterait là :
#    il ne le trouve PAS. C'est le prix du filet de sécurité ; comme les
#    payloads de GH Archive sont peu profonds, on ne perd rien en
#    pratique.
#
# 2. Pourquoi profile() utilise set(...) ensuite. La liste contient
#    "payload.issue.assignees" DEUX fois (une pour ana, une pour marta).
#    profile() fait set(...), qui ne garde chaque chemin qu'une fois :
#
#        {'payload.issue.user', 'payload.issue.assignees',
#         'payload.issue.milestone.creator'}
#
#    Ainsi cet événement compte comme UN événement qui a des personnes
#    assignées, pas deux : ce qu'on compte, c'est DANS COMBIEN
#    D'ÉVÉNEMENTS apparaît chaque chemin, pas combien d'utilisateurs il
#    y a.
# ---------------------------------------------------------------------


def profile(file_path: Path, type_filter: str | None) -> None:
    event_type_totals: Counter[str] = Counter()
    # Pour chaque type d'événement, pour chaque nom de champ de payload,
    # un Counter de combien de fois chaque type Python (dict/list/str/
    # int/bool/NoneType) a été vu dans ce champ. Même idée de Counter
    # imbriqué que summarize_data.py, juste avec un niveau de clé
    # supplémentaire (type d'événement -> nom de champ -> nom de type).
    payload_field_types: dict[str, dict[str, Counter[str]]] = {}
    # Pour chaque type d'événement, un Counter de combien d'événements
    # contenaient une référence de type acteur à chaque chemin imbriqué
    # (par ex. « payload.pull_request.user »).
    actor_ref_counts: dict[str, Counter[str]] = {}

    with open(file_path, "r", encoding="utf-8") as f:
        for line in f:
            event = json.loads(line)
            event_type = event["type"]

            # ---------------------------------------------------------
            # --type permet de concentrer le rapport (potentiellement
            # long) sur un seul type d'événement à la fois. `continue`
            # saute le reste de CETTE itération de boucle et passe
            # directement à la ligne suivante, sans toucher aux
            # compteurs ci-dessous — donc les événements filtrés ne
            # contribuent en rien aux totaux ou aux rapports.
            # ---------------------------------------------------------
            if type_filter is not None and event_type != type_filter:
                continue

            event_type_totals[event_type] += 1
            fields = payload_field_types.setdefault(event_type, {})
            payload = event.get("payload", {})

            for key, value in payload.items():
                type_counts = fields.setdefault(key, Counter())
                type_counts[type(value).__name__] += 1

            # ---------------------------------------------------------
            # set(find_actor_refs(...))
            #
            # find_actor_refs peut renvoyer LE MÊME chemin plus d'une
            # fois pour un seul événement — par ex. trois relecteurs
            # demandés sous « payload.requested_reviewers » reviendraient
            # comme ce chemin trois fois, une fois par relecteur.
            # Envelopper le résultat dans set(...) élimine les doublons,
            # ce qui correspond au fonctionnement des compteurs de type
            # de champ ci-dessus : compter combien d'ÉVÉNEMENTS ont une
            # référence à ce chemin, pas combien de références existent
            # au total.
            # ---------------------------------------------------------
            ref_paths = set(find_actor_refs(payload, "payload", MAX_SEARCH_DEPTH))
            ref_counts = actor_ref_counts.setdefault(event_type, Counter())
            for ref_path in ref_paths:
                ref_counts[ref_path] += 1

    # ---------------------------------------------------------------
    # Comment lire la sortie
    #
    # Un exemple réel tiré de l'heure fixe de ce projet :
    #
    #   IssueCommentEvent (194 events)
    #     payload.action               present in 100.0% (194/194) - types: str x194
    #     payload.issue                present in 100.0% (194/194) - types: dict x194
    #     payload.comment              present in 100.0% (194/194) - types: dict x194
    #     actor references (nested 'login' fields):
    #       payload.issue.user                  present in 100.0% (194/194)
    #       payload.comment.user                present in 100.0% (194/194)
    #
    # - Ligne 1 : le type d'événement, et combien d'événements de ce
    #   type le fichier contient.
    # - Chaque ligne de payload : le nom du champ, puis « present in
    #   X% » — dans combien de CES événements le champ existe. 100 %
    #   veut dire toujours là (fiable) ; un faible % veut dire
    #   seulement parfois, donc ce serait une colonne
    #   optionnelle/nullable. « types » indique quel genre de valeur
    #   il contenait (str, int, dict, list, NoneType) et combien de
    #   fois. NoneType veut dire que le champ est parfois vide — par
    #   ex. la description de CreateEvent vaut None dans 633
    #   événements sur 1290.
    # - « actor references » : les chemins vers des objets
    #   utilisateur imbriqués (tout ce qui a un « login »), et dans
    #   quel % des événements chacun apparaît.
    #
    # IMPORTANT : cela vérifie seulement qu'un objet utilisateur
    # EXISTE à ce chemin, pas QUI il est. payload.comment.user est
    # l'auteur du commentaire — c'est-à-dire l'acteur lui-même (100 %
    # du temps). payload.issue.user est l'auteur de l'issue, une
    # personne différente dans 66 % des cas. Voir project-notes.md
    # (« Étape de conception du schéma ») pour la comparaison avec
    # l'acteur de l'événement.
    # ---------------------------------------------------------------
    for event_type, total in event_type_totals.most_common():
        print(f"{event_type} ({total} events)")
        fields = payload_field_types[event_type]
        if not fields:
            print("  (empty payload)")
        for field_name, type_counts in fields.items():
            presence = sum(type_counts.values())
            pct = 100 * presence / total
            types = ", ".join(f"{t} x{c}" for t, c in type_counts.most_common())
            print(f"  payload.{field_name:<20} present in {pct:5.1f}% ({presence}/{total}) - types: {types}")

        print("  actor references (nested 'login' fields):")
        refs = actor_ref_counts[event_type]
        if not refs:
            print("    (none found)")
        for ref_path, count in refs.most_common():
            pct = 100 * count / total
            print(f"    {ref_path:<35} present in {pct:5.1f}% ({count}/{total})")
        print()


# parse_args() : même schéma global que les trois autres scripts —
# --file et --type suivent le même style que --file/--lines dans
# peek_data.py et --file/--top dans summarize_data.py.
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--type", type=str, default=None,
                         help="Only profile this event type (default: all types)")
    return parser.parse_args()


# main() et la garde `if __name__ == "__main__":` : but et mécanique
# identiques aux trois autres scripts.
def main() -> None:
    args = parse_args()
    profile(args.file, args.type)


if __name__ == "__main__":
    main()
