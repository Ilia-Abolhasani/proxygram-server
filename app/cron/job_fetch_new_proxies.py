from app.util.Mtproto import extract_all_mtproto, parse_proxy_link
from app.util.DotDict import DotDict
from tqdm import tqdm
import time
import threading
from proxies_tg_wrapper.api_wrapper import Telegram_API
from app.config.config import Config

# This job runs every few minutes. Building a Telegram_API per call meant a new
# TDLib client and a full login each time, never stopped -- and every one of
# them opened the same tdlib_directory, which two concurrent clients can
# corrupt. One client is created lazily and reused for the life of the process.
_telegram_api = None
_telegram_api_lock = threading.Lock()


def _get_telegram_api():
    global _telegram_api
    if _telegram_api is not None:
        return _telegram_api
    with _telegram_api_lock:
        if _telegram_api is None:
            _telegram_api = Telegram_API(
                Config.telegram_app_id,
                Config.telegram_app_hash,
                Config.telegram_phone,
                Config.database_encryption_key,
                Config.tdlib_directory,
                Config.tdlib_lib_path,
            )
    return _telegram_api


def stop_telegram_api():
    """Shut the shared TDLib client down (used when the process exits)."""
    global _telegram_api
    with _telegram_api_lock:
        if _telegram_api is not None:
            try:
                _telegram_api.stop()
            except Exception as error:
                print(f"failed to stop TDLib client: {error}")
            _telegram_api = None


def fetch(context, logger_api):
    telegram_api = _get_telegram_api()
    telegram_api.remove_all_proxies()
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


def start(context, logger_api):
    # No lock: the job queue's single worker is what serialises jobs now.
    print("job_fetch_new_proxies")
    fetch(context, logger_api)
