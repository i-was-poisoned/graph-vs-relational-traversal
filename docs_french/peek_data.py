########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de scripts/peek_data.py.
# Il n'est PAS destiné à être exécuté dans le cadre du pipeline du projet — il se
# trouve dans docs_french/ car son but est d'enseigner, pas de s'exécuter. Le
# script réel et « propre » (sans tous ces commentaires) est
# scripts/peek_data.py.
#
# Ce fichier suppose que vous avez déjà lu docs_french/download_gharchive.py —
# les fondamentaux qui y sont expliqués (docstrings, imports, Path,
# annotations de type, f-strings, argparse, main(), la garde __name__) ne
# sont PAS réexpliqués depuis zéro ici. Ce fichier se concentre sur ce qui
# est NOUVEAU dans peek_data.py.
########################################################################

"""Peek at the first few events in a downloaded GH Archive JSON Lines file.

Usage:
    python scripts/peek_data.py
    python scripts/peek_data.py --file data/2026-08-27-15.json --lines 10
"""

# argparse, Path : déjà expliqués dans docs_french/download_gharchive.py.
import argparse

# json : le module de la bibliothèque standard pour convertir entre du
# texte JSON et des objets Python. `json.loads(text)` (« load string »)
# analyse une chaîne de caractères au format JSON en valeurs Python — un
# objet JSON comme {"a": 1} devient un dict Python, un tableau JSON devient
# une list Python, et ainsi de suite. C'est exactement ce dont on a besoin
# ici : chaque ligne du fichier de données est un objet JSON sous forme de
# texte, et on veut l'obtenir comme un dict Python dont on peut extraire
# des champs.
#
# (Comparez `json.loads` avec `json.load` — sans « s » — qui lit
# directement depuis un fichier déjà ouvert plutôt que depuis une chaîne.
# On utilise `loads` ici car on traite une ligne de texte déjà lue à la
# fois, et non un objet fichier entier.)
import json

from pathlib import Path

# ---------------------------------------------------------------------
# DEFAULT_FILE : la même technique de construction de Path que DATA_DIR
# dans download_gharchive.py — calculé à partir de l'emplacement propre
# de ce script (__file__), en remontant jusqu'à la racine du projet
# (.parent.parent), puis en descendant dans data/2026-08-27-15.json. Cela
# code en dur le fichier de jeu de données spécifique que ce projet
# utilise comme cible par défaut à examiner, tout en laissant --file la
# remplacer pour une heure téléchargée différente.
# ---------------------------------------------------------------------
DEFAULT_FILE = Path(__file__).resolve().parent.parent / "data" / "2026-08-27-15.json"

# Combien d'événements afficher si --lines n'est pas spécifié. Gardé petit
# (5) puisque cette fonction sert à une vérification rapide de cohérence,
# pas à la lecture du fichier entier.
DEFAULT_LINES = 5


