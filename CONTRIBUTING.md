# Contributing to Hybrid Search Product Store

Thanks for your interest in contributing! This repo contains a React front-end and a Python FastAPI backend that implements a hybrid (lexical + semantic) product search on Elasticsearch.

By participating in this project, you agree to abide by our [Code of Conduct](CODE_OF_CONDUCT.md).


## Project Structure

- `frontend/` — React app (Create React App). UI for search, suggestions, filters, analytics.
- `backend/` — FastAPI app plus infra and ingestion scripts for Elasticsearch.
  - `backend/docker/` — Docker Compose for Elasticsearch + Kibana.
  - `backend/infra/` — index creation scripts and mappings.
  - `backend/ingestion/` — dataset ingestion and vector generation.
  - `backend/api/` — FastAPI application.

See the root `README.md` for a full run guide.


## Prerequisites

- Node.js 18+
- Python 3.10+
- Docker (recommended for running Elasticsearch and Kibana)


## Development Setup

### Backend

1) Install Python deps using uv (recommended):

```bash
cd backend
uv sync
```

2) Create env file:

```bash
cp .env.example .env
# Update ES_HOST / ES_USERNAME / ES_PASSWORD as needed
```

3) Start Elasticsearch and Kibana (recommended via Docker):

```bash
cd docker
docker compose up -d
# ES → http://localhost:9200, Kibana → http://localhost:5601
```

4) Create index and mappings:

```bash
cd ../infra
python create_index.py
```

5) Ingest data (downloads and caches embedding model on first run):

```bash
cd ../ingestion
python ingestion.py
```

6) Run the API (FastAPI + Uvicorn):

```bash
cd ../api
python -m pip install -r ../requirements.txt
uvicorn api:app --host 127.0.0.1 --port 5000 --reload
```

Endpoints (examples):
- `GET /api/products/search?query=term`
- `GET /api/products/facets?query=term`
- `GET /api/products/suggest?query=te` (autocomplete)


### Frontend

```bash
cd frontend
npm install
npm start
# Opens http://127.0.0.1:3000 (API defaults to http://127.0.0.1:5000)
```

Scripts:
- `npm start` — dev server
- `npm run build` — production build
- `npm test` — React Testing Library tests (if/when added)


## Coding Guidelines

- Keep UI state colocated and components small in `frontend/src/`.
- Use clear, typed interfaces where appropriate (JSDoc or TS in future).
- Follow idiomatic FastAPI patterns in `backend/api/`.
- Prefer pure functions for search transformations and mappings.
- Large data/IO steps live under `backend/ingestion/` and `backend/infra/`.

Formatting/linting:
- Frontend uses CRA’s ESLint config. Please run `npm test` and ensure no ESLint errors are introduced.
- Backend: follow PEP8; add type hints where helpful. If you use formatters (e.g., black, ruff), mention in the PR.


## Branching and Commits

- Create a feature branch from `main`: `feat/<scope>-<short-desc>` or `fix/<issue-number>`.
- Prefer Conventional Commits style when possible:
  - `feat:`, `fix:`, `docs:`, `refactor:`, `test:`, `chore:`
- Reference GitHub issues in your commits/PR description (e.g., `Fixes #123`).


## Tests

- Frontend: add tests with React Testing Library for new UI logic where feasible.
- Backend: add unit tests for parser/transform functions. Start with simple assertions; mock ES when needed.
- If adding endpoints or query logic, include example requests in the PR description.


## Pull Requests

- Use the existing issue templates under `.github/ISSUE_TEMPLATE/` when filing bugs/feature requests.
- Keep PRs focused and small; include:
  - What and why of the change
  - Screenshots/GIFs for UI changes
  - Steps to reproduce/verify
- Ensure you can run through the “Full Run Guide” in `README.md` locally after your changes.

Checklist before opening a PR:
- [ ] Code builds and runs locally (frontend and backend as applicable)
- [ ] Lint passes / no obvious warnings
- [ ] Added/updated tests or notes on test coverage
- [ ] Updated docs/README where relevant


## Reporting Bugs and Requesting Features

- Search existing issues first. If none exist, open a new issue using the templates in `.github/ISSUE_TEMPLATE/`.
- Include reproduction steps, logs, screenshots, and environment details.


## Security

If you discover a security or data exposure issue, please do not open a public issue. Instead, start a private report via GitHub Security Advisories ("Report a vulnerability" on the repo) or contact the maintainers via a private channel (e.g., direct message to the repository owner on GitHub). We will coordinate a fix and disclosure.


## License

By contributing, you agree that your contributions will be licensed under the project’s existing LICENSE.
