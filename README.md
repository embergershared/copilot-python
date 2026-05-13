# Copilot Python App

Azure-ready FastAPI service scaffold optimized for GitHub Copilot CLI, local development, GitHub Actions, and Copilot cloud agent workflows.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,azure]"
pytest
uvicorn copilot_python_app.main:app --reload
```

## Developer commands

| Task | Command |
| --- | --- |
| Install app | `python -m pip install -e .` |
| Install dev dependencies | `python -m pip install -e ".[dev,azure]"` |
| Lint | `ruff check .` |
| Format | `ruff format .` |
| Type-check | `mypy` |
| Test | `pytest` |
| Coverage | `pytest --cov=copilot_python_app --cov-report=term-missing` |
| Run locally | `uvicorn copilot_python_app.main:app --reload` |
| Security checks | `bandit -r src` and `pip-audit` |
| Build container | `docker build -t copilot-python-app:local .` |
| Run container | `docker compose up --build` |

## Runtime configuration

Configuration is loaded from environment variables prefixed with `APP_` and an optional `.env` file.

| Variable | Default | Description |
| --- | --- | --- |
| `APP_NAME` | `copilot-python-app` | Service display name |
| `APP_ENVIRONMENT` | `local` | Runtime environment: `local`, `dev`, `test`, or `prod` |
| `APP_LOG_LEVEL` | `INFO` | Python logging level |
| `APP_VERSION` | `0.1.0` | Service version exposed by health checks |

## Endpoints

| Endpoint | Description |
| --- | --- |
| `/` | Basic service metadata |
| `/health` | Health response for local, container, and Azure probes |

## Dev container and Docker

The `.devcontainer/devcontainer.json` uses the Microsoft Dev Containers Python 3.12 image and installs the project with development and Azure extras after creation.

The Docker image runs the FastAPI app with Uvicorn on port `8000`. Use `docker compose up --build` for a local container run with the same health endpoint used by Azure probes.

## Azure MCP Server deployment

To deploy the official Azure MCP Server to Azure Container Apps for Copilot Studio with OAuth On-Behalf-Of user delegation, follow [docs/azure-mcp-obo-container-app.md](docs/azure-mcp-obo-container-app.md). That deployment is intentionally separate from this FastAPI service because it uses the official Azure MCP Server image and Entra app-registration model.

