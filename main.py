"""
Основной файл запуска Telegram бота для Gemini Image Generator
Совместим с aiogram 2.x и 3.x
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Добавляем путь к проекту для импорта модулей
sys.path.append(str(Path(__file__).parent))

# Определение версии aiogram и соответствующие импорты
try:
    # Пробуем импортировать из aiogram 3.x
    from aiogram import Bot, Dispatcher, types
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    from aiogram.filters import Command
    from aiogram.types import Message
    from aiogram.utils.markdown import hbold, hlink
    AIOGRAM_VERSION = 3
    logger.info("Using aiogram 3.x")
except (ImportError, ModuleNotFoundError):
    # Если не получилось, используем aiogram 2.x
    from aiogram import Bot, Dispatcher, types
    from aiogram.contrib.middlewares.logging import LoggingMiddleware
    from aiogram.utils import executor
    from aiogram.utils.markdown import hbold, hlink
    from aiogram.types import Message
    AIOGRAM_VERSION = 2
    logging.info("Using aiogram 2.x")

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout),
        logging.FileHandler('bot.log')
    ]
)
logger = logging.getLogger(__name__)

# Импорт конфигурации
try:
    from src.utils.config import config
    from src.database import init_db, close_db
    from src.services.gemini_service import GeminiService
except ImportError as e:
    logger.error(f"Failed to import local modules: {e}")
    logger.info("Creating minimal config for testing")
    
    # Минимальная конфигурация для тестирования
    class Config:
        BOT_TOKEN = os.getenv('BOT_TOKEN', '')
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
        ADMIN_IDS = [int(id) for id in os.getenv('ADMIN_IDS', '').split(',') if id]
        MAX_REQUESTS_PER_DAY = int(os.getenv('MAX_REQUESTS_PER_DAY', '50'))
        MAX_REQUESTS_PER_HOUR = int(os.getenv('MAX_REQUESTS_PER_HOUR', '10'))
        DEFAULT_ASPECT_RATIO = os.getenv('DEFAULT_ASPECT_RATIO', '1:1')
    
    config = Config()
    
    # Заглушки для сервисов
    async def init_db():
        logger.info("Database initialization skipped (minimal mode)")
    
    async def close_db():
        pass
    
    class GeminiService:
        def __init__(self, api_key):
            self.api_key = api_key
            logger.info(f"GeminiService initialized with API key: {api_key[:10]}...")
        
        async def generate_image(self, prompt, aspect_ratio=None):
            return f"Generated image for: {prompt} (aspect ratio: {aspect_ratio or config.DEFAULT_ASPECT_RATIO})"

# Инициализация сервисов
gemini_service = GeminiService(config.GEMINI_API_KEY)

# Обработчики команд
async def start_command(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) started the bot")
    
    welcome_text = (
        f"{hbold('🎨 Gemini Image Bot')}\n\n"
        f"Привет, {hbold(message.from_user.first_name)}!\n\n"
        f"Я бот для генерации и редактирования изображений с помощью "
        f"{hbold('Google Gemini 2.5 Flash Image')} (Nana Banana).\n\n"
        f"📝 {hbold('Команды:')}\n"
        f"/start - Главное меню\n"
        f"/help - Справка\n"
        f"/stats - Моя статистика\n"
        f"/history - История генераций\n\n"
        f"Просто отправь мне текст, и я сгенерирую изображение!"
    )
    
    await message.reply(welcome_text, parse_mode="HTML")

async def help_command(message: Message):
    """Обработчик команды /help"""
    help_text = (
        f"{hbold('📚 Справка по использованию')}\n\n"
        f"{hbold('🎨 Генерация изображений:')}\n"
        f"• Отправь текстовое описание\n"
        f"• Например: 'a cute cat in space, digital art'\n\n"
        f"{hbold('📝 Редактирование фото:')}\n"
        f"• Загрузи фото с подписью\n"
        f"• Например: 'сделай фон черно-белым'\n\n"
        f"{hbold('⚙️ Настройки:')}\n"
        f"• Можно указать соотношение сторон\n"
        f"• 1:1 (квадрат), 16:9 (широкий), 9:16 (портрет)\n\n"
        f"{hbold('ℹ️ Дополнительно:')}\n"
        f"• /stats - твоя статистика\n"
        f"• /history - история генераций"
    )
    
    await message.reply(help_text, parse_mode="HTML")

async def stats_command(message: Message):
    """Обработчик команды /stats"""
    user_id = message.from_user.id
    
    # Здесь должна быть логика получения статистики из БД
    stats_text = (
        f"{hbold('📊 Ваша статистика')}\n\n"
        f"• Генераций сегодня: 0/50\n"
        f"• Генераций за час: 0/10\n"
        f"• Всего генераций: 0\n\n"
        f"(Статистика временно не доступна в тестовом режиме)"
    )
    
    await message.reply(stats_text, parse_mode="HTML")

async def history_command(message: Message):
    """Обработчик команды /history"""
    history_text = (
        f"{hbold('📜 История генераций')}\n\n"
        f"У вас пока нет сохраненных изображений.\n"
        f"Сгенерируйте что-нибудь с помощью текстового описания!"
    )
    
    await message.reply(history_text, parse_mode="HTML")

async def handle_text(message: Message):
    """Обработчик текстовых сообщений (генерация изображений)"""
    user_id = message.from_user.id
    prompt = message.text
    
    # Проверяем, не команда ли это
    if prompt.startswith('/'):
        return
    
    logger.info(f"User {user_id} requested image generation: {prompt[:50]}...")
    
    # Отправляем статус "печатает"
    await message.bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Генерируем изображение
        result = await gemini_service.generate_image(prompt)
        
        # Отправляем результат
        response_text = f"{hbold('✨ Сгенерировано по запросу:')}\n{prompt}\n\n{result}"
        await message.reply(response_text, parse_mode="HTML")
        
        logger.info(f"Image generated successfully for user {user_id}")
        
    except Exception as e:
        error_text = f"{hbold('❌ Ошибка генерации:')}\n{str(e)}"
        await message.reply(error_text, parse_mode="HTML")
        logger.error(f"Error generating image for user {user_id}: {e}")

async def handle_photo(message: Message):
    """Обработчик фотографий (редактирование изображений)"""
    user_id = message.from_user.id
    caption = message.caption or "Редактировать это изображение"
    
    logger.info(f"User {user_id} sent photo for editing")
    
    # Получаем фото
    photo = message.photo[-1]
    file_id = photo.file_id
    
    # Отправляем статус "печатает"
    await message.bot.send_chat_action(message.chat.id, 'upload_photo')
    
    try:
        # Здесь должна быть логика скачивания и обработки фото
        # file = await message.bot.get_file(file_id)
        # await file.download(f"downloads/{file_id}.jpg")
        
        response_text = (
            f"{hbold('🖼️ Редактирование фото')}\n\n"
            f"Запрос: {caption}\n\n"
            f"Функция редактирования временно не доступна в тестовом режиме."
        )
        await message.reply(response_text, parse_mode="HTML")
        
    except Exception as e:
        error_text = f"{hbold('❌ Ошибка обработки фото:')}\n{str(e)}"
        await message.reply(error_text, parse_mode="HTML")
        logger.error(f"Error processing photo for user {user_id}: {e}")

# Инициализация бота и диспетчера
async def init_bot():
    """Инициализация бота в зависимости от версии aiogram"""
    global bot, dp
    
    if AIOGRAM_VERSION == 3:
        # Aiogram 3.x инициализация
        bot = Bot(
            token=config.BOT_TOKEN,
            default=DefaultBotProperties(parse_mode=ParseMode.HTML)
        )
        dp = Dispatcher()
        
        # Регистрация обработчиков для aiogram 3.x
        dp.message.register(start_command, Command("start"))
        dp.message.register(help_command, Command("help"))
        dp.message.register(stats_command, Command("stats"))
        dp.message.register(history_command, Command("history"))
        dp.message.register(handle_photo, lambda message: message.photo)
        dp.message.register(handle_text, lambda message: message.text and not message.text.startswith('/'))
        
    else:
        # Aiogram 2.x инициализация
        bot = Bot(token=config.BOT_TOKEN, parse_mode="HTML")
        dp = Dispatcher(bot)
        
        # Регистрация обработчиков для aiogram 2.x
        dp.register_message_handler(start_command, commands=['start'])
        dp.register_message_handler(help_command, commands=['help'])
        dp.register_message_handler(stats_command, commands=['stats'])
        dp.register_message_handler(history_command, commands=['history'])
        dp.register_message_handler(handle_photo, content_types=['photo'])
        dp.register_message_handler(handle_text, lambda message: message.text and not message.text.startswith('/'))
        
        # Добавляем middleware для логирования
        dp.middleware.setup(LoggingMiddleware())
    
    return bot, dp

async def main():
    """Основная функция запуска бота"""
    logger.info("Starting bot initialization...")
    
    # Проверка наличия токена
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set!")
        return
    
    logger.info(f"Using aiogram version {AIOGRAM_VERSION}")
    logger.info(f"Bot token: {config.BOT_TOKEN[:10]}...")
    logger.info(f"Gemini API key: {config.GEMINI_API_KEY[:10] if config.GEMINI_API_KEY else 'Not set'}...")
    
    # Инициализация базы данных
    try:
        await init_db()
        logger.info("Database initialized successfully")
    except Exception as e:
        logger.warning(f"Database initialization failed: {e}")
    
    # Инициализация бота
    bot, dp = await init_bot()
    
    logger.info("Bot initialized successfully!")
    logger.info("Starting polling...")
    
    try:
        if AIOGRAM_VERSION == 3:
            # Запуск для aiogram 3.x
            await dp.start_polling(bot)
        else:
            # Запуск для aiogram 2.x
            await dp.start_polling()
    except Exception as e:
        logger.error(f"Error during polling: {e}")
    finally:
        # Закрытие соединений
        await bot.session.close()
        await close_db()
        logger.info("Bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Bot stopped by user")
    except Exception as e:
        logger.error(f"Fatal error: {e}")
