# Callback data prefixes — used in make_callback/parse_callback
# and in CallbackQueryHandler pattern matching (e.g. pattern=r"^aw:")
ADD_WORKOUT = "aw"
FINISH_TRAINING = "fin"
COMPLETED = "cmp"
CALENDAR_FILTER = "cal"
SELECT_SESSION = "ss"
SELECT_EXERCISE = "ex"
REPORT_TYPE = "rt"


def make_callback(prefix: str, value: str) -> str:
    return f"{prefix}:{value}"


def parse_callback(data: str) -> tuple[str, str]:
    prefix, _, value = data.partition(":")
    return prefix, value
