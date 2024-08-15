import traceback
from pytgbot import Bot
from pytgbot.api_types.sendable import files
import logging

logging.basicConfig(level=logging.DEBUG)


class BotAPI:
    def __init__(self, bot_api_key, bot_chat_id):
        self.bot = Bot(bot_api_key)
        self.chat = bot_chat_id

    def send(self, text):
        if len(text) > 4000:
            text = text[:4000]
        result = self.bot.send_message(self.chat, text)
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
        result = self.bot.send_message(self.chat, text, parse_mode)
        return result

    def edit_message_text(self, text, message_id, parse_mode="HTML"):
        result = self.bot.edit_message_text(
            text=text, chat_id=self.chat, message_id=message_id, parse_mode=parse_mode
        )
        return result

    def delete_message(self, message_id):
        result = self.bot.delete_message(self.chat, message_id)
        return result

    def pin_chat_message(self, message_id, disable_notification):
        result = self.bot.pin_chat_message(self.chat, message_id, disable_notification)
        return result
