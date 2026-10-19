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
# poignée de lignes, compter/agréger avec collections.Counter, suivre les
# partenaires DISTINCTS avec des ensembles (set) et
# collections.defaultdict, ignorer les événements de bots avec `continue`,
# et mesurer à quel point acteurs et dépôts sont connectés entre eux.
########################################################################

"""Summarize a downloaded GH Archive JSON Lines file.

Reads the full file once and reports total event count, the event type
breakdown, unique actor/repo counts, and how connected actors and repos are
to each other — a first read on data volume and connectivity before modeling
the data relationally or as a graph.

Usage:
    python scripts/summarize_data.py
    python scripts/summarize_data.py --file data/2026-08-27-15.json --top 10
    python scripts/summarize_data.py --exclude-bots
"""

# argparse, Path, json : déjà expliqués dans docs_french/download_gharchive.py
# et docs_french/peek_data.py.
import argparse
import json

# ---------------------------------------------------------------------
# from collections import Counter, defaultdict
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
#
# `defaultdict` est la même idée, généralisée : un dict où une clé absente
# est créée automatiquement avec une valeur de départ de votre choix. Ici
# on utilise defaultdict(set), donc une clé absente démarre comme un
# ENSEMBLE VIDE (voir actor_repos / repo_actors plus bas pour comprendre
# pourquoi on a besoin d'ensembles).
# ---------------------------------------------------------------------
from collections import Counter, defaultdict
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
# BOT_SUFFIX = "[bot]"
#
# Sur GitHub, les comptes automatisés créés en tant que « GitHub Apps »
# ont toujours un login qui se termine par "[bot]" (github-actions[bot],
# dependabot[bot], ...). Ce suffixe est le moyen fiable le plus simple de
# les reconnaître. Ce n'est PAS un filtre parfait : certains comptes
# automatisés ne l'utilisent pas (par ex. le login "Copilot"), donc
# --exclude-bots retire les bots officiels, pas tous les comptes
# automatisés.
# ---------------------------------------------------------------------
BOT_SUFFIX = "[bot]"


# ---------------------------------------------------------------------
# def is_bot(login: str) -> bool:
#
# Une toute petite fonction utilitaire qui répond à une seule question
# par oui ou par non. `-> bool` signifie qu'elle renvoie True ou False.
# str.endswith() vérifie si le texte se termine par le suffixe donné :
# "dependabot[bot]".endswith("[bot]") vaut True,
# "octocat".endswith("[bot]") vaut False. Placer cela dans sa propre
# fonction donne un nom à la règle : si la définition de « bot » change
# un jour, elle ne change qu'ici.
# ---------------------------------------------------------------------
def is_bot(login: str) -> bool:
    return login.endswith(BOT_SUFFIX)


