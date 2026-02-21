"""
Telegram бот для генерации изображений через Google Gemini
ИСПРАВЛЕНО: используется стабильная модель gemini-2.5-flash-image
"""

import asyncio
import logging
import sys
import os
import io
import random
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont
import datetime

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
    from aiogram.types import Message, ParseMode
    from aiogram.utils.exceptions import TelegramAPIError
    
    logger.info("✅ Successfully imported aiogram 2.x")
except ImportError as e:
    logger.error(f"❌ Failed to import aiogram 2.x: {e}")
    logger.error("Please install: pip install aiogram==2.25.1")
    sys.exit(1)

# Импорт Google Gemini API
try:
    import google.generativeai as genai
    GENAI_AVAILABLE = True
    logger.info("✅ Google Generative AI library loaded")
except ImportError:
    GENAI_AVAILABLE = False
    logger.warning("⚠️ google-generativeai not installed")

# Конфигурация из переменных окружения
class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    GEMINI_API_KEY = os.getenv('GEMINI_API_KEY', '')
    
    # ID администраторов
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

config = Config()

# Проверка наличия токена
if not config.BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is not set!")
    sys.exit(1)

# Инициализация Gemini с правильными моделями
gemini_available = False
gemini_image_model = None
gemini_text_model = None

if config.GEMINI_API_KEY and GENAI_AVAILABLE:
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # 1. Пробуем стабильную модель для изображений (рекомендуется)
        try:
            gemini_image_model = genai.GenerativeModel('gemini-2.5-flash-image')
            logger.info("✅ Using stable image model: gemini-2.5-flash-image")
            gemini_available = True
        except Exception as e:
            logger.warning(f"⚠️ Stable image model not available: {e}")
            
            # 2. Пробуем альтернативную модель для изображений
            try:
                gemini_image_model = genai.GenerativeModel('gemini-3-pro-image-preview')
                logger.info("✅ Using preview image model: gemini-3-pro-image-preview")
                gemini_available = True
            except Exception as e2:
                logger.warning(f"⚠️ Preview image model not available: {e2}")
                
                # 3. Пробуем текстовую модель как fallback
                try:
                    gemini_text_model = genai.GenerativeModel('gemini-1.5-pro')
                    logger.info("✅ Using text model as fallback: gemini-1.5-pro")
                    gemini_available = True
                except Exception as e3:
                    logger.error(f"❌ No Gemini models available: {e3}")
    
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini: {e}")

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Простая статистика
user_stats = {}

# ================== ФУНКЦИИ ГЕНЕРАЦИИ ==================

