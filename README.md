# TODO
 - [x] It is not asking completed
 - [ ] Download upload scripts should use loggers
 - [ ] Down up scripts should use mongo service
 - [ ] Down up scripts must use other settings for mongo service, raspy ones, another init?
 - [ ] Merge upload download scripts?
 - [ ] Eliminate enums for names
 - [ ] Bot should load config from mongo itself
 - [ ] Reporting in bot

# Gym Bot - Workout Logging Telegram Bot

A Telegram bot for logging personal workout sessions. The bot is designed to be flexible, allowing users to dynamically combine pre-configured workouts into a single training session.

The project is deployed using Ansible, with the bot running as a systemd service on a host machine (e.g., a Raspberry Pi) and the database running as a Docker container.


## Mongo setup
```docker
docker run -d \
  --name "mongo-db" \
  -p 127.0.0.1:27017:27017 \
  -v /home/jonrda/code/gym-bot/mongo-data:/data/db \
  mongo:latest
```

```
db.trainings.createIndex({ user_id: 1, date: 1 })
```

An index acts like a table of contents for your database collection. Without it, MongoDB would have to scan every single document to find the trainings for a specific user within a date range. With the index, it can find them almost instantly.
Why is the number 1 used in user_id: 1?

The number 1 specifies that the index should be sorted in ascending order for that field. A value of -1 would specify descending order. For this type of query, the direction doesn't significantly impact performance, but 1 is the standard convention for ascending order.