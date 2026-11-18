#!/usr/bin/env bash
########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de research.sh (dans le
# dossier du projet). Il n'est PAS destiné à être exécuté — il se trouve
# dans docs_french/ car son but est d'enseigner, pas de s'exécuter. (Il
# ne fonctionnerait même pas depuis ici : il cherche run.sh et scripts/
# à côté de lui-même.) Le fichier réel et « propre » (sans tous ces
# commentaires) est research.sh.
#
# La ligne au-dessus de ce cadre est la première ligne de l'original,
# gardée en tête volontairement (voir « le shebang » juste en dessous). À
# part ces lignes de commentaires ajoutées, chaque ligne est identique à
# l'original.
#
# Quoi lire d'abord : research.sh appelle run.sh, qui n'a pas de copie
# annotée mais qui est court et commenté — lisez run.sh lui-même. Il est
# utile de comparer les deux (voir « research.sh et run.sh » plus bas).
# Pour ce que fait chaque étape Python, voir docs_french/choose_starts.py,
# docs_french/measure.py et docs_french/analyze.py.
#
# Ce qui est NOUVEAU ici : c'est le premier script BASH du projet
# expliqué ligne par ligne. C'est le point d'entrée unique de la
# recherche : une seule commande lance les trois étapes pour une base de
# données, dans l'ordre, et s'arrête à la première qui échoue. Notions de
# bash abordées : le shebang, set -eo pipefail, cd "$(dirname "$0")", une
# boucle sur les arguments avec case / shift, les tableaux (arrays),
# mapfile avec la substitution de processus, tr -d '\r', read -p, et une
# vérification par expression régulière avec [[ =~ ]].
#
# Toute la recherche, en trois commandes :
#     ./run.sh scripts/drop_databases.py   (facultatif : repartir de zéro)
#     ./run.sh scripts/build_hours.py      (une base par volume de données)
#     ./research.sh                        (ce fichier : en mesurer une)
#
# Comment lancer le vrai fichier (depuis Git Bash, dans le dossier du
# projet, avec PostgreSQL en marche et Neo4j Desktop ouvert) :
#     ./research.sh
#     ./research.sh --database gharchive-2026-08-27-12-6h
########################################################################

# ---------------------------------------------------------------------
# Le shebang : #!/usr/bin/env bash  (la toute première ligne du fichier)
#
# « #! » tout au début d'un fichier indique au système QUEL PROGRAMME
# doit lire la suite quand vous lancez le fichier directement avec
# ./research.sh. /usr/bin/env bash signifie « trouve bash là où il est
# installé et utilise-le ». Pour bash lui-même, ce n'est qu'un
# commentaire (la ligne commence par #).
#
# research.sh et run.sh
#   run.sh       un LANCEUR générique : il prépare l'environnement
#                (.venv, les mots de passe de secrets.sh), puis devient
#                `python <script>`. Il lance UN SEUL script Python.
#   research.sh  un ORCHESTRATEUR : il ne touche jamais lui-même à .venv
#                ni aux mots de passe. Il appelle ./run.sh une fois par
#                étape (et une fois pour la liste des bases) ; chaque
#                appel reçoit son propre environnement, qui disparaît à
#                la fin de cette étape.
# Les deux commencent par les trois mêmes lignes : le shebang,
# set -eo pipefail, cd.
# ---------------------------------------------------------------------
# Run the whole research for one database, in order:
#     1. choose_starts.py  - the 10 top and 10 median starting actors (same on both sides)
#     2. measure.py        - the traversal in PostgreSQL and Neo4j, timed and checked
#     3. analyze.py        - the summary tables, and the comparison of every volume measured
#
# Usage (from Git Bash, with PostgreSQL running and Neo4j Desktop open):
#     ./research.sh                                     # asks which database to measure
#     ./research.sh --database gharchive-2026-08-27-12-6h
#     ./research.sh --database ... --max-depth 4 --repeats 5 --timeout 60
#
# The work is done by the Python scripts; this file only runs them in order,
# asks the one question, and stops at the first step that fails. Each script
# can also be run alone with ./run.sh (see README).

# ---------------------------------------------------------------------
# set -eo pipefail — S'ARRÊTER AU PREMIER ÉCHEC
#
# Par défaut, bash continue avec la ligne suivante même quand une
# commande échoue. Ce serait grave ici : si le choix des acteurs
# échouait, la mesure tournerait ensuite sur un starts.csv absent ou
# périmé.
#   -e         quitter dès qu'une commande échoue (se termine avec un code
#              de sortie différent de zéro — par ex. un script Python qui
#              appelle sys.exit(1), voir docs_french/check_connections.py).
#   -o pipefail
#              dans un TUBE (pipe) `a | b`, le tube compte comme échoué si
#              N'IMPORTE QUELLE partie échoue. Sans cela, seul le résultat
#              de la dernière commande compte, donc
#              `commande_qui_échoue | tr ...` aurait l'air d'un succès.
#
# cd "$(dirname "$0")" — TRAVAILLER DEPUIS LE DOSSIER DU PROJET
#   $0             le chemin avec lequel ce script a été lancé, par ex.
#                  ./research.sh ou /c/dev/Research/research.sh
#   dirname ...    n'en garde que la partie dossier : . ou /c/dev/Research
#   $( ... )       la SUBSTITUTION DE COMMANDE : exécute la commande à
#                  l'intérieur et met sa sortie à sa place.
#   les guillemets gardent d'un seul tenant un nom de dossier contenant
#                  des espaces.
# Ainsi, quel que soit le dossier où vous êtes quand vous le lancez, le
# script se place dans son propre dossier, et des chemins comme ./run.sh
# et scripts/... fonctionnent.
# ---------------------------------------------------------------------
set -eo pipefail
cd "$(dirname "$0")"

