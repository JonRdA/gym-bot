# Gym Bot

A Telegram bot for logging personal workout sessions. Users combine pre-configured
workouts into a single training and log metrics per exercise. Each user has their
own training configuration stored in MongoDB.

Stack: `python-telegram-bot` v22, `motor` (async MongoDB), Pydantic v2, matplotlib.

## Quick start

```bash
# 1. Create env file and edit credentials
cp .env.example .env
$EDITOR .env

# 2. Start MongoDB
docker compose up -d

# 3. Install and run the bot
python -m venv .venv && source .venv/bin/activate
pip install -e .
python -m gym_bot
```

The first time a user talks to the bot, their config is seeded from
`training_config_default.yaml` into the `user_configs` collection. Indexes are
created automatically on startup.

## MongoDB (Docker)

`docker-compose.yml` starts a `mongo:7` container with credentials pulled from
`.env` and data persisted to `./mongo-data`:

```bash
docker compose up -d          # start
docker compose logs -f mongo  # follow logs
docker compose down           # stop (data kept)
docker compose down -v        # stop and wipe volume
```

The `MONGO_ROOT_USER` / `MONGO_ROOT_PASSWORD` values in `.env` must match the
user/password embedded in `GYMBOT_MONGO_URI`. If you change them after the
volume has been initialised, Mongo will refuse the new credentials — wipe
`mongo-data/` or create a new user via `mongosh`.

Sanity check:

```bash
docker exec -it gym-bot-mongo mongosh \
  -u gymbot -p changeme --authenticationDatabase admin
```

## Configuration

There are **two distinct config layers**. Don't confuse them.

### 1. App config — environment variables (`.env`)

Read by `pydantic-settings` in `src/gym_bot/settings.py`. All keys are prefixed
with `GYMBOT_`:

| Variable                      | Purpose                                       | Default                         |
|-------------------------------|-----------------------------------------------|---------------------------------|
| `GYMBOT_TELEGRAM_TOKEN`       | BotFather token                               | *(required)*                    |
| `GYMBOT_MONGO_URI`            | MongoDB connection string                     | `mongodb://localhost:27017/`    |
| `GYMBOT_MONGO_DATABASE`       | Database name                                 | `gym-bot`                       |
| `GYMBOT_DEFAULT_CONFIG_PATH`  | YAML template used to seed new users          | `training_config_default.yaml`  |
| `GYMBOT_EXCLUDED_WORKOUTS`    | Workouts hidden from the unfiltered calendar  | `["home"]`                      |

`.env` is gitignored. `docker-compose.yml` reads `MONGO_ROOT_USER` and
`MONGO_ROOT_PASSWORD` from the same file — keep them in sync with the URI.

### 2. Training config — per-user, stored in MongoDB

Each user has one document in the `user_configs` collection. It has two
independent sections:

- **`exercises`** — a catalog. Each exercise is defined **once**, with its list
  of metrics. This is the single source of truth for "what does `pullup` mean".
- **`workouts`** — named, ordered lists of exercise *names* (pointers into the
  catalog). A workout is just a playlist.

```json
{
  "user_id": 5947426856,
  "exercises": {
    "pullup":    { "metrics": ["reps", "weight"], "track_rest": false },
    "row":       { "metrics": ["reps"],           "track_rest": false },
    "backsquat": { "metrics": ["reps", "weight"], "track_rest": true  },
    "pushup":    { "metrics": ["reps"],           "track_rest": false }
  },
  "workouts": {
    "pull":  ["pullup", "row"],
    "lower": ["backsquat"],
    "home":  ["pushup"]
  }
}
```

The loader rejects a config where any workout references an unknown exercise,
and rejects any metric not in `METRIC_REGISTRY`.

