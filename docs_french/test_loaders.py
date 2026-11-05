########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de tests/test_loaders.py.
# Il n'est PAS destiné à être exécuté — il se trouve dans docs_french/ car son
# but est d'enseigner. Le fichier réel et « propre » (sans tous ces
# commentaires) est tests/test_loaders.py.
#
# Ce fichier suppose que vous avez déjà lu docs_french/test_extract_csv.py —
# les bases de pytest qui y sont expliquées (le nom test_, assert, les
# fonctions d'aide, la fixture tmp_path) ne sont PAS réexpliquées ici. Les
# fonctions testées sont expliquées dans docs_french/load_neo4j.py et
# docs_french/load_postgres.py.
#
# Son rôle dans le projet : vérifier la partie des chargeurs qui travaille
# sur des FICHIERS. Le chargement dans une vraie base de données n'est pas
# testé ici : c'est le rôle du futur test d'intégration (étape 3 du plan).
########################################################################

"""Unit tests for the CSV-reading helpers of the two loaders.

Only the parts that work on files are tested here; loading into a real
PostgreSQL or Neo4j database belongs to the integration test.

Run with:  python -m pytest
"""

from pathlib import Path

# ---------------------------------------------------------------------
# On importe une fonction de chaque chargeur. Importer ces modules ne
# se connecte à aucune base : la connexion n'a lieu que dans load(),
# qu'on n'appelle pas ici. Les tests n'ont donc besoin d'aucun mot de
# passe.
# ---------------------------------------------------------------------
from load_neo4j import read_csv
from load_postgres import count_csv_rows


# ---------------------------------------------------------------------
# write_text : fonction d'aide qui écrit un petit CSV et renvoie son
# chemin. Le contenu est donné directement comme texte : "id,login\n1,ana\n"
# correspond à deux lignes, l'en-tête `id,login` puis `1,ana` ("\n" est
# le retour à la ligne).
# ---------------------------------------------------------------------
def write_text(path: Path, text: str) -> Path:
    path.write_text(text, encoding="utf-8")
    return path


# ---------- load_neo4j.read_csv ----------

# ---------------------------------------------------------------------
# read_csv renvoie une liste de dicts, un par ligne, avec les noms de
# l'en-tête comme clés. ("id",) est un tuple d'UN seul élément : la
# virgule est obligatoire, sans elle ("id") ne serait qu'un texte entre
# parenthèses.
#
# Le test compare avec 1 et 2 SANS guillemets : des nombres. Si read_csv
# oubliait la conversion, on aurait "1" et "2" (du texte) et le test
# échouerait.
# ---------------------------------------------------------------------
def test_read_csv_converts_id_columns_to_int(tmp_path):
    file = write_text(tmp_path / "actors.csv", "id,login\n1,ana\n2,bea\n")
    rows = read_csv(file, ("id",))
    # Numbers, not text: in Neo4j, 1 and "1" are different values and would never match.
    assert rows == [{"id": 1, "login": "ana"}, {"id": 2, "login": "bea"}]


# L'autre côté de la même règle : une colonne qu'on n'a pas nommée ne
# doit PAS être convertie, même si elle ne contient que des chiffres. Le
# login "12345" doit rester le texte "12345".
def test_read_csv_leaves_other_columns_as_text(tmp_path):
    # A login made of digits must stay text: only the columns we name are converted.
    file = write_text(tmp_path / "actors.csv", "id,login\n3,12345\n")
    rows = read_csv(file, ("id",))
    assert rows == [{"id": 3, "login": "12345"}]


# Le fichier des connexions a DEUX colonnes d'ids : on les nomme toutes
# les deux, et toutes les deux deviennent des nombres.
def test_read_csv_converts_both_columns_of_connections(tmp_path):
    file = write_text(tmp_path / "actor_repo.csv", "actor_id,repo_id\n1,10\n")
    rows = read_csv(file, ("actor_id", "repo_id"))
    assert rows == [{"actor_id": 1, "repo_id": 10}]


# ---------- load_postgres.count_csv_rows ----------

# ---------------------------------------------------------------------
# count_csv_rows compte les lignes du fichier moins une (l'en-tête). Le
# chargeur compare ce nombre aux lignes de chaque table pour vérifier
# que tout a été chargé : une erreur d'une ligne ici ferait croire à une
# donnée perdue (ou en cacherait une).
# ---------------------------------------------------------------------
def test_count_csv_rows_excludes_header(tmp_path):
    file = write_text(tmp_path / "repos.csv", "id,name\n10,ana/project\n20,bea/tool\n")
    assert count_csv_rows(file) == 2


# Le cas limite : un CSV vide (seulement l'en-tête) doit donner 0, pas -1
# ni 1.
def test_count_csv_rows_header_only_is_zero(tmp_path):
    file = write_text(tmp_path / "repos.csv", "id,name\n")
    assert count_csv_rows(file) == 0
