"""Optional seeders that ingest ``data/processed/*`` into Postgres + Qdrant.

The legacy ``app/scripts/seed_vocabulary.py`` (CSV-based) has been retired in
favour of :mod:`app.seeders.seed_processed`. These commands hydrate demo,
evaluation, and inspection stores from curated JSON files produced by
``src/data_pipeline``; they are not required for the live chat hotpath.
"""


# Private no-op marker; seeder scripts remain explicitly invoked.
# def _seeders_package_marker() -> str:
#     return "seeders"
