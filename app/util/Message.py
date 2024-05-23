import app.util.Mtproto as Mtproto
from app.util.StringOperation import padding, current_solar_date, persian_numeral


def create_star(ping, speed):
    num_star = 1
    if (speed > 2000 and ping < 120):
        num_star = 5
    elif (speed > 1000 and ping < 200):
        num_star = 4
    elif (speed > 500 and ping < 300):
        num_star = 3
    elif (speed > 200 and ping < 400):
        num_star = 2
    return "⭐️" * num_star


def create_message(proxies, connect_num, total, channels_num):
    text = "سریع‌ترین پروکسی‌های انتخاب شده"
    message = f"<b>{text}:</b>\n\n"

    for proxy in proxies:
        url = Mtproto.create_proxy_link(proxy.server, proxy.port, proxy.secret)
        speed = round(proxy.average_speed / 1024, 2)
        speed = f"<b>speed:</b> {padding(speed, 4)} MB/s"
        ping = f"<b>ping:</b> {padding(proxy.average_ping // 1, 5)} ms"
        star = create_star(proxy.average_ping, proxy.average_speed)
        proxy_info = f"<i><a href='{url}'>📶 Connect Proxy {star}</a>\nℹ️ {speed} | {ping}</i>\n"
        message += proxy_info + "\n"

    current_date = current_solar_date()
    message += f"<b>وضعیت مجموعه:</b>\n"
    message += f"📊 <b>{connect_num}</b> پروکسی از <b>{total}</b> پروکسی قابلیت اتصال دارند.\n"
    message += f"📡 <b>{channels_num}</b> کانال پروکسی دائم در حال بررسی شدن هستند.\n\n"
    #message += f"پست‌ها را با دوستان و عزیزانتان به اشتراک بگذارید. 🙏😍\n"
    message += f"آپدیت شده در (<i>{current_date}</i>)\n"
    message += "\n🆔 @mtprotoAI"
    return message
