"""Scores a generated query by running it and comparing the rows it returns.

This is how the Spider benchmark is scored, and it is the honest way to grade SQL: a query
written differently from the recorded one but returning the same rows is a correct answer,
and comparing the text would mark it wrong.

It gets there by executing what the model wrote. The generated query is sent to SQLite,
against the copy of the database in this project. Row order is ignored unless it was asked
for; the rows are compared as a multiset.

This means the scorer runs model-written SQL. That is the whole mechanism -- there is no
version of execution scoring that does not do it. Three bounds are placed on it, and they
are worth stating exactly, because "it only reads" is easy to claim and easy to have wrong:

* The database is opened read-only, so a query that writes fails instead of writing. This
  matters more than it sounds. SQLite runs DDL outside the implicit transaction Python
  opens for INSERT/UPDATE/DELETE, so without this a hallucinated `DROP TABLE` really did
  drop the table, permanently -- and every later row on that database then failed and
  blamed the recorded answer for it.
* Only reading is authorised at all, which read-only mode by itself does not give:
  `ATTACH` and `VACUUM INTO` name their own files and would otherwise write outside the
  database.
* One query may run for five seconds and return a bounded number of rows. The time limit
  alone does not bound memory: a cross join can produce a gigabyte well inside it.

Those bounds limit the damage. They do not change what the scorer is.
"""

import sqlite3
import time
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_ROOT = PROJECT_ROOT / "databases"

QUERY_TIMEOUT_SECONDS = 5.0
# Comparing result sets is the point, and no recorded answer here returns anything like this
# many rows. The cap exists so a runaway cross join cannot exhaust memory inside the time
# limit; a query that reaches it is wrong by construction.
MAX_ROWS = 100_000
# Everything a scorer needs, and nothing that can name a file of its own.
READ_ONLY_ACTIONS = frozenset(
    {sqlite3.SQLITE_SELECT, sqlite3.SQLITE_READ, sqlite3.SQLITE_FUNCTION}
)


def _authorise_reads_only(action, *_arguments):
    return sqlite3.SQLITE_OK if action in READ_ONLY_ACTIONS else sqlite3.SQLITE_DENY


def database_path(db_id):
    path = DATABASE_ROOT / db_id / f"{db_id}.sqlite"
    if not path.exists():
        raise FileNotFoundError(
            f"no copy of the {db_id!r} database in this project: {path}"
        )
    return path


def execute(sql, db_id):
    """The rows a query returns, or the error that stopped it."""
    started = time.monotonic()
    connection = sqlite3.connect(
        f"file:{database_path(db_id)}?mode=ro", uri=True, timeout=QUERY_TIMEOUT_SECONDS
    )
    connection.text_factory = lambda raw: raw.decode("utf-8", "replace")
    try:
        connection.set_authorizer(_authorise_reads_only)
        connection.set_progress_handler(
            lambda: 1 if time.monotonic() - started > QUERY_TIMEOUT_SECONDS else 0,
            10_000,
        )
        rows = []
        for row in connection.execute(str(sql)):
            rows.append(row)
            if len(rows) > MAX_ROWS:
                return None, f"returned more than {MAX_ROWS} rows"
        return rows, None
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
        raise ValueError(
            "this row has no recorded query, so there is nothing to compare against"
        )

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
        return (
            1.0
            if [repr(r) for r in predicted_rows] == [repr(r) for r in gold_rows]
            else 0.0
        )
    return 1.0 if as_multiset(predicted_rows) == as_multiset(gold_rows) else 0.0
