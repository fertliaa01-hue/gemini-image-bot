"""
Основной файл запуска Telegram бота для Gemini Image Generator
Совместим с aiogram 2.x и 3.x, исправлена ошибка с pwd
"""

import asyncio
import logging
import sys
import os
from pathlib import Path

# Добавляем путь к проекту для импорта модулей
sys.path.append(str(Path(__file__).parent))

# Настройка логирования ДО всего остального
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[
        logging.StreamHandler(sys.stdout)
    ]
)
logger = logging.getLogger(__name__)

# Подавляем импорт pwd, если он вызывает проблемы
try:
    import pwd
    HAS_PWD = True
except ImportError:
    HAS_PWD = False
    logger.info("Running on Windows or system without pwd module")

# Определение версии aiogram и соответствующие импорты
AIOGRAM_VERSION = 2  # По умолчанию используем 2.x
try:
    # Сначала пробуем импортировать из aiogram 3.x
    from aiogram import Bot, Dispatcher, types
    from aiogram.enums import ParseMode
    from aiogram.client.default import DefaultBotProperties
    from aiogram.filters import Command
    from aiogram.types import Message
    AIOGRAM_VERSION = 3
    logger.info("Using aiogram 3.x")
except (ImportError, ModuleNotFoundError) as e:
    logger.info(f"aiogram 3.x not available ({e}), trying 2.x...")
    try:
        # Пробуем aiogram 2.x
        from aiogram import Bot, Dispatcher, types
        from aiogram.contrib.middlewares.logging import LoggingMiddleware
        from aiogram.utils import executor
        from aiogram.types import Message
        AIOGRAM_VERSION = 2
        logger.info("Using aiogram 2.x")
    except ImportError as e2:
        logger.error(f"Neither aiogram 3.x nor 2.x is available: {e2}")
        logger.error("Please install aiogram: pip install aiogram>=2.0,<4.0")
        sys.exit(1)

# Импорт конфигурации с защитой от ошибок
try:
    from src.utils.config import config
    from src.database import init_db, close_db
    from src.services.gemini_service import GeminiService
    USING_LOCAL_MODULES = True
    logger.info("Using local modules from src/")
except ImportError as e:
    logger.warning(f"Local modules not found: {e}")
    logger.info("Using built-in minimal configuration")
    USING_LOCAL_MODULES = False
    
    # Минимальная конфигурация для тестирования
    class Config:
        BOT_TOKEN = os.getenv('BOT_TOKEN', '')
        GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
        ADMIN_IDS = []
        admin_ids_str = os.getenv('ADMIN_IDS', '')
        if admin_ids_str:
            try:
                ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
            except ValueError:
                logger.warning("Invalid ADMIN_IDS format")
        
        MAX_REQUESTS_PER_DAY = int(os.getenv('MAX_REQUESTS_PER_DAY', '50'))
        MAX_REQUESTS_PER_HOUR = int(os.getenv('MAX_REQUESTS_PER_HOUR', '10'))
        DEFAULT_ASPECT_RATIO = os.getenv('DEFAULT_ASPECT_RATIO', '1:1')
    
    config = Config()
    
    # Заглушки для сервисов
    async def init_db():
        logger.info("Database initialization skipped (minimal mode)")
        return True
    
    async def close_db():
        pass
    
    class GeminiService:
        def __init__(self, api_key):
            self.api_key = api_key
            logger.info(f"GeminiService initialized in minimal mode")
        
        async def generate_image(self, prompt, aspect_ratio=None):
            # В реальности здесь будет вызов API Gemini
            return f"🖼️ Сгенерировано изображение по запросу: '{prompt}'\n(Демо-режим, API Gemini не подключен)"

# Инициализация сервисов
gemini_service = GeminiService(config.GEMINI_API_KEY)

# Обработчики команд
async def start_command(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) started the bot")
    
    welcome_text = (
        f"🎨 **Gemini Image Bot**\n\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"Я бот для генерации и редактирования изображений с помощью "
        f"**Google Gemini 2.5 Flash Image** (Nana Banana).\n\n"
        f"📝 **Команды:**\n"
        f"/start - Главное меню\n"
        f"/help - Справка\n"
        f"/stats - Моя статистика\n"
        f"/history - История генераций\n\n"
        f"Просто отправь мне текст, и я сгенерирую изображение!"
    )
    
    if AIOGRAM_VERSION == 3:
        await message.reply(welcome_text, parse_mode="Markdown")
    else:
        await message.reply(welcome_text, parse_mode="Markdown")

