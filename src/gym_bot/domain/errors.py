class GymBotError(Exception):
    pass


class TrainingNotFoundError(GymBotError):
    pass


class ConfigNotFoundError(GymBotError):
    pass
