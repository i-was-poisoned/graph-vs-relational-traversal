########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/summarize_data.py.
# Il n'est PAS destiné à être exécuté dans le cadre du pipeline du projet — il se
# trouve dans docs_french/ car son but est d'enseigner, pas de s'exécuter. Le
# script réel et « propre » (sans tous ces commentaires) est
# scripts/summarize_data.py.
#
# Ce fichier suppose que vous avez déjà lu docs_french/download_gharchive.py
# et docs_french/peek_data.py — argparse, Path, les f-strings, les
# recherches dans des dict imbriqués, main() et la garde __name__ ne sont
# PAS réexpliqués depuis zéro ici. Ce fichier se concentre sur ce qui est
# NOUVEAU dans summarize_data.py : lire un fichier entier plutôt qu'une
# poignée de lignes, et compter/agréger avec collections.Counter.
########################################################################

"""Summarize a downloaded GH Archive JSON Lines file.

Reads the full file once and reports total event count, the event type
breakdown, and unique actor/repo counts — a first read on data volume and
connectivity before modeling the data relationally or as a graph.

Usage:
    python scripts/summarize_data.py
    python scripts/summarize_data.py --file data/2026-08-27-15.json --top 10
"""

# argparse, Path, json : déjà expliqués dans docs_french/download_gharchive.py
# et docs_french/peek_data.py.
import argparse
import json

# ---------------------------------------------------------------------
# from collections import Counter
#
# `collections` est un module de la bibliothèque standard regroupant des
# types de conteneurs spécialisés, construits par-dessus les dict/list/tuple
# intégrés. `Counter` est une sous-classe de dict conçue spécifiquement pour
# compter des choses : chaque clé vaut 0 par défaut la première fois qu'on y
# touche, donc `counter[key] += 1` fonctionne même sur une clé jamais vue
# auparavant — pas besoin d'écrire
#     if key not in counter:
#         counter[key] = 0
#     counter[key] += 1
# à chaque fois, comme on devrait le faire avec un dict ordinaire.
#
# On en a besoin trois fois dans ce script : pour compter combien
# d'événements il y a de chaque `type`, combien d'événements chaque acteur
# a produits, et combien d'événements chaque dépôt a reçus.
# ---------------------------------------------------------------------
from collections import Counter
from pathlib import Path

# Même technique de construction de Path que DEFAULT_FILE dans
# peek_data.py — voir la copie annotée de ce fichier pour l'explication
# complète.
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# Combien d'acteurs/dépôts les plus actifs afficher si --top n'est pas
# spécifié. 5 suffit pour repérer des tendances (par ex. « les comptes les
# plus actifs sont tous des bots ») sans surcharger le terminal.
DEFAULT_TOP = 5


