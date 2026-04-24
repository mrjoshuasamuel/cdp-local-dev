# CDP Local Developer Environment

Run Apache Airflow locally in Docker Compose so you can iterate on DAGs on
your laptop — no cloud account, no VPN, no waiting for Dataproc.

- Install in **under 2 minutes** (excluding first-time Docker image pull)
- **~2 GB RAM** at rest
- Your **`./dags/`** folder is mounted live into Airflow — save a file, the
  scheduler picks it up in ~30 seconds
- One-shot DAG runs via **`cdp-dev test <dag_id>`** for fast feedback

---

## Prerequisites

| Tool | Notes |
|------|-------|
| Docker Desktop (Mac/Win) or Docker Engine + Compose plugin (Linux) | Allocate ≥ 4 GB RAM to Docker. Auto-started if installed but stopped. |
| Python 3.10+ | Required to run the CLI. |

---

## Install

```bash
pip install git+https://github.com/mrjoshuasamuel/cdp-local-dev.git
```

Then, **from inside your pipeline repository**:

```bash
cd path/to/your-pipeline
python -m cdp_dev install
```

This initializes the project (creates `./dags`, `./logs`, `./plugins`, `.env`,
and a managed `docker-compose.yml`) and starts the Airflow stack.

After the first run, `cdp-dev` is also available as a direct command:

```bash
cdp-dev install
cdp-dev test my_dag
cdp-dev stop
```

---

## Daily workflow

```bash
# Write DAGs into ./dags — scheduler picks them up automatically in ~30s.
vim dags/my_pipeline.py

# Run a DAG end-to-end without waiting for the scheduler:
cdp-dev test my_pipeline

# Open the Airflow UI:
open http://127.0.0.1:8080      # admin / admin

# Pause at end of day (data preserved):
cdp-dev stop

# Resume next morning:
cdp-dev start
```

---

## All commands

| Command | Description |
|---------|-------------|
| `cdp-dev install` | First-time setup: init project + start Airflow. |
| `cdp-dev start` | Resume the stack after `stop` or a reboot. |
| `cdp-dev stop` | Pause containers (data preserved). |
| `cdp-dev status` | Show container state + health. |
| `cdp-dev logs [service]` | Tail logs (`airflow`/`webserver`/`scheduler`/`triggerer`/`postgres`). |
| `cdp-dev test <dag_id>` | Run a DAG end-to-end via `airflow dags test`. |
| `cdp-dev destroy` | Remove containers + metadata DB (your `./dags` and `./logs` are kept). |

---

## What's in your project dir after `install`

```
your-pipeline/
├── .cdp-dev/
│   └── state.json          ← project marker (don't delete)
├── .env                    ← generated secrets (Fernet key etc.)
├── docker-compose.yml      ← managed by cdp-dev (regenerated on install)
├── dags/                   ← put your DAG files here
├── logs/                   ← Airflow task logs land here
└── plugins/                ← optional: custom operators / hooks
```

The `.env`, `docker-compose.yml`, `logs/`, and `plugins/` entries are safe
to add to `.gitignore`. Commit `dags/` and `.cdp-dev/` if you want teammates
to share the same local setup.

---

## Extra pip packages (providers, libraries)

Edit `.env`:

```
_PIP_ADDITIONAL_REQUIREMENTS=apache-airflow-providers-google==10.17.0 pandas
```

Then `cdp-dev stop && cdp-dev start`. The containers install these on boot.

---

## Troubleshooting

- **Webserver never becomes healthy** — `cdp-dev logs webserver` and check
  the error. Most often it's a DAG import error in your `./dags` folder.
- **Port 8080 already in use** — edit `docker-compose.yml` and change
  `127.0.0.1:8080:8080` to another host port.
- **Permission denied writing to ./logs (Linux)** — `cdp-dev destroy &&
  cdp-dev install`; the installer now writes the correct `AIRFLOW_UID` into
  `.env`.
- **Coming from the old Kind-based v0.1.x** — `cdp-dev install` detects the
  old `cdp-local` Kind cluster and offers to delete it before continuing.
