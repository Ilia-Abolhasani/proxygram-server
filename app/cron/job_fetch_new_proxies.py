from app.util.Mtproto import extract_all_mtproto, parse_proxy_link
from app.util.DotDict import DotDict
from app.cron import job_lock
from tqdm import tqdm
import time


def fetch(context, telegram_api, logger_api):
    output = []
    channels = context.get_all_channel(limit=15)
    for channel in tqdm(channels):
        try:
            if not channel.chat_id:
                if channel.is_public:
                    chat_id = telegram_api.search_public_chat(channel.username)
                    if not chat_id:
                        raise Exception(
                            f"public channel username '{channel.username}' not found!"
                        )
                    channel.chat_id = chat_id
                else:
                    raise Exception("private channel without chat_id!")
            if channel.is_public:
                pass
                # telegram_api.search_public_chat(channel.username)
            messages, last_message_id = telegram_api.channel_history(
                int(channel.chat_id), 500, channel.last_id
            )
            if last_message_id != channel.last_id:
                res = telegram_api.view_messages(
                    int(channel.chat_id), [last_message_id]
                )
                if res.error:
                    print(res.error_info)
            proxy_linkes = []
            # get messages
            for message in messages:
                for link in extract_all_mtproto(message):
                    proxy_linkes.append(link)
            proxy_linkes = list(set(proxy_linkes))
            proxies = []
            for link in proxy_linkes:
                server, port, secret = parse_proxy_link(link)
                if port < 1 or port > 65535:
                    continue
                if len(server) > 255 or len(secret) > 255:
                    continue
                proxies.append(
                    DotDict({"server": server, "port": port, "secret": secret})
                )
            _res = {
                "channel_name": channel.username if channel.is_public else channel.name,
                "number_message": len(messages),
                "number_proxy": len(proxies),
                "error": False,
                "error_message": "",
            }
            output.append(_res)

            context.add_proxies_of_channel(proxies, channel, last_message_id)
        except Exception as error:
            logger_api.announce(
                error, f"Job fetch new proxy erro at channel_id {channel.id}."
            )
            _res = {
                "error": True,
                "error_message": f"Job fetch new proxy erro at channel_id {channel.id}.",
            }
            output.append(_res)
        finally:
            time.sleep(0)
    return output


def start(context, telegram_api, logger_api):
    global job_lock
    with job_lock:
        print("job_fetch_new_proxies")
        fetch(context, telegram_api, logger_api)
