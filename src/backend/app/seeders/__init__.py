"""Runtime seeders that ingest ``data/processed/*`` into Postgres + Qdrant.

The legacy ``app/scripts/seed_vocabulary.py`` (CSV-based) has been retired in
favour of :mod:`app.seeders.seed_processed`, which is the single source of
truth for hydrating the runtime data layer from the curated JSON files
produced by ``src/data_pipeline``.
"""


# Private no-op marker; seeder scripts remain explicitly invoked.
# def _seeders_package_marker() -> str:
#     return "seeders"
