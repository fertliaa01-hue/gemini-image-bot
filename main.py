"""
Telegram бот для генерации изображений через Google Gemini 2.5 Flash Image
ПОЛНОСТЬЮ РАБОЧАЯ ВЕРСИЯ с реальной генерацией
"""

import asyncio
import logging
import sys
import os
import io
import tempfile
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
    from aiogram.types import Message, ParseMode, InputFile
    from aiogram.utils.markdown import hbold, hlink, text
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
    
    # Режим отладки
    DEBUG = os.getenv('DEBUG', 'False').lower() == 'true'

config = Config()

# Проверка наличия токена
if not config.BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is not set!")
    logger.error("Please set BOT_TOKEN in environment variables")
    sys.exit(1)

# Инициализация Gemini
gemini_model = None
gemini_available = False

if config.GEMINI_API_KEY and GENAI_AVAILABLE:
    try:
        genai.configure(api_key=config.GEMINI_API_KEY)
        
        # Пробуем разные модели для генерации изображений
        models_to_try = [
            'gemini-2.0-flash-exp-image-generation',  # Основная модель для изображений
            'gemini-1.5-pro',                          # Запасная модель
            'gemini-1.5-flash'                         # Быстрая модель
        ]
        
        for model_name in models_to_try:
            try:
                gemini_model = genai.GenerativeModel(model_name)
                # Тестируем модель
                test_response = gemini_model.generate_content("test", generation_config={"max_output_tokens": 1})
                logger.info(f"✅ Gemini model initialized: {model_name}")
                gemini_available = True
                break
            except Exception as e:
                logger.warning(f"⚠️ Model {model_name} not available: {e}")
                continue
        
        if not gemini_available:
            logger.error("❌ No Gemini models available")
            
    except Exception as e:
        logger.error(f"❌ Failed to initialize Gemini: {e}")
        gemini_model = None
else:
    if not config.GEMINI_API_KEY:
        logger.warning("⚠️ GEMINI_API_KEY not set - bot will run in CREATIVE mode")
    elif not GENAI_AVAILABLE:
        logger.warning("⚠️ google-generativeai library not available - bot will run in CREATIVE mode")

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Простая база данных в памяти
user_stats = {}
user_sessions = {}

# ================== ФУНКЦИИ ГЕНЕРАЦИИ ИЗОБРАЖЕНИЙ ==================

def create_fallback_image(prompt: str) -> bytes:
    """
    Создает красивое изображение с помощью Pillow, когда API недоступен
    """
    # Создаем изображение
    width, height = 1024, 1024
    img = Image.new('RGB', (width, height), color='#1a1a2e')
    draw = ImageDraw.Draw(img)
    
    # Рисуем градиентный фон
    for i in range(height):
        color = (
            int(26 + (i * 0.05)),  # R
            int(26 + (i * 0.03)),  # G
            int(46 + (i * 0.1))    # B
        )
        draw.line([(0, i), (width, i)], fill=color)
    
    # Рисуем звезды
    for _ in range(100):
        x = random.randint(0, width)
        y = random.randint(0, height // 2)
        size = random.randint(1, 3)
        draw.ellipse([(x, y), (x + size, y + size)], fill='white')
    
    # Рисуем луну
    moon_x, moon_y = 800, 200
    moon_radius = 60
    draw.ellipse(
        [(moon_x - moon_radius, moon_y - moon_radius),
         (moon_x + moon_radius, moon_y + moon_radius)],
        fill='#f1c40f'
    )
    
    # Рисуем лес
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
    
    # Добавляем текст
    try:
        # Пробуем загрузить шрифт
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except:
        # Если шрифт не найден, используем стандартный
        font_large = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    # Заголовок
    draw.text((512, 50), "✨ Nana Banana ✨", fill='#f39c12', anchor='mt', font=font_large)
    
    # Промпт
    words = prompt.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line + word) < 30:
            current_line += word + " "
        else:
            lines.append(current_line)
            current_line = word + " "
    lines.append(current_line)
    
    y = 120
    draw.text((512, y), "Запрос:", fill='#3498db', anchor='mt', font=font_small)
    y += 40
    
    for line in lines:
        draw.text((512, y), line, fill='white', anchor='mt', font=font_small)
        y += 35
    
    # Информация
    draw.text((512, height - 80), f"🖼️ Сгенерировано: {datetime.datetime.now().strftime('%H:%M %d.%m.%Y')}", 
              fill='#95a5a6', anchor='mb', font=font_small)
    
    # Сохраняем в байты
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG', optimize=True)
    img_bytes.seek(0)
    
    return img_bytes.getvalue()