# ---------------------------------------------------------------------
# def summarize(file_path: Path, top_n: int, exclude_bots: bool) -> None:
# Même forme que peek() (file_path, num_lines), plus un troisième
# paramètre : exclude_bots, un interrupteur True/False qui vient de
# l'option --exclude-bots de la ligne de commande (voir parse_args()
# plus bas).
# ---------------------------------------------------------------------
def summarize(file_path: Path, top_n: int, exclude_bots: bool) -> None:
    # Un simple int, incrémenté une fois par ligne. Plus simple que de
    # faire un len() sur une liste de tous les événements, et cela évite
    # de garder les 69 000+ événements en mémoire juste pour les compter.
    total_events = 0

    # Combien d'événements ont été ignorés parce que leur acteur est un
    # bot. N'est affiché que lorsque --exclude-bots est utilisé, pour
    # qu'on puisse voir quelle quantité de données le filtre a retirée.
    skipped_bot_events = 0

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
    # actor_repos / repo_actors : defaultdict(set)
    #
    # Les Counter ci-dessus comptent des ÉVÉNEMENTS. Mais pour un graphe,
    # la question est différente : « combien de dépôts DIFFÉRENTS cet
    # acteur a-t-il touchés ? » et « combien d'acteurs DIFFÉRENTS ont
    # touché ce dépôt ? ». Si ana fait 10 push vers le même dépôt, cela
    # fait 10 événements mais toujours un seul dépôt.
    #
    # Un ENSEMBLE (set) est une collection qui ne garde chaque élément
    # qu'une seule fois : ajouter quelque chose qui s'y trouve déjà ne
    # fait rien. Ainsi :
    #
    #     s = set()
    #     s.add("ana/app"); s.add("ana/app"); s.add("luis/web")
    #     s        # {"ana/app", "luis/web"}  -> len(s) == 2
    #
    #   actor_repos  clé = login de l'acteur, valeur = ensemble de noms de dépôts
    #   repo_actors  clé = nom du dépôt,      valeur = ensemble de logins d'acteurs
    #
    # Ces deux dict SONT le graphe acteur <-> dépôt, vu de chaque côté.
    # defaultdict(set) signifie que la première fois qu'un acteur/dépôt
    # apparaît, son ensemble vide est créé automatiquement (même
    # commodité que Counter qui démarre à 0).
    # ---------------------------------------------------------------
    actor_repos: defaultdict[str, set[str]] = defaultdict(set)
    repo_actors: defaultdict[str, set[str]] = defaultdict(set)

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
        # for line in f:
        #
        # C'est une BOUCLE : un bloc de code qui SE RÉPÈTE. À lire comme
        # « pour chaque ligne du fichier f, exécute les lignes indentées
        # ci-dessous ». Ces lignes indentées sont écrites une seule fois
        # mais s'exécutent une fois PAR LIGNE du fichier — 69 429 fois
        # pour l'heure de ce projet, une par événement. Pensez au
        # dépouillement d'une urne : on prend un bulletin, on ajoute un
        # trait à côté de son nom, on revient prendre le suivant, jusqu'à
        # ce que l'urne soit vide. Quand le fichier n'a plus de lignes, la
        # boucle se termine et Python continue avec la première ligne non
        # indentée qui suit (les print() ci-dessous).
        #
        # Pas besoin d'enumerate() ici — contrairement à peek(),
        # summarize() n'affiche jamais d'index de ligne, donc la position
        # dans la boucle ne sert à rien, seul l'événement analysé compte.
        for line in f:
            event = json.loads(line)

            # On extrait les deux noms une seule fois et on leur donne
            # des noms de variables courts, puisque chacun est utilisé
            # plusieurs fois ci-dessous.
            actor = event["actor"]["login"]
            repo = event["repo"]["name"]

            # ---------------------------------------------------------
            # if exclude_bots and is_bot(actor): ... continue
            #
            # `continue` signifie « ignore le reste du corps de la
            # boucle pour CETTE ligne et passe directement à la
            # suivante ». À comparer avec le `break` de peek_data.py,
            # qui quitte complètement la boucle :
            #   break     -> arrêter complètement la lecture du fichier
            #   continue  -> ignorer cet événement-là, continuer à lire
            # Un événement de bot est donc compté dans
            # skipped_bot_events puis n'atteint jamais les compteurs
            # ci-dessous. Sans --exclude-bots, exclude_bots vaut False,
            # toute la condition vaut False, et chaque événement passe
            # comme avant.
            # ---------------------------------------------------------
            if exclude_bots and is_bot(actor):
                skipped_bot_events += 1
                continue
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
            actor_event_counts[actor] += 1
            repo_event_counts[repo] += 1

            # On enregistre la connexion dans les deux sens. Comme ce
            # sont des ensembles, des événements répétés entre le même
            # acteur et le même dépôt n'ajoutent pas de doublons — seuls
            # les NOUVEAUX partenaires agrandissent l'ensemble.
            actor_repos[actor].add(repo)
            repo_actors[repo].add(actor)

    if exclude_bots:
        print(f"Bot events excluded: {skipped_bot_events}")
    print(f"Total events: {total_events}")

    # ---------------------------------------------------------------
    # len(actor_event_counts)
    #
    # Comme Counter est une sous-classe de dict, len() dessus renvoie le
    # nombre de clés DISTINCTES, pas la somme des décomptes. C'est donc
    # exactement « combien d'acteurs/dépôts uniques sont apparus dans le
    # fichier » — la somme de toutes les valeurs redonnerait simplement
    # total_events, ce qui n'est pas ce qu'on veut ici.
    #
    # Exemple concret : si le fichier ne contenait que 6 événements, faits
    # par les acteurs ana, luis, ana, marta, ana, luis (dans cet ordre),
    # la boucle ci-dessus laisserait
    #
    #     actor_event_counts == Counter({"ana": 3, "luis": 2, "marta": 1})
    #
    # Chaque entrée a une CLÉ (le nom) et une VALEUR (combien de fois ce
    # nom est apparu). Alors :
    #
    #     len(actor_event_counts)            # 3 -> ana, luis, marta
    #     sum(actor_event_counts.values())   # 6 -> 3 + 2 + 1
    #
    # len() répond à « combien d'acteurs DIFFÉRENTS ? » (ana compte une
    # seule fois, même avec 3 événements). La somme répond à « combien
    # d'événements ? » — et comme chaque événement a exactement un
    # acteur, elle est toujours égale à total_events, donc elle ne nous
    # apprendrait rien de nouveau.
    #
    # « Sous-classe de dict » veut simplement dire que Counter EST un
    # dictionnaire avec des fonctionnalités en plus (.most_common(), les
    # clés absentes qui valent 0). Donc tout ce qui marche sur un dict
    # ordinaire — comme len() qui compte ses clés — marche exactement
    # de la même façon sur un Counter.
    # ---------------------------------------------------------------
    print(f"Unique actors: {len(actor_event_counts)}")
    print(f"Unique repos: {len(repo_event_counts)}")

    print("\nEvent types:")
    # ---------------------------------------------------------------
    # type_width = max(len(event_type) for event_type in event_type_counts)
    #
    # La largeur de la colonne des types d'événements, calculée à partir
    # des données au lieu d'être fixe. Une version précédente utilisait
    # une largeur fixe de 25, et "PullRequestReviewCommentEvent" (29
    # caractères) ne rentrait pas, ce qui décalait ses nombres. Ici on
    # mesure la longueur de chaque nom de type d'événement et on garde la
    # plus grande (max), pour que la colonne soit toujours exactement
    # assez large.
    # ---------------------------------------------------------------
    type_width = max(len(event_type) for event_type in event_type_counts)

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
        # f"{event_type:<{type_width}} {count:>7} ({pct:5.1f}%)"
        #
        # La partie après les deux-points à l'intérieur de {} est une
        # SPÉCIFICATION DE FORMAT — elle contrôle comment la valeur est
        # complétée/alignée une fois convertie en texte, pas seulement
        # quelle est la valeur.
        #   <{type_width}  alignement à gauche, complété avec des espaces
        #         jusqu'à type_width caractères. Le {type_width} intérieur
        #         est d'abord remplacé par sa valeur (par ex. 29), donc
        #         cela devient <29. Utilisé pour event_type afin que les
        #         nombres qui suivent s'alignent en colonne, peu importe
        #         la longueur du nom du type d'événement.
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
        print(f"  {event_type:<{type_width}} {count:>7} ({pct:5.1f}%)")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")

    # ---------------------------------------------------------------
    # Connectivité : peut-on vraiment PARCOURIR ce graphe ?
    #
    # Le benchmark parcourt acteur -> dépôt -> acteur -> dépôt. Chaque
    # étape d'un dépôt vers « un autre acteur » ne fonctionne que si ce
    # dépôt a été touché par au moins 2 acteurs différents ; sinon le
    # parcours est bloqué. Ces trois nombres mesurent à quelle fréquence
    # c'est possible :
    #
    #   shared_repos       dépôts avec 2+ acteurs distincts — les seuls
    #                      « ponts » d'un acteur vers un autre.
    #   multi_repo_actors  acteurs ayant touché 2+ dépôts — les seuls
    #                      acteurs à partir desquels un parcours peut
    #                      bifurquer vers un autre dépôt.
    #   connected_actors   tout acteur qui apparaît dans au moins un
    #                      dépôt partagé, c.-à-d. qui a au moins un
    #                      acteur voisin. Tous les autres sont des îles.
    #
    # Syntaxe utilisée :
    #   [x for x, y in d.items() if cond]   une COMPRÉHENSION DE LISTE :
    #       une boucle sur une ligne qui construit une liste, en ne
    #       gardant que les éléments pour lesquels cond vaut True.
    #       .items() donne des paires (clé, valeur).
    #   {a for r in shared_repos for a in repo_actors[r]}   une
    #       COMPRÉHENSION D'ENSEMBLE avec deux boucles : pour chaque
    #       dépôt partagé, on prend chaque acteur qui s'y trouve. Comme
    #       c'est un ensemble, un acteur présent dans plusieurs dépôts
    #       partagés n'est compté qu'une seule fois.
    # ---------------------------------------------------------------
    shared_repos = [repo for repo, actors in repo_actors.items() if len(actors) >= 2]
    multi_repo_actors = [actor for actor, repos in actor_repos.items() if len(repos) >= 2]
    connected_actors = {actor for repo in shared_repos for actor in repo_actors[repo]}
    num_actors = len(actor_repos)
    num_repos = len(repo_actors)

    print("\nConnectivity:")
    print(f"  Repos with 2+ distinct actors:         {len(shared_repos):>6} "
          f"({100 * len(shared_repos) / num_repos:5.1f}% of repos)")
    print(f"  Actors who touched 2+ repos:           {len(multi_repo_actors):>6} "
          f"({100 * len(multi_repo_actors) / num_actors:5.1f}% of actors)")
    print(f"  Actors sharing a repo with another one: {len(connected_actors):>5} "
          f"({100 * len(connected_actors) / num_actors:5.1f}% of actors)")

    # ---------------------------------------------------------------
    # repos_per_actor = Counter({actor: len(repos) for ...})
    #
    # {k: v for ...} est une COMPRÉHENSION DE DICT : une boucle sur une
    # ligne qui construit un dict. Ici, elle transforme « acteur ->
    # ensemble de dépôts » en « acteur -> COMBIEN de dépôts ». L'envelopper
    # dans Counter(...) sert simplement à pouvoir réutiliser
    # .most_common(top_n) pour obtenir les premiers, triés.
    #
    # Ce classement compte davantage que « le plus d'événements » : un
    # compte qui touche des centaines de dépôts DIFFÉRENTS joue le rôle
    # de plaque tournante reliant des parties du graphe qui seraient
    # sinon sans rapport — et c'est exactement ce que font des bots comme
    # github-actions[bot].
    # ---------------------------------------------------------------
    repos_per_actor = Counter({actor: len(repos) for actor, repos in actor_repos.items()})
    print(f"\nTop {top_n} actors by distinct repos touched:")
    for actor, count in repos_per_actor.most_common(top_n):
        print(f"  {actor:<30} {count:>5} repos")

    # Même idée du côté des dépôts : les dépôts qui ont le plus d'acteurs
    # distincts sont les « points de rencontre » les plus fréquentés du
    # graphe.
    actors_per_repo = Counter({repo: len(actors) for repo, actors in repo_actors.items()})
    print(f"\nTop {top_n} repos by distinct actors:")
    for repo, count in actors_per_repo.most_common(top_n):
        print(f"  {repo:<40} {count:>5} actors")


