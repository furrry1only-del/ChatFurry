import os
import asyncio
import logging
from aiogram import Bot, Dispatcher, types, F
from aiogram.types import Message, ReplyKeyboardMarkup, KeyboardButton
from aiogram.filters import CommandStart, Command
from aiogram.utils.keyboard import ReplyKeyboardBuilder
from aiohttp import web

# ========================
# 🔧 Налаштування
# ========================

BOT_TOKEN = "7733643731:AAFlN-E4RDBu4YTiaJpBmUXsbSLgKq1E6A0"  # встав сюди свій токен бота
ADMIN_GROUP_ID = -1002808799226     # група адмінів
DATA_DIR = "data"

if not os.path.exists(DATA_DIR):
    os.makedirs(DATA_DIR)

logging.basicConfig(level=logging.INFO)

bot = Bot(token=BOT_TOKEN)
dp = Dispatcher()

# ========================
# 📍 Міста
# ========================
CITIES = [
    "Суми", "Лебедин", "Харків", "Київ", "Запоріжжя",
    "Дніпро", "Львів", "Полтава", "Одеса"
]

admin_selected_city = {}

# ========================
# 🧠 Адмін-група
# ========================

@dp.message(Command("оновити"))
async def cmd_onovyty(message: Message):
    """Адмін викликає команду /оновити"""
    if message.chat.id != ADMIN_GROUP_ID:
        return
    kb = ReplyKeyboardBuilder()
    for city in CITIES:
        kb.button(text=city)
    kb.adjust(3)
    await message.answer("Оберіть місто для оновлення графіка:", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.chat.id == ADMIN_GROUP_ID, F.text.in_(CITIES))
async def admin_choose_city(message: Message):
    """Адмін вибирає місто"""
    admin_selected_city[message.from_user.id] = message.text
    await message.answer(f"📤 Надішліть новий графік для міста: {message.text}",
                         reply_markup=types.ReplyKeyboardRemove())

@dp.message(F.chat.id == ADMIN_GROUP_ID, F.content_type.in_({"photo", "document"}))
async def admin_send_graph(message: Message):
    """Адмін надсилає фото/документ"""
    user_id = message.from_user.id
    if user_id not in admin_selected_city:
        await message.reply("❗ Спочатку оберіть місто командою /оновити")
        return

    city = admin_selected_city[user_id]
    if message.photo:
        file_id = message.photo[-1].file_id
    else:
        file_id = message.document.file_id

    file_path = os.path.join(DATA_DIR, f"{city}.txt")
    with open(file_path, "w", encoding="utf-8") as f:
        f.write(file_id)

    await message.answer(f"✅ Графік для міста {city} оновлено!")
    admin_selected_city.pop(user_id, None)

# ========================
# 👥 Користувачі
# ========================

@dp.message(CommandStart())
async def start_cmd(message: Message):
    kb = ReplyKeyboardMarkup(resize_keyboard=True)
    kb.add(KeyboardButton("📅 Графіки відключень"))
    kb.add(KeyboardButton("ℹ️ Про бота"))
    await message.answer(
        "Вітаємо у боті 💡 <b>єСвітло Україна</b>!\n"
        "Тут ви можете переглянути актуальні графіки відключень.",
        parse_mode="HTML",
        reply_markup=kb
    )

@dp.message(F.text == "ℹ️ Про бота")
async def about(message: Message):
    await message.answer(
        "🔌 <b>єСвітло Україна</b> — бот, який допомагає швидко знаходити актуальні графіки відключень у вашому місті.\n\n"
        "📢 Дані оновлюють офіційні адміністратори в реальному часі.",
        parse_mode="HTML"
    )

@dp.message(F.text == "📅 Графіки відключень")
async def show_cities(message: Message):
    kb = ReplyKeyboardBuilder()
    for city in CITIES:
        kb.button(text=f"🏙 Графік відключення {city}")
    kb.adjust(2)
    await message.answer("Оберіть ваше місто:", reply_markup=kb.as_markup(resize_keyboard=True))

@dp.message(F.text.regexp(r"^🏙 Графік відключення (.+)$"))
async def show_city_graph(message: Message):
    city = message.text.replace("🏙 Графік відключення ", "").strip()
    file_path = os.path.join(DATA_DIR, f"{city}.txt")

    if not os.path.exists(file_path):
        await message.answer(f"⚠️ Немає актуального графіка для міста {city}.")
        return

    with open(file_path, "r", encoding="utf-8") as f:
        file_id = f.read().strip()

    try:
        await bot.send_photo(chat_id=message.chat.id, photo=file_id, caption=f"📅 Актуальний графік для міста {city}")
    except:
        await bot.send_document(chat_id=message.chat.id, document=file_id, caption=f"📅 Актуальний графік для міста {city}")

# ========================
# 🌐 Keep-Alive для Replit
# ========================
async def keep_alive():
    async def handle(request):
        return web.Response(text="✅ Bot is alive")

    app = web.Application()
    app.router.add_get("/", handle)
    runner = web.AppRunner(app)
    await runner.setup()
    site = web.TCPSite(runner, "0.0.0.0", 8080)
    await site.start()
    print("🌐 Keep-alive сервер запущено (порт 8080)")

# ========================
# 🚀 Запуск
# ========================
async def main():
    print("🚀 Запуск бота...")
    await keep_alive()
    try:
        await dp.start_polling(bot)
    except Exception as e:
        print("❌ Помилка запуску:", e)

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except (KeyboardInterrupt, SystemExit):
        print("🛑 Бот вимкнено вручну")
