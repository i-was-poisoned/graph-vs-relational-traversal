########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de tests/test_extract_csv.py.
# Il n'est PAS destiné à être exécuté — il se trouve dans docs_french/ car son
# but est d'enseigner. Le fichier réel et « propre » (sans tous ces
# commentaires) est tests/test_extract_csv.py, et c'est celui-là que pytest
# trouve et lance (pytest.ini lui dit de chercher seulement dans tests/).
#
# Ce fichier suppose que vous avez déjà lu docs_french/extract_csv.py — les
# fonctions testées ici (is_bot, remember_latest, extract, write_all) y sont
# expliquées. Ce fichier se concentre sur ce qui est NOUVEAU : comment on
# écrit des tests avec pytest.
#
# Son rôle dans le projet : vérifier automatiquement, en quelques
# millisecondes, que l'extraction traite correctement les cas difficiles
# déjà rencontrés dans les vraies données (bots, repo vide {}, logins
# renommés, paires répétées).
########################################################################

"""Unit tests for scripts/extract_csv.py.

Each test builds a tiny GH Archive-like file (two or three made-up events) in a
temporary folder, so the tests run in milliseconds and need no downloaded data.

Run with:  python -m pytest
"""

# csv, gzip, json, Path : déjà expliqués dans les scripts annotés
# précédents. Ici, csv sert à RELIRE les fichiers écrits par write_all(),
# json et gzip servent à ÉCRIRE les petits fichiers d'événements inventés.
import csv
import gzip
import json
from pathlib import Path

# ---------------------------------------------------------------------
# On importe les fonctions à tester directement depuis extract_csv.
#
# Comment Python trouve-t-il extract_csv, alors que ce fichier est dans
# tests/ et le script dans scripts/ ? Grâce à la ligne
# `pythonpath = scripts` de pytest.ini : avant de lancer les tests, pytest
# ajoute scripts/ aux endroits où Python cherche les modules.
#
# Importer extract_csv NE lance PAS le script : grâce à la garde
# `if __name__ == "__main__":`, main() ne s'exécute que quand on lance le
# fichier directement. Ici, on récupère seulement ses fonctions.
# ---------------------------------------------------------------------
from extract_csv import extract, is_bot, remember_latest, write_all


# ---------------------------------------------------------------------
# make_event : une fonction d'AIDE (en anglais, un « helper »), pas un
# test. pytest ne la lance pas toute seule, car son nom ne commence pas
# par `test_`.
#
# Elle fabrique un événement GH Archive minimal, sous forme de dict
# Python. Un vrai événement a des dizaines de champs ; ici, seuls ceux que
# lit extract_csv.py comptent (actor.id, actor.login, repo.id, repo.name,
# created_at). Cela rend chaque test court et lisible : une ligne
# make_event(1, "ana", 10, "ana/project") au lieu de tout un dict.
#
# `created_at: str = "2026-08-27T15:00:00Z"` : un paramètre avec une
# valeur PAR DÉFAUT. Si on ne le donne pas, il vaut cette date ; les tests
# qui parlent de l'ordre des événements le donnent explicitement.
# ---------------------------------------------------------------------
def make_event(actor_id: int, login: str, repo_id: int, repo_name: str,
               created_at: str = "2026-08-27T15:00:00Z") -> dict:
    # Only the fields extract_csv.py reads; real events have many more.
    return {
        "actor": {"id": actor_id, "login": login},
        "repo": {"id": repo_id, "name": repo_name},
        "created_at": created_at,
    }


