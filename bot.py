# bot.py
import asyncio
import csv
import json
import os
import re
from collections import defaultdict
from datetime import datetime
from pathlib import Path
from typing import Optional, Tuple

from aiogram import Bot, Dispatcher, F
from aiogram.client.default import DefaultBotProperties
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart
from aiogram.types import Message, CallbackQuery
from aiogram.utils.keyboard import InlineKeyboardBuilder, ReplyKeyboardBuilder

# === CONFIG ===
BOT_TOKEN = os.getenv("BOT_TOKEN")
if not BOT_TOKEN:
    raise ValueError("BOT_TOKEN environment variable is required")

CHANNEL_ID = int(os.getenv("CHANNEL_ID", "-1002808799226"))
MODERATION_GROUP = int(os.getenv("MODERATION_GROUP", "-1002935218273"))
BOT_LINK = os.getenv("BOT_LINK", "https://t.me/Git_fan_bot")

CARD_NUMBER = os.getenv("CARD_NUMBER")
if not CARD_NUMBER:
    raise ValueError("CARD_NUMBER environment variable is required")

LOGS_FILE = Path("logs.csv")
MOD_FILE = Path("moderators.json")
POSTS_FILE = Path("posts.json")

bot = Bot(token=BOT_TOKEN, default=DefaultBotProperties(parse_mode=ParseMode.HTML))
dp = Dispatcher()

# === STORAGE ===
pending_posts = {}     
paid_requests = {}
media_groups_buffer = defaultdict(list)     

if MOD_FILE.exists():
    moderator_names = json.loads(MOD_FILE.read_text(encoding="utf-8"))
else:
    moderator_names = {}
    MOD_FILE.write_text("{}", encoding="utf-8")

if POSTS_FILE.exists():
    try:
        posts_data = json.loads(POSTS_FILE.read_text(encoding="utf-8"))
    except Exception:
        posts_data = {}
else:
    posts_data = {}
    POSTS_FILE.write_text("{}", encoding="utf-8")

# === HELPERS ===
    def now_str():
        """Повертає поточний час по Києву у форматі YYYY-MM-DD HH:MM:SS"""
        return datetime.now(ZoneInfo("Europe/Kyiv")).strftime("%Y-%m-%d %H:%M:%S")

def save_posts():
    POSTS_FILE.write_text(json.dumps(posts_data, ensure_ascii=False, indent=2), encoding="utf-8")
def log_action(action: str, moderator: str = "-", user: str = "-", extra: str = ""):
    # Словник перекладів дій
    action_map = {
        "start": "Початок роботи з ботом",
        "ask_send_post": "Користувач хоче відправити пост",
        "post_submitted": "Пост відправлено на модерацію",
        "proof_sent_to_mods": "Доказ оплати відправлено модераторам",
        "post_approved": "Пост схвалено модератором",
        "post_rejected": "Пост відхилено модератором",
        "evidence_requested": "Модератор запросив докази",
        "ask_info_start": "Користувач хоче дізнатись чий пост",
        "ask_delete_start": "Користувач хоче видалити пост",
        "user_sent_link": "Користувач надіслав посилання на пост",
        "select_action_post_not_found": "Пост не знайдено в базі",
        "payment_requested": "Користувачу надіслано інструкцію для оплати",
        "mod_confirm_info_sent": "Модератор підтвердив оплату і відправив інформацію користувачу",
        "mod_confirm_deleted": "Модератор підтвердив оплату і видалив пост",
        "mod_confirm_post_not_found": "Модератор підтвердив оплату, але пост не знайдено",
        "mod_rejected_payment": "Модератор відхилив доказ оплати",
        "mod_delete_failed": "Не вдалося видалити пост",
    }


    ts = now_str()
    translated = action_map.get(action, action)
    row = [ts, moderator, user, translated, extra]

    new_file = not LOGS_FILE.exists()
    with open(LOGS_FILE, "a", newline="", encoding="utf-8") as f:
        writer = csv.writer(f)
        if new_file:
            writer.writerow(["час", "модератор", "користувач", "дія", "додаткова_інформація"])
        writer.writerow(row)

def auto_footer(text: str) -> str:
    return f"{text}\n\n👉 <b>Надіслати новину:</b> <a href='{BOT_LINK}'>{BOT_LINK}</a>\n⚡ <b>Сутність UA ONLINE:</b> <a href='https://t.me/sutnistua'>@sutnistua</a>"

