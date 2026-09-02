import traceback
from pytgbot import Bot
from pytgbot.api_types.sendable import files
import logging

logging.basicConfig(level=logging.DEBUG)


# Telegram rejects messages over 4096 characters.
MAX_MESSAGE_LENGTH = 4000


def _fit(text):
    """Trim to Telegram's limit on a blank-line boundary.

    Channel messages are HTML, so cutting mid-tag would break parse_mode;
    the proxy blocks are separated by blank lines, which are safe to cut on.
    """
    if len(text) <= MAX_MESSAGE_LENGTH:
        return text
    clipped = text[:MAX_MESSAGE_LENGTH]
    boundary = clipped.rfind("\n\n")
    return clipped[:boundary] if boundary > 0 else clipped


class BotAPI:
    def __init__(self, bot_api_key, bot_chat_id):
        self.bot = Bot(bot_api_key)
        self.chat = bot_chat_id

    def send(self, text):
        result = self.bot.send_message(self.chat, _fit(text))
        return result

    def announce(self, error, extra_message=None):
        traceback_str = traceback.format_exc()
        error_message = str(error)
        if extra_message:
            error_message = extra_message + " " + error_message
        message = f"{error_message}\n\n{traceback_str}"
        print(message)
        self.send(message)

    def send_document(self, file_path, file_name, caption):
        with open(file_path, "rb") as file:
            blob_data = file.read()
            document = files.InputFileFromBlob(blob_data, file_name)
            result = self.bot.send_document(
                self.chat, document=document, caption=caption
            )
        return result

    def send_message(self, text, parse_mode="HTML"):
        result = self.bot.send_message(self.chat, _fit(text), parse_mode)
        return result

    def edit_message_text(self, text, message_id, parse_mode="HTML"):
        result = self.bot.edit_message_text(
            text=_fit(text),
            chat_id=self.chat,
            message_id=message_id,
            parse_mode=parse_mode,
        )
        return result

    def delete_message(self, message_id):
        result = self.bot.delete_message(self.chat, message_id)
        return result

    def pin_chat_message(self, message_id, disable_notification):
        result = self.bot.pin_chat_message(self.chat, message_id, disable_notification)
        return result
