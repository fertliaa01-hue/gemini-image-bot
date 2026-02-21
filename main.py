"""
Telegram бот для генерации тестовых изображений (Творческий режим)
Работает без Gemini API, создает красивые изображения через Pillow
"""

import asyncio
import logging
import sys
import os
import io
import random
import datetime
from pathlib import Path
from PIL import Image, ImageDraw, ImageFont, ImageFilter, ImageEnhance

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

# Конфигурация из переменных окружения
class Config:
    BOT_TOKEN = os.getenv('BOT_TOKEN', '')
    
    # ID администраторов (через запятую)
    ADMIN_IDS = []
    admin_ids_str = os.getenv('ADMIN_IDS', '')
    if admin_ids_str:
        try:
            ADMIN_IDS = [int(id.strip()) for id in admin_ids_str.split(',') if id.strip()]
        except ValueError:
            logger.warning("⚠️ Invalid ADMIN_IDS format")
    
    # Лимиты для пользователей
    MAX_REQUESTS_PER_DAY = int(os.getenv('MAX_REQUESTS_PER_DAY', '100'))  # Увеличен лимит
    MAX_REQUESTS_PER_HOUR = int(os.getenv('MAX_REQUESTS_PER_HOUR', '20'))

config = Config()

# Проверка наличия токена
if not config.BOT_TOKEN:
    logger.error("❌ BOT_TOKEN is not set!")
    logger.error("Please set BOT_TOKEN in environment variables")
    sys.exit(1)

# Инициализация бота
bot = Bot(token=config.BOT_TOKEN, parse_mode=ParseMode.HTML)
dp = Dispatcher(bot)
dp.middleware.setup(LoggingMiddleware())

# Статистика пользователей
user_stats = {}
user_sessions = {}

# ================== КРЕАТИВНЫЕ ФУНКЦИИ ГЕНЕРАЦИИ ==================

