# TODO -> CLEAN CODE
 - Read modules and cleanup ideas, tell g
 - Reorganize files
 - Think more reporting
 - [x] It is not asking completed
 - [x] Download upload scripts should use loggers
 - [x] Down up scripts should use mongo service
 - [x] Down up scripts must use other settings for mongo service, raspy ones, another init?
 - [x] Merge upload download scripts?
 - [ ] View training must be different, list trainings and select. Nothing else.
 - [ ] Calendar must be different, per workout or all (all except home)
 - [ ] Eliminate enums for names
 - [ ] Bot should load config from mongo itself? Not yet
 - [x] Reporting in bot

## Report ideas
* Calendar for each workout, choose with keyboard, all (excluding) or specific wo. Good backend function
* Maybe training duration?

# Gym Bot - Workout Logging Telegram Bot

A Telegram bot for logging personal workout sessions. The bot is designed to be flexible, allowing users to dynamically combine pre-configured workouts into a single training session.

The project is deployed using Ansible, with the bot running as a systemd service on a host machine (e.g., a Raspberry Pi) and the database running as a Docker container.


## Mongo setup
```docker
docker run -d \
  --name mongo \
  --restart always \
  -p 27017:27017 \
  -e MONGO_INITDB_ROOT_USERNAME=your_mongo_user \
  -e MONGO_INITDB_ROOT_PASSWORD=your_secret_mongo_password \
  -v /path/on/your/machine/mongo-data:/data/db \
  mongo:4.0
```

```
db.trainings.createIndex({ user_id: 1, date: 1 })
```

An index acts like a table of contents for your database collection. Without it, MongoDB would have to scan every single document to find the trainings for a specific user within a date range. With the index, it can find them almost instantly.
Why is the number 1 used in user_id: 1?

The number 1 specifies that the index should be sorted in ascending order for that field. A value of -1 would specify descending order. For this type of query, the direction doesn't significantly impact performance, but 1 is the standard convention for ascending order.

# BotFather commands
add - Add new training
calendar - View trainings calendar
view_training - View complete training
cancel - Cancel current conversation