"""Scores a generated query by running it and comparing the rows it returns.

This is how the Spider benchmark is scored, and it is the honest way to grade SQL: a query
written differently from the recorded one but returning the same rows is a correct answer,
and comparing the text would mark it wrong.

It gets there by executing what the model wrote. The generated query is sent to SQLite,
against the copy of the database in this project. Row order is ignored unless it was asked
for; the rows are compared as a multiset.

This means the scorer runs model-written SQL. That is the whole mechanism -- there is no
version of execution scoring that does not do it. A query is executed on a local copy of a
small database, read-only in practice, with a five-second ceiling on how long any one of
them may run. Those bounds limit the damage; they do not change what the scorer is.
"""

import sqlite3
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_ROOT = PROJECT_ROOT / "databases"

QUERY_TIMEOUT_SECONDS = 5.0


def database_path(db_id):
    path = DATABASE_ROOT / db_id / f"{db_id}.sqlite"
    if not path.exists():
        raise FileNotFoundError(f"no copy of the {db_id!r} database in this project: {path}")
    return path


def execute(sql, db_id):
    """The rows a query returns, or the error that stopped it."""
    started = time.monotonic()
    connection = sqlite3.connect(str(database_path(db_id)), timeout=QUERY_TIMEOUT_SECONDS)
    connection.text_factory = lambda raw: raw.decode("utf-8", "replace")
    try:
        connection.set_progress_handler(
            lambda: 1 if time.monotonic() - started > QUERY_TIMEOUT_SECONDS else 0, 10_000
        )
        return connection.execute(str(sql)).fetchall(), None
    except sqlite3.Error as error:
        return None, str(error)
    finally:
        connection.close()


def as_multiset(rows):
    return sorted(repr(row) for row in rows)


def resolve_db_id(metadata, input_data):
    for source in (metadata, input_data):
        if isinstance(source, dict) and source.get("db_id"):
            return source["db_id"]
    raise KeyError(
        "no db_id on this row, so there is no database to run the query against -- "
        "running it against a different one would produce a confident wrong score"
    )


def score(output, expected, input_data=None, metadata=None):
    """1.0 when the generated query returns the same rows as the recorded one."""
    db_id = resolve_db_id(metadata, input_data)
    expected_sql = expected.get("sql") if isinstance(expected, dict) else expected
    if expected_sql is None or not str(expected_sql).strip():
        raise ValueError("this row has no recorded query, so there is nothing to compare against")

    gold_rows, gold_error = execute(expected_sql, db_id)
    if gold_error is not None:
        raise RuntimeError(
            f"the recorded query for this row does not run against {db_id}: {gold_error}. "
            "That is a fault in the data, not a wrong answer -- scoring around it would mark "
            "every attempt at this row wrong."
        )

    predicted_rows, predicted_error = execute(output, db_id)
    if predicted_error is not None:
        return 0.0
    ordered = "order by" in str(expected_sql).lower()
    if ordered:
        return 1.0 if [repr(r) for r in predicted_rows] == [repr(r) for r in gold_rows] else 0.0
    return 1.0 if as_multiset(predicted_rows) == as_multiset(gold_rows) else 0.0
