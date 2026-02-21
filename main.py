"""
Telegram бот для генерации изображений через Google Gemini 2.5 Flash Image
Полностью рабочий код с поддержкой aiogram 2.x
"""

import asyncio
import logging
import sys
import os
import io
import tempfile
from pathlib import Path
from PIL import Image

# Настройка логирования
logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s - %(message)s',
    handlers=[logging.StreamHandler(sys.stdout)]
)
logger = logging.getLogger(__name__)

# Импортируем aiogram 2.x
try:
    from aiogram import Bot, Dispatcher, types
    from aiogram.contrib.middlewares.logging import LoggingMiddleware
    from aiogram.utils import executor
    from aiogram.types import Message, ParseMode, InputFile
    from aiogram.utils.markdown import hbold, hlink, text
    from aiogram.utils.exceptions import TelegramAPIError
    
    logger.info("✅ Successfully imported aiogram 2.x")
except ImportError as e:
    logger.error(f"❌ Failed to import aiogram 2.x: {e}")
    logger.error("Please install: pip install aiogram==2.25.1")
    sys.exit(1)

# Попытка импорта Google Gemini API
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
    logger.info("✅ Google Generative AI library loaded")
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("⚠️ google-generativeai not installed. Install with: pip install google-generativeai")

# Конфигурация из переменных окружения
class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    
    # ID администраторов (через запятую)
    ADMIN_IDS = []
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    if admin_ids_str:
        try:
            ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
        except ValueError:
            logger.warning("⚠️ Invalid ADMIN_IDS format")
    
    # Лимиты
    MAX_REQUESTS_PER_DAY = int(os.getenv('MAX_REQUESTS_PER_DAY', '50'))
    MAX_REQUESTS_PER_HOUR = int(os.getenv('MAX_REQUESTS_PER_HOUR', '10'))
    DEFAULT_ASPECT_RATIO = os.getenv('DEFAULT_ASPECT_RATIO', '1:1')
    
    # Модель Gemini для изображений
    GEMINI_IMAGE_MODEL = os.getenv('GEMINI_IMAGE_MODEL', 'gemini-2.5-flash-image-preview')
    
    # Режим отладки
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

config = Config()

# Проверка наличия токена
if not config.BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is not set!")
    logger.error("Please set BOT_TOKEN in environment variables")
    sys.exit(1)

# Инициализация Gemini (если есть ключ)
gemini_model = None
if config.GEMINI_API_KEY and GENAI_AVAILABLE:
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        gemini_model = genai.GenerativeModel(config.GEMINI_IMAGE_MODEL)
        logger.info(f"✅ Gemini model initialized: {config.GEMINI_IMAGE_MODEL}")
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini: {e}")
        gemini_model = None
else:
    if not config.GEMINI_API_KEY:
        logger.warning("⚠️ GEMINI_API_KEY not set - bot will run in DEMO mode")
    elif not GENAI_AVAILABLE:
        logger.warning("⚠️ google-generativeai library not available - bot will run in DEMO mode")

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Простая база данных в памяти для демо-режима (замените на реальную БД при необходимости)
user_stats = {}

# ================== ВСПОМОГАТЕЛЬНЫЕ ФУНКЦИИ ==================

async def check_user_limit(user_id: int) -> tuple[bool, str]:
    """
    Проверка лимитов для пользователя
    Возвращает (разрешено, сообщение)
    """
    # Простая реализация для демо
    if user_id not in user_stats:
        user_stats[user_id] = {
            'today': 0,
            'hour': 0,
            'last_reset': asyncio.get_event_loop().time()
        }
    
    # Здесь должна быть более сложная логика с временными метками
    # Для демо просто проверяем общее количество
    if user_stats[user_id]['today'] >= config.MAX_REQUESTS_PER_DAY:
        return False, f"❌ Достигнут дневной лимит ({config.MAX_REQUESTS_PER_DAY} запросов)"
    
    if user_stats[user_id]['hour'] >= config.MAX_REQUESTS_PER_HOUR:
        return False, f"❌ Достигнут часовой лимит ({config.MAX_REQUESTS_PER_HOUR} запросов)"
    
    return True, ""

async def increment_user_usage(user_id: int):
    """Увеличение счетчика использования"""
    if user_id not in user_stats:
        await check_user_limit(user_id)  # инициализация
    
    user_stats[user_id]['today'] += 1
    user_stats[user_id]['hour'] += 1

