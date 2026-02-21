import asyncio
import logging
from aiogram import Bot, Dispatcher
from aiogram.enums import ParseMode
from aiogram.client.default import DefaultBotProperties

from src.bot.handlers import start, image_generation, history, admin
from src.bot.middleware.rate_limit import RateLimitMiddleware
from src.database import init_db
from src.utils.config import config
from src.utils.logger import setup_logger

# Настройка логирования
setup_logger()
logger = logging.getLogger(__name__)

async def main():
    # Инициализация базы данных
    await init_db()
    logger.info("Database initialized")
    
    # Создание бота и диспетчера
    bot = Bot(
        token=config.BOT_TOKEN,
        default=DefaultBotProperties(parse_mode=ParseMode.HTML)
    )
    dp = Dispatcher()
    
    # Регистрация middleware
    dp.message.middleware(RateLimitMiddleware())
    
    # Регистрация роутеров (обработчиков команд)
    dp.include_router(start.router)
    dp.include_router(image_generation.router)
    dp.include_router(history.router)
    dp.include_router(admin.router)
    
    logger.info("Bot started!")
    
    # Запуск бота
    await dp.start_polling(bot)

if __name__ == "__main__":
    asyncio.run(main())
