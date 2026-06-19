import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup, InlineQueryResultArticle, InputTextMessageContent
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    InlineQueryHandler,
    ContextTypes,
)
from uuid import uuid4

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = "8689524571:AAGHV8xQKboVwWxmLvyrLdZeudmkQIplInE"
CHANNEL_ID = -1003717805514
CHANNEL_LINK = "https://t.me/+rTIsSbfkngUwZGNi"
TARGET_BOT = "@sherlock0941bot"
TARGET_BOT_LINK = "https://t.me/sherlock0941bot"

# ---------- БАЗА ДАННЫХ ----------
DB_NAME = os.path.join(os.getcwd(), "bot_requests.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS join_requests (user_id INTEGER PRIMARY KEY)"
    )
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS referrals (user_id INTEGER PRIMARY KEY, count INTEGER DEFAULT 0)"
    )
    conn.commit()
    conn.close()
    logger.info(f"База данных создана/подключена: {DB_NAME}")

def add_request(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("INSERT OR IGNORE INTO join_requests (user_id) VALUES (?)", (user_id,))
    conn.commit()
    conn.close()

def has_request(user_id: int) -> bool:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT user_id FROM join_requests WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result is not None

def remove_request(user_id: int):
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("DELETE FROM join_requests WHERE user_id = ?", (user_id,))
    conn.commit()
    conn.close()

def add_referral(user_id: int):
    """Добавляет +5 запросов пользователю за переход"""
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "INSERT INTO referrals (user_id, count) VALUES (?, 5) "
        "ON CONFLICT(user_id) DO UPDATE SET count = count + 5",
        (user_id,)
    )
    conn.commit()
    conn.close()

def get_referral_count(user_id: int) -> int:
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute("SELECT count FROM referrals WHERE user_id = ?", (user_id,))
    result = cursor.fetchone()
    conn.close()
    return result[0] if result else 0

# ---------- ЛОГИРОВАНИЕ ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- ОБРАБОТЧИКИ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — с поддержкой реферального параметра"""
    user_id = update.effective_user.id

    # Если пришёл по реферальной ссылке из инлайна (?start=ref_USERID)
    if context.args and context.args[0].startswith("ref_"):
        try:
            referrer_id = int(context.args[0].replace("ref_", ""))
            if referrer_id != user_id:
                add_referral(referrer_id)
                logger.info(f"Реферал засчитан: {referrer_id} +5 запросов")
                try:
                    await context.bot.send_message(
                        chat_id=referrer_id,
                        text=(
                            f"🎉 По вашей ссылке перешёл новый пользователь!\n"
                            f"+5 запросов начислено.\n"
                            f"Всего запросов: {get_referral_count(referrer_id)}"
                        )
                    )
                except Exception:
                    pass
        except ValueError:
            pass

    keyboard = [[InlineKeyboardButton("Я подписался ✅", callback_data="check_sub")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"👋 Привет! Чтобы получить доступ к актуальному боту, "
        f"подпишись на канал:\n{CHANNEL_LINK}\n\n"
        f"Отправь заявку на вступление и нажми кнопку «Я подписался».",
        reply_markup=reply_markup,
    )
    logger.info(f"Отправлено приглашение пользователю {user_id}")

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия на кнопку «Я подписался»"""
    query = update.callback_query
    logger.info(f"Получен callback от {query.from_user.id}, data='{query.data}'")

    try:
        await query.answer()
    except Exception as e:
        logger.error(f"Ошибка query.answer(): {e}")

    user_id = query.from_user.id

    if has_request(user_id):
        remove_request(user_id)
        logger.info(f"Заявка найдена для {user_id}, отправляю ссылку")
        try:
            await query.edit_message_text(
                f"✅ Всё верно! Вот твой актуальный бот:\n{TARGET_BOT}"
            )
        except Exception as e:
            logger.error(f"Ошибка при edit_message_text: {e}")
    else:
        logger.info(f"Заявка НЕ найдена для {user_id}")
        try:
            await query.answer(
                "❌ Вы ещё не отправили заявку или она не обработана. Попробуйте позже.",
                show_alert=True,
            )
        except Exception as e:
            logger.error(f"Ошибка при alert: {e}")

async def handle_join_request(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка входящей заявки в канал"""
    join_request = update.chat_join_request
    user = join_request.from_user
    if join_request.chat.id == CHANNEL_ID:
        add_request(user.id)
        logger.info(f"Новая заявка от {user.id} (@{user.username})")

async def inline_query(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработчик инлайн-запросов (@bot в чатах)"""
    query = update.inline_query
    user_id = query.from_user.id

    bot_info = await context.bot.get_me()
    ref_link = f"https://t.me/{bot_info.username}?start=ref_{user_id}"

    message_text = (
        "Актуальный Sh3rlock\n"
        f"➡️ {TARGET_BOT}"
    )

    keyboard = InlineKeyboardMarkup([
        [InlineKeyboardButton("🤖 Перейти в бота", url=TARGET_BOT_LINK)]
    ])

    results = [
        InlineQueryResultArticle(
            id=str(uuid4()),
            title="Актуальный Sh3rlock",
            description=f"➡️ {TARGET_BOT} — нажми чтобы поделиться",
            input_message_content=InputTextMessageContent(
                message_text=message_text,
            ),
            reply_markup=keyboard,
        )
    ]

    await query.answer(results, cache_time=10, is_personal=True)
    logger.info(f"Инлайн-запрос от {user_id}: '{query.query}'")

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Логирование ошибок"""
    logger.error(f"Ошибка при обработке обновления {update}: {context.error}")

async def post_init(application: Application):
    bot = application.bot
    try:
        bot_info = await bot.get_me()
        logger.info(f"Бот подключён: @{bot_info.username} (id: {bot_info.id})")
    except Exception as e:
        logger.critical(f"Не удалось подключиться к Telegram. Ошибка: {e}")
        raise SystemExit(1)

# ---------- ЗАПУСК ----------
def main():
    init_db()

    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    application.add_handler(CommandHandler("start", start))
    application.add_handler(CallbackQueryHandler(check_subscription))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_handler(InlineQueryHandler(inline_query))
    application.add_error_handler(error_handler)

    logger.info("Запуск поллинга...")
    application.run_polling(
        allowed_updates=["message", "callback_query", "chat_join_request", "inline_query"],
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()
