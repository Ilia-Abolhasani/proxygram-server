import pytz
from datetime import datetime, timezone
from convertdate import persian


def padding(text, num):
    # The old loop added two spaces per iteration but counted one, so it
    # produced roughly 2*num - len(text) characters instead of num.
    return str(text).center(num)


def persian_numeral(input):
    numeral_mapping = {
        "0": "۰",
        "1": "۱",
        "2": "۲",
        "3": "۳",
        "4": "۴",
        "5": "۵",
        "6": "۶",
        "7": "۷",
        "8": "۸",
        "9": "۹",
    }
    outout = ""
    for char in str(input):
        if (char in numeral_mapping):
            outout += numeral_mapping[char]
        else:
            outout += char
    return outout


def current_solar_date():
    utc_time = datetime.utcnow()
    tehran_timezone = pytz.timezone('Asia/Tehran')
    tehran_time = utc_time.replace(tzinfo=pytz.utc).astimezone(tehran_timezone)
    solar_hijri_date = persian.from_gregorian(
        tehran_time.year,
        tehran_time.month,
        tehran_time.day
    )
    year = solar_hijri_date[0]
    month = solar_hijri_date[1]
    day = solar_hijri_date[2]
    return f"{tehran_time.hour:02}:{tehran_time.minute:02} {year}/{month:02}/{day:02}"