# ---------------------------------------------------------------------
# def peek(file_path: Path, num_lines: int) -> None:
# Deux paramètres, tous deux obligatoires (pas de valeurs par défaut ici,
# contrairement au data_dir de download()) — cette fonction a toujours
# besoin qu'on lui indique explicitement quel fichier lire et combien de
# lignes afficher.
# ---------------------------------------------------------------------
def peek(file_path: Path, num_lines: int) -> None:
    # ---------------------------------------------------------------
    # open(file_path, "r", encoding="utf-8") :
    #   "r"                mode « lecture », et — contrairement aux
    #                      "rb"/"wb" (modes binaires) de
    #                      download_gharchive.py — le simple "r" ici
    #                      signifie mode TEXTE : Python décode
    #                      automatiquement les octets bruts du disque en
    #                      un str Python au fur et à mesure de la lecture,
    #                      en utilisant l'encodage donné. Le mode binaire
    #                      convenait à download_gharchive.py car on ne
    #                      faisait que relayer des octets inchangés ; ici,
    #                      on veut réellement interpréter le contenu comme
    #                      du texte (plus précisément, comme du JSON), donc
    #                      le mode texte est correct.
    #   encoding="utf-8"    les fichiers JSON Lines (et le JSON en général)
    #                      sont quasi universellement encodés en UTF-8.
    #                      Être explicite sur l'encodage, plutôt que de se
    #                      fier à ce que le système d'exploitation utilise
    #                      par défaut, évite des bugs subtils où le même
    #                      fichier pourrait être lu différemment sur des
    #                      machines différentes (par ex. Windows utilise
    #                      parfois par défaut un encodage différent de
    #                      macOS/Linux).
    #
    # Tout comme download_gharchive.py, ceci utilise un bloc `with` afin
    # que le fichier soit fermé automatiquement et de façon fiable une
    # fois le travail terminé.
    # ---------------------------------------------------------------
    with open(file_path, "r", encoding="utf-8") as f:
        # ---------------------------------------------------------------
        # for i, line in enumerate(f):
        #
        # Un simple `for line in f:` bouclerait déjà sur le fichier une
        # ligne à la fois (c'est l'une des propriétés les plus utiles d'un
        # objet fichier ouvert en Python — il est directement itérable
        # ligne par ligne, donc on n'a jamais besoin d'appeler
        # manuellement f.readline() dans une boucle). Mais on veut aussi
        # savoir SUR QUELLE ligne on se trouve, pour afficher quelque
        # chose comme « [0] », « [1] », « [2] » et savoir quand s'arrêter.
        #
        # enumerate(f) enveloppe cette même itération ligne par ligne,
        # mais au lieu de simplement rendre chaque `line`, elle rend une
        # paire : (index, line) — l'index commençant à 0 par défaut.
        # Écrire `for i, line in enumerate(f):` déballe directement cette
        # paire dans deux variables séparées, `i` (la position, 0, 1,
        # 2, ...) et `line` (le texte réel de cette ligne).
        # ---------------------------------------------------------------
        for i, line in enumerate(f):
            # S'arrête une fois le nombre de lignes demandé affiché. Sans
            # cela, la boucle continuerait à parcourir la TOTALITÉ du
            # fichier (qui pourrait compter des dizaines de milliers de
            # lignes) alors qu'on voulait seulement en examiner quelques-unes.
            if i >= num_lines:
                break

            # Analyse cette seule ligne de texte (un unique objet JSON,
            # par ex. {"type": "PushEvent", "actor": {...}, ...}) en un
            # dict Python, afin de pouvoir accéder à ses champs avec des
            # recherches entre crochets ci-dessous.
            event = json.loads(line)

            # ---------------------------------------------------------------
            # Affichage des champs qui nous intéressent.
            #
            # event['type']              une recherche dans un dict :
            #                            'type' est une clé de l'objet
            #                            JSON de premier niveau, par ex.
            #                            "PushEvent".
            # event['actor']['login']     une recherche IMBRIQUÉE : 'actor'
            #                            est lui-même un dict (un objet à
            #                            l'intérieur de l'objet), et
            #                            'login' est une clé à l'intérieur
            #                            de CE dict imbriqué — cela reflète
            #                            la structure JSON imbriquée
            #                            montrée dans gh-archive-guide.md
            #                            (la forme "actor": {"login": ...}).
            # event['repo']['name']       même idée de recherche imbriquée,
            #                            en accédant au sous-objet 'repo'.
            # event['created_at']         à nouveau une simple recherche de
            #                            premier niveau.
            #
            # Le `!r` à l'intérieur de chaque emplacement de f-string (par
            # ex. {event['type']!r}) demande la « repr » (représentation)
            # de la valeur plutôt que sa forme de chaîne ordinaire. Pour
            # les chaînes, cela entoure la valeur de guillemets dans la
            # sortie (par ex. 'PushEvent' au lieu de PushEvent), ce qui
            # rend visuellement non ambiguë la frontière entre la valeur
            # d'un champ et le libellé du champ suivant en parcourant la
            # sortie affichée.
            #
            # Cet unique appel à print() est réparti sur quatre lignes dans
            # le code source grâce à la concaténation implicite de
            # chaînes — Python joint automatiquement des littéraux de
            # chaîne adjacents qui apparaissent l'un à côté de l'autre
            # sans rien d'autre que des espaces/retours à la ligne entre
            # eux, donc il s'agit en réalité d'une seule longue f-string
            # écrite sur plusieurs lignes pour plus de lisibilité.
            # ---------------------------------------------------------------
            print(f"[{i}] type={event['type']!r} "
                  f"actor={event['actor']['login']!r} "
                  f"repo={event['repo']['name']!r} "
                  f"created_at={event['created_at']!r}")


