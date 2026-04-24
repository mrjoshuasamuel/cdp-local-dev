# CLAUDE.md

This file provides guidance to Claude Code (claude.ai/code) when working with code in this repository.

## What this is

A Python CLI that runs Apache Airflow in Docker Compose on a developer's laptop so they can iterate on DAG code without touching the cloud. The whole project is end-user install tooling: its job is to orchestrate `docker compose` reliably across Windows / macOS / Linux with zero manual setup, while bind-mounting the developer's `./dags` directory live into the Airflow containers.

Previously this project provisioned Kind + Helm (see git history). That was dropped in favour of Compose because (a) the Kind path never wired DAG ingestion up and (b) prod runs on Kubernetes but local dev only needs DAG-code iteration speed, not real pod-spec parity.

## Install & run (dev)

```bash
pip install -e .                 # editable install from repo root
python -m cdp_dev <command>      # always works (python always on PATH)
cdp-dev <command>                # available after first run installs the wrapper
```

Commands: `install`, `start`, `stop`, `status`, `logs [service]`, `destroy`, `test <dag_id>`. No test suite or lint config — this is a pure runtime CLI.

## Architecture

The CLI is a thin Click group ([cdp_dev/cli.py](cdp_dev/cli.py)) that dispatches to one file per command in [cdp_dev/commands/](cdp_dev/commands/). Commands delegate to a small set of modules:

- [compose_manager.py](cdp_dev/compose_manager.py) — wraps `docker compose`. Every call passes `--project-directory` and `-f <compose>` explicitly, so CWD-relative confusion cannot happen. Also owns `wait_healthy()` which polls `docker inspect` until a service's healthcheck passes.
- [project.py](cdp_dev/project.py) — locates / initializes a cdp-local-dev project. A project is any directory containing `.cdp-dev/state.json`. `find_project_root()` walks up from CWD, git-style. `ensure_or_init()` creates `dags/ logs/ plugins/`, copies the compose template, and renders `.env` (Fernet key, webserver secret, `AIRFLOW_UID`).
- [preflight.py](cdp_dev/preflight.py) — ensures Docker is installed and running, then detects whether `docker compose` V2 or legacy `docker-compose` V1 is available and tells `compose_manager` which to use via `set_compose_cmd()`.
- [migration.py](cdp_dev/migration.py) — one-shot cleanup of the old `cdp-local` Kind cluster when users upgrade from the Helm-based v0.1.x. No-op when `kind` isn't on PATH.
- [path_helper.py](cdp_dev/path_helper.py) — makes the `cdp-dev` script globally accessible. On Windows writes `cdp-dev.bat` into `C:\Windows\System32`; on Unix appends to the shell rc file. Called on **every** CLI invocation via the Click group callback in [cli.py:40-41](cdp_dev/cli.py#L40) so first-run setup is silent.

## Non-obvious behaviors to preserve

- **Apple Silicon Rosetta detection in preflight.** `platform.machine()` lies under Rosetta (returns `x86_64` on ARM hardware), so `_is_rosetta_translated()` uses `sysctl -n sysctl.proc_translated == "1"` instead. `_brew_cmd()` returns `["arch", "-arm64", "/opt/homebrew/bin/brew"]` when a translated process is about to invoke ARM Homebrew. This avoids the "Cannot install under Rosetta 2 in ARM default prefix" error that killed the previous Kind-based install.

- **Compose CLI is runtime-detected.** Do not hardcode `docker compose` in `compose_manager.py`. [preflight.py:_detect_compose](cdp_dev/preflight.py) probes V2 first, falls back to V1, and stores the result via `set_compose_cmd()`. `COMPOSE_CMD` is a module-level list that all compose calls splat into their argv.

- **Templates are package data, resolved via two paths.** `compose_manager.template_path()` currently resolves against `cdp_dev/templates/` only. The old helm-dir resolution pattern from the previous architecture is gone because templates always ship inside the package — do not reintroduce a repo-root fallback unless we add a non-package source.

- **`.env` is written once, never regenerated.** `project._ensure_env_file()` is a no-op if `.env` exists so Fernet keys are stable across reinstalls (regenerating them would orphan encrypted connection passwords in Postgres). To rotate keys, the user deletes `.env` manually.

- **`docker-compose.yml` is overwritten on every install except when hand-edited.** `_ensure_compose_file()` looks for the `# cdp-local-dev managed` header in the first bytes. If missing (dev customized the file), it leaves the file alone and warns. Keep that header in [cdp_dev/templates/docker-compose.yml](cdp_dev/templates/docker-compose.yml).

- **AIRFLOW_UID must equal `id -u` on Linux.** `project._resolve_airflow_uid()` returns `os.getuid()` on Linux, `50000` elsewhere. Without this, Linux users get root-owned `./logs` and Airflow can't write to it. Docker Desktop on Mac/Windows handles UID mapping transparently so the 50000 default is fine there.

- **`destroy` deletes the Postgres volume but never user files.** `compose down -v` removes the named `postgres-db-volume` only. `./dags`, `./logs`, `./plugins` are user files and stay. If that ever changes, it's a breaking behavior change — callers rely on this.

- **`test <dag_id>` uses `airflow dags test`, not `airflow tasks test`.** Full-DAG, in-process, no scheduler dependency. This is the intended fast-feedback primitive for DAG development — don't "upgrade" it to a trigger-via-API.

- **Non-install commands require a project root or fail loudly.** Use `project.require_project_root()`, not `Path.cwd()`. It walks up like git. Running `cdp-dev stop` from `/` should error, not silently no-op.

## Hard-coded values worth knowing

- Airflow image: `apache/airflow:2.9.3` (both template default and `.env` default).
- Executor: `LocalExecutor` — avoids Redis/Celery/Flower. Changing this requires editing the template.
- UI: `127.0.0.1:8080` (localhost-only binding, not `0.0.0.0`). Creds `admin` / `admin`.
- Postgres: `postgres:13`, named volume `postgres-db-volume`, credentials `airflow`/`airflow`/`airflow`.
- DAG pickup latency: `AIRFLOW__SCHEDULER__DAG_DIR_LIST_INTERVAL=30` (tuned down from the 300s default for dev feedback speed).
- Project marker: `.cdp-dev/state.json` at project root.
- Old Kind cluster name (for migration detection only): `cdp-local`.
