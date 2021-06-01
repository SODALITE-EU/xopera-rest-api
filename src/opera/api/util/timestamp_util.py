import datetime


def datetime_now_to_string():
    return datetime.datetime.now(tz=datetime.timezone.utc).isoformat()


def datetime_to_str(timestamp: datetime.datetime):
    return timestamp.isoformat()


def str_to_datetime(time_str: str):
    return datetime.datetime.fromisoformat(time_str)
