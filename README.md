# Copilot Python App

Azure-ready FastAPI service scaffold optimized for GitHub Copilot CLI, local development, GitHub Actions, and Copilot cloud agent workflows.

## Quick start

```powershell
python -m venv .venv
.\.venv\Scripts\Activate.ps1
python -m pip install --upgrade pip
python -m pip install -e ".[dev,azure]"
pytest
python src\main.py serve --reload
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
| Run locally | `python src\main.py serve --reload` (or `uvicorn copilot_python_app.main:app --reload`) |
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

## Reusable modules

Two top-level packages live alongside the FastAPI app and are intentionally portable —
they have **no FastAPI imports** and can be lifted into other Python services:

### `emm_logging` — opinionated logging bootstrap

Wires Python's stdlib `logging` to a console handler (human-readable text by default;
opt-in JSON via `LOG_CONSOLE_FORMAT=json`) plus optional Seq (HTTP/CLEF) and Azure
Monitor sinks. Configuration is read from `LOG_*` environment variables via
`pydantic-settings` (independent of the app's `APP_*` namespace).

```python
from emm_logging import LoggingSettings, get_logger, setup_logging

sinks = setup_logging(LoggingSettings(service_name="my-service", service_version="1.2.3"))
log = get_logger(__name__)
log.info("ready", extra={"console": sinks.console is not None, "seq": sinks.seq})
```

Public API: `setup_logging`, `LoggingSettings`, `LoggingSinks`, `get_logger`,
`timestamp_prefix`. Optional Seq dep: `pip install ".[seq]"`. Optional Azure Monitor dep:
`pip install ".[azure]"`.

### `emm_settings` — typed env accessors + `.env` loading

Lightweight helpers for reading typed env vars with logged provenance, loading
`.env` files (graceful when `python-dotenv` is missing), and emitting a redacted
settings snapshot at startup.

```python
from emm_settings import env_int, env_str, load_dotenv_files, log_settings

load_dotenv_files(".env", ".env.local")
port = env_int("PORT", default=8000)
db = env_str("DATABASE_URL", default="", secret=True)
log_settings(my_settings_object)  # auto-redacts *_key, *_secret, *_password, etc.
```

Public API: `env_str`, `env_int`, `env_float`, `env_bool`, `env_path`, `env_csv`,
`load_dotenv_files`, `log_settings`. Each accessor logs the resolved value (or
`***REDACTED***` when `secret=True`) at INFO if it came from the environment, DEBUG if
the default was used.

The FastAPI app bootstraps both modules in `copilot_python_app.main._bootstrap()`.

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

