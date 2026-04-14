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

Each user has one document in the `user_configs` collection describing their
workouts, exercises and metrics. Shape:

```json
{
  "user_id": 5947426856,
  "workouts": {
    "pull": {
      "exercises": [
        {"name": "pullup", "metrics": ["reps", "weight"], "track_rest": false},
        {"name": "row",    "metrics": ["reps"],           "track_rest": false}
      ]
    },
    "push": { "exercises": [ ... ] }
  }
}
```

**Lifecycle**

1. On a user's first command, `UserConfigService.get_config(user_id)` checks
   the cache, then Mongo, and — if the user is unknown — copies
   `training_config_default.yaml` into a fresh document.
2. From that moment the user's config is independent of the YAML template.
   Changing the YAML only affects *future* new users.
3. Configs are cached in-process (`TTLCache`, 1h TTL, 100 entries) to avoid
   hitting Mongo on every message.

**Editing a user's config (for now)**

There is no in-bot editor yet. Edit directly in `mongosh`:

```js
use gym-bot
db.user_configs.updateOne(
  { user_id: 5947426856 },
  { $push: { "workouts.pull.exercises":
      { name: "chin_up", metrics: ["reps", "weight"], track_rest: false } } }
)
```

Then invalidate the cache by restarting the bot (or wait up to 1h).

**Metric validation**

Exercise metrics must exist in `METRIC_REGISTRY` (`domain/metrics.py`). Adding
a new metric is one line there; the config loader rejects anything unknown.

## Backup / restore

```bash
python -m gym_bot.scripts.backup download            # dumps to trainings_backup/
python -m gym_bot.scripts.backup upload trainings_backup/
```

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
