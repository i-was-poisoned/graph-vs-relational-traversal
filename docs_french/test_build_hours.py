########################################################################
# COPIE ANNOTÉE — à des fins d'apprentissage uniquement.
#
# Ceci est un duplicata expliqué ligne par ligne de
# tests/test_build_hours.py. Il n'est PAS destiné à être exécuté — il se
# trouve dans docs_french/ car son but est d'enseigner, pas de s'exécuter
# (pytest ne cherche des tests que dans tests/, comme l'indique
# pytest.ini). Le fichier réel et « propre » (sans tous ces commentaires)
# est tests/test_build_hours.py.
#
# Lisez d'abord ces fichiers ; ce qu'ils expliquent n'est PAS répété ici :
#   docs_french/test_extract_csv.py   les bases de pytest (le nom test_,
#                                     assert, les fixtures comme tmp_path
#                                     et caplog)
#   docs_french/test_pipeline.py      la fonction d'aide utc(), comparer
#                                     des datetime, `assert not`
#   docs_french/build_hours.py        les fonctions testées ici
#
# Ce qui est NOUVEAU ici :
#   - pytest.raises : vérifier qu'une fonction LÈVE une erreur (et avec
#     quel message) ;
#   - la fixture capsys : capturer ce qu'une fonction AFFICHE ;
#   - SIMULER LE CLAVIER : une fonction qui renvoie des réponses toutes
#     prêtes (avec iter(), next() et une lambda), passée à ask_hours() à
#     la place d'input() ;
#   - *replies : une fonction qui accepte n'importe quel nombre
#     d'arguments.
#
# Son rôle dans le projet : build_hours.py pose des questions et
# SUPPRIME des bases de données, donc ses règles doivent tenir : les
# réponses invalides sont refusées, la date et l'heure ne sont jamais
# choisies à votre place, les heures non publiées sont refusées, les noms
# n'entrent jamais en conflit avec les autres bases, et la vérification
# de sécurité refuse de vider tout ce qui ne s'appelle pas
# « gharchive-... ». Tout cela est testé SANS réseau, sans base de
# données et sans que personne ne tape rien.
#
# Comment lancer les vrais tests (depuis le dossier du projet) :
#     python -m pytest
########################################################################

"""Unit tests for the pure functions of scripts/build_hours.py (no network, no databases).

Run with:  python -m pytest
"""

from datetime import date, datetime, timezone

# Cette fois, on importe pytest lui-même, pour pytest.raises (voir plus
# bas). (Les tests simples avec assert n'ont pas besoin de cet import ;
# les fixtures non plus.)
import pytest

# Un long import, coupé sur deux lignes : entre ( ), Python permet à une
# ligne de continuer sur la suivante. Ce sont les fonctions testées.
from build_hours import (ask_hours, chosen_hours, database_name, hours_are_published, may_be_emptied, parse_count,
                         parse_date, parse_hour, recreate_databases)

# ---------------------------------------------------------------------
# NOW — une « heure actuelle » FIXE pour tous les tests : 2026-11-12 15:20
# UTC. build_hours.py reçoit `now` en paramètre précisément pour que les
# tests puissent faire cela. Avec la vraie horloge, un test sur les
# « heures récentes » passerait aujourd'hui et échouerait demain. Écrit
# en MAJUSCULES : une constante.
# Avec NOW, l'heure en cours est 15:00, donc la plage d'heures la plus
# tardive acceptée doit SE TERMINER au plus tard à 14:00 (voir
# hours_are_published() dans build_hours.py).
# ---------------------------------------------------------------------
NOW = datetime(2026, 11, 12, 15, 20, tzinfo=timezone.utc)


# La même fonction d'aide que dans test_pipeline.py, sans les minutes
# (inutiles ici).
def utc(year: int, month: int, day: int, hour: int) -> datetime:
    return datetime(year, month, day, hour, tzinfo=timezone.utc)


# ---------------------------------------------------------------------
# def answers(*replies): — le FAUX CLAVIER.
#
# *replies — l'étoile rassemble N'IMPORTE QUEL NOMBRE d'arguments dans un
#   seul tuple :
#   answers("2026-08-27", "15", "", "y")  ->  replies = ("2026-08-27", "15", "", "y")
#
# iter(replies) — transforme le tuple en ITÉRATEUR : un objet qui
#   distribue les éléments UN PAR UN et se souvient où il en est.
# next(remaining) — donne l'élément suivant ; le premier appel donne
#   "2026-08-27", le deuxième "15", et ainsi de suite. (Si les réponses
#   s'épuisent, next() lève StopIteration et le test échoue — signe que
#   la fonction a posé plus de questions que prévu.)
#
# lambda prompt: next(remaining) — une LAMBDA est une toute petite
#   fonction sans nom, écrite en une seule expression. C'est la même
#   chose que :
#       def fake_input(prompt):
#           return next(remaining)
#   Elle reçoit `prompt` (le texte de la question), comme input(),
#   l'ignore, et renvoie la réponse toute prête suivante.
#
# answers(...) RENVOIE cette fonction ; les tests la passent comme ask=...
# à ask_hours(), qui l'appelle alors à la place d'input(). La lambda
# continue d'utiliser `remaining` après la fin d'answers() : une fonction
# se souvient des variables de l'endroit où elle a été créée.
# ---------------------------------------------------------------------
def answers(*replies):
    # Stands in for the keyboard: each call returns the next ready-made answer.
    remaining = iter(replies)
    return lambda prompt: next(remaining)