def pretty_caption(post_id: int, user: str) -> str:
    return (
        f"📰 <b>НОВИЙ ПОСТ #{post_id}</b>\n"
        f"👤 Від користувача: @{user}\n\n"
        "🔍 Модератор, обери дію нижче 👇"
    )

def parse_tg_link(text: str) -> Optional[Tuple[str, int]]:
    m = re.search(r"(?:https?://)?t\.me/([^/]+)/(\d+)", text.strip())
    if not m:
        return None
    return (m.group(1), int(m.group(2)))

def find_post_by_msgid(msg_id: int) -> Optional[dict]:
    return posts_data.get(str(msg_id))

# === KEYBOARD ===
def main_kb():
    kb = ReplyKeyboardBuilder()
    kb.button(text="📨 Відправити пост")
    kb.button(text="👤 Дізнатись чий пост")
    kb.button(text="🗑 Видалити пост")
    kb.adjust(1)
    return kb.as_markup(resize_keyboard=True)

# === START ===
@dp.message(CommandStart())
async def start_cmd(m: Message):
    await m.answer("👋 Вітаю! Оберіть дію нижче:", reply_markup=main_kb())
    log_action("start", user=str(m.from_user.id))

# === CREATE POST (USER) ===
@dp.message(F.text == "📨 Відправити пост")
async def ask_post(m: Message):
    await m.answer("📸 Надішліть фото або відео з підписом до публікації.")
    log_action("ask_send_post", user=str(m.from_user.id))

@dp.message(F.media_group_id)
async def handle_album(m: Message):
    """Обробка альбомів (кілька фото/відео з підписом)"""
    media_groups_buffer[m.media_group_id].append(m)
    await asyncio.sleep(1)
    if m.media_group_id not in media_groups_buffer:
        return

    album_messages = media_groups_buffer.pop(m.media_group_id)
    uid = str(m.from_user.id)

    media_group = []
    caption = None
    for msg in album_messages:
        if msg.photo:
            media_group.append(("photo", msg.photo[-1].file_id))
        elif msg.video:
            media_group.append(("video", msg.video.file_id))
        if msg.caption and not caption:
            caption = msg.caption

    if not caption:
        await m.answer("⚠️ Додайте підпис до альбому.")
        return

    post_id = len(pending_posts) + 1
    pending_posts[post_id] = {
        "id": post_id,
        "user_id": m.from_user.id,
        "username": m.from_user.username or m.from_user.full_name,
        "media": media_group,
        "caption": caption,
        "status": "pending",
        "created": now_str(),
        "is_album": True,
    }

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Схвалити", callback_data=f"approve:{post_id}")
    kb.button(text="❌ Відхилити", callback_data=f"reject:{post_id}")
    kb.button(text="📎 Запросити докази", callback_data=f"request_evidence:{post_id}")
    kb.adjust(2)

    text = pretty_caption(post_id, pending_posts[post_id]["username"])
    media_to_send = []
    for i, (m_type, file_id) in enumerate(media_group):
        if i == 0:
            if m_type == "photo":
                media_to_send.append({"type": "photo", "media": file_id, "caption": f"{text}\n\n📝 {caption}"})
            else:
                media_to_send.append({"type": "video", "media": file_id, "caption": f"{text}\n\n📝 {caption}"})
        else:
            media_to_send.append({"type": m_type, "media": file_id})

    await bot.send_media_group(MODERATION_GROUP, media=media_to_send)
    await bot.send_message(MODERATION_GROUP, "⬆️ Новий альбом очікує модерації:", reply_markup=kb.as_markup())

    await m.answer("✅ Ваш пост (альбом) відправлено на модерацію. Очікуйте рішення.")
    log_action("post_submitted", user=str(m.from_user.id), extra=f"post_id={post_id}, album={len(media_group)}")