# ---------------------------------------------------------------------
# Des variables et un TABLEAU (array)
#
# DATABASE=""          une variable, vide pour l'instant. En bash, il ne
#                      doit y avoir AUCUN espace autour du = (DATABASE = ""
#                      échouerait).
# MEASURE_OPTIONS=()   un TABLEAU : une liste de chaînes séparées, vide
#                      pour l'instant. Il rassemblera les options
#                      destinées à measure.py, par ex.
#                      (--max-depth 4 --timeout 60).
# Pourquoi un tableau et pas une seule chaîne ? Chaque élément reste un
# argument séparé quand il est transmis, même s'il contenait des espaces.
# ---------------------------------------------------------------------
DATABASE=""
MEASURE_OPTIONS=()
# ---------------------------------------------------------------------
# LA BOUCLE SUR LES ARGUMENTS : while / case / shift
#
# $#  le nombre d'arguments qui restent ; $1, $2 le premier et le
#     deuxième.
#   ./research.sh --database X --repeats 5
#     -> $# = 4, $1 = --database, $2 = X
#
# while [ $# -gt 0 ]; do ... done
#   répéter tant qu'il reste des arguments (-gt : « greater than », plus
#   grand que ; [ ] est un test, et il faut des espaces à l'intérieur des
#   crochets).
#
# case "$1" in ... esac — comparer $1 à plusieurs motifs, comme une suite
# de if/elif. Chaque branche s'écrit `motif) commandes ;;`
#   --database)        garder l'argument suivant comme nom de la base.
#   --max-depth|--repeats|--timeout)
#                      `|` signifie OU. Ces trois-là ne sont pas utilisées
#                      par research.sh lui-même : elles sont ajoutées au
#                      tableau, l'option ET sa valeur, pour être passées
#                      plus tard à measure.py. += ( ... ) ajoute à un
#                      tableau.
#   *)                 `*` correspond à tout le reste : une option
#                      inconnue. Le message va sur la sortie d'ERREUR
#                      (>&2 : « envoie ceci sur le flux 2 », stderr) et
#                      exit 1 arrête avec un échec.
#
# shift 2 — jeter les deux premiers arguments ($1 et $2) : ce qui était
# $3 devient $1, et $# diminue de 2. C'est ainsi que la boucle avance,
# deux par deux (une option et sa valeur).
# ---------------------------------------------------------------------
while [ $# -gt 0 ]; do
    case "$1" in
        --database) DATABASE="$2"; shift 2 ;;
        --max-depth|--repeats|--timeout) MEASURE_OPTIONS+=("$1" "$2"); shift 2 ;;
        *) echo "Unknown option: $1 (see the top of research.sh)" >&2; exit 1 ;;
    esac
done

# Étape 0 : check_connections.py (docs_french/check_connections.py). Si
# un serveur ne tourne pas, il se termine avec 1 et, grâce à set -e, la
# recherche s'arrête ici — avant de demander ou de mesurer quoi que ce
# soit.
echo "== 0. Check that both servers are answering"
./run.sh scripts/check_connections.py