# ---------------------------------------------------------------------
# write_events : la deuxième fonction d'aide. Elle écrit une liste
# d'événements dans un fichier, au même format que GH Archive : JSON
# Lines, c'est-à-dire UN objet JSON par ligne.
#
# json.dumps(event) : l'inverse de json.loads. « dump string » transforme
# un dict Python en texte JSON. On ajoute "\n" pour finir chaque ligne,
# puis "".join(...) colle toutes ces lignes en un seul texte.
#
# Si le nom se termine par .gz, on écrit le fichier COMPRESSÉ avec
# gzip.open(path, "wt", ...) : "w" = écrire (write), "t" = en texte. C'est
# le pendant du "rt" (lire en texte) qu'utilise open_text() dans
# extract_csv.py. Sinon, path.write_text écrit du texte normal.
#
# Elle renvoie le chemin (`return path`), pour qu'un test puisse écrire
# `file = write_events(...)` en une seule ligne.
# ---------------------------------------------------------------------
def write_events(path: Path, events: list[dict]) -> Path:
    # One JSON object per line (JSON Lines), like GH Archive; compressed if the name ends in .gz.
    text = "".join(json.dumps(event) + "\n" for event in events)
    if path.suffix == ".gz":
        with gzip.open(path, "wt", encoding="utf-8") as f:
            f.write(text)
    else:
        path.write_text(text, encoding="utf-8")
    return path


# ---------- is_bot ----------

# ---------------------------------------------------------------------
# Le premier VRAI test. Deux règles suffisent pour que pytest le trouve
# et le lance :
#   1. le nom de la fonction commence par `test_` ;
#   2. le fichier aussi (test_extract_csv.py) et il est dans tests/.
# Pas besoin de l'enregistrer nulle part, ni d'appeler la fonction.
#
# Le nom est long exprès : il décrit le cas testé. Quand un test échoue,
# pytest affiche ce nom, et on sait tout de suite ce qui ne va plus.
#
# `assert` : « j'affirme que ceci est vrai ». Si c'est vrai, rien ne se
# passe et le test PASSE. Si c'est faux, Python lève une AssertionError,
# et pytest marque le test comme ÉCHOUÉ, en montrant les valeurs.
# ---------------------------------------------------------------------
def test_is_bot_true_for_bot_suffix():
    assert is_bot("dependabot[bot]")


# `assert not ...` : j'affirme que ceci est FAUX.
def test_is_bot_false_for_normal_login():
    assert not is_bot("pedro")


# Le cas piège : le mot « bot » n'est pas en fin de login. Un test peut
# contenir plusieurs assert ; il échoue dès que l'un d'eux est faux.
def test_is_bot_false_when_bot_is_not_the_suffix():
    # Only the "[bot]" ending counts, not the word "bot" somewhere in the login.
    assert not is_bot("robot")
    assert not is_bot("bot-builder")


# ---------- remember_latest ----------

# ---------------------------------------------------------------------
# Les trois tests de remember_latest reprennent l'exemple écrit au-dessus
# de la fonction dans extract_csv.py (l'actor 7, « ana » renommée en
# « ana-dev »). Chaque test suit le même schéma en trois temps, très
# courant dans les tests :
#   1. PRÉPARER : l'état de départ (le dict `names`) ;
#   2. AGIR : appeler la fonction testée ;
#   3. VÉRIFIER : un assert sur le résultat.
#
# remember_latest ne renvoie rien : elle MODIFIE le dict qu'on lui donne.
# On vérifie donc le contenu du dict après l'appel.
# ---------------------------------------------------------------------
def test_remember_latest_stores_new_key():
    names = {}
    remember_latest(names, 7, "2026-08-27T15:10:00Z", "ana")
    # `==` sur deux dicts : vrai seulement s'ils ont exactement les mêmes
    # clés et les mêmes valeurs.
    assert names == {7: ("2026-08-27T15:10:00Z", "ana")}


def test_remember_latest_newer_name_replaces_older():
    names = {7: ("2026-08-27T15:10:00Z", "ana")}
    remember_latest(names, 7, "2026-08-27T15:30:00Z", "ana-dev")
    assert names[7] == ("2026-08-27T15:30:00Z", "ana-dev")


