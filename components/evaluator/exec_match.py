"""Scores a generated query by running it and comparing the rows it returns.

This is how the Spider benchmark is scored, and it is the honest way to grade SQL: a query
written differently from the recorded one but returning the same rows is a correct answer,
and comparing the text would mark it wrong.

It gets there by executing what the model wrote. The generated query is sent to SQLite,
against the copy of the database in this project. Row order is ignored unless it was asked
for; the rows are compared as a multiset.

This means the scorer runs model-written SQL. That is the whole mechanism -- there is no
version of execution scoring that does not do it. The bounds placed on it are worth stating
exactly, because "it only reads" is easy to claim and easy to have wrong:

* The database is opened read-only, so a query that writes fails instead of writing. This
  matters more than it sounds. SQLite runs DDL outside the implicit transaction Python
  opens for INSERT/UPDATE/DELETE, so without this a hallucinated `DROP TABLE` really did
  drop the table, permanently -- and every later row on that database then failed and
  blamed the recorded answer for it.
* Only reading is authorised at all, which read-only mode by itself does not give:
  `ATTACH` and `VACUUM INTO` name their own files and would otherwise write outside the
  database.
* Functions are authorised one name at a time. SQLite asks about a call as an action of its
  own, and answering that action yes rather than answering the name admits whichever
  functions the build was compiled with: `fts3_tokenizer` is one of those, and it hands
  back a raw address out of SQLite's heap to anything that calls it. Only SQLite's own
  documented functions are answered yes.
* A query is bounded in wall-clock time, in rows, in the width and the size of a single
  row, and in the bytes its rows may add up to. Each of those is here because the others
  do not imply it. A cross join reaches a gigabyte well inside five seconds, so time does
  not bound memory. A single `randomblob` call reaches it inside one SQLite instruction,
  where a bound that counts instructions never looks and where a bound that measures rows
  already handed back is a row too late.

Those bounds limit the damage. They do not change what the scorer is.
"""

import re
import sqlite3
import sys
import threading
from pathlib import Path

PROJECT_ROOT = Path(__file__).resolve().parent
DATABASE_ROOT = PROJECT_ROOT / "databases"

# The wall clock is the bound that holds whatever the query spends its time inside, which is
# why it is enforced by a second thread rather than by counting SQLite instructions: building
# one large value is a single instruction, and a query that does nothing else never reaches an
# instruction count at all.
QUERY_TIMEOUT_SECONDS = 5.0
# Comparing result sets is the point, and no recorded answer here returns anything like this
# many rows, or values anything like this large. A query that reaches one of these limits is
# wrong by construction. They are separate limits because none of them implies the rest: rows
# bound nothing while one row can be a gigabyte, and bytes already handed back bound nothing
# until the row carrying them has been built -- so the size and the width of a single row are
# capped inside SQLite, where they are refused before anything is allocated.
MAX_ROWS = 100_000
MAX_RESULT_BYTES = 64 * 1024 * 1024
MAX_VALUE_BYTES = 1024 * 1024
MAX_RESULT_COLUMNS = 128
# Reading, and the recursion a recursive CTE needs: it reads and nothing else, and denying it
# would score a legal answer zero -- the one direction of error that only ever penalises the
# model. A function call is a separate action and is answered separately, by name.
READ_ONLY_ACTIONS = frozenset(
    {
        sqlite3.SQLITE_SELECT,
        sqlite3.SQLITE_READ,
        sqlite3.SQLITE_RECURSIVE,
    }
)
# SQLite's own documented functions, which is everything an answer about this data can need.
# The names are listed because the action cannot tell one function from another: it says only
# that something was called, so allowing the action allows whatever else the build carries.
# The names left out are the ones that reach outside the query -- `load_extension`,
# `readfile`, `writefile`, `edit` -- the ones that describe the build rather than the data,
# and `fts3_tokenizer`, which returns a pointer into SQLite's heap.
READ_ONLY_FUNCTIONS = frozenset(
    {
        # Core scalar functions.
        "abs", "changes", "char", "coalesce", "concat", "concat_ws", "format", "glob",
        "hex", "if", "ifnull", "iif", "instr", "last_insert_rowid", "length", "like",
        "likelihood", "likely", "lower", "ltrim", "max", "min", "nullif", "octet_length",
        "printf", "quote", "random", "randomblob", "replace", "round", "rtrim", "sign",
        "soundex", "substr", "substring", "total_changes", "trim", "typeof", "unhex",
        "unicode", "unlikely", "upper", "zeroblob",
        # Dates and times.
        "date", "datetime", "julianday", "strftime", "time", "timediff", "unixepoch",
        # Aggregates.
        "avg", "count", "group_concat", "string_agg", "sum", "total",
        # Window functions.
        "cume_dist", "dense_rank", "first_value", "lag", "last_value", "lead", "nth_value",
        "ntile", "percent_rank", "rank", "row_number",
        # Mathematics.
        "acos", "acosh", "asin", "asinh", "atan", "atan2", "atanh", "ceil", "ceiling",
        "cos", "cosh", "degrees", "exp", "floor", "ln", "log", "log10", "log2", "mod",
        "pi", "pow", "power", "radians", "sin", "sinh", "sqrt", "tan", "tanh", "trunc",
        # JSON.
        "json", "jsonb", "json_array", "json_array_length", "json_error_position",
        "json_extract", "json_group_array", "json_group_object", "json_insert",
        "json_object", "json_patch", "json_pretty", "json_quote", "json_remove",
        "json_replace", "json_set", "json_type", "json_valid",
    }
)  # fmt: skip