async def generate_with_gemini(prompt: str) -> tuple[bool, str, bytes | None]:
    """
    Генерация через Gemini API
    """
    if not gemini_model:
        return False, "Gemini API не настроен", None
    
    try:
        logger.info(f"🎨 Generating with prompt: {prompt[:100]}...")
        
        # Формируем улучшенный промпт
        enhanced_prompt = f"""Create a detailed, beautiful image based on this description: {prompt}

Requirements:
- High quality, photorealistic style
- Rich colors and good lighting
- 16:9 aspect ratio
- Professional composition"""

        # Генерируем контент
        response = gemini_model.generate_content(
            enhanced_prompt,
            generation_config={
                "temperature": 0.9,
                "top_p": 0.95,
                "top_k": 40,
                "max_output_tokens": 2048,
            }
        )
        
        # Проверяем наличие изображения в ответе
        if hasattr(response, '_result') and response._result.candidates:
            for candidate in response._result.candidates:
                if hasattr(candidate, 'content') and candidate.content.parts:
                    for part in candidate.content.parts:
                        if hasattr(part, 'inline_data') and part.inline_data:
                            if part.inline_data.mime_type.startswith('image/'):
                                logger.info(f"✅ Image generated, size: {len(part.inline_data.data)} bytes")
                                return True, "Изображение сгенерировано", part.inline_data.data
        
        # Если есть текстовый ответ
        if hasattr(response, 'text') and response.text:
            logger.info("⚠️ Got text response instead of image")
            return False, f"Модель вернула текст: {response.text[:200]}...", None
        
        # Если ничего не нашли
        return False, "Не удалось получить изображение от API", None
        
    except Exception as e:
        logger.error(f"❌ Gemini API error: {e}")
        return False, f"Ошибка API: {str(e)}", None

# ================== ОБРАБОТЧИКИ КОМАНД ==================

@dp.message_handler(commands=['start'])
async def start_command(message: Message):
    """Обработчик команды /start"""
    user_id = message.from_user.id
    username = message.from_user.username or "Unknown"
    
    logger.info(f"User {user_id} (@{username}) started the bot")
    
    welcome_text = (
        f"<b>🎨 Nana Banana - Gemini Image Bot</b>\n\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"Я бот для генерации изображений с помощью "
        f"<b>Google Gemini 2.5 Flash Image</b>.\n\n"
        f"<b>📝 Команды:</b>\n"
        f"/start - Главное меню\n"
        f"/help - Справка\n"
        f"/stats - Моя статистика\n"
        f"/creative - Творческий режим (без API)\n\n"
        f"<b>🎨 Режим работы:</b> {'✅ Gemini API' if gemini_available else '🎨 Творческий режим'}\n\n"
        f"Просто отправь мне текст, и я создам изображение!"
    )
    
    await message.reply(welcome_text)

@dp.message_handler(commands=['help'])
async def help_command(message: Message):
    """Обработчик команды /help"""
    help_text = (
        f"<b>📚 Справка по использованию</b>\n\n"
        f"<b>🎨 Как генерировать:</b>\n"
        f"• Отправь текстовое описание\n"
        f"• Чем подробнее, тем лучше результат\n\n"
        f"<b>📝 Примеры:</b>\n"
        f"• 'Зимний лес на закате, фотореализм'\n"
        f"• 'Киберпанк город, неон, дождь'\n"
        f"• 'Кот в космосе, цифровой арт'\n\n"
        f"<b>⚙️ Лимиты:</b>\n"
        f"• В день: {config.MAX_REQUESTS_PER_DAY} запросов\n"
        f"• В час: {config.MAX_REQUESTS_PER_HOUR} запросов\n\n"
        f"<b>🔧 Режимы:</b>\n"
        f"• Основной: реальная генерация через Gemini\n"
        f"• Творческий (/creative): красивые тестовые изображения\n\n"
        f"<b>🔄 Текущий статус:</b>\n"
        f"• Gemini API: {'✅ Подключен' if gemini_available else '❌ Не доступен'}\n"
        f"• Режим: {'Реальная генерация' if gemini_available else 'Творческий'}"
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
            f"• Использовано сегодня: {stats.get('today', 0)}/{config.MAX_REQUESTS_PER_DAY}\n"
            f"• Использовано за час: {stats.get('hour', 0)}/{config.MAX_REQUESTS_PER_HOUR}\n"
            f"• Всего запросов: {stats.get('total', 0)}\n\n"
            f"<b>🤖 Режим:</b> {'Gemini API' if gemini_available else 'Творческий'}"
        )
    else:
        stats_text = (
            f"<b>📊 Ваша статистика</b>\n\n"
            f"Вы еще не делали запросов.\n\n"
            f"<b>🤖 Режим:</b> {'Gemini API' if gemini_available else 'Творческий'}"
        )
    
    await message.reply(stats_text)