# ---------------------------------------------------------------------
# AUCUN --database DONNÉ : DEMANDER LAQUELLE
#
# [ -z "$DATABASE" ] — vrai si la variable est vide (-z : « zero
# length », longueur nulle).
# ---------------------------------------------------------------------
if [ -z "$DATABASE" ]; then
    # -----------------------------------------------------------------
    # mapfile -t DATABASES < <( ... )
    #
    # choose_starts.py --list-databases affiche les bases qui existent
    # des DEUX côtés, une par ligne (voir docs_french/choose_starts.py).
    # Cette ligne met ces lignes dans un tableau :
    #   mapfile -t NOM     lit des lignes depuis son entrée dans le
    #                      tableau NOM, un élément par ligne ; -t enlève
    #                      le retour à la ligne à la fin de chacune.
    #   < <( commande )    la SUBSTITUTION DE PROCESSUS : <( commande )
    #                      exécute la commande et fait passer sa sortie
    #                      pour un fichier ; le premier < donne ce
    #                      « fichier » à mapfile.
    #                      (Pourquoi pas `commande | mapfile` ? Chaque côté
    #                      d'un tube tourne dans une copie séparée du
    #                      shell, donc le tableau disparaîtrait à la fin du
    #                      tube.)
    #
    # | tr -d '\r' — LES FINS DE LIGNE WINDOWS
    #   Sous Windows, Python termine les lignes affichées par « \r\n »
    #   (retour chariot + saut de ligne), alors que bash n'attend que
    #   « \n ». mapfile -t enlève le \n, mais le \r invisible resterait
    #   collé à chaque nom, et « gharchive-...-6h\r » n'est pas une base
    #   qui existe. tr -d '\r' (« translate: delete », traduire :
    #   supprimer) enlève tous les caractères \r.
    # -----------------------------------------------------------------
    mapfile -t DATABASES < <(./run.sh scripts/choose_starts.py --list-databases | tr -d '\r')
    # ${#DATABASES[@]} — le nombre d'éléments du tableau. -eq : « equals »
    # (égal à). Aucun : il n'y a rien à mesurer ; dire quoi lancer
    # d'abord.
    if [ ${#DATABASES[@]} -eq 0 ]; then
        echo "There's no database to measure yet. Load one first: ./run.sh scripts/build_hours.py" >&2
        exit 1
    fi
    echo ""
    echo "Databases you can measure:"
    # -----------------------------------------------------------------
    # Un menu numéroté.
    #   "${!DATABASES[@]}"   les INDICES du tableau : 0 1 2 ... (le !
    #                        demande les positions, pas les valeurs)
    #   ${DATABASES[$i]}     l'élément à la position i
    #   $((i + 1))           de l'ARITHMÉTIQUE : bash calcule i + 1, pour
    #                        que le menu commence à 1 plutôt qu'à 0, comme
    #                        comptent les gens.
    # -----------------------------------------------------------------
    for i in "${!DATABASES[@]}"; do
        echo "  $((i + 1))) ${DATABASES[$i]}"
    done
    # -----------------------------------------------------------------
    # read -r -p "question " CHOICE
    #   Affiche la question (-p : « prompt », invite) et attend que vous
    #   tapiez quelque chose et appuyiez sur Entrée ; ce que vous avez
    #   tapé va dans CHOICE. -r garde les barres obliques inverses telles
    #   qu'elles ont été tapées (toujours une bonne habitude avec read).
    # -----------------------------------------------------------------
    read -r -p "Which one? (number) " CHOICE
    # -----------------------------------------------------------------
    # VÉRIFIER LA RÉPONSE avant de l'utiliser.
    #
    # [[ "$CHOICE" =~ ^[0-9]+$ ]] — un test par EXPRESSION RÉGULIÈRE (la
    # forme [[ ]] de bash ; =~ signifie « correspond au motif ») :
    #   ^       le début du texte
    #   [0-9]+  un ou plusieurs chiffres
    #   $       la fin du texte
    # c'est-à-dire « uniquement des chiffres, rien d'autre ». Le `!`
    # devant l'inverse : « n'est PAS un nombre ». Cette vérification vient
    # en premier car -lt / -gt plus loin provoqueraient une erreur si
    # CHOICE valait, disons, « abc ».
    #
    # || signifie OU, entre trois tests : pas un nombre, OU inférieur à 1
    # (-lt : « less than », plus petit que), OU supérieur au nombre de
    # bases. Si l'un d'eux est vrai : refuser, sans rien faire.
    # -----------------------------------------------------------------
    if ! [[ "$CHOICE" =~ ^[0-9]+$ ]] || [ "$CHOICE" -lt 1 ] || [ "$CHOICE" -gt ${#DATABASES[@]} ]; then
        echo "Not a number from the list; nothing done." >&2
        exit 1
    fi
    # Le menu affichait 1, 2, 3..., le tableau compte 0, 1, 2... : d'où
    # le - 1.
    DATABASE="${DATABASES[$((CHOICE - 1))]}"
fi

# ---------------------------------------------------------------------
# LES TROIS ÉTAPES, chacune via run.sh.
#
# "$DATABASE" est toujours entre guillemets doubles : la valeur est
# transmise comme UN SEUL argument, exactement telle quelle. \" à
# l'intérieur de "..." affiche un vrai caractère ".
#
# "${MEASURE_OPTIONS[@]}" — se développe en chaque élément du tableau,
# CHACUN comme un argument séparé : --max-depth 4 --timeout 60. Si le
# tableau est vide, il ne se développe en rien du tout, et measure.py
# utilise ses propres valeurs par défaut.
#
# Grâce à set -e, si l'étape 1 échoue, les étapes 2 et 3 ne sont jamais
# lancées.
# ---------------------------------------------------------------------
echo ""
echo "== 1. Choose the starting actors in \"$DATABASE\""
./run.sh scripts/choose_starts.py --database "$DATABASE"

echo ""
echo "== 2. Measure the traversal in \"$DATABASE\""
./run.sh scripts/measure.py --database "$DATABASE" "${MEASURE_OPTIONS[@]}"

echo ""
echo "== 3. Analyse"
./run.sh scripts/analyze.py --database "$DATABASE"

echo "Done. Everything is in results/$DATABASE/"
