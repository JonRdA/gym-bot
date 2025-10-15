# Gym Bot - Workout Logging Telegram Bot

A Telegram bot for logging personal workout sessions. The bot is designed to be flexible, allowing users to dynamically combine pre-configured workouts into a single training session.

The project is deployed using Ansible, with the bot running as a systemd service on a host machine (e.g., a Raspberry Pi) and the database running as a Docker container.
## Deployment

Deployment is fully automated using the Ansible playbook in the ansible/ directory.
### Prerequisites
 1 - A target host (e.g., Raspberry Pi) with SSH access.
 2 - Ansible installed on your local machine.
 3 - A Git repository for your bot's code.

### Steps

    * Configure Inventory: Edit ansible/inventory.ini to point to your target host.

    * Set Up Secrets: Create an encrypted vault file for your Telegram bot token:

    ansible-vault create ansible/secrets.yml

    Add your token to the file in the format: gym_bot_token: "12345:ABC..."

    Run the Playbook: Execute the main playbook from your local machine. You will be prompted for your vault password.

    ansible-playbook -i ansible/inventory.ini ansible/playbook.yml --ask-vault-pass -e "@ansible/secrets.yml"

This playbook will create a dedicated user, deploy the MongoDB container, clone the latest code from your repository, set up a Python virtual environment, and configure a systemd service to keep the bot running.
Database Configuration

The application uses a MongoDB database to store all data. For optimal query performance, especially when retrieving trainings by date, it is crucial to create an index on the trainings collection.

Connect to your MongoDB instance and run the following command:

db.trainings.createIndex({ user_id: 1, date: 1 })

Why is an index important?

An index acts like a table of contents for your database collection. Without it, MongoDB would have to scan every single document to find the trainings for a specific user within a date range. With the index, it can find them almost instantly.
Why is the number 1 used in user_id: 1?

The number 1 specifies that the index should be sorted in ascending order for that field. A value of -1 would specify descending order. For this type of query, the direction doesn't significantly impact performance, but 1 is the standard convention for ascending order.
TODO

    [ ] Implement a bot command to allow users to load their own workout configurations.