# ---------------------------------------------------------------------
# parse_args() : même schéma global que la version de peek_data.py. Deux
# choses méritent d'être soulignées :
#
#   --top joue le même rôle que jouait --lines là-bas (un simple entier
#   positif, sans restriction `choices=`) — juste appliqué à « combien
#   d'acteurs/dépôts les plus actifs afficher » plutôt qu'à « combien
#   d'événements d'exemple afficher ».
#
#   action="store_true" (pour --exclude-bots)
#     Un DRAPEAU (flag) : une option qui ne prend pas de valeur. Si vous
#     écrivez --exclude-bots sur la ligne de commande, args.exclude_bots
#     vaut True ; si vous l'omettez, il vaut False. argparse transforme
#     aussi le tiret en tiret bas (--exclude-bots -> args.exclude_bots),
#     car un tiret n'est pas autorisé dans un nom de variable Python.
# ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--top", type=int, default=DEFAULT_TOP,
                         help=f"How many top actors/repos to show (default: {DEFAULT_TOP})")
    parser.add_argument("--exclude-bots", action="store_true",
                         help=f"Skip events whose actor login ends with '{BOT_SUFFIX}'")
    return parser.parse_args()


# main() et la garde `if __name__ == "__main__":` : but et mécanique
# identiques aux deux autres scripts — voir la copie annotée de
# download_gharchive.py pour l'explication complète.
def main() -> None:
    args = parse_args()
    summarize(args.file, args.top, args.exclude_bots)


if __name__ == "__main__":
    main()