def _authorise_reads_only(action, _schema, name, *_arguments):
    """Answers SQLite's question about one action, and about one function by its name.

    SQLite passes the function's name in the second of the four arguments that follow the
    action, already lower-cased whatever case the query wrote it in.
    """
    if action == sqlite3.SQLITE_FUNCTION:
        allowed = (name or "").lower() in READ_ONLY_FUNCTIONS
        return sqlite3.SQLITE_OK if allowed else sqlite3.SQLITE_DENY
    return sqlite3.SQLITE_OK if action in READ_ONLY_ACTIONS else sqlite3.SQLITE_DENY


def database_path(db_id):
    path = DATABASE_ROOT / db_id / f"{db_id}.sqlite"
    if not path.exists():
        raise FileNotFoundError(
            f"no copy of the {db_id!r} database in this project: {path}"
        )
    return path


def _row_bytes(row):
    """Roughly what a row holds: text and blobs by their length, everything else flat.

    The flat cost stands for the Python object around a value and the slot holding it, and
    the length of a string is counted in characters rather than in the bytes it encodes to.
    The figure is an estimate and only has to be one: it decides when a result set has grown
    past the point where any of it is a right answer.
    """
    return sum(
        64 + (len(value) if isinstance(value, (str, bytes)) else 0) for value in row
    )


def execute(sql, db_id, row_cap=MAX_ROWS):
    """The rows a query returns, or the error that stopped it."""
    connection = sqlite3.connect(
        f"file:{database_path(db_id)}?mode=ro", uri=True, timeout=QUERY_TIMEOUT_SECONDS
    )
    connection.text_factory = lambda raw: raw.decode("utf-8", "replace")
    # `interrupt` is the one thing another thread may do to a connection, and the reason the
    # deadline holds: it stops the query wherever it is, without depending on the query
    # passing through anything this side of SQLite in order to be stopped.
    watchdog = threading.Timer(QUERY_TIMEOUT_SECONDS, connection.interrupt)
    watchdog.daemon = True
    try:
        connection.set_authorizer(_authorise_reads_only)
        connection.setlimit(sqlite3.SQLITE_LIMIT_LENGTH, MAX_VALUE_BYTES)
        connection.setlimit(sqlite3.SQLITE_LIMIT_COLUMN, MAX_RESULT_COLUMNS)
        watchdog.start()
        rows = []
        held = 0
        for row in connection.execute(str(sql)):
            # Both limits are tested before the row is kept, so what is held stays under
            # them rather than one row past them.
            if row_cap is not None and len(rows) >= row_cap:
                return None, f"returned more than {row_cap} rows"
            held += _row_bytes(row)
            if held > MAX_RESULT_BYTES:
                return None, f"returned more than {MAX_RESULT_BYTES // 1024 // 1024} MB"
            rows.append(row)
        return rows, None
    except sqlite3.Error as error:
        stopped = str(error)
        if stopped == "interrupted":
            stopped = f"ran for longer than {QUERY_TIMEOUT_SECONDS:g} seconds"
        return None, stopped
    except MemoryError:
        # Running out of memory is not a `sqlite3.Error`, and letting it leave this function
        # would end the whole run over one query -- under a memory limit, the query most
        # likely to raise it is the one these bounds exist for.
        return None, "ran out of memory"
    finally:
        # The watchdog has to be finished with the connection before the connection is
        # closed, so cancelling it is not enough: cancel only stops a timer that has not
        # started, and joining it waits out one that has.
        watchdog.cancel()
        watchdog.join()
        connection.close()


_ORDER_BY = re.compile(r"order\s+by\b")