def test_remember_latest_older_name_is_ignored():
    # Events can arrive out of order: an older event must not undo a newer name.
    names = {7: ("2026-08-27T15:30:00Z", "ana-dev")}
    remember_latest(names, 7, "2026-08-27T15:20:00Z", "ana")
    assert names[7] == ("2026-08-27T15:30:00Z", "ana-dev")


# ---------- extract ----------

# ---------------------------------------------------------------------
# NOUVEAU : `tmp_path`, une « fixture » de pytest.
#
# Une fixture est un outil que pytest prépare pour le test. Il suffit de
# mettre son NOM comme paramètre de la fonction : pytest voit
# `tmp_path`, crée un dossier temporaire neuf et vide, et le passe au
# test sous forme de Path. Chaque test reçoit son propre dossier, donc
# les tests ne se gênent jamais entre eux, et personne n'a besoin de les
# supprimer à la main.
#
# `tmp_path / "hour.json"` : l'opérateur / de Path, déjà vu dans les
# scripts, pour construire un chemin à l'intérieur de ce dossier.
#
# extract() renvoie un tuple de 4 valeurs ; on les « déballe » dans 4
# variables en une seule ligne (actors, repos, pairs, skipped_bots).
# ---------------------------------------------------------------------
def test_extract_normal_event(tmp_path):
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project")])
    # extract attend une LISTE de fichiers, d'où les crochets [file].
    actors, repos, pairs, skipped_bots = extract([file])
    assert actors == {1: ("2026-08-27T15:00:00Z", "ana")}
    assert repos == {10: ("2026-08-27T15:00:00Z", "ana/project")}
    # {(1, 10)} : un set contenant un seul tuple, la paire (actor, repo).
    assert pairs == {(1, 10)}
    assert skipped_bots == 0


def test_extract_skips_bots(tmp_path):
    file = write_events(tmp_path / "hour.json", [
        make_event(1, "ana", 10, "ana/project"),
        make_event(2, "dependabot[bot]", 10, "ana/project"),
    ])
    actors, repos, pairs, skipped_bots = extract([file])
    # set(actors) : l'ensemble des CLÉS du dict, c'est-à-dire les ids.
    # On ne vérifie que les ids ici, pas les dates ni les logins.
    assert set(actors) == {1}
    assert pairs == {(1, 10)}
    assert skipped_bots == 1


# ---------------------------------------------------------------------
# NOUVEAU : `caplog`, une autre fixture de pytest (« capture log »).
# Elle capture tout ce qui est écrit dans le log pendant le test ;
# caplog.text contient ce texte. On peut donc vérifier que l'avertissement
# de extract() a bien été écrit.
#
# Un test peut demander plusieurs fixtures : ici tmp_path ET caplog.
#
# `empty_repo` est écrit à la main, sans make_event, car make_event donne
# toujours un repo avec id et name : il nous faut justement un "repo": {}.
#
# `_` comme nom de variable : une convention Python pour dire « cette
# valeur ne m'intéresse pas » (ici, le nombre de bots ignorés).
#
# `"..." in caplog.text` : vrai si ce morceau de texte apparaît quelque
# part dans le log.
# ---------------------------------------------------------------------
def test_extract_skips_event_with_empty_repo(tmp_path, caplog):
    # The real case found on 2026-10-22: a ForkEvent whose repo was {} (no id, no name).
    empty_repo = {"actor": {"id": 2, "login": "bea"}, "repo": {}, "created_at": "2026-08-27T15:05:00Z"}
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project"), empty_repo])
    actors, repos, pairs, _ = extract([file])
    assert set(actors) == {1}
    assert pairs == {(1, 10)}
    assert "Skipped 1 event(s) without an actor or repo id" in caplog.text


# ---------------------------------------------------------------------
# `[make_event(...)] * 3` : multiplier une liste la RÉPÈTE.
# [x] * 3 donne [x, x, x] : trois fois le même événement. C'est une façon
# courte d'écrire « le même acteur sur le même repo, trois fois ».
# ---------------------------------------------------------------------
def test_extract_repeated_pair_counted_once(tmp_path):
    # Three events by the same actor on the same repo -> one connection.
    file = write_events(tmp_path / "hour.json", [make_event(1, "ana", 10, "ana/project")] * 3)
    _, _, pairs, _ = extract([file])
    assert pairs == {(1, 10)}