async def help_command(message: Message):
    """Обработчик команды /help"""
    help_text = (
        f"📚 **Справка по использованию**\n\n"
        f"🎨 **Генерация изображений:**\n"
        f"• Отправь текстовое описание\n"
        f"• Например: 'a cute cat in space, digital art'\n\n"
        f"📝 **Редактирование фото:**\n"
        f"• Загрузи фото с подписью\n"
        f"• Например: 'сделай фон черно-белым'\n\n"
        f"⚙️ **Настройки:**\n"
        f"• Можно указать соотношение сторон\n"
        f"• 1:1 (квадрат), 16:9 (широкий), 9:16 (портрет)\n\n"
        f"ℹ️ **Дополнительно:**\n"
        f"• /stats - твоя статистика\n"
        f"• /history - история генераций"
    )
    
    if AIOGRAM_VERSION == 3:
        await message.reply(help_text, parse_mode="Markdown")
    else:
        await message.reply(help_text, parse_mode="Markdown")

async def stats_command(message: Message):
    """Обработчик команды /stats"""
    stats_text = (
        f"📊 **Ваша статистика**\n\n"
        f"• Генераций сегодня: 0/{config.MAX_REQUESTS_PER_DAY}\n"
        f"• Генераций за час: 0/{config.MAX_REQUESTS_PER_HOUR}\n"
        f"• Всего генераций: 0\n\n"
        f"*(Статистика временно не доступна в тестовом режиме)*"
    )
    
    if AIOGRAM_VERSION == 3:
        await message.reply(stats_text, parse_mode="Markdown")
    else:
        await message.reply(stats_text, parse_mode="Markdown")

async def history_command(message: Message):
    """Обработчик команды /history"""
    history_text = (
        f"📜 **История генераций**\n\n"
        f"У вас пока нет сохраненных изображений.\n"
        f"Сгенерируйте что-нибудь с помощью текстового описания!"
    )
    
    if AIOGRAM_VERSION == 3:
        await message.reply(history_text, parse_mode="Markdown")
    else:
        await message.reply(history_text, parse_mode="Markdown")

async def handle_text(message: Message):
    """Обработчик текстовых сообщений (генерация изображений)"""
    user_id = message.from_user.id
    prompt = message.text
    
    # Проверяем, не команда ли это
    if prompt.startswith('/'):
        return
    
    logger.info(f"User {user_id} requested image generation: {prompt[:50]}...")
    
    # Отправляем статус "печатает"
    if AIOGRAM_VERSION == 3:
        await message.bot.send_chat_action(chat_id=message.chat.id, action='typing')
    else:
        await message.bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        # Генерируем изображение
        result = await gemini_service.generate_image(prompt)
        
        # Отправляем результат
        response_text = f"✨ **Сгенерировано по запросу:**\n{prompt}\n\n{result}"
        
        if AIOGRAM_VERSION == 3:
            await message.reply(response_text, parse_mode="Markdown")
        else:
            await message.reply(response_text, parse_mode="Markdown")
        
        logger.info(f"Image generated successfully for user {user_id}")
        
    except Exception as e:
        error_text = f"❌ **Ошибка генерации:**\n{str(e)}"
        
        if AIOGRAM_VERSION == 3:
            await message.reply(error_text, parse_mode="Markdown")
        else:
            await message.reply(error_text, parse_mode="Markdown")
            
        logger.error(f"Error generating image for user {user_id}: {e}")