# ---------------------------------------------------------------------
# parse_args() : même schéma global que la version de
# download_gharchive.py, avec deux différences à souligner :
#
#   type=Path (pour --file)
#     Idée clé : tout ce que vous tapez dans le terminal arrive à Python
#     sous forme de TEXTE (une str). Si vous exécutez
#
#         python scripts/peek_data.py --file data/2026-08-27-15.json --lines 10
#
#     Python reçoit "data/2026-08-27-15.json" et "10" — les deux sous
#     forme de texte, même le 10. Le paramètre `type=` indique à argparse
#     en quoi convertir ce texte avant de nous le donner. En coulisses, il
#     fait à peu près :
#
#         args.file  = Path("data/2026-08-27-15.json")   # texte -> Path
#         args.lines = int("10")                          # texte -> nombre 10
#
#     C'est ce que signifie « argparse appellera Path(...) pour nous » :
#     sans type=Path, args.file serait une simple chaîne et il faudrait
#     écrire nous-mêmes Path(args.file) plus loin.
#
#     Pourquoi un Path plutôt que du texte ? Un Path est un objet qui
#     « sait » qu'il est un chemin de fichier, et il offre donc des outils
#     utiles qu'une chaîne n'a pas :
#
#         p = Path("data/2026-08-27-15.json")
#         p.exists()   # le fichier existe-t-il ? -> True / False
#         p.name       # "2026-08-27-15.json"
#         p.parent     # Path("data")
#
#     et il fonctionne de la même façon sous Windows et sous Linux (pas
#     besoin de se soucier de / ou \). Cela garde aussi les choses
#     cohérentes : DEFAULT_FILE est déjà un Path, donc avec type=Path,
#     args.file est TOUJOURS un Path, que l'utilisateur ait passé --file
#     ou non — peek() reçoit toujours le même type.
#
#     Pourquoi --date de download_gharchive.py restait du texte : là-bas,
#     la valeur sert seulement à construire UN AUTRE texte (l'URL de
#     téléchargement, https://data.gharchive.org/2026-08-27-15.json.gz),
#     il n'y a donc rien en quoi la convertir. Ici, --file est vraiment
#     un chemin vers un fichier sur le disque, donc il est logique que ce
#     soit un Path.
#
#   Pas de restriction `choices=` sur --lines
#     download_gharchive.py restreignait --hour à range(0, 24) car seules
#     24 valeurs sont jamais valides. Ici, --lines représente simplement
#     « autant que vous voulez en voir » — tout entier positif est
#     raisonnable, donc il n'y a pas d'ensemble fixe de choix valides
#     auquel le restreindre.
# ---------------------------------------------------------------------
def parse_args() -> argparse.Namespace:
    parser = argparse.ArgumentParser(description=__doc__)
    parser.add_argument("--file", type=Path, default=DEFAULT_FILE,
                         help=f"Path to the JSON Lines file (default: {DEFAULT_FILE})")
    parser.add_argument("--lines", type=int, default=DEFAULT_LINES,
                         help=f"How many events to print (default: {DEFAULT_LINES})")
    return parser.parse_args()


# main() et la garde `if __name__ == "__main__":` : but et mécanique
# identiques à download_gharchive.py — voir la copie annotée de ce fichier
# pour l'explication complète. En bref : main() relie l'analyse des
# arguments au travail effectif (ici, peek() au lieu de download()), et la
# garde garantit que ce travail ne s'exécute que lorsque ce fichier est
# exécuté directement, pas lorsqu'il est importé.
def main() -> None:
    args = parse_args()
    peek(args.file, args.lines)


if __name__ == "__main__":
    main()