# ---------- parse_date ----------

def test_parse_date_valid():
    assert parse_date("2026-08-27") == date(2026, 8, 27)


# ---------------------------------------------------------------------
# with pytest.raises(ValueError):
#     parse_date(bad)
#
# NOUVEAU : un test qui S'ATTEND à une erreur. Normalement, une erreur
# dans un test le fait échouer. Dans `with pytest.raises(ValueError):`,
# c'est l'inverse : le test ne réussit que si le code du bloc lève une
# ValueError, et ÉCHOUE s'il s'exécute sans en lever.
#
# Les trois mauvaises dates : le mauvais ordre (jour/mois/année), un mois
# qui n'existe pas (13), et un mot. La boucle vérifie chacune ; chacune a
# son propre `with`, car le bloc s'arrête à la première erreur.
# ---------------------------------------------------------------------
def test_parse_date_rejects_other_formats():
    for bad in ("27/08/2026", "2026-13-01", "yesterday"):
        with pytest.raises(ValueError):
            parse_date(bad)


# match="older GH Archive format" — l'erreur doit AUSSI contenir ce texte
# dans son message. Le test vérifie ainsi que c'est la BONNE erreur
# (celle du « avant 2015 »), et pas une autre ValueError. (match= est en
# réalité une expression régulière, un motif de recherche, mais des mots
# simples comme ceux-ci veulent juste dire « contient ce texte ».)
def test_parse_date_rejects_dates_before_2015():
    with pytest.raises(ValueError, match="older GH Archive format"):
        parse_date("2014-12-31")


# ---------- parse_hour and parse_count ----------

# CAS LIMITES : les deux bornes, 0 et 23, doivent être acceptées ; juste
# en dehors (24, -1), ainsi que ce qui n'est pas un nombre (« 3pm »,
# vide), refusé. C'est aux bornes qu'apparaissent les erreurs d'une unité
# (< au lieu de <=).
def test_parse_hour_valid_limits():
    assert parse_hour("0") == 0
    assert parse_hour("23") == 23


def test_parse_hour_rejects_out_of_range():
    for bad in ("24", "-1", "3pm", ""):
        with pytest.raises(ValueError):
            parse_hour(bad)


# Même chose pour le nombre d'heures : 1 et 168 (une semaine, MAX_HOURS)
# acceptés ; 0, 169 et un mot refusés.
def test_parse_count_limits():
    assert parse_count("1") == 1
    assert parse_count("168") == 168
    for bad in ("0", "169", "two"):
        with pytest.raises(ValueError):
            parse_count(bad)


# ---------- chosen_hours ----------

def test_chosen_hours_one_hour():
    assert chosen_hours(date(2026, 8, 27), 15, 1) == [utc(2026, 8, 27, 15)]


# 23:00 plus une heure doit donner 00:00 le jour SUIVANT, pas une heure 24.
def test_chosen_hours_cross_midnight():
    assert chosen_hours(date(2026, 8, 27), 23, 2) == [utc(2026, 8, 27, 23), utc(2026, 8, 28, 0)]


# ---------- hours_are_published ----------

# Trois cas autour de la règle, avec NOW = 15:20 (fin la plus tardive
# permise : 14:00) : des heures anciennes (août) conviennent ; des heures
# qui se terminent exactement à 14:00 conviennent (la borne elle-même) ;
# celles qui se terminent à 15:00, ou demain, sont refusées. Les
# commentaires en fin de certaines lignes sont les notes propres au
# fichier original.
def test_old_hours_are_published():
    assert hours_are_published(chosen_hours(date(2026, 8, 27), 15, 3), NOW)


def test_hours_ending_one_hour_before_the_current_hour_are_published():
    # now 15:20 -> current hour 15:00; 12:00-14:00 is accepted
    assert hours_are_published(chosen_hours(date(2026, 11, 12), 12, 2), NOW)


def test_recent_or_future_hours_are_not_published():
    assert not hours_are_published(chosen_hours(date(2026, 11, 12), 13, 2), NOW)   # ends 15:00, too recent
    assert not hours_are_published(chosen_hours(date(2026, 11, 13), 0, 1), NOW)    # tomorrow


# ---------- database_name ----------

def test_database_name_one_hour_has_no_leading_zero_like_gh_archive():
    assert database_name(chosen_hours(date(2026, 8, 27), 5, 1)) == "gharchive-2026-08-27-5"


def test_database_name_several_hours_says_how_many():
    assert database_name(chosen_hours(date(2026, 8, 27), 15, 3)) == "gharchive-2026-08-27-15-3h"