# ---------------------------------------------------------------------
# def summarize(file_path: Path, top_n: int) -> None:
# Même forme à deux paramètres obligatoires que peek() (file_path,
# num_lines).
# ---------------------------------------------------------------------
def summarize(file_path: Path, top_n: int) -> None:
    # Un simple int, incrémenté une fois par ligne. Plus simple que de
    # faire un len() sur une liste de tous les événements, et cela évite
    # de garder les 69 000+ événements en mémoire juste pour les compter.
    total_events = 0

    # ---------------------------------------------------------------
    # Counter[str] : l'annotation de type se lit comme « un Counter dont
    # les clés sont des chaînes » (les valeurs sont toujours les
    # décomptes, donc des int — Counter n'a pas besoin qu'on le précise
    # séparément).
    #
    # Trois compteurs distincts, un par élément décompté :
    #   event_type_counts   clé = event["type"], par ex. "PushEvent"
    #   actor_event_counts  clé = event["actor"]["login"], par ex. "octocat"
    #   repo_event_counts   clé = event["repo"]["name"], par ex. "octocat/Hello-World"
    # ---------------------------------------------------------------
    event_type_counts: Counter[str] = Counter()
    actor_event_counts: Counter[str] = Counter()
    repo_event_counts: Counter[str] = Counter()

    # ---------------------------------------------------------------
    # Même schéma `with open(..., "r", encoding="utf-8") as f:` que
    # peek() — voir la copie annotée de peek_data.py pour comprendre
    # pourquoi le mode texte et l'UTF-8 explicite sont les bons choix
    # ici.
    #
    # La différence clé avec peek() : il n'y a AUCUN `if i >= num_lines:
    # break` ici. peek() s'arrête volontairement tôt car il ne veut
    # qu'une poignée d'événements d'exemple ; summarize() lit volontairement
    # chaque ligne, une par une, car un décompte ou un pourcentage calculé
    # sur seulement les premières centaines d'événements ne représenterait
    # pas le fichier entier.
    # ---------------------------------------------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        # Pas besoin d'enumerate() ici — contrairement à peek(),
        # summarize() n'affiche jamais d'index de ligne, donc la position
        # dans la boucle ne sert à rien, seul l'événement analysé compte.
        for line in f:
            event = json.loads(line)
            total_events += 1

            # ---------------------------------------------------------
            # counter[key] += 1
            #
            # C'est ici que Counter paie par rapport à un dict ordinaire :
            # la première fois qu'un type d'événement / acteur / dépôt
            # donné est rencontré, Counter traite silencieusement la clé
            # manquante comme 0, donc `+= 1` la fait passer à 1. Chaque
            # occurrence suivante ajoute simplement 1 à ce qu'elle valait
            # déjà. À la fin de la boucle, chaque Counter contient le
            # décompte complet de chaque clé distincte qu'il a rencontrée.
            # ---------------------------------------------------------
            event_type_counts[event["type"]] += 1
            actor_event_counts[event["actor"]["login"]] += 1
            repo_event_counts[event["repo"]["name"]] += 1

    print(f"Total events: {total_events}")

    # ---------------------------------------------------------------
    # len(actor_event_counts)
    #
    # Comme Counter est une sous-classe de dict, len() dessus renvoie le
    # nombre de clés DISTINCTES, pas la somme des décomptes. C'est donc
    # exactement « combien d'acteurs/dépôts uniques sont apparus dans le
    # fichier » — la somme de toutes les valeurs redonnerait simplement
    # total_events, ce qui n'est pas ce qu'on veut ici.
    # ---------------------------------------------------------------
    print(f"Unique actors: {len(actor_event_counts)}")
    print(f"Unique repos: {len(repo_event_counts)}")

    print("\nEvent types:")
    # ---------------------------------------------------------------
    # .most_common()
    #
    # Une méthode que seul Counter possède (les dict ordinaires ne l'ont
    # pas). Appelée sans argument, elle renvoie CHAQUE paire (clé,
    # décompte) sous forme de liste de tuples, triée de la plus fréquente
    # à la moins fréquente — exactement l'ordre voulu pour repérer d'un
    # coup d'œil « ce qui domine ce jeu de données ». Appelée comme
    # .most_common(n) (utilisé plus bas pour les acteurs/dépôts), elle ne
    # renvoie que les n premières paires, ce qui est plus efficace que de
    # tout trier puis découper quand on n'a besoin que de quelques
    # résultats.
    # ---------------------------------------------------------------
    for event_type, count in event_type_counts.most_common():
        pct = 100 * count / total_events

        # ---------------------------------------------------------------
        # f"{event_type:<25} {count:>7} ({pct:5.1f}%)"
        #
        # La partie après les deux-points à l'intérieur de {} est une
        # SPÉCIFICATION DE FORMAT — elle contrôle comment la valeur est
        # complétée/alignée une fois convertie en texte, pas seulement
        # quelle est la valeur.
        #   <25   alignement à gauche, complété avec des espaces jusqu'à
        #         au moins 25 caractères de large. Utilisé pour
        #         event_type afin que les nombres qui suivent s'alignent
        #         en colonne, peu importe la longueur du nom du type
        #         d'événement.
        #   >7    alignement à droite, complété jusqu'à au moins 7
        #         caractères de large. Utilisé pour count afin que les
        #         chiffres s'alignent sur leur bord droit, comme on le
        #         fait conventionnellement pour les nombres dans un
        #         tableau.
        #   5.1f  un float en VIRGULE FIXE, d'au moins 5 caractères de
        #         large au total, avec exactement 1 chiffre après la
        #         virgule (par ex. " 95.3" ou "  0.1"). Utilisé pour le
        #         pourcentage afin que chaque ligne affiche le même
        #         nombre de décimales.
        # Rien de tout cela ne change la valeur sous-jacente — seulement
        # la façon dont elle est rendue en texte.
        # ---------------------------------------------------------------
        print(f"  {event_type:<25} {count:>7} ({pct:5.1f}%)")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")


# ---------------------------------------------------------------------
# parse_args() : même schéma global que la version de peek_data.py. La
# seule chose à souligner est que --top joue le même rôle que jouait
# --lines là-bas (un simple entier positif, sans restriction `choices=`)
# — juste appliqué à « combien d'acteurs/dépôts les plus actifs afficher »
# plutôt qu'à « combien d'événements d'exemple afficher ».
# ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                         help=f"How many top actors/repos to show (default: {DEFAULT_TOP})")
    return parser.parse_args()


# main() et la garde `if __name__ == "__main__":` : but et mécanique
# identiques aux deux autres scripts — voir la copie annotée de
# download_gharchive.py pour l'explication complète.
def main() -> None:
    args = parse_args()
    summarize(args.file, args.top)


if __name__ == "__main__":
    main()