# L'événement le plus récent (15:30) est écrit EN PREMIER dans le fichier,
# exprès : le test vérifie que c'est la date qui décide, pas l'ordre des
# lignes. actors[1][1] : l'actor 1, puis le 2e élément du tuple
# (date, login), c'est-à-dire le login (on compte à partir de 0).
def test_extract_keeps_latest_login(tmp_path):
    file = write_events(tmp_path / "hour.json", [
        make_event(1, "ana-dev", 10, "ana/project", "2026-08-27T15:30:00Z"),
        make_event(1, "ana", 10, "ana/project", "2026-08-27T15:10:00Z"),
    ])
    actors, _, _, _ = extract([file])
    assert actors[1][1] == "ana-dev"


# Deux fichiers, l'un en texte normal et l'autre compressé, avec des noms
# comme ceux de GH Archive. Ce test vérifie à la fois open_text() (qui
# choisit gzip ou non selon l'extension) et le fait qu'extract réunit les
# données de PLUSIEURS fichiers, comme le fait la pipeline de 24 heures.
def test_extract_reads_several_files_plain_and_gz(tmp_path):
    plain = write_events(tmp_path / "2026-10-20-5.json", [make_event(1, "ana", 10, "ana/project")])
    compressed = write_events(tmp_path / "2026-10-20-6.json.gz", [make_event(2, "bea", 20, "bea/tool")])
    actors, repos, pairs, _ = extract([plain, compressed])
    assert set(actors) == {1, 2}
    assert set(repos) == {10, 20}
    assert pairs == {(1, 10), (2, 20)}


# ---------- write_all / write_csv ----------

# ---------------------------------------------------------------------
# Ici, les données d'entrée sont données directement (pas besoin
# d'extract) et volontairement DANS LE DÉSORDRE (l'id 2 avant l'id 1),
# pour vérifier que write_all trie bien par id. "t" remplace une vraie
# date : write_all ne l'écrit pas, sa valeur n'a donc pas d'importance.
#
# write_csv affiche aussi une ligne par fichier avec print() ; pytest
# capture cet affichage, il n'apparaît donc pas pendant les tests.
# ---------------------------------------------------------------------
def test_write_all_writes_headers_and_sorted_rows(tmp_path):
    actors = {2: ("t", "bea"), 1: ("t", "ana")}
    repos = {10: ("t", "ana/project")}
    pairs = {(2, 10), (1, 10)}
    write_all(tmp_path, actors, repos, pairs)

    # -----------------------------------------------------------------
    # NOUVEAU : une fonction définie À L'INTÉRIEUR d'une autre (une
    # fonction imbriquée). Elle n'existe que dans ce test. Elle peut
    # utiliser tmp_path, car elle « voit » les variables de la fonction
    # qui l'entoure.
    #
    # Elle relit un CSV et renvoie toutes ses lignes, chacune étant une
    # liste de textes. csv.reader renvoie TOUJOURS du texte : d'où les
    # "1" et "10" entre guillemets dans les assert ci-dessous.
    # -----------------------------------------------------------------
    def read(name: str) -> list[list[str]]:
        with open(tmp_path / name, encoding="utf-8", newline="") as f:
            return list(csv.reader(f))

    # Chaque assert compare le fichier entier : l'en-tête puis les lignes,
    # dans l'ordre attendu (triées par id).
    assert read("actors.csv") == [["id", "login"], ["1", "ana"], ["2", "bea"]]
    assert read("repos.csv") == [["id", "name"], ["10", "ana/project"]]
    assert read("actor_repo.csv") == [["actor_id", "repo_id"], ["1", "10"], ["2", "10"]]