@dp.message(F.photo | F.video)
async def handle_single_media(m: Message):
    uid = str(m.from_user.id)
    # --- Обробка доказів оплати ---
    if uid in paid_requests and paid_requests[uid]["status"] == "awaiting_proof":
        entry = paid_requests[uid]
        action = entry["action"]
        target_msg_id = entry["target_msg_id"]
        requester_username = m.from_user.username or m.from_user.full_name

        text = (f"💳 Доказ оплати для дії <b>{action}</b>\n"
                f"Запитувач: @{requester_username} (id: {uid})\n"
                f"Цільовий пост: {target_msg_id}\n"
                f"Надіслано: {now_str()}")

        kb = InlineKeyboardBuilder()
        kb.button(text="✅ Оплачено", callback_data=f"moderator_confirm_payment:{uid}:{target_msg_id}:{action}")
        kb.button(text="🚫 Відхилити оплату", callback_data=f"moderator_reject_payment:{uid}:{target_msg_id}:{action}")
        kb.adjust(2)

        if m.photo:
            file_id = m.photo[-1].file_id
            await bot.send_photo(MODERATION_GROUP, file_id, caption=text, reply_markup=kb.as_markup())
        else:
            file_id = m.video.file_id
            await bot.send_video(MODERATION_GROUP, file_id, caption=text, reply_markup=kb.as_markup())

        paid_requests[uid]["status"] = "proof_sent"
        paid_requests[uid]["proof_sent_at"] = now_str()
        log_action("proof_sent_to_mods", user=uid, extra=f"target_msg_id={target_msg_id}, action={action}")
        await m.answer("✅ Доказ отримано. Ми переслали його модераторам для перевірки. Очікуйте рішення.")
        return

    # --- Обробка нового поста ---
    caption = m.caption or ""
    if not caption.strip():
        await m.answer("⚠️ Додайте підпис до фото/відео.")
        return

    post_id = len(pending_posts) + 1
    file_id = m.photo[-1].file_id if m.photo else m.video.file_id
    media_type = "photo" if m.photo else "video"

    pending_posts[post_id] = {
        "id": post_id,
        "user_id": m.from_user.id,
        "username": m.from_user.username or m.from_user.full_name,
        "file_id": file_id,
        "media_type": media_type,
        "caption": caption,
        "status": "pending",
        "created": now_str(),
        "is_album": False,
    }

    kb = InlineKeyboardBuilder()
    kb.button(text="✅ Схвалити", callback_data=f"approve:{post_id}")
    kb.button(text="❌ Відхилити", callback_data=f"reject:{post_id}")
    kb.button(text="📎 Запросити докази", callback_data=f"request_evidence:{post_id}")
    kb.adjust(2)

    text = pretty_caption(post_id, pending_posts[post_id]["username"])
    if media_type == "photo":
        await bot.send_photo(MODERATION_GROUP, file_id, caption=f"{text}\n\n📝 {caption}", reply_markup=kb.as_markup())
    else:
        await bot.send_video(MODERATION_GROUP, file_id, caption=f"{text}\n\n📝 {caption}", reply_markup=kb.as_markup())

    await m.answer("✅ Ваш пост відправлено на модерацію. Очікуйте рішення.")
    log_action("post_submitted", user=str(m.from_user.id), extra=f"post_id={post_id}")

# === MODERATION CALLBACKS ===
@dp.callback_query(F.data.startswith("approve:"))
async def approve_post(cb: CallbackQuery):
    post_id = int(cb.data.split(":", 1)[1])
    post = pending_posts.get(post_id)
    if not post or post["status"] != "pending":
        return await cb.answer("⚠️ Пост вже оброблено.", show_alert=True)
    post["status"] = "approved"
    caption = auto_footer(post["caption"])
    
    if post.get("is_album"):
        media_to_send = []
        for i, (m_type, file_id) in enumerate(post["media"]):
            if i == 0:
                if m_type == "photo":
                    media_to_send.append({"type": "photo", "media": file_id, "caption": caption})
                else:
                    media_to_send.append({"type": "video", "media": file_id, "caption": caption})
            else:
                media_to_send.append({"type": m_type, "media": file_id})
        
        sent_messages = await bot.send_media_group(CHANNEL_ID, media=media_to_send)
        sent = sent_messages[0]
    else:
        if post["media_type"] == "photo":
            sent = await bot.send_photo(CHANNEL_ID, post["file_id"], caption=caption)
        else:
            sent = await bot.send_video(CHANNEL_ID, post["file_id"], caption=caption)
    
    posts_data[str(sent.message_id)] = {
        "post_id": post_id,
        "author_id": post["user_id"],
        "author_username": post["username"],
        "author_phone": post.get("author_phone", ""),
        "publish_date": now_str(),
        "channel_id": CHANNEL_ID,
        "caption": post["caption"]
    }
    save_posts()
    await cb.message.edit_reply_markup(reply_markup=None)
    try:
        await bot.send_message(post["user_id"], "✅ Ваш пост схвалено і опубліковано в каналі!")
    except:
        pass
    mod_name = moderator_names.get(str(cb.from_user.id), cb.from_user.full_name)
    log_action("post_approved", moderator=mod_name, user=str(post["user_id"]), extra=f"post_id={post_id}, channel_msg_id={sent.message_id}")
    await cb.answer("✅ Пост схвалено та опубліковано!", show_alert=True)

