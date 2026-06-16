import os
import sqlite3
import logging
from telegram import Update, InlineKeyboardButton, InlineKeyboardMarkup
from telegram.ext import (
    Application,
    CommandHandler,
    CallbackQueryHandler,
    ChatJoinRequestHandler,
    ContextTypes,
)

# ---------- НАСТРОЙКИ ----------
BOT_TOKEN = "8689524571:AAGHV8xQKboVwWxmLvyrLdZeudmkQIplInE"
CHANNEL_ID = -1003717805514
CHANNEL_LINK = "https://t.me/+rTIsSbfkngUwZGNi"
TARGET_BOT = "@xnode50724z4_bot"

# ---------- БАЗА ДАННЫХ ----------
DB_NAME = os.path.join(os.getcwd(), "bot_requests.db")

def init_db():
    conn = sqlite3.connect(DB_NAME)
    cursor = conn.cursor()
    cursor.execute(
        "CREATE TABLE IF NOT EXISTS join_requests (user_id INTEGER PRIMARY KEY)"
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

# ---------- ЛОГИРОВАНИЕ ----------
logging.basicConfig(
    format="%(asctime)s - %(name)s - %(levelname)s - %(message)s",
    level=logging.INFO,
)
logger = logging.getLogger(__name__)

# ---------- ОБРАБОТЧИКИ ----------
async def start(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Команда /start — приглашение подписаться"""
    keyboard = [[InlineKeyboardButton("Я подписался ✅", callback_data="check_sub")]]
    reply_markup = InlineKeyboardMarkup(keyboard)
    await update.message.reply_text(
        f"👋 Привет! Чтобы получить доступ к актуальному боту, "
        f"подпишись на канал:\n{CHANNEL_LINK}\n\n"
        f"Отправь заявку на вступление и нажми кнопку «Я подписался».",
        reply_markup=reply_markup,
    )
    logger.info(f"Отправлено приглашение пользователю {update.effective_user.id}")

async def check_subscription(update: Update, context: ContextTypes.DEFAULT_TYPE):
    """Обработка нажатия на кнопку «Я подписался»"""
    query = update.callback_query
    logger.info(f"Получен callback от {query.from_user.id}, data='{query.data}'")

    # Всегда сначала подтверждаем нажатие (убираем "часики")
    try:
        await query.answer()
    except Exception as e:
        logger.error(f"Ошибка query.answer(): {e}")

    user_id = query.from_user.id

    if has_request(user_id):
        # Заявка найдена — отдаём ссылку и удаляем заявку из базы
        remove_request(user_id)
        logger.info(f"Заявка найдена для {user_id}, отправляю ссылку")
        try:
            await query.edit_message_text(
                f"✅ Всё верно! Вот твой актуальный бот:\n{TARGET_BOT}"
            )
        except Exception as e:
            logger.error(f"Ошибка при edit_message_text: {e}")
    else:
        # Заявки нет — предупреждение
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
        # Раскомментируйте следующую строку, если хотите автоматически одобрять заявки:
        # await join_request.approve()

async def error_handler(update: object, context: ContextTypes.DEFAULT_TYPE):
    """Логирование ошибок"""
    logger.error(f"Ошибка при обработке обновления {update}: {context.error}")

async def post_init(application: Application):
    """Проверка токена при запуске — получаем информацию о боте"""
    bot = application.bot
    try:
        bot_info = await bot.get_me()
        logger.info(f"Бот подключён: @{bot_info.username} (id: {bot_info.id})")
    except Exception as e:
        logger.critical(f"Не удалось подключиться к Telegram. Проверьте токен и сеть. Ошибка: {e}")
        raise SystemExit(1)

# ---------- ЗАПУСК ----------
def main():
    # Инициализация БД
    init_db()

    # Создаём приложение
    application = Application.builder().token(BOT_TOKEN).post_init(post_init).build()

    # Регистрация обработчиков
    application.add_handler(CommandHandler("start", start))
    # Обработчик callback без фильтра pattern, чтобы ловить все нажатия
    application.add_handler(CallbackQueryHandler(check_subscription))
    application.add_handler(ChatJoinRequestHandler(handle_join_request))
    application.add_error_handler(error_handler)

    logger.info("Запуск поллинга с очисткой старых обновлений...")
    # drop_pending_updates=True сбрасывает все обновления, накопившиеся до запуска
    application.run_polling(
        allowed_updates=["message", "callback_query", "chat_join_request"],
        drop_pending_updates=True,
    )

if __name__ == "__main__":
    main()