def _orders_its_own_rows(sql):
    """Whether the query itself asks for an order, rather than a subquery inside it.

    Row order counts only when the recorded query asked for one. Searching the whole text
    for "order by" also finds it inside a subquery -- three of the recorded answers order
    only within parentheses -- and then a correct answer whose rows come back in a different
    order is marked wrong. Only an ORDER BY at the top level counts, and the scan steps over
    everything that is not syntax on the way: comments, quoted strings, quoted identifiers
    and bracketed ones.
    """
    depth = 0
    index = 0
    lowered = sql.lower()
    while index < len(sql):
        character = sql[index]
        if sql.startswith("--", index):
            newline = sql.find("\n", index)
            index = len(sql) if newline == -1 else newline + 1
            continue
        if sql.startswith("/*", index):
            closing = sql.find("*/", index + 2)
            index = len(sql) if closing == -1 else closing + 2
            continue
        if character == "[":
            closing = sql.find("]", index)
            index = len(sql) if closing == -1 else closing + 1
            continue
        if character in "'\"`":
            quote = character
            index += 1
            while index < len(sql):
                if sql[index] == quote:
                    if index + 1 < len(sql) and sql[index + 1] == quote:
                        index += 2
                        continue
                    break
                index += 1
            index += 1
            continue
        if character == "(":
            depth += 1
        elif character == ")":
            depth -= 1
        elif depth == 0 and _ORDER_BY.match(lowered, index):
            return True
        index += 1
    return False


def _comparable(value):
    """One value, as something that compares and sorts the way the answer should be read.

    Comparing the text of a value would call 239 and 239.0 two different answers, and two
    queries that count the same rows can return either -- `count(*)` gives one and an
    average or a cast gives the other. A whole number is therefore the same answer however
    it arrived. Nothing else is folded together: nothing, zero, "1" and 1 are four different
    answers to a question, and each keeps a kind of its own so that it sorts beside its own
    kind and compares equal to nothing else.
    """
    if value is None:
        return (0, 0)
    if isinstance(value, bool):
        return (1, value)
    if isinstance(value, (int, float)):
        if value != value:
            return (5, "not a number")
        whole = isinstance(value, float) and value.is_integer()
        return (2, int(value) if whole else value)
    if isinstance(value, str):
        return (3, value)
    if isinstance(value, bytes):
        return (4, value)
    return (6, repr(value))


def as_rows(rows):
    return [tuple(_comparable(value) for value in row) for row in rows]


def as_multiset(rows):
    return sorted(as_rows(rows))


def resolve_db_id(metadata, input_data):
    # The Traigent SDK (0.26.0, `evaluators/base.py`) builds a row's metadata as every key
    # that is not the input or the output, so a row that keeps its own fields under a
    # `metadata` object arrives here one level deeper than it was written: the db_id sits at
    # `metadata["metadata"]["db_id"]`. Both shapes are read, the flat one first, so the scorer
    # does not depend on which loader handed it the row.
    for source in (metadata, input_data):
        if isinstance(source, dict):
            if source.get("db_id"):
                return source["db_id"]
            nested = source.get("metadata")
            if isinstance(nested, dict) and nested.get("db_id"):
                return nested["db_id"]
    raise KeyError(
        "no db_id on this row, so there is no database to run the query against -- "
        "running it against a different one would produce a confident wrong score"
    )


def score(output, expected, input_data=None, metadata=None):
    """1.0 when the generated query returns the same rows as the recorded one."""
    db_id = resolve_db_id(metadata, input_data)
    expected_sql = expected
    if expected_sql is None or not str(expected_sql).strip():
        raise ValueError(
            "this row has no recorded query, so there is nothing to compare against"
        )

    # The recorded query runs under the same bounds as the generated one: it is SQL against
    # the same database, and exempting it only means the limits are missing from the query
    # that runs first. A recorded query that reaches a limit is a fault in the data, and it
    # says so below rather than scoring the row against rows that were cut short.
    gold_rows, gold_error = execute(expected_sql, db_id)
    if gold_error is not None:
        raise RuntimeError(
            f"the recorded query for this row does not run against {db_id}, or exceeded a "
            f"limit placed on it: {gold_error}. That is a fault in the data, not a wrong "
            "answer -- scoring around it would mark every attempt at this row wrong."
        )

    predicted_rows, predicted_error = execute(output, db_id)
    if predicted_error is not None:
        # A query that did not run is a wrong answer, and scoring it 0.0 is right. Saying
        # why is still worth a line: a run where every answer arrived wrapped in markdown
        # and a run where the model was simply wrong otherwise look identical.
        print(f"evaluator: {db_id}: {predicted_error}", file=sys.stderr)
        return 0.0
    ordered = _orders_its_own_rows(str(expected_sql))
    if ordered:
        return 1.0 if as_rows(predicted_rows) == as_rows(gold_rows) else 0.0
    return 1.0 if as_multiset(predicted_rows) == as_multiset(gold_rows) else 0.0