async def generate_image_with_gemini(prompt: str) -> tuple[bool, str, bytes | None]:
    """
    Генерация изображения через Gemini API
    Возвращает (успех, сообщение, данные изображения)
    """
    if not gemini_model:
        return False, "Gemini API не настроен. Добавьте GEMINI_API_KEY", None
    
    try:
        logger.info(f"🎨 Generating image with prompt: {prompt[:100]}...")
        
        # Добавляем инструкции для лучшего результата
        enhanced_prompt = f"""
        Create a high-quality, detailed image based on this description: {prompt}
        
        Requirements:
        - Photorealistic style
        - High resolution
        - Good lighting and composition
        - 16:9 aspect ratio if not specified otherwise
        """
        
        # Генерация контента
        response = gemini_model.generate_content(enhanced_prompt)
        
        # Проверяем, есть ли изображение в ответе
        if hasattr(response, '_result') and response._result.candidates:
            for part in response._result.candidates[0].content.parts:
                if hasattr(part, 'inline_data') and part.inline_data and part.inline_data.mime_type.startswith('image/'):
                    image_data = part.inline_data.data
                    logger.info(f"✅ Image generated successfully, size: {len(image_data)} bytes")
                    return True, "Изображение сгенерировано", image_data
        
        # Если изображения нет, возвращаем текст
        if hasattr(response, 'text'):
            return False, f"Текстовый ответ: {response.text}", None
        else:
            return False, "Не удалось сгенерировать изображение", None
            
    except Exception as e:
        logger.error(f"❌ Gemini API error: {e}")
        return False, f"Ошибка Gemini API: {str(e)}", None

# ================== ОБРАБОТЧИКИ КОМАНД ==================

@dp.message_handler(commands=['start'])
async def start_command(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) started the bot")
    
    welcome_text = (
        f"<b>🎨 Gemini Image Bot (Nana Banana)</b>\n\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"Я бот для генерации изображений с помощью "
        f"<b>Google Gemini 2.5 Flash Image</b>.\n\n"
        f"<b>📝 Команды:</b>\n"
        f"/start - Главное меню\n"
        f"/help - Справка\n"
        f"/stats - Моя статистика\n"
        f"/model - Информация о модели\n\n"
        f"<b>🎨 Режим работы:</b> {'✅ Реальный (Gemini API)' if gemini_model else '⚠️ Демо-режим'}\n\n"
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
        f"• Чем подробнее, тем лучше результат\n"
        f"• Например: 'a cute cat in space, digital art, 4k'\n\n"
        f"<b>📝 Примеры промптов:</b>\n"
        f"• 'Зимний лес на закате, фотореализм'\n"
        f"• 'Киберпанк город в стиле аниме'\n"
        f"• 'Кот в космосе, неоновые цвета'\n\n"
        f"<b>⚙️ Лимиты:</b>\n"
        f"• В день: {config.MAX_REQUESTS_PER_DAY} запросов\n"
        f"• В час: {config.MAX_REQUESTS_PER_HOUR} запросов\n\n"
        f"<b>ℹ️ Статус API:</b> {'✅ Подключен' if gemini_model else '❌ Не подключен'}"
    )
    
    await message.reply(help_text)

@dp.message_handler(commands=['stats'])
async def stats_command(message: Message):
    """Обработчик команды /stats"""
    user_id = message.from_user.id
    
    if user_id in user_stats:
        stats = user_stats[user_id]
        stats_text = (
            f"<b>📊 Ваша статистика</b>\n\n"
            f"• Использовано сегодня: {stats['today']}/{config.MAX_REQUESTS_PER_DAY}\n"
            f"• Использовано за час: {stats['hour']}/{config.MAX_REQUESTS_PER_HOUR}\n"
            f"• Всего запросов: {stats['today']}\n\n"
            f"<b>🔑 Статус API:</b> {'✅ Работает' if gemini_model else '❌ Демо-режим'}"
        )
    else:
        stats_text = (
            f"<b>📊 Ваша статистика</b>\n\n"
            f"Вы еще не делали запросов.\n\n"
            f"<b>🔑 Статус API:</b> {'✅ Работает' if gemini_model else '❌ Демо-режим'}"
        )
    
    await message.reply(stats_text)

@dp.message_handler(commands=['model'])
async def model_command(message: Message):
    """Информация о модели"""
    model_info = (
        f"<b>🤖 Информация о модели</b>\n\n"
        f"<b>Модель:</b> {config.GEMINI_IMAGE_MODEL}\n"
        f"<b>Название:</b> Gemini 2.5 Flash Image (Nana Banana)\n"
        f"<b>Статус:</b> {'✅ Подключена' if gemini_model else '❌ Не подключена'}\n\n"
        f"<b>Возможности:</b>\n"
        f"• Генерация изображений по тексту\n"
        f"• Сохранение персонажей\n"
        f"• Высокое качество\n"
        f"• Различные соотношения сторон\n\n"
    )
    
    if config.DEBUG and config.GEMINI_API_KEY:
        model_info += f"<b>API Key:</b> {config.GEMINI_API_KEY[:10]}...\n"
    
    await message.reply(model_info)

