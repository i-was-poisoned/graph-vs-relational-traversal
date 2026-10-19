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
# collections.defaultdict, regrouper tous ces décomptes dans une CLASSE
# pour pouvoir exécuter la même analyse deux fois (avec et sans bots), et
# mesurer à quel point acteurs et dépôts sont connectés entre eux.
#
# La sortie comporte trois sections :
#   1. GENERAL                 totaux, répartis entre bots et non-bots
#   2. ANALYSIS WITH BOTS      tous les événements
#   3. ANALYSIS WITHOUT BOTS   la même analyse, sans les événements de bots
# Les sections 2 et 3 affichent exactement les mêmes choses, pour qu'on
# puisse les comparer côte à côte.
########################################################################

"""Summarize a downloaded GH Archive JSON Lines file.

Reads the full file once and reports, in three sections: general totals
(split into bot and non-bot), then the same analysis twice — with bots and
without bots — covering the event type breakdown, the most active actors and
repos, and how connected actors and repos are to each other. A first read on
data volume and connectivity before modeling the data relationally or as a
graph.

Usage:
    python scripts/summarize_data.py
    python scripts/summarize_data.py --file data/2026-08-27-15.json --top 10
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
# On en a besoin trois fois dans chaque analyse : pour compter combien
# d'événements il y a de chaque `type`, combien d'événements chaque acteur
# a produits, et combien d'événements chaque dépôt a reçus.
#
# `defaultdict` est la même idée, généralisée : un dict où une clé absente
# est créée automatiquement avec une valeur de départ de votre choix. Ici
# on utilise defaultdict(set), donc une clé absente démarre comme un
# ENSEMBLE VIDE (voir actor_repos / repo_actors dans la classe Stats pour
# comprendre pourquoi on a besoin d'ensembles).
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
# l'analyse « sans bots » retire les bots officiels, pas tous les comptes
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
# class Stats:
#
# On veut exécuter la MÊME analyse deux fois : une fois sur tous les
# événements, une fois sur les événements non-bots uniquement. Il faut
# donc deux jeux de compteurs complets et séparés. Au lieu de créer six
# compteurs avec des noms en « _all » et six autres avec des noms en
# « _non_bot », on définit une CLASSE : un modèle qui dit « un objet
# Stats contient ces six compteurs, et sait comment y ajouter un
# événement ». Ensuite, on crée deux objets à partir du même modèle :
#
#     all_events = Stats()     # un jeu complet de compteurs
#     non_bot = Stats()        # un autre, complètement séparé
#
# Voyez la classe comme un formulaire vierge, et chaque objet comme un
# exemplaire rempli de ce formulaire.
#
# La ligne """...""" sous `class Stats:` est une DOCSTRING — le même
# genre de description que celle en haut de ce fichier, mais pour la
# classe.
# ---------------------------------------------------------------------
class Stats:
    """All the counts for one group of events (e.g. all events, or non-bot events only)."""

    # -----------------------------------------------------------------
    # def __init__(self) -> None:
    #
    # __init__ est une méthode spéciale que Python exécute
    # automatiquement chaque fois qu'un nouvel objet est créé avec
    # Stats(). Son rôle est de mettre en place les valeurs de départ de
    # l'objet.
    #
    # `self` est l'objet en cours de mise en place. `self.total_events =
    # 0` signifie « cet objet a son propre total_events, qui démarre à
    # 0 ». Comme chaque objet a son propre `self`,
    # all_events.total_events et non_bot.total_events sont deux nombres
    # différents.
    # -----------------------------------------------------------------
    def __init__(self) -> None:
        # Un simple int, incrémenté une fois par événement. Plus simple
        # que de faire un len() sur une liste de tous les événements, et
        # cela évite de garder les 69 000+ événements en mémoire juste
        # pour les compter.
        self.total_events = 0

        # -------------------------------------------------------------
        # Counter[str] : l'annotation de type se lit comme « un Counter
        # dont les clés sont des chaînes » (les valeurs sont toujours les
        # décomptes, donc des int — Counter n'a pas besoin qu'on le
        # précise séparément).
        #
        # Trois compteurs distincts, un par élément décompté :
        #   event_type_counts   clé = event["type"], par ex. "PushEvent"
        #   actor_event_counts  clé = event["actor"]["login"], par ex. "octocat"
        #   repo_event_counts   clé = event["repo"]["name"], par ex. "octocat/Hello-World"
        # -------------------------------------------------------------
        self.event_type_counts: Counter[str] = Counter()
        self.actor_event_counts: Counter[str] = Counter()
        self.repo_event_counts: Counter[str] = Counter()

        # -------------------------------------------------------------
        # actor_repos / repo_actors : defaultdict(set)
        #
        # Les Counter ci-dessus comptent des ÉVÉNEMENTS. Mais pour un
        # graphe, la question est différente : « dans combien de dépôts
        # DIFFÉRENTS cet acteur a-t-il fait des événements ? » et
        # « combien d'acteurs DIFFÉRENTS ont fait des événements dans ce
        # dépôt ? ». Si ana fait 10 push vers le même dépôt, cela fait
        # 10 événements mais toujours un seul dépôt.
        #
        # Un ENSEMBLE (set) est une collection qui ne garde chaque
        # élément qu'une seule fois : ajouter quelque chose qui s'y
        # trouve déjà ne fait rien. Ainsi :
        #
        #     s = set()
        #     s.add("ana/app"); s.add("ana/app"); s.add("luis/web")
        #     s        # {"ana/app", "luis/web"}  -> len(s) == 2
        #
        #   actor_repos  clé = login de l'acteur, valeur = ensemble de noms de dépôts
        #   repo_actors  clé = nom du dépôt,      valeur = ensemble de logins d'acteurs
        #
        # Ces deux dict SONT le graphe acteur <-> dépôt, vu de chaque
        # côté. defaultdict(set) signifie que la première fois qu'un
        # acteur/dépôt apparaît, son ensemble vide est créé
        # automatiquement (même commodité que Counter qui démarre à 0).
        # -------------------------------------------------------------
        self.actor_repos: defaultdict[str, set[str]] = defaultdict(set)
        self.repo_actors: defaultdict[str, set[str]] = defaultdict(set)

    # -----------------------------------------------------------------
    # def add(self, event_type, actor, repo) -> None:
    #
    # Une MÉTHODE : une fonction qui appartient à la classe et qui agit
    # sur les compteurs propres à un objet (via `self`). Appeler
    # all_events.add("PushEvent", "ana", "ana/app") ne met à jour que
    # les compteurs de all_events ; ceux de non_bot restent intacts.
    # -----------------------------------------------------------------
    def add(self, event_type: str, actor: str, repo: str) -> None:
        self.total_events += 1

        # -------------------------------------------------------------
        # counter[key] += 1
        #
        # C'est ici que Counter paie par rapport à un dict ordinaire :
        # la première fois qu'un type d'événement / acteur / dépôt
        # donné est rencontré, Counter traite silencieusement la clé
        # manquante comme 0, donc `+= 1` la fait passer à 1. Chaque
        # occurrence suivante ajoute simplement 1 à ce qu'elle valait
        # déjà. À la fin de la boucle, chaque Counter contient le
        # décompte complet de chaque clé distincte qu'il a rencontrée.
        # -------------------------------------------------------------
        self.event_type_counts[event_type] += 1
        self.actor_event_counts[actor] += 1
        self.repo_event_counts[repo] += 1

        # On enregistre la connexion dans les deux sens. Comme ce sont
        # des ensembles, des événements répétés entre le même acteur et
        # le même dépôt n'ajoutent pas de doublons — seuls les NOUVEAUX
        # partenaires agrandissent l'ensemble.
        self.actor_repos[actor].add(repo)
        self.repo_actors[repo].add(actor)


# ---------------------------------------------------------------------
# def pct(part: int, whole: int) -> str:
#
# Transforme « part sur whole » en pourcentage, déjà mis en forme sous
# forme de texte (par ex. pct(1970, 69429) -> "  2.8%"). Le script
# affiche des pourcentages à de nombreux endroits ; écrire la formule
# une seule fois ici garantit que chaque pourcentage est calculé et mis
# en forme de la même façon. `5.1f` est expliqué plus bas, dans la
# boucle des types d'événements.
# ---------------------------------------------------------------------
def pct(part: int, whole: int) -> str:
    return f"{100 * part / whole:5.1f}%"


# ---------------------------------------------------------------------
# def print_header(title: str) -> None:
#
# Affiche un titre de section entre deux lignes de signes "=", pour que
# les trois sections soient faciles à distinguer dans le terminal.
# "=" * 70 répète le caractère "=" 70 fois ; "\n" est un saut de ligne,
# qui laisse une ligne vide avant chaque section.
# ---------------------------------------------------------------------
def print_header(title: str) -> None:
    print("\n" + "=" * 70)
    print(title)
    print("=" * 70)


# ---------------------------------------------------------------------
# def print_general(all_events: Stats, non_bot: Stats) -> None:
#
# SECTION 1 : la vue d'ensemble. Elle n'a pas besoin d'un décompte
# séparé des bots — elle les obtient par SOUSTRACTION : tout moins les
# non-bots = les bots.
#   événements de bots = tous les événements - événements non-bots
#   acteurs bots       = tous les acteurs    - acteurs non-bots
#   dépôts bots seuls  = tous les dépôts - dépôts où au moins 1 non-bot
#                        a fait un événement (dépôts touchés UNIQUEMENT
#                        par des bots)
#
# `:>7` aligne chaque nombre à droite dans une colonne de 7 caractères,
# pour que les nombres s'alignent (même idée de spécification de format
# que dans la boucle des types d'événements plus bas).
# ---------------------------------------------------------------------
def print_general(all_events: Stats, non_bot: Stats) -> None:
    total = all_events.total_events
    bot_events = total - non_bot.total_events

    # -----------------------------------------------------------------
    # len(all_events.actor_event_counts)
    #
    # Comme Counter est une sous-classe de dict, len() dessus renvoie le
    # nombre de clés DISTINCTES, pas la somme des décomptes. C'est donc
    # exactement « combien d'acteurs/dépôts uniques sont apparus dans le
    # fichier » — la somme de toutes les valeurs redonnerait simplement
    # total_events, ce qui n'est pas ce qu'on veut ici.
    #
    # Exemple concret : si le fichier ne contenait que 6 événements, faits
    # par les acteurs ana, luis, ana, marta, ana, luis (dans cet ordre),
    # la boucle laisserait
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
    # -----------------------------------------------------------------
    num_actors = len(all_events.actor_event_counts)
    non_bot_actors = len(non_bot.actor_event_counts)
    num_repos = len(all_events.repo_event_counts)
    non_bot_repos = len(non_bot.repo_event_counts)

    print_header("GENERAL")
    print(f"Total events:     {total:>7}")
    print(f"  Bot events:     {bot_events:>7} ({pct(bot_events, total)})")
    print(f"  Non-bot events: {non_bot.total_events:>7} ({pct(non_bot.total_events, total)})")
    print(f"Unique actors:    {num_actors:>7}")
    print(f"  Bot actors:     {num_actors - non_bot_actors:>7} "
          f"({pct(num_actors - non_bot_actors, num_actors)})")
    print(f"  Non-bot actors: {non_bot_actors:>7} ({pct(non_bot_actors, num_actors)})")
    print(f"Unique repos:     {num_repos:>7}")
    print(f"  Only bots made events in it:     {num_repos - non_bot_repos:>7} "
          f"({pct(num_repos - non_bot_repos, num_repos)})")
    print(f"  At least 1 non-bot made events:  {non_bot_repos:>7} "
          f"({pct(non_bot_repos, num_repos)})")


# ---------------------------------------------------------------------
# def print_analysis(title: str, stats: Stats, top_n: int) -> None:
#
# SECTIONS 2 et 3. Cette seule fonction affiche toute l'analyse pour
# l'objet Stats qu'on lui donne, quel qu'il soit. summarize() l'appelle
# deux fois : une fois avec all_events, une fois avec non_bot. Comme
# c'est le même code les deux fois, les deux sections affichent
# forcément exactement les mêmes choses dans le même ordre — c'est ce
# qui les rend comparables.
# ---------------------------------------------------------------------
def print_analysis(title: str, stats: Stats, top_n: int) -> None:
    print_header(title)

    print("Event types:")
    # -----------------------------------------------------------------
    # type_width = max(len(event_type) for event_type in stats.event_type_counts)
    #
    # La largeur de la colonne des types d'événements, calculée à partir
    # des données au lieu d'être fixe. Une version précédente utilisait
    # une largeur fixe de 25, et "PullRequestReviewCommentEvent" (29
    # caractères) ne rentrait pas, ce qui décalait ses nombres. Ici on
    # mesure la longueur de chaque nom de type d'événement et on garde la
    # plus grande (max), pour que la colonne soit toujours exactement
    # assez large.
    # -----------------------------------------------------------------
    type_width = max(len(event_type) for event_type in stats.event_type_counts)

    # -----------------------------------------------------------------
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
    # -----------------------------------------------------------------
    for event_type, count in stats.event_type_counts.most_common():
        # -------------------------------------------------------------
        # f"{event_type:<{type_width}} {count:>7} ({pct(...)})"
        #
        # La partie après les deux-points à l'intérieur de {} est une
        # SPÉCIFICATION DE FORMAT — elle contrôle comment la valeur est
        # complétée/alignée une fois convertie en texte, pas seulement
        # quelle est la valeur.
        #   <{type_width}  alignement à gauche, complété avec des
        #         espaces jusqu'à type_width caractères. Le {type_width}
        #         intérieur est d'abord remplacé par sa valeur (par ex.
        #         29), donc cela devient <29. Utilisé pour event_type
        #         afin que les nombres qui suivent s'alignent en
        #         colonne, peu importe la longueur du nom du type
        #         d'événement.
        #   >7    alignement à droite, complété jusqu'à au moins 7
        #         caractères de large. Utilisé pour count afin que les
        #         chiffres s'alignent sur leur bord droit, comme on le
        #         fait conventionnellement pour les nombres dans un
        #         tableau.
        #   5.1f  (dans pct()) un float en VIRGULE FIXE, d'au moins 5
        #         caractères de large au total, avec exactement 1
        #         chiffre après la virgule (par ex. " 95.3" ou "  0.1").
        #         Utilisé pour le pourcentage afin que chaque ligne
        #         affiche le même nombre de décimales.
        # Rien de tout cela ne change la valeur sous-jacente — seulement
        # la façon dont elle est rendue en texte.
        # -------------------------------------------------------------
        print(f"  {event_type:<{type_width}} {count:>7} ({pct(count, stats.total_events)})")

    print(f"\nTop {top_n} most active actors:")
    for actor, count in stats.actor_event_counts.most_common(top_n):
        print(f"  {actor:<30} {count:>5} events")

    print(f"\nTop {top_n} most active repos:")
    for repo, count in stats.repo_event_counts.most_common(top_n):
        print(f"  {repo:<40} {count:>5} events")

    # -----------------------------------------------------------------
    # Connectivité : peut-on vraiment PARCOURIR ce graphe ?
    #
    # Le benchmark parcourt acteur -> dépôt -> acteur -> dépôt. Chaque
    # étape d'un dépôt vers « un autre acteur » ne fonctionne que si ce
    # dépôt a reçu des événements d'au moins 2 acteurs différents ;
    # sinon le parcours est bloqué. Ces trois nombres mesurent à quelle
    # fréquence c'est possible :
    #
    #   shared_repos       dépôts avec 2+ acteurs différents — les seuls
    #                      « ponts » d'un acteur vers un autre.
    #   multi_repo_actors  acteurs ayant fait des événements dans 2+
    #                      dépôts — les seuls acteurs à partir desquels
    #                      un parcours peut bifurquer vers un autre
    #                      dépôt.
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
    # -----------------------------------------------------------------
    shared_repos = [repo for repo, actors in stats.repo_actors.items() if len(actors) >= 2]
    multi_repo_actors = [actor for actor, repos in stats.actor_repos.items() if len(repos) >= 2]
    connected_actors = {actor for repo in shared_repos for actor in stats.repo_actors[repo]}
    num_actors = len(stats.actor_repos)
    num_repos = len(stats.repo_actors)

    print("\nConnectivity:")
    print(f"  Repos with 2+ different actors:           {len(shared_repos):>6} "
          f"({pct(len(shared_repos), num_repos)} of repos)")
    print(f"  Actors who made events in 2+ repos:       {len(multi_repo_actors):>6} "
          f"({pct(len(multi_repo_actors), num_actors)} of actors)")
    print(f"  Actors sharing a repo with another actor: {len(connected_actors):>6} "
          f"({pct(len(connected_actors), num_actors)} of actors)")

    # -----------------------------------------------------------------
    # repos_per_actor = Counter({actor: len(repos) for ...})
    #
    # {k: v for ...} est une COMPRÉHENSION DE DICT : une boucle sur une
    # ligne qui construit un dict. Ici, elle transforme « acteur ->
    # ensemble de dépôts » en « acteur -> COMBIEN de dépôts différents ».
    # L'envelopper dans Counter(...) sert simplement à pouvoir
    # réutiliser .most_common(top_n) pour obtenir les premiers, triés.
    #
    # Ce classement compte davantage que « le plus d'événements » : un
    # compte qui fait des événements dans des centaines de dépôts
    # DIFFÉRENTS joue le rôle de plaque tournante reliant des parties du
    # graphe qui seraient sinon sans rapport — et c'est exactement ce que
    # font des bots comme github-actions[bot].
    # -----------------------------------------------------------------
    repos_per_actor = Counter({actor: len(repos) for actor, repos in stats.actor_repos.items()})
    print(f"\nTop {top_n} actors by number of different repos they made events in:")
    for actor, count in repos_per_actor.most_common(top_n):
        print(f"  {actor:<30} {count:>5} different repos")

    # Même idée du côté des dépôts : les dépôts qui ont le plus d'acteurs
    # différents sont les « points de rencontre » les plus fréquentés du
    # graphe.
    actors_per_repo = Counter({repo: len(actors) for repo, actors in stats.repo_actors.items()})
    print(f"\nTop {top_n} repos by number of different actors who made events in them:")
    for repo, count in actors_per_repo.most_common(top_n):
        print(f"  {repo:<40} {count:>5} different actors")


# ---------------------------------------------------------------------
# def summarize(file_path: Path, top_n: int) -> None:
# Même forme à deux paramètres obligatoires que peek() (file_path,
# num_lines). Elle lit le fichier UNE SEULE FOIS, remplit deux objets
# Stats en même temps, puis affiche les trois sections.
# ---------------------------------------------------------------------
def summarize(file_path: Path, top_n: int) -> None:
    all_events = Stats()
    non_bot = Stats()

    # -----------------------------------------------------------------
    # Même schéma `with open(..., "r", encoding="utf-8") as f:` que
    # peek() — voir la copie annotée de peek_data.py pour comprendre
    # pourquoi le mode texte et l'UTF-8 explicite sont les bons choix
    # ici.
    #
    # La différence clé avec peek() : il n'y a AUCUN `if i >= num_lines:
    # break` ici. peek() s'arrête volontairement tôt car il ne veut
    # qu'une poignée d'événements d'exemple ; summarize() lit
    # volontairement chaque ligne, une par une, car un décompte ou un
    # pourcentage calculé sur seulement les premières centaines
    # d'événements ne représenterait pas le fichier entier.
    # -----------------------------------------------------------------
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
        # indentée qui suit (les appels print_...() ci-dessous).
        #
        # Pas besoin d'enumerate() ici — contrairement à peek(),
        # summarize() n'affiche jamais d'index de ligne, donc la position
        # dans la boucle ne sert à rien, seul l'événement analysé compte.
        for line in f:
            event = json.loads(line)

            # On extrait les trois valeurs une seule fois et on leur
            # donne des noms de variables courts, puisque chacune est
            # utilisée deux fois ci-dessous.
            event_type = event["type"]
            actor = event["actor"]["login"]
            repo = event["repo"]["name"]

            # ---------------------------------------------------------
            # Chaque événement va dans all_events. Seuls les événements
            # non-bots vont AUSSI dans non_bot. Donc, après la boucle :
            #   all_events  = les décomptes AVEC les bots
            #   non_bot     = les décomptes SANS les bots
            # Les deux viennent d'un seul passage sur le fichier — pas
            # besoin de lire les 69 000 lignes deux fois.
            # ---------------------------------------------------------
            all_events.add(event_type, actor, repo)
            if not is_bot(actor):
                non_bot.add(event_type, actor, repo)

    print_general(all_events, non_bot)
    print_analysis("ANALYSIS WITH BOTS (all events)", all_events, top_n)
    print_analysis(f"ANALYSIS WITHOUT BOTS (logins ending in '{BOT_SUFFIX}' removed)",
                   non_bot, top_n)


# ---------------------------------------------------------------------
# parse_args() : même schéma global que la version de peek_data.py. La
# seule chose qui mérite d'être soulignée est que --top joue le même
# rôle que jouait --lines là-bas (un simple entier positif, sans
# restriction `choices=`) — juste appliqué à « combien d'acteurs/dépôts
# les plus actifs afficher » plutôt qu'à « combien d'événements
# d'exemple afficher ».
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