def create_fallback_image(prompt: str) -> bytes:
    """Создает тестовое изображение с помощью Pillow"""
    width, height = 1024, 1024
    img = Image.new('RGB', (width, height), color='#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # Градиентный фон
    for i in range(height):
        color = (
            int(26 + (i * 0.05)),
            int(26 + (i * 0.03)),
            int(46 + (i * 0.1))
        )
        draw.line([(0, i), (width, i)], fill=color)
    
    # Звезды
    for _ in range(100):
        x = random.randint(0, width)
        y = random.randint(0, height // 2)
        size = random.randint(1, 3)
        draw.ellipse([(x, y), (x + size, y + size)], fill='white')
    
    # Лес
    tree_colors = ['#27ae60', '#2ecc71', '#16a085']
    for i in range(10):
        x = 100 + i * 90
        for j in range(3):
            tree_y = height - 150 + j * 30
            tree_width = 40 - j * 10
            draw.polygon([
                (x - tree_width, tree_y + 50),
                (x, tree_y),
                (x + tree_width, tree_y + 50)
            ], fill=random.choice(tree_colors))
    
    # Текст
    try:
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except:
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    draw.text((512, 50), "✨ Nana Banana ✨", fill='#f39c12', anchor='mt', font=font_large)
    draw.text((512, 120), f"Запрос:", fill='#3498db', anchor='mt', font=font_small)
    draw.text((512, 160), prompt[:50], fill='white', anchor='mt', font=font_small)
    
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes.getvalue()

async def generate_with_gemini(prompt: str) -> tuple[bool, str, bytes | None]:
    """Генерация через Gemini с правильными моделями"""
    
    # Сначала пробуем модель для изображений
    if gemini_image_model:
        try:
            logger.info(f"🎨 Generating image with prompt: {prompt[:100]}...")
            
            response = await gemini_image_model.generate_content_async(prompt)
            
            # Проверяем наличие изображения
            if hasattr(response, '_result') and response._result.candidates:
                for candidate in response._result.candidates:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            if part.inline_data.mime_type.startswith('image/'):
                                logger.info(f"✅ Image generated, size: {len(part.inline_data.data)} bytes")
                                return True, "Изображение сгенерировано", part.inline_data.data
            
            # Если изображения нет, возвращаем текст
            if hasattr(response, 'text') and response.text:
                return False, f"Модель вернула текст: {response.text[:200]}", None
            
        except Exception as e:
            logger.warning(f"⚠️ Image generation failed: {e}")
    
    # Если модель изображений не сработала, пробуем текстовую модель
    if gemini_text_model:
        try:
            logger.info(f"📝 Using text model for prompt: {prompt[:100]}...")
            
            enhanced_prompt = f"""
            Create a detailed description of an image based on: {prompt}
            
            Requirements:
            - Describe the scene in vivid detail
            - Include colors, lighting, composition
            - Make it suitable for image generation
            """
            
            response = await gemini_text_model.generate_content_async(enhanced_prompt)
            
            if hasattr(response, 'text') and response.text:
                return False, response.text, None
                
        except Exception as e:
            logger.error(f"❌ Text model failed: {e}")
    
    return False, "Не удалось сгенерировать изображение", None

# ================== ОБРАБОТЧИКИ ==================

@dp.message_handler(commands=['start'])
async def start_command(message: Message):
    welcome_text = (
        f"<b>🎨 Nana Banana - Gemini Image Bot</b>\n\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"<b>🤖 Статус моделей:</b>\n"
        f"{'✅ Image model' if gemini_image_model else '❌ Image model'}\n"
        f"{'✅ Text model' if gemini_text_model else '❌ Text model'}\n\n"
        f"Просто отправь мне текст, и я создам изображение!"
    )
    await message.reply(welcome_text)

@dp.message_handler(commands=['help'])
async def help_command(message: Message):
    help_text = (
        f"<b>📚 Справка</b>\n\n"
        f"Отправьте текстовое описание, и я создам изображение.\n\n"
        f"<b>Примеры:</b>\n"
        f"• 'Зимний лес на закате'\n"
        f"• 'Кот в космосе'\n"
        f"• 'Киберпанк город'\n\n"
        f"<b>⚙️ Лимиты:</b> {config.MAX_REQUESTS_PER_DAY}/день"
    )
    await message.reply(help_text)

@dp.message_handler(commands=['stats'])
async def stats_command(message: Message):
    user_id = message.from_user.id
    stats = user_stats.get(user_id, {'today': 0, 'total': 0})
    await message.reply(
        f"<b>📊 Статистика</b>\n\n"
        f"• Сегодня: {stats['today']}/{config.MAX_REQUESTS_PER_DAY}\n"
        f"• Всего: {stats['total']}"
    )

@dp.message_handler(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: Message):
    user_id = message.from_user.id
    prompt = message.text.strip()
    
    # Инициализация статистики
    if user_id not in user_stats:
        user_stats[user_id] = {'today': 0, 'total': 0}
    
    # Проверка лимитов
    if user_stats[user_id]['today'] >= config.MAX_REQUESTS_PER_DAY:
        await message.reply("❌ Дневной лимит исчерпан")
        return
    
    await bot.send_chat_action(message.chat.id, 'upload_photo')
    
    try:
        if gemini_available:
            # Пробуем Gemini
            success, result, image_data = await generate_with_gemini(prompt)
            
            if success and image_data:
                await message.reply_photo(
                    io.BytesIO(image_data),
                    caption=f"<b>✨ По запросу:</b> {prompt[:200]}"
                )
                user_stats[user_id]['today'] += 1
                user_stats[user_id]['total'] += 1
            else:
                # Если Gemini вернул текст или ошибку
                await message.reply_photo(
                    io.BytesIO(create_fallback_image(prompt)),
                    caption=f"<b>🎨 Тестовое изображение</b>\n\n{result}"
                )
        else:
            # Режим без Gemini
            await message.reply_photo(
                io.BytesIO(create_fallback_image(prompt)),
                caption=f"<b>🎨 Творческий режим</b>\n\nЗапрос: {prompt}"
            )
            
    except Exception as e:
        logger.error(f"Error: {e}")
        await message.reply(f"❌ Ошибка: {str(e)}")

# ================== ЗАПУСК ==================

if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК GEMINI IMAGE BOT (NANA BANANA)")
    logger.info("=" * 70)
    logger.info(f"📊 Python: {sys.version}")
    logger.info(f"🤖 Image model: {'✅' if gemini_image_model else '❌'}")
    logger.info(f"🤖 Text model: {'✅' if gemini_text_model else '❌'}")
    logger.info(f"🔑 Bot token: {config.BOT_TOKEN[:10]}...")
    logger.info("🔄 Запуск polling...")
    logger.info("=" * 70)
    
    executor.start_polling(dp, skip_updates=True)
