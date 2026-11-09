# Backend test tiers

The default test command runs unit and contract tests without requiring
PostgreSQL, Groq, Gemini, or Qdrant:

```text
pytest -m "not integration and not external"
```

PostgreSQL integration tests require an explicit `TEST_DATABASE_URL` pointing
to a reachable database whose name is not `payflow_copilot`:

```text
set TEST_DATABASE_URL=postgresql+psycopg://user:password@localhost:5432/payflow_copilot_test
pytest -m integration
```

The integration fixture runs `alembic upgrade head` before tests and truncates
only the explicitly configured test database after each test. It refuses to
run against the development database and skips with a reason when the test
database is missing or unreachable. PostgreSQL-specific UUID, JSONB, partial
index, foreign-key, and uniqueness behavior is therefore tested against
PostgreSQL, not SQLite.

External-provider tests are reserved for the `external` marker. Ordinary
integration tests mock Groq and Qdrant at service boundaries and do not require
network access to those providers.
