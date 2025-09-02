import os
import re
import asyncio
import hashlib
import threading
import pythoncom
import subprocess
import win32com.client
from dotenv import load_dotenv
from num2words import num2words
from telethon import TelegramClient, events
from telethon.tl.types import MessageMediaDocument


load_dotenv()

api_id = os.environ.get('API_ID')
api_hash = os.environ.get('API_HASH')
session_name = "tts_session"
target_bot = "@silero_voice_bot"  # @username целевого бота
folder_path = 'eve-bot-framework/sound/'
speaker = win32com.client.Dispatch("SAPI.SpVoice")


def get_hashed_filename(text: str) -> str:
    return hashlib.sha256(text.encode("utf-8")).hexdigest()


async def get_voice_acting(text: str):
    async with TelegramClient(session_name, api_id, api_hash) as client:
        await client.send_message(target_bot, text)

        # Ждём первое reply от бота в этот диалог с медиа
        async for msg in client.iter_messages(target_bot, limit=30):
            # iter_messages идет от новых к старым; лучше слушать новые события:
            pass

        @client.on(events.NewMessage(chats=target_bot))
        async def handler(event):
            m = event.message
            # Проверяем, есть ли медиа-документ (voice/audio обычно document с audio mime)
            if isinstance(m.media, MessageMediaDocument):
                # Скачиваем в текущую папку (имя определит сам Telethon по атрибутам)
                text_hash = get_hashed_filename(text)
                file_path = await m.download_media(f'{folder_path}{text_hash}')
                print("Скачано:", file_path)
                # После первого успешного медиа можно отключать обработчик
                await client.disconnect()
            else:
                await client.disconnect()
                raise Exception('Лимит кончился')

        # Ждем, пока придет ответ и файл скачается
        await client.run_until_disconnected()


def play_mp3(path, speed=1.):
    # Собираем цепочку atempo для вне диапазона 0.5–2.0
    def atempo_chain(r):
        if r == 1.0:
            return []
        if 0.5 <= r <= 2.0:
            return [f"atempo={r}"]
        chain = []
        target = r
        while target < 0.5:
            chain.append("atempo=0.5")
            target /= 0.5
        while target > 2.0:
            chain.append("atempo=2.0")
            target /= 2.0
        chain.append(f"atempo={target}")
        return chain

    af = ",".join(atempo_chain(speed)) if speed != 1.0 else None
    cmd = ["ffplay", "-loglevel", "quiet", "-nodisp", "-autoexit"]
    if af:
        cmd += ["-af", af]
    cmd += [path]

    subprocess.Popen(cmd)


def numbers_to_words_ru(text: str) -> str:
    """
    Заменяет целые числа в тексте на их словесное представление (русский).
    Примеры:
      "я съел 2 яблока" -> "я съел два яблока"
      "В 2025 году" -> "В две тысячи двадцать пятом году" (имейте в виду падежи не согласуются автоматически)
    """
    # Ищем целые числа, отделённые от букв (чтобы не трогать, например, a1b)
    pattern = re.compile(r'(?<!\w)(\d+)(?!\w)')

    def repl(match):
        num_str = match.group(1)
        # Пропускаем очень большие/нестандартные, если нужно — можно убрать этот блок
        try:
            n = int(num_str)
        except ValueError:
            return num_str
        # Переводим число в слова на русском
        return num2words(n, lang="ru")

    return pattern.sub(repl, text)


def speak_in_thread(message):
    pythoncom.CoInitialize()
    try:
        speaker.Speak(message)
    finally:
        pythoncom.CoUninitialize()


def say_ffplay(text, speed=1.5):
    try:
        text = numbers_to_words_ru(text)
        text_hash = get_hashed_filename(text)
        file_path = os.path.join(folder_path, f'{text_hash}.mp3')
        if not os.path.exists(file_path):
            asyncio.run(get_voice_acting(text))
        play_mp3(file_path, speed)
    except:
        threading.Thread(target=speak_in_thread, args=(text,)).start()