**Tracking rest time.** Rest is a *per-exercise-per-session* value, not a
set-level metric — you enter it once (e.g. "180s between sets of squats
today") and it's stored on the `Exercise`. Enable it by setting
`track_rest: true` on the catalog entry. During `/add` the bot prompts once
at the start of the exercise, before any set. Disable by removing the flag.

**Lifecycle**

1. On a user's first command, `UserConfigService.get_config(user_id)` checks
   the cache, then Mongo, and — if the user is unknown — copies
   `training_config_default.yaml` into a fresh document.
2. From that moment the user's config is independent of the YAML template.
   Changing the YAML only affects *future* new users — **unless** that user
   is the designated owner (see below).
3. Configs are cached in-process (plain dict, refilled at startup).

**Owner mode (single-user / personal use)**

Set `GYMBOT_OWNER_USER_ID` to your Telegram user id. On every startup the bot
reads `training_config_default.yaml` and upserts it into that user's Mongo
document, overwriting whatever was there. Workflow:

```bash
$EDITOR training_config_default.yaml   # comment out pullups this month
docker compose restart                 # or: systemctl restart gym-bot
```

Other users (if any) are untouched — they still use whatever was seeded on
their first `/add`. Leave `GYMBOT_OWNER_USER_ID` unset to run in pure
multi-user mode (seed-on-first-run, no sync, no rewrites).

**Metric validation**

Exercise metrics must exist in `METRIC_REGISTRY` (`domain/metrics.py`). Adding
a new metric is one line there; the config loader rejects anything unknown.

## Reports

The bot exposes three read-only commands for reviewing past trainings.

### `/calendar [months]`

Monthly activity grid for the last *N* months (default: 1). Each day shows
🟢 for a completed session, 🔶 for an incomplete one, `·` for rest days.
`GYMBOT_EXCLUDED_WORKOUTS` hides noisy categories (e.g. `home`) from the
unfiltered view; inline buttons let you re-filter by a single workout.

### `/view_training`

Lists your most recent trainings. Picking one expands the full breakdown:
workouts, exercises, per-set metrics, and rest time when tracked.

### `/exercise_report [days]`

Per-exercise trend over the last *N* days (default: 30). You pick the
exercise, then pick a report — the available reports depend on the metrics
configured for that exercise in `training_config_default.yaml`:

| Report           | Requires              | Shows                                           |
|------------------|-----------------------|-------------------------------------------------|
| **Total Reps**   | `reps`                | Reps summed per session. Max/day + last session.|
| **Volume**| `reps` + `weight`     | `reps × weight` per session. Sessions + max/day.|
| **Max Weight**   | `reps` + `weight`     | Heaviest set per session. All-time max + last.  |
| **Total Time**   | `time`                | Time summed per session. Max/day + last session.|
| **Max Time**     | `time`                | Longest hold per session. All-time max + last.  |
| **Rest**         | `track_rest: true`    | Configured rest per session. Avg, min, last.    |

Each report returns a text header plus a matplotlib bar chart.

## Testing

```bash
# Install dev dependencies (only needed once)
pip install -e '.[dev]'

# Run all tests
pytest

# Run a specific file
pytest tests/config/test_models.py

# Run with more detail (shows each test name)
pytest -v
```

Tests are fast and hermetic — no real database or Telegram connection needed. Everything
runs in-process with fake collections and temp YAML files.

## Backup / restore

```bash
python -m gym_bot.scripts.backup download            # dumps to trainings_backup/
python -m gym_bot.scripts.backup upload trainings_backup/
```

## Deployment (Raspberry Pi)

Deployment is automated with Ansible. It SSHes into the Pi and handles everything —
code sync, venv, MongoDB, and the systemd service.

**First-time setup**

```bash
# 1. Install Ansible on your laptop
pip install ansible

# 2. Create and encrypt your secrets
cp deploy/vault.yml.example deploy/vault.yml
$EDITOR deploy/vault.yml          # fill in token, mongo password, owner user id
ansible-vault encrypt deploy/vault.yml

# 3. Set your Pi's IP in deploy/inventory.ini

# 4. Deploy
ansible-playbook deploy/playbook.yml -i deploy/inventory.ini --ask-vault-pass
```

**Re-deploying after changes**

Same command — Ansible is idempotent (only changes what needs changing) and
restarts the bot automatically when code or config changed.

```bash
ansible-playbook deploy/playbook.yml -i deploy/inventory.ini --ask-vault-pass
```

**Check bot status on the Pi**

```bash
ssh pi@<your-pi-ip>
sudo systemctl status gym-bot
sudo journalctl -u gym-bot -f     # live logs
```

> **Python version note**: Raspberry Pi OS Bookworm ships Python 3.11. If the
> install fails because of the `>=3.12` requirement in `pyproject.toml`, change
> it to `>=3.11` — the code is compatible.

## BotFather commands

```
add - Add new training
calendar - View trainings calendar
view_training - View complete training
cancel - Cancel current conversation
exercise_report - Report exercise's metrics
repeat - Repeat metric input
done - Finish entering exercise's metrics
```