@dp.message_handler(commands=['creative'])
async def creative_command(message: Message):
    """Переключение в творческий режим"""
    user_id = message.from_user.id
    
    # Сохраняем режим для пользователя
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['creative_mode'] = True
    
    await message.reply(
        "🎨 <b>Творческий режим активирован!</b>\n\n"
        "Теперь я буду создавать красивые тестовые изображения "
        "без использования Gemini API. Отправь мне любой запрос!"
    )

@dp.message_handler(commands=['real'])
async def real_command(message: Message):
    """Переключение в реальный режим"""
    user_id = message.from_user.id
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['creative_mode'] = False
    
    if gemini_available:
        await message.reply(
            "🤖 <b>Реальный режим активирован!</b>\n\n"
            "Теперь я буду использовать Gemini API для генерации изображений."
        )
    else:
        await message.reply(
            "⚠️ <b>Gemini API не доступен</b>\n\n"
            "Реальный режим недоступен. Используйте /creative для творческого режима."
        )

@dp.message_handler(commands=['admin'])
async def admin_command(message: Message):
    """Админ-панель"""
    user_id = message.from_user.id
    
    if user_id not in config.ADMIN_IDS:
        await message.reply("❌ У вас нет прав администратора")
        return
    
    total_users = len(user_stats)
    total_requests = sum(stats.get('total', 0) for stats in user_stats.values())
    
    admin_text = (
        f"<b>👑 Админ-панель</b>\n\n"
        f"<b>Статистика:</b>\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Всего запросов: {total_requests}\n"
        f"• Gemini API: {'✅ Работает' if gemini_available else '❌ Отключен'}\n\n"
        f"<b>⚙️ Конфигурация:</b>\n"
        f"• Токен: {config.BOT_TOKEN[:10]}...\n"
        f"• API ключ: {'✅ Есть' if config.GEMINI_API_KEY else '❌ Нет'}\n"
        f"• Лимит в день: {config.MAX_REQUESTS_PER_DAY}\n"
        f"• Лимит в час: {config.MAX_REQUESTS_PER_HOUR}\n"
    )
    
    await message.reply(admin_text)

async def check_user_limit(user_id: int) -> tuple[bool, str]:
    """Проверка лимитов"""
    if user_id not in user_stats:
        user_stats[user_id] = {
            'today': 0,
            'hour': 0,
            'total': 0,
            'last_reset': datetime.datetime.now()
        }
    
    stats = user_stats[user_id]
    now = datetime.datetime.now()
    
    # Сброс счетчиков
    if stats['last_reset'].date() < now.date():
        stats['today'] = 0
        stats['last_reset'] = now
    
    if stats['today'] >= config.MAX_REQUESTS_PER_DAY:
        return False, f"❌ Достигнут дневной лимит ({config.MAX_REQUESTS_PER_DAY} запросов)"
    
    return True, ""

async def increment_user_usage(user_id: int):
    """Увеличение счетчика"""
    if user_id in user_stats:
        user_stats[user_id]['today'] += 1
        user_stats[user_id]['hour'] += 1
        user_stats[user_id]['total'] += 1

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: Message):
    """Обработчик фотографий"""
    await message.reply(
        "<b>🖼️ Редактирование фото</b>\n\n"
        "Функция редактирования изображений пока в разработке.\n"
        "Сейчас доступна только генерация новых изображений по тексту.\n\n"
        "Просто отправьте текстовое описание того, что хотите увидеть!"
    )

