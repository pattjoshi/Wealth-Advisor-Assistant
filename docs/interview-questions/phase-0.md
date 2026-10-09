# Phase 0 — Setup — Interview Notes

## 1. What was built

Pure scaffolding, no business logic — the foundation every later phase builds on:

- `pyproject.toml` — single source of truth for dependencies, Ruff config, pytest config, build metadata (`hatchling`, src-layout).
- `Makefile` — the interface for every command (`install`, `lint`, `format`, `test`, `run`, `evaluate`, `ui`, `docker-build`, `clean`), so no one needs to remember raw tool invocations.
- `.env.example` — documents every `WA_*` environment variable, including `WA_OPENAI_MODEL` (never hardcoded).
- Empty `src/wealth_advisor/` package skeleton: `schemas/`, `graph/`, `agents/`, `tools/`, `services/`, `llm/`, `memory/`, `observability/` — the layer boundaries exist before a single feature does.
- `tests/unit/`, `tests/integration/`, one placeholder test, `data/`, `samples/`, `scripts/`, `ui/` directories.
- Minimal `README.md` stub (required by `pyproject.toml`'s `readme` field; full content comes in Phase 10).

Covers the project-setup prerequisite behind every "Core Requirement" in the assignment — nothing in R1–R12 is implemented yet.

## 2. Approach used and why

Scaffold the architecture *before* any feature, not alongside the first feature. The folder boundaries (`agents/` → `tools/` → `services/`) are a design decision, and committing them empty, on their own reviewable PR, makes that decision visible in the commit history rather than smuggled in with Phase 1's diff. It also means every later phase's PR diff is small and about one thing — easy to review, easy to explain in an interview commit-by-commit.

Verified the scaffold is real, not aspirational, before moving on: created a venv, ran `pip install -e ".[dev]"`, `pytest`, `ruff check`, `ruff format --check` — all green — rather than just writing config files and assuming they work.

## 3. Technology used and why

| Choice | Why | Alternative considered |
|---|---|---|
| `pyproject.toml` + `hatchling` | One file for deps/build/tool config (PEP 621); no `setup.py`, no `requirements.txt` drift | `setuptools` + `requirements.txt` — more files, no single source of truth |
| `src/` layout | Forces the package to be installed (`pip install -e .`) to be importable, which catches "works on my machine because cwd is on sys.path" bugs early | flat layout (`wealth_advisor/` at repo root) — simpler but hides import bugs until packaging |
| `Makefile` | Universal, zero extra dependency, self-documenting via `make help` | `tox`/`nox`/`invoke` — more powerful task runners, but another dependency for a solo assessment project |
| Ruff | One tool for lint + format, written in Rust (fast), replaces flake8 + isort + black | flake8 + black + isort separately — three tools, three configs, slower |
| `.env.example` committed, `.env` git-ignored | Documents required config without leaking secrets | Hardcoding defaults in code — breaks "model name is config, not code" requirement from the assignment's cost-control thinking |

## 4. Alternative approaches considered

- **Skip the Makefile, just document raw commands in README.** Rejected — a reviewer who clones the repo should not need to read prose to know `make test` works; `make help` is self-discovery.
- **Build Phase 0 and Phase 1 together in one PR.** Rejected — mixing scaffolding with the first real feature makes the diff harder to review and breaks the "one phase = one PR" convention the whole project follows.
- **Use `uv` instead of `pip` for the lockfile.** Considered, since `planning.md` allows either; stuck with `pip -e` for Phase 0 to keep the verification step dependency-free (no extra tool install needed to prove `make install` works) — `uv` can still be adopted later without changing `pyproject.toml`.

## 5. Expected interview questions

- Why `src/` layout instead of a flat package at the repo root?
- Why Ruff instead of flake8/black/isort?
- Why is `pyproject.toml` the single config file — what would go wrong with a `requirements.txt` + `setup.cfg` split?
- Why commit an empty package skeleton before writing any agent code?
- How do you keep `OPENAI_MODEL` out of code entirely — walk through the mechanism.
- What does `make check`/CI gain you that running tests locally doesn't?

## 6. Scenario-based questions

- **"A teammate adds a new dependency by editing `requirements.txt` directly."** How does this project's structure prevent that, and what's the correct way to add a dependency here?
- **"The CI pipeline needs to run on a clean machine with no Python preinstalled."** Walk through exactly what `make install` does and what could go wrong (Python version mismatch, missing build tools for a C-extension dependency, etc.).
- **"You need to swap the LLM provider from OpenAI to Anthropic six months from now."** Which files does Phase 0's scaffolding already isolate that change to, and why does that matter?
- **"A new engineer joins and wants to add a 'notification' feature that needs to call Slack."** Where would that code go in this skeleton, and what would you push back on if they tried to put the Slack API call directly inside `agents/insight.py`?
