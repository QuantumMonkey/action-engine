import os
import sqlite3
import sys

import pytest

sys.path.insert(0, os.path.dirname(os.path.dirname(os.path.abspath(__file__))))

from sqlite_mcp_server.guards import (  # noqa: E402
    PathLock, RefusalError, run_query, screen_select_only,
)
from scripts.make_fixture import build  # noqa: E402


@pytest.fixture()
def db(tmp_path):
    path = str(tmp_path / "sample.db")
    build(path)
    return path


@pytest.fixture()
def lock(db):
    return PathLock(db)


def test_select_passes(lock):
    result = run_query(lock, "SELECT name FROM customers ORDER BY id")
    assert result["columns"] == ["name"]
    assert result["row_count"] == 5
    assert result["rows"][0] == ["Meridian Textiles"]


def test_join_and_with_pass(lock):
    result = run_query(lock, (
        "WITH big AS (SELECT * FROM orders WHERE amount > 10000) "
        "SELECT c.name, b.amount FROM big b "
        "JOIN customers c ON c.id = b.customer_id"
    ))
    assert result["row_count"] >= 3


@pytest.mark.parametrize("sql", [
    "UPDATE customers SET name = 'x'",
    "DELETE FROM orders",
    "INSERT INTO customers VALUES (9, 'x', 'y', 'z')",
    "DROP TABLE customers",
    "CREATE TABLE evil (id INTEGER)",
    "PRAGMA journal_mode = DELETE",
    "ATTACH DATABASE 'other.db' AS other",
    "SELECT 1; DELETE FROM orders",
    "/* sneaky */ UPDATE customers SET name = 'x'",
])
def test_writes_refused_typed(lock, sql):
    with pytest.raises(RefusalError) as exc:
        run_query(lock, sql)
    assert exc.value.payload["error"] == "read_only_violation"
    assert exc.value.payload["attempted_sql"] == sql


def test_refusal_leaves_db_untouched(lock, db):
    with pytest.raises(RefusalError):
        run_query(lock, "DELETE FROM orders")
    conn = sqlite3.connect(db)
    assert conn.execute("SELECT COUNT(*) FROM orders").fetchone()[0] == 8
    conn.close()


def test_screen_strips_comments_and_semicolon():
    assert screen_select_only("SELECT 1; -- trailing").startswith("SELECT")


def test_missing_db_rejected(tmp_path):
    with pytest.raises(FileNotFoundError):
        PathLock(str(tmp_path / "nope.db"))


def test_symlink_swap_refused(tmp_path):
    real = str(tmp_path / "real.db")
    decoy = str(tmp_path / "decoy.db")
    build(real)
    build(decoy)
    link = str(tmp_path / "served.db")
    os.link(real, link)  # hardlink stands in; realpath check below uses swap
    lock = PathLock(link)
    # swap the served path for a symlink to the decoy
    os.remove(link)
    try:
        os.symlink(decoy, link)
    except OSError:
        pytest.skip("symlink creation not permitted (needs Windows dev mode)")
    with pytest.raises(RefusalError) as exc:
        run_query(lock, "SELECT 1")
    assert exc.value.payload["error"] == "path_lock_violation"


def test_row_cap_truncates(lock):
    result = run_query(lock, "SELECT * FROM orders", max_rows=3)
    assert result["row_count"] == 3
    assert result["truncated"] is True
