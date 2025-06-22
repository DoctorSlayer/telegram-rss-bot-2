
import asyncio
import json
import os
import feedparser
import openai
import logging
from aiogram import Bot, Dispatcher, types
from aiogram.enums import ParseMode
from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

BOT_TOKEN = os.getenv("BOT_TOKEN")
OPENAI_API_KEY = os.getenv("OPENAI_API_KEY")
OWNER_ID = int(os.getenv("OWNER_ID", "1071247500"))

TOPICS = {
    "📱 Технології": [
        "https://ain.ua/feed/",
        "https://dev.ua/feed",
        "https://mezha.media/feed/"
    ],
    "🧠 Психологія": [
        "https://www.psychologies.ru/rss/all.xml",
        "https://life.pravda.com.ua/rss-section/psy/"
    ],
    "🌊 Новини": [
        "https://www.pravda.com.ua/rss/section/news/",
        "https://suspilne.media/rss/news.xml"
    ]
}

DATA_FILE = "admins.json"
openai.api_key = OPENAI_API_KEY
logging.basicConfig(level=logging.INFO)
bot = Bot(token=BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher()

def load_data():
    try:
        with open(DATA_FILE, "r") as f:
            return json.load(f)
    except:
        return {}

def save_data(data):
    with open(DATA_FILE, "w") as f:
        json.dump(data, f)

def main_menu():
    kb = InlineKeyboardMarkup(inline_keyboard=[
        [InlineKeyboardButton(text="➕ Додати канал", callback_data="add_channel")],
        [InlineKeyboardButton(text="📂 Обрати тематику", callback_data="choose_topic")],
        [InlineKeyboardButton(text="▶️ Запустити розсилку", callback_data="start_posting")],
        [InlineKeyboardButton(text="⏹️ Зупинити розсилку", callback_data="stop_posting")],
        [InlineKeyboardButton(text="🔀 Адміни", callback_data="manage_admins")]
    ])
    return kb

def topic_menu():
    kb = InlineKeyboardBuilder()
    for name in TOPICS.keys():
        kb.button(text=name, callback_data=f"topic:{name}")
    return kb.as_markup()

@dp.message(commands=["start"])
async def cmd_start(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data()
    if user_id not in data:
        if message.from_user.id == OWNER_ID:
            data[user_id] = {"channels": [], "topic": None, "active": False}
            save_data(data)
        else:
            await message.answer("❌ У вас немає доступу.")
            return
    await message.answer("🌐 Привіт! Обери дію:", reply_markup=main_menu())

@dp.callback_query()
async def handle_callback(query: types.CallbackQuery):
    user_id = str(query.from_user.id)
    data = load_data()
    if user_id not in data:
        await query.answer("❌ Немає доступу")
        return

    if query.data.startswith("topic:"):
        topic = query.data.split(":", 1)[1]
        data[user_id]["topic"] = topic
        save_data(data)
        await query.message.answer(f"🔹 Тематика встановлена: {topic}")

    elif query.data == "choose_topic":
        await query.message.answer("🔍 Обери тематику:", reply_markup=topic_menu())

    elif query.data == "start_posting":
        data[user_id]["active"] = True
        save_data(data)
        await query.message.answer("✅ Розсилку активовано.")
        await post_news(user_id)

    elif query.data == "stop_posting":
        data[user_id]["active"] = False
        save_data(data)
        await query.message.answer("❌ Розсилку зупинено.")

    elif query.data == "add_channel":
        await query.message.answer("🔑 Відправ ID каналу (бот має бути адміном):")

    elif query.data == "manage_admins":
        await query.message.answer("Поки що цей блок в розробці")

@dp.message()
async def handle_text(message: types.Message):
    user_id = str(message.from_user.id)
    data = load_data()
    if user_id not in data:
        return
    text = message.text.strip()
    if text.isdigit():
        data[user_id].setdefault("channels", []).append(int(text))
        save_data(data)
        await message.answer(f"✅ Канал {text} додано до розсилки.")

async def post_news(user_id):
    data = load_data()
    user = data.get(user_id)
    if not user or not user.get("active"):
        return
    topic = user.get("topic")
    if not topic:
        return
    for url in TOPICS.get(topic, []):
        feed = feedparser.parse(url)
        for entry in feed.entries[:1]:
            prompt = f"Переформулюй для Telegram:\nЗаголовок: {entry.title}\nТекст: {entry.summary[:500]}"
            try:
                completion = openai.ChatCompletion.create(
                    model="gpt-3.5-turbo",
                    messages=[{"role": "user", "content": prompt}]
                )
                text = completion.choices[0].message.content
                for chat_id in user.get("channels", []):
                    await bot.send_message(chat_id=chat_id, text=text)
            except Exception as e:
                logging.error(e)

async def main():
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
