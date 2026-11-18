"""Unit tests for the safety rules of scripts/drop_databases.py (no network, no databases).

Run with:  python -m pytest
"""

import pytest

from drop_databases import drop_neo4j, drop_postgres, is_project_database, project_databases


def test_project_databases_are_recognised():
    for name in ("gharchive", "gharchive24h", "gharchive-2026-08-27-15", "gharchive-2026-08-27-15-6h",
                 "gharchivetest"):
        assert is_project_database(name)


def test_server_databases_are_never_project_databases():
    for name in ("postgres", "template0", "template1", "neo4j", "system", "myothers", "archive"):
        assert not is_project_database(name)


def test_project_databases_picks_only_the_project_ones_sorted():
    names = ["postgres", "gharchive24h", "template1", "gharchive", "neo4j", "gharchive-2026-11-09-9-5h"]
    assert project_databases(names) == ["gharchive", "gharchive-2026-11-09-9-5h", "gharchive24h"]


def test_drop_refuses_server_databases_before_connecting_to_anything():
    # The check comes first, so this fails safely even with no server running.
    with pytest.raises(ValueError, match="Refusing to delete"):
        drop_postgres("postgres")
    with pytest.raises(ValueError, match="Refusing to delete"):
        drop_neo4j(None, "neo4j")