async def handle_photo(message: Message):
    """Обработчик фотографий (редактирование изображений)"""
    user_id = message.from_user.id
    caption = message.caption or "Редактировать это изображение"
    
    logger.info(f"User {user_id} sent photo for editing")
    
    # Отправляем статус
    if AIOGRAM_VERSION == 3:
        await message.bot.send_chat_action(chat_id=message.chat.id, action='upload_photo')
    else:
        await message.bot.send_chat_action(message.chat.id, 'upload_photo')
    
    try:
        response_text = (
            f"🖼️ **Редактирование фото**\n\n"
            f"Запрос: {caption}\n\n"
            f"Функция редактирования временно не доступна в тестовом режиме."
        )
        
        if AIOGRAM_VERSION == 3:
            await message.reply(response_text, parse_mode="Markdown")
        else:
            await message.reply(response_text, parse_mode="Markdown")
        
    except Exception as e:
        error_text = f"❌ **Ошибка обработки фото:**\n{str(e)}"
        
        if AIOGRAM_VERSION == 3:
            await message.reply(error_text, parse_mode="Markdown")
        else:
            await message.reply(error_text, parse_mode="Markdown")
            
        logger.error(f"Error processing photo for user {user_id}: {e}")

# Инициализация бота и диспетчера
async def init_bot():
    """Инициализация бота в зависимости от версии aiogram"""
    global bot, dp
    
    if not config.BOT_TOKEN:
        logger.error("BOT_TOKEN is not set! Please check your environment variables.")
        return None, None
    
    if AIOGRAM_VERSION == 3:
        # Aiogram 3.x инициализация
        bot = Bot(token=config.BOT_TOKEN)
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
        bot = Bot(token=config.BOT_TOKEN)
        dp = Dispatcher(bot)
        
        # Регистрация обработчиков для aiogram 2.x
        dp.register_message_handler(start_command, commands=['start'])
        dp.register_message_handler(help_command, commands=['help'])
        dp.register_message_handler(stats_command, commands=['stats'])
        dp.register_message_handler(history_command, commands=['history'])
        dp.register_message_handler(handle_photo, content_types=['photo'])
        dp.register_message_handler(handle_text, lambda message: message.text and not message.text.startswith('/'))
        
        # Добавляем middleware для логирования (если доступно)
        try:
            dp.middleware.setup(LoggingMiddleware())
        except:
            pass
    
    logger.info(f"Bot initialized with aiogram {AIOGRAM_VERSION}.x")
    return bot, dp

async def main():
    """Основная функция запуска бота"""
    logger.info("=" * 50)
    logger.info("Starting Gemini Image Bot...")
    logger.info("=" * 50)
    
    # Проверка наличия токена
    if not config.BOT_TOKEN:
        logger.error("❌ BOT_TOKEN is not set!")
        logger.error("Please set BOT_TOKEN in environment variables or .env file")
        return
    
    logger.info(f"✅ Bot token: {config.BOT_TOKEN[:10]}... (length: {len(config.BOT_TOKEN)})")
    
    if config.GEMINI_API_KEY:
        logger.info(f"✅ Gemini API key: {config.GEMINI_API_KEY[:10]}...")
    else:
        logger.warning("⚠️ GEMINI_API_KEY is not set - bot will run in demo mode")
    
    logger.info(f"✅ Using aiogram version: {AIOGRAM_VERSION}.x")
    logger.info(f"✅ System: {sys.platform}")
    logger.info(f"✅ Python version: {sys.version}")
    
    # Инициализация базы данных
    try:
        await init_db()
        logger.info("✅ Database initialized successfully")
    except Exception as e:
        logger.warning(f"⚠️ Database initialization skipped: {e}")
    
    # Инициализация бота
    bot, dp = await init_bot()
    if not bot or not dp:
        logger.error("❌ Failed to initialize bot")
        return
    
    logger.info("✅ Bot initialized successfully!")
    logger.info("🔄 Starting polling... (Press Ctrl+C to stop)")
    
    try:
        if AIOGRAM_VERSION == 3:
            # Запуск для aiogram 3.x
            await dp.start_polling(bot)
        else:
            # Запуск для aiogram 2.x
            await dp.start_polling()
    except Exception as e:
        logger.error(f"❌ Error during polling: {e}")
        import traceback
        traceback.print_exc()
    finally:
        # Закрытие соединений
        try:
            await bot.session.close()
        except:
            pass
        await close_db()
        logger.info("👋 Bot stopped")

if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("👋 Bot stopped by user")
    except Exception as e:
        logger.error(f"💥 Fatal error: {e}")
        import traceback
        traceback.print_exc()
