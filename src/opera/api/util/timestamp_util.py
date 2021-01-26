import datetime


def datetime_now_to_string():
    return datetime_to_str(datetime.datetime.now())


def datetime_to_str(timestamp: datetime.datetime):
    return timestamp.strftime('%Y-%m-%dT%H:%M:%S.%f%z')


def str_to_datetime(time_str: str):
    return datetime.datetime.strptime(time_str, '%Y-%m-%dT%H:%M:%S.%f%z')