@dp.message_handler(commands=['admin'])  # Скрытая команда для администраторов
async def admin_command(message: Message):
    """Админ-панель (только для администраторов)"""
    user_id = message.from_user.id
    
    if user_id not in config.ADMIN_IDS:
        await message.reply("❌ У вас нет прав администратора")
        return
    
    total_users = len(user_stats)
    total_requests = sum(stats['today'] for stats in user_stats.values())
    
    admin_text = (
        f"<b>👑 Админ-панель</b>\n\n"
        f"<b>Статистика:</b>\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Всего запросов: {total_requests}\n"
        f"• Gemini API: {'✅ Работает' if gemini_model else '❌ Отключен'}\n\n"
        f"<b>Конфигурация:</b>\n"
        f"• Модель: {config.GEMINI_IMAGE_MODEL}\n"
        f"• Лимит в день: {config.MAX_REQUESTS_PER_DAY}\n"
        f"• Лимит в час: {config.MAX_REQUESTS_PER_HOUR}\n"
        f"• Соотношение: {config.DEFAULT_ASPECT_RATIO}\n"
    )
    
    await message.reply(admin_text)

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: Message):
    """Обработчик фотографий (пока в разработке)"""
    await message.reply(
        "<b>🖼️ Редактирование фото</b>\n\n"
        "Функция редактирования изображений находится в разработке.\n"
        "Пока доступна только генерация по тексту."
    )

@dp.message_handler(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: Message):
    """Обработчик текстовых сообщений - генерация изображений"""
    user_id = message.from_user.id
    prompt = message.text.strip()
    
    if not prompt:
        await message.reply("❌ Пожалуйста, введите описание изображения")
        return
    
    logger.info(f"User {user_id} requested: {prompt[:100]}...")
    
    # Проверка лимитов
    allowed, limit_msg = await check_user_limit(user_id)
    if not allowed:
        await message.reply(limit_msg)
        return
    
    # Отправляем статус "печатает"
    await bot.send_chat_action(message.chat.id, 'typing')
    
    try:
        if gemini_model:
            # РЕАЛЬНАЯ ГЕНЕРАЦИЯ через Gemini
            await message.reply("🎨 Генерирую изображение, пожалуйста подождите...")
            
            success, msg, image_data = await generate_image_with_gemini(prompt)
            
            if success and image_data:
                # Отправляем изображение
                await bot.send_chat_action(message.chat.id, 'upload_photo')
                
                # Сохраняем во временный файл
                with tempfile.NamedTemporaryFile(suffix='.png', delete=False) as tmp_file:
                    tmp_file.write(image_data)
                    tmp_path = tmp_file.name
                
                try:
                    # Отправляем фото
                    with open(tmp_path, 'rb') as photo:
                        await message.reply_photo(
                            photo,
                            caption=f"<b>✨ По запросу:</b> {prompt[:200]}{'...' if len(prompt) > 200 else ''}"
                        )
                    
                    # Увеличиваем счетчик использования
                    await increment_user_usage(user_id)
                    
                finally:
                    # Удаляем временный файл
                    try:
                        os.unlink(tmp_path)
                    except:
                        pass
            else:
                await message.reply(f"❌ {msg}")
        else:
            # ДЕМО-РЕЖИМ
            await message.reply(
                f"<b>🖼️ Демо-режим</b>\n\n"
                f"Запрос: '{prompt}'\n\n"
                f"<i>Для реальной генерации изображений добавьте GEMINI_API_KEY в переменные окружения.</i>\n\n"
                f"Как получить ключ:\n"
                f"1. Перейдите на https://aistudio.google.com/apikey\n"
                f"2. Войдите в аккаунт Google\n"
                f"3. Нажмите 'Get API key'\n"
                f"4. Скопируйте ключ и добавьте в переменные окружения Bothost"
            )
        
    except Exception as e:
        error_text = f"❌ <b>Ошибка:</b> {str(e)}"
        await message.reply(error_text)
        logger.error(f"Error processing request for user {user_id}: {e}", exc_info=True)

@dp.message_handler()
async def handle_unknown(message: Message):
    """Обработчик неизвестных сообщений"""
    await message.reply(
        "❓ Неизвестная команда. Используйте /help для списка команд."
    )

# ================== ЗАПУСК БОТА ==================

if __name__ == '__main__':
    logger.info("=" * 60)
    logger.info("🚀 ЗАПУСК GEMINI IMAGE BOT (NANA BANANA)")
    logger.info("=" * 60)
    logger.info(f"📊 Python version: {sys.version}")
    logger.info(f"💻 Platform: {sys.platform}")
    logger.info(f"🤖 aiogram version: 2.x")
    logger.info(f"🔑 Bot token: {config.BOT_TOKEN[:10]}... (length: {len(config.BOT_TOKEN)})")
    
    if gemini_model:
        logger.info(f"✅ Gemini API: ПОДКЛЮЧЕН (модель: {config.GEMINI_IMAGE_MODEL})")
    else:
        logger.warning("⚠️ Gemini API: НЕ ПОДКЛЮЧЕН - бот работает в ДЕМО-РЕЖИМЕ")
        if config.GEMINI_API_KEY:
            logger.warning("   Ключ API задан, но библиотека google-generativeai не установлена")
        else:
            logger.warning("   Добавьте GEMINI_API_KEY в переменные окружения для реальной работы")
    
    logger.info(f"👥 Admin IDs: {config.ADMIN_IDS}")
    logger.info(f"📈 Лимиты: {config.MAX_REQUESTS_PER_DAY}/день, {config.MAX_REQUESTS_PER_HOUR}/час")
    logger.info("🔄 Запуск polling...")
    logger.info("=" * 60)
    
    try:
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("👋 Бот остановлен")