@dp.callback_query(F.data.startswith("reject:"))
async def reject_post(cb: CallbackQuery):
    post_id = int(cb.data.split(":", 1)[1])
    post = pending_posts.get(post_id)
    if not post or post["status"] != "pending":
        return await cb.answer("⚠️ Пост вже оброблено.", show_alert=True)
    post["status"] = "rejected"
    await cb.message.edit_reply_markup(reply_markup=None)
    try:
        await bot.send_message(post["user_id"], "❌ Ваш пост відхилено модератором.")
    except:
        pass
    mod_name = moderator_names.get(str(cb.from_user.id), cb.from_user.full_name)
    log_action("post_rejected", moderator=mod_name, user=str(post["user_id"]), extra=f"post_id={post_id}")
    await cb.answer("❌ Пост відхилено.", show_alert=True)

@dp.callback_query(F.data.startswith("request_evidence:"))
async def request_evidence(cb: CallbackQuery):
    post_id = int(cb.data.split(":", 1)[1])
    post = pending_posts.get(post_id)
    if not post or post["status"] != "pending":
        return await cb.answer("⚠️ Немає такого поста в очікуванні.", show_alert=True)
    post["awaiting_evidence"] = True
    post["evidence_requested_by"] = cb.from_user.id
    await cb.message.edit_reply_markup(reply_markup=None)
    try:
        await bot.send_message(post["user_id"], f"Модератор просить надіслати фото/відео доказ для вашого поста #{post_id}. Надішліть тут медіа (воно не створить новий пост).")
    except:
        pass
    mod_name = moderator_names.get(str(cb.from_user.id), cb.from_user.full_name)
    log_action("evidence_requested", moderator=mod_name, user=str(post["user_id"]), extra=f"post_id={post_id}")
    await cb.answer("✅ Запит на докази надіслано користувачу.", show_alert=True)

# === USER BUTTONS ===
@dp.message(F.text == "👤 Дізнатись чий пост")
async def ask_info(m: Message):
    await m.answer("ℹ️ Надішліть посилання на пост (https://t.me/channel/123). Ви отримаєте інструкції щодо оплати (25 грн).")
    log_action("ask_info_start", user=str(m.from_user.id))

@dp.message(F.text == "🗑 Видалити пост")
async def ask_delete(m: Message):
    await m.answer("🗑 Надішліть посилання на пост (https://t.me/channel/123). Ви отримаєте інструкції щодо оплати (50 грн).")
    log_action("ask_delete_start", user=str(m.from_user.id))

@dp.message()
async def handle_links_and_other(m: Message):
    text = (m.text or "").strip()
    parsed = parse_tg_link(text)
    if not parsed:
        return
    channel_part, msg_id = parsed
    user_id = str(m.from_user.id)

    kb = InlineKeyboardBuilder()
    kb.button(text="Дізнатись (25 грн)", callback_data=f"select_action:{user_id}:{msg_id}:info")
    kb.button(text="Видалити (50 грн)", callback_data=f"select_action:{user_id}:{msg_id}:delete")
    kb.adjust(2)

    await m.answer("Оберіть дію для цього посилання:", reply_markup=kb.as_markup())
    log_action("user_sent_link", user=user_id, extra=f"msg_id={msg_id}")

# === USER SELECT ACTION ===
@dp.callback_query(F.data.startswith("select_action:"))
async def select_action(cb: CallbackQuery):
    try:
        _, requester_id, msg_id, action = cb.data.split(":", 3)
    except:
        return await cb.answer("Невірні дані.", show_alert=True)

    post = find_post_by_msgid(int(msg_id))
    if not post:
        await cb.answer("❗ Пост не знайдено у базі.", show_alert=True)
        log_action("select_action_post_not_found", user=requester_id, extra=f"msg_id={msg_id}")
        return

    price = 25 if action == "info" else 50
    text = (f"💰 Для виконання дії <b>{'Дізнатись' if action=='info' else 'Видалити'}</b> над постом {msg_id}\n"
            f"➤ Сума: {price} грн\n"
            f"➤ Проведіть оплату на картку:\n<b>{CARD_NUMBER}</b>\n"
            f'➤ У призначенні платежу вкажіть: "{action}"\n\n'
            "🔔 Після оплати: надішліть фото або скрін підтвердження переказу сюди.")

    paid_requests[requester_id] = {
        "action": action,
        "target_msg_id": int(msg_id),
        "status": "awaiting_proof",
        "price": price,
        "requested_at": now_str()
    }
    log_action("payment_requested", user=requester_id, extra=f"action={action}, msg_id={msg_id}, price={price}")

    await cb.message.answer(text)
    await cb.answer("Інструкції для оплати надіслані користувачу.", show_alert=True)

