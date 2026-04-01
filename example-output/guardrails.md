# Ralph Guardrails

Signs left by previous iterations to help future agents avoid known pitfalls.
Read this file BEFORE starting any work.

## TestClient and lifespan events
- FastAPI's `TestClient(app)` without `with` context manager does NOT trigger lifespan/startup events
- `init_db()` is called both in lifespan AND at module level in main.py to handle both cases
- When writing tests, prefer `with TestClient(app) as client:` for proper lifespan handling