def create_beautiful_landscape(prompt: str, style: str = "realistic") -> bytes:
    """
    Создает красивое изображение пейзажа на основе промпта
    """
    # Размер изображения
    width, height = 1024, 1024
    
    # Создаем градиентный фон в зависимости от времени суток из промпта
    prompt_lower = prompt.lower()
    
    # Определяем цветовую гамму по ключевым словам
    if any(word in prompt_lower for word in ['закат', 'вечер', ' sunset', 'evening']):
        # Закатные тона
        sky_top = (255, 120, 50)      # Оранжевый
        sky_bottom = (75, 0, 130)      # Индиго
        ground_color = (34, 139, 34)   # Лесная зелень
    elif any(word in prompt_lower for word in ['ночь', 'night', 'луна', 'moon']):
        # Ночные тона
        sky_top = (25, 25, 112)        # Полуночный синий
        sky_bottom = (0, 0, 0)         # Черный
        ground_color = (20, 40, 20)    # Темно-зеленый
    elif any(word in prompt_lower for word in ['утро', 'morning', 'рассвет', 'dawn']):
        # Утренние тона
        sky_top = (255, 200, 150)      # Светло-оранжевый
        sky_bottom = (135, 206, 235)   # Небесно-голубой
        ground_color = (60, 120, 60)   # Ярко-зеленый
    else:
        # Дневные тона (по умолчанию)
        sky_top = (100, 180, 255)      # Голубой
        sky_bottom = (200, 230, 255)   # Светло-голубой
        ground_color = (34, 139, 34)   # Лесная зелень
    
    # Создаем изображение
    img = Image.new('RGB', (width, height), sky_top)
    draw = ImageDraw.Draw(img)
    
    # Рисуем градиент неба
    for y in range(height // 2):
        ratio = y / (height // 2)
        r = int(sky_top[0] * (1 - ratio) + sky_bottom[0] * ratio)
        g = int(sky_top[1] * (1 - ratio) + sky_bottom[1] * ratio)
        b = int(sky_top[2] * (1 - ratio) + sky_bottom[2] * ratio)
        draw.line([(0, y), (width, y)], fill=(r, g, b))
    
    # Рисуем землю/лес
    ground_height = height // 3
    for y in range(height - ground_height, height):
        ratio = (y - (height - ground_height)) / ground_height
        shade = int(ground_color[0] * (0.5 + 0.5 * ratio))
        draw.line([(0, y), (width, y)], fill=(shade, ground_color[1], ground_color[2]))
    
    # Рисуем деревья
    tree_colors = [
        (34, 139, 34),   # Лесная зелень
        (46, 125, 50),   # Темно-зеленый
        (27, 94, 32),    # Очень темно-зеленый
        (56, 142, 60),   # Средне-зеленый
    ]
    
    # Случайное количество деревьев
    num_trees = random.randint(15, 25)
    for i in range(num_trees):
        x = random.randint(50, width - 50)
        tree_height = random.randint(80, 150)
        tree_width = random.randint(30, 50)
        tree_y = height - ground_height - random.randint(0, 30)
        
        # Ствол
        trunk_color = (101, 67, 33)  # Коричневый
        draw.rectangle(
            [x - 5, tree_y - 20, x + 5, tree_y + 40],
            fill=trunk_color
        )
        
        # Крона (несколько треугольников)
        crown_color = random.choice(tree_colors)
        for j in range(3):
            crown_y = tree_y - 40 - j * 30
            crown_size = tree_width - j * 10
            draw.polygon([
                (x - crown_size, crown_y + 20),
                (x, crown_y),
                (x + crown_size, crown_y + 20)
            ], fill=crown_color)
    
    # Рисуем солнце/луну
    if 'ночь' in prompt_lower or 'night' in prompt_lower:
        # Луна
        moon_x, moon_y = random.randint(700, 900), random.randint(100, 200)
        draw.ellipse(
            [(moon_x - 40, moon_y - 40), (moon_x + 40, moon_y + 40)],
            fill=(255, 255, 200)
        )
        # Звезды
        for _ in range(50):
            star_x = random.randint(0, width)
            star_y = random.randint(0, height // 2)
            star_size = random.randint(1, 3)
            draw.ellipse(
                [(star_x, star_y), (star_x + star_size, star_y + star_size)],
                fill=(255, 255, 255)
            )
    else:
        # Солнце
        sun_x, sun_y = random.randint(600, 900), random.randint(80, 150)
        # Сияние
        for i in range(3):
            radius = 70 + i * 20
            alpha = 100 - i * 30
            glow = Image.new('RGBA', (width, height), (0, 0, 0, 0))
            glow_draw = ImageDraw.Draw(glow)
            glow_draw.ellipse(
                [(sun_x - radius, sun_y - radius), (sun_x + radius, sun_y + radius)],
                fill=(255, 200, 100, alpha)
            )
            img = Image.alpha_composite(img.convert('RGBA'), glow).convert('RGB')
            draw = ImageDraw.Draw(img)
        
        # Само солнце
        draw.ellipse(
            [(sun_x - 30, sun_y - 30), (sun_x + 30, sun_y + 30)],
            fill=(255, 200, 50)
        )
    
    # Добавляем текст с промптом
    try:
        # Пробуем загрузить шрифты
        font_large = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans-Bold.ttf", 40)
        font_medium = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
        font_small = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 20)
    except:
        # Если шрифты не найдены, используем стандартный
        font_large = ImageFont.load_default()
        font_medium = ImageFont.load_default()
        font_small = ImageFont.load_default()
    
    draw = ImageDraw.Draw(img)
    
    # Заголовок
    draw.text((512, 40), "✨ Nana Banana ✨", fill='white', anchor='mt', font=font_large, stroke_width=2, stroke_fill='black')
    
    # Промпт
    words = prompt.split()
    lines = []
    current_line = ""
    for word in words:
        if len(current_line + word) < 40:
            current_line += word + " "
        else:
            lines.append(current_line)
            current_line = word + " "
    lines.append(current_line)
    
    y = 100
    draw.text((512, y), "🎨 Ваш запрос:", fill='#FFD700', anchor='mt', font=font_medium)
    y += 40
    
    for line in lines:
        draw.text((512, y), line, fill='white', anchor='mt', font=font_small, stroke_width=1, stroke_fill='black')
        y += 25
    
    # Информация внизу
    draw.text((512, 950), f"🖼️ Творческий режим | {datetime.datetime.now().strftime('%d.%m.%Y %H:%M')}", 
              fill='#CCCCCC', anchor='mb', font=font_small)
    
    # Сохраняем в байты
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG', optimize=True)
    img_bytes.seek(0)
    
    return img_bytes.getvalue()

def create_abstract_art(prompt: str) -> bytes:
    """
    Создает абстрактное изображение
    """
    width, height = 1024, 1024
    img = Image.new('RGB', (width, height), color='black')
    draw = ImageDraw.Draw(img)
    
    # Рисуем случайные геометрические фигуры
    colors = [
        (255, 99, 71),   # Томатный
        (135, 206, 235), # Небесно-голубой
        (255, 215, 0),   # Золотой
        (147, 112, 219), # Фиолетовый
        (255, 182, 193), # Розовый
        (64, 224, 208),  # Бирюзовый
        (255, 140, 0),   # Оранжевый
        (50, 205, 50),   # Лаймовый
    ]
    
    # Рисуем круги
    for _ in range(30):
        x = random.randint(0, width)
        y = random.randint(0, height)
        radius = random.randint(30, 150)
        color = random.choice(colors)
        opacity = random.randint(50, 150)
        
        # Создаем полупрозрачный круг
        circle = Image.new('RGBA', (width, height), (0, 0, 0, 0))
        circle_draw = ImageDraw.Draw(circle)
        circle_draw.ellipse(
            [(x - radius, y - radius), (x + radius, y + radius)],
            fill=(*color, opacity)
        )
        img = Image.alpha_composite(img.convert('RGBA'), circle).convert('RGB')
        draw = ImageDraw.Draw(img)
    
    # Рисуем линии
    for _ in range(20):
        start = (random.randint(0, width), random.randint(0, height))
        end = (random.randint(0, width), random.randint(0, height))
        color = random.choice(colors)
        width_line = random.randint(2, 10)
        draw.line([start, end], fill=color, width=width_line)
    
    # Добавляем текст
    try:
        font = ImageFont.truetype("/usr/share/fonts/truetype/dejavu/DejaVuSans.ttf", 30)
    except:
        font = ImageFont.load_default()
    
    draw.text((512, 512), f"✨ {prompt[:50]}", fill='white', anchor='mm', font=font)
    
    img_bytes = io.BytesIO()
    img.save(img_bytes, format='PNG')
    img_bytes.seek(0)
    
    return img_bytes.getvalue()

# ================== ОБРАБОТЧИКИ КОМАНД ==================

@dp.message_handler(commands=['start'])
async def start_command(message: Message):
    """Приветствие"""
    welcome_text = (
        f"<b>🎨 Nana Banana - Творческий бот</b>\n\n"
        f"Привет, {message.from_user.first_name}!\n\n"
        f"Я создаю красивые изображения в <b>творческом режиме</b> без использования внешних API.\n\n"
        f"<b>📝 Команды:</b>\n"
        f"/start - Главное меню\n"
        f"/help - Справка\n"
        f"/stats - Моя статистика\n"
        f"/style - Выбрать стиль\n\n"
        f"<b>✨ Доступные стили:</b>\n"
        f"• Пейзаж (по умолчанию)\n"
        f"• Абстракция\n\n"
        f"Просто отправь мне текст, и я создам изображение!"
    )
    await message.reply(welcome_text)

@dp.message_handler(commands=['help'])
async def help_command(message: Message):
    """Справка"""
    help_text = (
        f"<b>📚 Как это работает</b>\n\n"
        f"<b>🎨 Творческий режим:</b>\n"
        f"Я создаю изображения прямо на сервере с помощью библиотеки Pillow.\n\n"
        f"<b>📝 Примеры запросов:</b>\n"
        f"• 'Зимний лес на закате'\n"
        f"• 'Красивый горный пейзаж'\n"
        f"• 'Абстракция в синих тонах'\n\n"
        f"<b>⚙️ Лимиты:</b>\n"
        f"• В день: {config.MAX_REQUESTS_PER_DAY} изображений\n"
        f"• В час: {config.MAX_REQUESTS_PER_HOUR} изображений\n\n"
        f"<b>🎭 Стили:</b>\n"
        f"/style - выбрать стиль генерации\n\n"
        f"<i>Этот бот не требует API ключей и всегда доступен!</i>"
    )
    await message.reply(help_text)

@dp.message_handler(commands=['stats'])
async def stats_command(message: Message):
    """Статистика пользователя"""
    user_id = message.from_user.id
    
    if user_id in user_stats:
        stats = user_stats[user_id]
        stats_text = (
            f"<b>📊 Ваша статистика</b>\n\n"
            f"• Сегодня: {stats.get('today', 0)}/{config.MAX_REQUESTS_PER_DAY}\n"
            f"• За час: {stats.get('hour', 0)}/{config.MAX_REQUESTS_PER_HOUR}\n"
            f"• Всего: {stats.get('total', 0)}\n\n"
            f"<i>Спасибо что пользуетесь ботом! ❤️</i>"
        )
    else:
        stats_text = (
            f"<b>📊 Ваша статистика</b>\n\n"
            f"Вы еще не создавали изображений.\n"
            f"Отправьте любой запрос, чтобы начать!"
        )
    
    await message.reply(stats_text)

@dp.message_handler(commands=['style'])
async def style_command(message: Message):
    """Выбор стиля генерации"""
    keyboard = types.InlineKeyboardMarkup(row_width=2)
    keyboard.add(
        types.InlineKeyboardButton("🏞️ Пейзаж", callback_data="style_landscape"),
        types.InlineKeyboardButton("🎨 Абстракция", callback_data="style_abstract")
    )
    
    await message.reply(
        "<b>🎭 Выберите стиль генерации:</b>\n\n"
        "🏞️ Пейзаж - красивые природные сцены\n"
        "🎨 Абстракция - яркие абстрактные композиции",
        reply_markup=keyboard
    )

@dp.callback_query_handler(lambda c: c.data.startswith('style_'))
async def process_style_callback(callback_query: types.CallbackQuery):
    """Обработка выбора стиля"""
    user_id = callback_query.from_user.id
    style = callback_query.data.replace('style_', '')
    
    if user_id not in user_sessions:
        user_sessions[user_id] = {}
    
    user_sessions[user_id]['style'] = style
    
    style_names = {
        'landscape': '🏞️ Пейзаж',
        'abstract': '🎨 Абстракция'
    }
    
    await bot.answer_callback_query(callback_query.id)
    await bot.send_message(
        user_id,
        f"✅ Стиль изменен на: {style_names.get(style, 'Пейзаж')}\n\n"
        f"Теперь отправьте запрос для генерации!"
    )

async def check_user_limit(user_id: int) -> tuple[bool, str]:
    """Проверка лимитов пользователя"""
    if user_id not in user_stats:
        user_stats[user_id] = {
            'today': 0,
            'hour': 0,
            'total': 0,
            'last_reset': datetime.datetime.now()
        }
    
    stats = user_stats[user_id]
    now = datetime.datetime.now()
    
    # Сброс дневных счетчиков
    if stats['last_reset'].date() < now.date():
        stats['today'] = 0
        stats['last_reset'] = now
    
    # Проверка лимитов
    if stats['today'] >= config.MAX_REQUESTS_PER_DAY:
        return False, f"❌ Дневной лимит ({config.MAX_REQUESTS_PER_DAY}) исчерпан. Попробуйте завтра!"
    
    if stats['hour'] >= config.MAX_REQUESTS_PER_HOUR:
        wait_until = stats['last_reset'] + datetime.timedelta(hours=1)
        wait_minutes = (wait_until - now).seconds // 60
        return False, f"⏳ Часовой лимит исчерпан. Подождите {wait_minutes} минут."
    
    return True, ""

async def increment_user_usage(user_id: int):
    """Увеличение счетчика использования"""
    if user_id in user_stats:
        user_stats[user_id]['today'] += 1
        user_stats[user_id]['hour'] += 1
        user_stats[user_id]['total'] += 1

@dp.message_handler(content_types=['photo'])
async def handle_photo(message: Message):
    """Обработчик фотографий"""
    await message.reply(
        "<b>🖼️ Режим редактирования</b>\n\n"
        "Сейчас я могу только создавать новые изображения по тексту.\n"
        "Просто отправьте текстовое описание того, что хотите увидеть!"
    )

@dp.message_handler(lambda message: message.text and not message.text.startswith('/'))
async def handle_text(message: Message):
    """ОСНОВНОЙ ОБРАБОТЧИК - создание изображений"""
    user_id = message.from_user.id
    prompt = message.text.strip()
    
    logger.info(f"User {user_id} | Запрос: {prompt[:100]}...")
    
    # Проверка лимитов
    allowed, limit_msg = await check_user_limit(user_id)
    if not allowed:
        await message.reply(limit_msg)
        return
    
    # Получаем стиль пользователя
    style = user_sessions.get(user_id, {}).get('style', 'landscape')
    
    # Отправляем статус
    await bot.send_chat_action(message.chat.id, 'upload_photo')
    await message.reply("🎨 Создаю изображение, пожалуйста подождите...")
    
    try:
        # Генерируем изображение в зависимости от стиля
        if style == 'abstract':
            image_data = create_abstract_art(prompt)
            style_name = "Абстракция"
        else:
            image_data = create_beautiful_landscape(prompt)
            style_name = "Пейзаж"
        
        # Отправляем изображение
        await bot.send_chat_action(message.chat.id, 'upload_photo')
        
        caption = (
            f"<b>✨ Ваше изображение готово!</b>\n\n"
            f"<b>Запрос:</b> {prompt}\n"
            f"<b>Стиль:</b> {style_name}\n\n"
            f"<i>Создано в творческом режиме с помощью Pillow</i>"
        )
        
        await message.reply_photo(
            io.BytesIO(image_data),
            caption=caption
        )
        
        # Увеличиваем счетчик
        await increment_user_usage(user_id)
        
        logger.info(f"✅ Изображение создано для пользователя {user_id}")
        
    except Exception as e:
        logger.error(f"❌ Ошибка создания изображения: {e}", exc_info=True)
        
        # Создаем простое запасное изображение
        try:
            img = Image.new('RGB', (512, 512), color='#2c3e50')
            draw = ImageDraw.Draw(img)
            draw.text((256, 256), f"Ошибка\n{str(e)[:50]}", fill='white', anchor='mm')
            
            img_bytes = io.BytesIO()
            img.save(img_bytes, format='PNG')
            img_bytes.seek(0)
            
            await message.reply_photo(
                io.BytesIO(img_bytes.getvalue()),
                caption=f"❌ Произошла ошибка, но я создал тестовое изображение."
            )
        except:
            await message.reply(f"❌ Критическая ошибка: {str(e)[:200]}")

@dp.message_handler(commands=['admin'])
async def admin_command(message: Message):
    """Админ-панель"""
    user_id = message.from_user.id
    
    if user_id not in config.ADMIN_IDS:
        await message.reply("❌ У вас нет прав администратора")
        return
    
    total_users = len(user_stats)
    total_requests = sum(stats.get('total', 0) for stats in user_stats.values())
    today_requests = sum(stats.get('today', 0) for stats in user_stats.values())
    
    admin_text = (
        f"<b>👑 Админ-панель</b>\n\n"
        f"<b>📊 Общая статистика:</b>\n"
        f"• Всего пользователей: {total_users}\n"
        f"• Всего запросов: {total_requests}\n"
        f"• Запросов сегодня: {today_requests}\n\n"
        f"<b>⚙️ Конфигурация:</b>\n"
        f"• Токен: {config.BOT_TOKEN[:10]}...\n"
        f"• Лимит в день: {config.MAX_REQUESTS_PER_DAY}\n"
        f"• Лимит в час: {config.MAX_REQUESTS_PER_HOUR}\n"
        f"• Режим: Творческий (без API)\n\n"
        f"<b>🖥️ Система:</b>\n"
        f"• Python: {sys.version.split()[0]}\n"
        f"• Pillow: готов к работе"
    )
    
    await message.reply(admin_text)

@dp.message_handler()
async def handle_unknown(message: Message):
    """Обработчик неизвестных сообщений"""
    await message.reply(
        "❓ Неизвестная команда. Используйте /help для списка команд."
    )

# ================== ЗАПУСК БОТА ==================

if __name__ == '__main__':
    logger.info("=" * 70)
    logger.info("🚀 ЗАПУСК NANA BANANA BOT (ТВОРЧЕСКИЙ РЕЖИМ)")
    logger.info("=" * 70)
    logger.info(f"📊 Python: {sys.version}")
    logger.info(f"💻 Platform: {sys.platform}")
    logger.info(f"🤖 aiogram: 2.x")
    logger.info(f"🖼️ Pillow: готов к работе")
    logger.info(f"🔑 Bot token: {config.BOT_TOKEN[:10]}...")
    logger.info(f"🎨 Режим: Творческий (без API)")
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