# === MODERATOR CONFIRM/REJECT PAYMENT ===
@dp.callback_query(F.data.startswith("moderator_confirm_payment:"))
async def moderator_confirm_payment(cb: CallbackQuery):
    try:
        _, requester_id, msg_id, action = cb.data.split(":", 3)
    except:
        return await cb.answer("Невірні дані.", show_alert=True)

    entry = paid_requests.get(str(requester_id))
    if not entry or entry["target_msg_id"] != int(msg_id) or entry["action"] != action:
        return await cb.answer("Запит оплати не знайдено.", show_alert=True)

    post = find_post_by_msgid(int(msg_id))
    if not post:
        await cb.answer("Пост не знайдено.", show_alert=True)
        log_action("mod_confirm_post_not_found", moderator=str(cb.from_user.id), extra=f"msg_id={msg_id}")
        return

    if action == "info":
        info_lines = []
        if post.get("author_username"): info_lines.append(f"👤 Telegram: @{post['author_username']}")
        if post.get("author_phone"): info_lines.append(f"☎️ Телефон: {post['author_phone']}")
        if post.get("publish_date"): info_lines.append(f"📅 Дата публікації: {post['publish_date']}")
        info_text = "🧾 <b>Інформація про автора:</b>\n" + "\n".join(info_lines) if info_lines else "ℹ️ Інформація недоступна."
        try: await bot.send_message(int(requester_id), info_text)
        except: pass
        paid_requests[str(requester_id)]["status"] = "completed"
        paid_requests[str(requester_id)]["completed_by"] = cb.from_user.id
        paid_requests[str(requester_id)]["completed_at"] = now_str()
        save_posts()
        log_action("mod_confirm_info_sent", moderator=str(cb.from_user.id), user=requester_id, extra=f"msg_id={msg_id}")
        await cb.answer("✅ Інформацію відправлено запитувачу.", show_alert=True)
        return

    if action == "delete":
        try:
            await bot.delete_message(post["channel_id"], int(msg_id))
            try: await bot.send_message(int(requester_id), "🗑️ Пост успішно видалено модератором.")
            except: pass
            paid_requests[str(requester_id)]["status"] = "completed"
            paid_requests[str(requester_id)]["completed_by"] = cb.from_user.id
            paid_requests[str(requester_id)]["completed_at"] = now_str()
            posts_data.pop(str(msg_id), None)
            save_posts()
            log_action("mod_confirm_deleted", moderator=str(cb.from_user.id), user=requester_id, extra=f"msg_id={msg_id}")
            await cb.answer("✅ Пост видалено.", show_alert=True)
        except Exception as e:
            log_action("mod_delete_failed", moderator=str(cb.from_user.id), user=requester_id, extra=f"msg_id={msg_id}, err={e}")
            await cb.answer("⚠️ Не вдалося видалити пост.", show_alert=True)

@dp.callback_query(F.data.startswith("moderator_reject_payment:"))
async def moderator_reject_payment(cb: CallbackQuery):
    try:
        _, requester_id, msg_id, action = cb.data.split(":", 3)
    except:
        return await cb.answer("Невірні дані.", show_alert=True)

    paid_requests[str(requester_id)]["status"] = "rejected"
    paid_requests[str(requester_id)]["rejected_by"] = cb.from_user.id
    paid_requests[str(requester_id)]["rejected_at"] = now_str()
    try:
        await bot.send_message(int(requester_id), "❌ Доказ оплати відхилено модератором. Будь ласка, повторіть оплату.")
    except: pass
    log_action("mod_rejected_payment", moderator=str(cb.from_user.id), user=requester_id, extra=f"msg_id={msg_id}")
    await cb.answer("✅ Запит відхилено та користувача повідомлено.", show_alert=True)

# === START BOT ===
async def main():
    """Основний цикл, який перезапускає бота при збоях."""
    while True:
        try:
            await bot.delete_webhook(drop_pending_updates=True)
            print(f"[{now_str()}] ✅ Бот запущено!")
            await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types(), timeout=60)
        except Exception as e:
            print(f"[{now_str()}] ⚠️ Помилка у роботі бота: {e}")
            await asyncio.sleep(5)  # перезапуск через 5 секунд

if __name__ == "__main__":
    asyncio.run(main())
