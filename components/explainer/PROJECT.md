# What is in here

Two agents share this directory.

`agent.py` answers a question about a database by writing the SQL for it. That is the one
we care about: it is what the product calls, its answers are what `dataset.jsonl` and
`evaluator.py` measure, and it is the one to work on.

`sql_explainer/` is a side tool. It takes a query and describes in a sentence what the
query returns; we use it to annotate reports. It has its own handful of queries to run on
and a rough check of its own, and it is fine as it is -- leave it alone.