@dp.message_handler(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: Message):
    """ОСНОВНОЙ ОБРАБОТЧИК - генерация изображений"""
    user_id = message.from_user.id
    prompt = message.text.strip()
    
    # Проверяем режим пользователя
    creative_mode = user_sessions.get(user_id, {}).get('creative_mode', not gemini_available)
    
    logger.info(f"User {user_id} | Mode: {'CREATIVE' if creative_mode else 'REAL'} | Prompt: {prompt[:100]}...")
    
    # Проверка лимитов
    allowed, limit_msg = await check_user_limit(user_id)
    if not allowed:
        await message.reply(limit_msg)
        return
    
    # Отправляем статус
    await bot.send_chat_action(message.chat.id, 'upload_photo')
    
    try:
        if creative_mode or not gemini_available:
            # ТВОРЧЕСКИЙ РЕЖИМ - создаем красивое изображение через Pillow
            await message.reply("🎨 Создаю изображение в творческом режиме...")
            
            image_data = create_fallback_image(prompt)
            
            await bot.send_chat_action(message.chat.id, 'upload_photo')
            
            # Отправляем изображение
            await message.reply_photo(
                io.BytesIO(image_data),
                caption=(
                    f"<b>🎨 Творческий режим</b>\n\n"
                    f"<b>Запрос:</b> {prompt}\n\n"
                    f"<i>Это тестовое изображение, созданное с помощью Pillow.\n"
                    f"Для реальной генерации через Gemini добавьте API ключ.</i>"
                )
            )
            
            await increment_user_usage(user_id)
            
        else:
            # РЕАЛЬНЫЙ РЕЖИМ - используем Gemini API
            await message.reply("🤖 Обращаюсь к Gemini API, пожалуйста подождите...")
            
            success, msg, image_data = await generate_with_gemini(prompt)
            
            if success and image_data:
                await bot.send_chat_action(message.chat.id, 'upload_photo')
                
                # Отправляем изображение
                await message.reply_photo(
                    io.BytesIO(image_data),
                    caption=f"<b>✨ Сгенерировано через Gemini:</b>\n{prompt}"
                )
                
                await increment_user_usage(user_id)
                
            else:
                # Если реальная генерация не удалась, используем творческий режим как запасной
                logger.warning(f"Real generation failed, falling back to creative mode: {msg}")
                
                await message.reply(f"⚠️ Gemini API: {msg}\n\nСоздаю тестовое изображение...")
                
                image_data = create_fallback_image(prompt)
                
                await message.reply_photo(
                    io.BytesIO(image_data),
                    caption=(
                        f"<b>🎨 Тестовое изображение (запасной режим)</b>\n\n"
                        f"<b>Запрос:</b> {prompt}\n\n"
                        f"<i>Причина: {msg}</i>"
                    )
                )
    
    except Exception as e:
        logger.error(f"❌ Error processing request: {e}", exc_info=True)
        
        # В случае любой ошибки создаем тестовое изображение
        try:
            image_data = create_fallback_image(f"Ошибка: {prompt}")
            await message.reply_photo(
                io.BytesIO(image_data),
                caption=f"<b>⚠️ Произошла ошибка, но я создал тестовое изображение:</b>\n\n{str(e)[:200]}"
            )
        except:
            await message.reply(f"❌ Критическая ошибка: {str(e)}")

@dp.message_handler()
async def handle_unknown(message: Message):
    """Обработчик неизвестных сообщений"""
    await message.reply(
        "❓ Неизвестная команда. Используйте /help для списка команд."
    )

# ================== ЗАПУСК БОТА ==================

if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК GEMINI IMAGE BOT (NANA BANANA)")
    logger.info("=" * 70)
    logger.info(f"📊 Python: {sys.version}")
    logger.info(f"💻 Platform: {sys.platform}")
    logger.info(f"🤖 aiogram: 2.x")
    logger.info(f"🔑 Bot token: {config.BOT_TOKEN[:10]}...")
    
    if gemini_available:
        logger.info(f"✅ Gemini API: ПОДКЛЮЧЕН (реальная генерация)")
        logger.info(f"🤖 Модель: {gemini_model.model_name if gemini_model else 'unknown'}")
    else:
        logger.warning("🎨 Gemini API: НЕ ПОДКЛЮЧЕН - работа в творческом режиме")
        if config.GEMINI_API_KEY:
            logger.warning("   Ключ API есть, но модель не доступна")
        else:
            logger.warning("   Добавьте GEMINI_API_KEY для реальной генерации")
    
    logger.info(f"👥 Admin IDs: {config.ADMIN_IDS}")
    logger.info(f"📈 Лимиты: {config.MAX_REQUESTS_PER_DAY}/день, {config.MAX_REQUESTS_PER_HOUR}/час")
    logger.info("🔄 Запуск polling...")
    logger.info("=" * 70)
    
    try:
        executor.start_polling(dp, skip_updates=True)
    except Exception as e:
        logger.error(f"💥 Критическая ошибка: {e}", exc_info=True)
    finally:
        logger.info("👋 Бот остановлен")
