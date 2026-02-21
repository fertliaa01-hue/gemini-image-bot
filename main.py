"""
Основной файл запуска Telegram бота
ИСПРАВЛЕНО: Принудительное использование aiogram 2.x
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Добавляем путь к проекту для импорта модулей
sys.path.append(str(Path(__file__).parent))

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# ПРИНУДИТЕЛЬНО ИСПОЛЬЗУЕМ AIOGRAM 2.X
# Импортируем напрямую из aiogram 2.x
try:
    from aiogram import Bot, Dispatcher, types
    from aiogram.contrib.middlewares.logging import LoggingMiddleware
    from aiogram.utils import executor
    from aiogram.types import Message, ParseMode
    from aiogram.utils.markdown import hbold, hlink, text
    
    logger.info("✅ Successfully imported aiogram 2.x")
    AIOGRAM_VERSION = 2
except ImportError as e:
    logger.error(f"❌ Failed to import aiogram 2.x: {e}")
    logger.error("Please install: pip install aiogram==2.25.1")
    sys.exit(1)

# Импорт конфигурации (если есть)
try:
    from src.utils.config import config
    USING_LOCAL_CONFIG = True
    logger.info("✅ Using local config from src/")
except ImportError:
    logger.warning("⚠️ Local config not found, using environment variables")
    USING_LOCAL_CONFIG = False
    
    # Простая конфигурация из переменных окружения
    class Config:
        BOT_TOKEN = os.getenv('BOT_TOKEN', '')
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
        ADMIN_IDS = []
        if os.getenv('ADMIN_IDS'):
            try:
                ADMIN_IDS = [int(id.strip()) for id in os.getenv('ADMIN_IDS').split(',')]
            except:
                pass
        MAX_REQUESTS_PER_DAY = int(os.getenv('MAX_REQUESTS_PER_DAY', '50'))
        MAX_REQUESTS_PER_HOUR = int(os.getenv('MAX_REQUESTS_PER_HOUR', '10'))
        DEFAULT_ASPECT_RATIO = os.getenv('DEFAULT_ASPECT_RATIO', '1:1')
    
    config = Config()

# Проверяем наличие токена
if not config.BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is not set!")
    logger.error("Please set BOT_TOKEN in environment variables")
    sys.exit(1)

logger.info(f"✅ Bot token: {config.BOT_TOKEN[:10]}...")
logger.info(f"✅ Gemini API key: {'set' if config.GEMINI_API_KEY else 'not set'}")

# Инициализация бота и диспетчера для aiogram 2.x
bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)

# Добавляем middleware для логирования
dp.middleware.setup(LoggingMiddleware())

# --- ОБРАБОТЧИКИ КОМАНД ---

@dp.message_handler(commands=['start'])
async def start_command(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) started the bot")
    
    welcome_text = (
        f"<b>🎨 Gemini Image Bot</b>\n\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"Я бот для генерации и редактирования изображений с помощью "
        f"<b>Google Gemini 2.5 Flash Image</b> (Nana Banana).\n\n"
        f"📝 <b>Команды:</b>\n"
        f"/start - Главное меню\n"
        f"/help - Справка\n"
        f"/stats - Моя статистика\n"
        f"/history - История генераций\n\n"
        f"Просто отправь мне текст, и я сгенерирую изображение!"
    )
    
    await message.reply(welcome_text)

@dp.message_handler(commands=['help'])
async def help_command(message: Message):
    """Обработчик команды /help"""
    help_text = (
        f"<b>📚 Справка по использованию</b>\n\n"
        f"<b>🎨 Генерация изображений:</b>\n"
        f"• Отправь текстовое описание\n"
        f"• Например: 'a cute cat in space, digital art'\n\n"
        f"<b>📝 Редактирование фото:</b>\n"
        f"• Загрузи фото с подписью\n"
        f"• Например: 'сделай фон черно-белым'\n\n"
        f"<b>⚙️ Настройки:</b>\n"
        f"• Можно указать соотношение сторон\n"
        f"• 1:1 (квадрат), 16:9 (широкий), 9:16 (портрет)\n\n"
        f"<b>ℹ️ Дополнительно:</b>\n"
        f"• /stats - твоя статистика\n"
        f"• /history - история генераций"
    )
    
    await message.reply(help_text)

@dp.message_handler(commands=['stats'])
async def stats_command(message: Message):
    """Обработчик команды /stats"""
    stats_text = (
        f"<b>📊 Ваша статистика</b>\n\n"
        f"• Генераций сегодня: 0/{config.MAX_REQUESTS_PER_DAY}\n"
        f"• Генераций за час: 0/{config.MAX_REQUESTS_PER_HOUR}\n"
        f"• Всего генераций: 0\n\n"
        f"<i>(Статистика временно не доступна)</i>"
    )
    
    await message.reply(stats_text)

@dp.message_handler(commands=['history'])
async def history_command(message: Message):
    """Обработчик команды /history"""
    history_text = (
        f"<b>📜 История генераций</b>\n\n"
        f"У вас пока нет сохраненных изображений.\n"
        f"Сгенерируйте что-нибудь с помощью текстового описания!"
    )
    
    await message.reply(history_text)

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: Message):
    """Обработчик фотографий"""
    user_id = message.from_user.id
    caption = message.caption or "Редактировать это изображение"
    
    logger.info(f"User {user_id} sent photo for editing")
    
    await bot.send_chat_action(message.chat.id, 'upload_photo')
    
    response_text = (
        f"<b>🖼️ Редактирование фото</b>\n\n"
        f"Запрос: {caption}\n\n"
        f"<i>Функция редактирования временно не доступна в тестовом режиме.</i>"
    )
    
    await message.reply(response_text)

@dp.message_handler(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: Message):
    """Обработчик текстовых сообщений"""
    user_id = message.from_user.id
    prompt = message.text
    
    logger.info(f"User {user_id} requested: {prompt[:50]}...")
    
    await bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        if config.GEMINI_API_KEY:
            # Здесь будет реальная генерация через Gemini
            result = f"✨ Сгенерировано по запросу: '{prompt}'\n\n(API Gemini пока не подключен)"
        else:
            result = f"✨ Демо-режим: '{prompt}'\n\nДля работы с реальными изображениями добавьте GEMINI_API_KEY"
        
        await message.reply(f"<b>{result}</b>")
        logger.info(f"Response sent to user {user_id}")
        
    except Exception as e:
        error_text = f"❌ <b>Ошибка:</b> {str(e)}"
        await message.reply(error_text)
        logger.error(f"Error: {e}")

# --- ЗАПУСК БОТА ---

if __name__ == '__main__':
    logger.info("=" * 50)
    logger.info("STARTING GEMINI IMAGE BOT")
    logger.info("=" * 50)
    logger.info(f"Python version: {sys.version}")
    logger.info(f"Platform: {sys.platform}")
    logger.info(f"aiogram version: 2.x")
    logger.info(f"Bot token: {config.BOT_TOKEN[:10]}...")
    logger.info(f"Gemini API key: {'✅ set' if config.GEMINI_API_KEY else '❌ not set (demo mode)'}")
    logger.info("Starting polling...")
    
    try:
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.error(f"Fatal error: {e}")
    finally:
        logger.info("Bot stopped")