# Les noms ne doivent jamais être celui de l'une des deux autres bases, ni
# contenir « _ » (Neo4j le refuserait). `not in (...)` : différent de
# chaque élément du tuple. `"_" not in name` : sur des chaînes, `in`
# cherche du texte.
def test_database_name_never_clashes_with_the_other_databases():
    for count in (1, 24):
        name = database_name(chosen_hours(date(2026, 8, 27), 15, count))
        assert name not in ("gharchive", "gharchive24h")
        assert "_" not in name   # Neo4j doesn't allow "_" in database names


# ---------- ask_hours ----------

# ---------------------------------------------------------------------
# capsys — NOUVELLE fixture (« capture system output », capturer la
# sortie du système). Comme caplog (voir test_extract_csv.py), mais pour
# print() : tout ce qui est affiché pendant le test est capturé au lieu
# d'être montré. capsys.readouterr().out le renvoie sous forme d'une seule
# chaîne, pour que le test puisse vérifier que les messages sont bien
# apparus.
#
# Ce test prouve la règle « la date et l'heure n'ont AUCUNE valeur par
# défaut » : le faux clavier appuie sur Entrée ("") à la date, puis à
# l'heure, et ask_hours() doit redemander à chaque fois (en affichant
# « Please type ... ») au lieu de choisir une valeur. Chaque ligne
# d'answers() est un tour de questions ; les commentaires disent ce que
# signifie chaque réponse. Ce n'est qu'au troisième tour qu'elle reçoit
# tout, avec Entrée au nombre d'heures (= 1 heure) et Entrée à la
# confirmation (= oui).
# ---------------------------------------------------------------------
def test_ask_hours_has_no_default_date_or_hour(capsys):
    # Pressing Enter at the date or the hour doesn't pick one: it asks again.
    reply = answers("",                      # no date
                    "2026-08-27", "",        # no hour
                    "2026-08-27", "15", "", "")   # Enter at the count = 1 hour; Enter to confirm
    assert ask_hours(NOW, ask=reply) == [utc(2026, 8, 27, 15)]
    printed = capsys.readouterr().out
    assert "Please type a date" in printed and "Please type an hour" in printed


# Le cas normal : date, heure 9, 3 heures, « y » -> trois heures
# consécutives.
def test_ask_hours_chosen_date_hour_and_count():
    hours = ask_hours(NOW, ask=answers("2026-11-10", "9", "3", "y"))
    assert hours == [utc(2026, 11, 10, 9), utc(2026, 11, 10, 10), utc(2026, 11, 10, 11)]


# Toutes les façons de mal répondre, un tour chacune, et enfin un bon
# tour. La dernière vérification parcourt les quatre messages attendus :
# chacun doit apparaître dans ce qui a été affiché, ce qui prouve que
# chaque erreur a été repérée et expliquée.
def test_ask_hours_asks_again_after_bad_answers(capsys):
    # a wrong date; a wrong hour; a wrong count; hours not published yet; then a good answer
    reply = answers("10/11/2026",
                    "2026-11-10", "25",
                    "2026-11-10", "9", "0",
                    "2026-11-12", "13", "2",
                    "2026-11-10", "9", "", "")
    assert ask_hours(NOW, ask=reply) == [utc(2026, 11, 10, 9)]
    printed = capsys.readouterr().out
    for message in ("isn't a date", "isn't an hour", "isn't a number of hours", "hasn't published"):
        assert message in printed


# Répondre « n » à la confirmation renvoie None : rien ne sera fait.
# `is None` (et non == None) est la façon habituelle de tester None.
def test_ask_hours_no_means_nothing_is_done():
    assert ask_hours(NOW, ask=answers("2026-08-27", "15", "", "n")) is None


# ---------- may_be_emptied / recreate_databases (the safety check before deleting) ----------

# Les noms que crée ce script sont autorisés...
def test_databases_made_by_this_script_may_be_emptied():
    assert may_be_emptied(database_name(chosen_hours(date(2026, 8, 27), 15, 1)))
    assert may_be_emptied(database_name(chosen_hours(date(2026, 8, 27), 15, 3)))


# ...et toutes les autres bases des deux serveurs sont refusées : le
# benchmark figé, celle du pipeline en direct, celle des tests
# d'intégration, et les bases intégrées des serveurs eux-mêmes.
def test_the_other_databases_may_never_be_emptied():
    for name in ("gharchive", "gharchive24h", "gharchivetest", "neo4j", "postgres", "system"):
        assert not may_be_emptied(name)


# ---------------------------------------------------------------------
# Le test le plus important du fichier : recreate_databases("gharchive")
# doit lever « Refusing to empty » AVANT de se connecter à quoi que ce
# soit. Ce test peut tourner sans aucun serveur de base de données et
# sans mot de passe : si la vérification venait après la connexion, le
# test échouerait plutôt avec une erreur de connexion — donc le fait
# qu'il réussisse prouve que l'ordre est le bon, et que le benchmark figé
# ne peut pas être supprimé par ce script.
# ---------------------------------------------------------------------
def test_recreate_refuses_before_connecting_to_anything():
    # The check comes first, so this fails safely even with no server running and no password.
    with pytest.raises(ValueError, match="Refusing to empty"):
        recreate_databases("gharchive")
