"""
Telegram-бот для получения погоды и ежедневных уведомлений.
Команды:
- /start — приветствие и главное меню
- /weather [city] — погода по городу (по умолчанию — установленный город)
- /default <city> — установить город по умолчанию
- /notify HH:MM — включить ежедневные уведомления в указанное время (по умолчанию 7:00)
- /notify — показать текущие настройки уведомлений
- /daily_off — выключить ежедневные уведомлений
- /daily_status — статус уведомлений
"""

import asyncio
import logging
from datetime import datetime

from aiogram import Bot, Dispatcher, Router, F
from aiogram.enums import ParseMode
from aiogram.filters import CommandStart, Command
from aiogram.types import (
    Message,
    InlineKeyboardMarkup,
    InlineKeyboardButton,
    ReplyKeyboardMarkup,
    KeyboardButton,
    CallbackQuery,
)
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from config import TELEGRAM_BOT_TOKEN, OPENWEATHER_API_KEY
from weather import format_weather, get_weather
from storage import init_db, get_user, update_user, get_enabled_users

# Логирование
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Router для обработки сообщений
router = Router()


def _build_main_kb(user):
    """Строит главную inline-клавиатуру с учётом текущего статуса уведомлений."""
    enabled = bool(user["notify_enabled"])
    h = user["notify_hour"]
    m = user["notify_minute"]

    if enabled:
        notify_btn_text = f"🔴 Выключить уведомления ({h:02d}:{m:02d})"
        notify_btn_data = "notify_off"
    else:
        notify_btn_text = "🟢 Включить уведомления"
        notify_btn_data = "notify_settings"

    return InlineKeyboardMarkup(inline_keyboard=[
        [
            InlineKeyboardButton(text="🌤 Погода", callback_data="weather"),
            InlineKeyboardButton(text="🏙️ Город по умолчанию", callback_data="default"),
        ],
        [
            InlineKeyboardButton(text=notify_btn_text, callback_data=notify_btn_data),
            InlineKeyboardButton(text="📊 Статус", callback_data="status"),
        ],
    ])


def _build_notify_settings_kb(user):
    """Строит клавиатуру настроек уведомлений (выбор времени, вкл/выкл)."""
    h = user["notify_hour"]
    m = user["notify_minute"]
    enabled = bool(user["notify_enabled"])

    preset_hours = [6, 7, 8, 9, 10, 12, 15, 18, 21]
    time_buttons = []
    for ph in preset_hours:
        mark = '✅' if enabled and h == ph and m == 0 else '🕒'
        time_buttons.append([
            InlineKeyboardButton(text=f"{mark} {ph:02d}:00", callback_data=f"time_{ph}_0")
        ])

    toggle_text = "🔴 Выключить" if enabled else "🟢 Включить"
    toggle_data = "notify_off" if enabled else "notify_on"

    return InlineKeyboardMarkup(inline_keyboard=[
        *time_buttons,
        [InlineKeyboardButton(text=toggle_text, callback_data=toggle_data)],
        [InlineKeyboardButton(text="✏️ Своё время", callback_data="notify_custom")],
        [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")],
    ])


def _build_notify_status_text(user):
    """Возвращает текст статуса уведомлений."""
    enabled = bool(user["notify_enabled"])
    h = user["notify_hour"]
    m = user["notify_minute"]
    city = user["default_city"] or '(не установлен)'

    return (
        f"⏰ <b>Настройка уведомлений</b>\n\n"
        f"Статус: <b>{'включено' if enabled else 'выключено'}</b>\n"
        f"Время: <b>{h:02d}:{m:02d}</b>\n"
        f"Город: <b>{city}</b>\n\n"
        f"Выберите время или включите/выключите:"
    )


def _build_main_menu_text():
    """Возвращает текст главного меню."""
    return "🤖 Главное меню. Выберите действие:"


# ─── Команды ───────────────────────────────────────────────────────

@router.message(CommandStart())
async def cmd_start(message: Message):
    """Обработчик команды /start."""
    user_id = message.from_user.id
    user = get_user(user_id)  # создаст пользователя если его нет
    kb = _build_main_kb(user)

    await message.answer(
        f"👋 Привет, {message.from_user.first_name}!\n\n"
        "🤖 Я — бот погоды. Выберите действие:",
        reply_markup=kb,
    )


@router.message(Command("weather"))
async def cmd_weather(message: Message):
    """Обработчик команды /weather."""
    args = message.text.split(maxsplit=1)
    city_arg = args[1].strip() if len(args) > 1 else None
    user_id = message.from_user.id

    user = get_user(user_id)
    city = city_arg or user["default_city"]

    if not city:
        await message.answer(
            "❌ Вы не указали город и не установили город по умолчанию.\n"
            "Используйте: /default <город> или /weather <город>"
        )
        return

    await message.answer("⏳ Получаю погоду...")
    weather = format_weather(get_weather(city, OPENWEATHER_API_KEY), city, for_telegram=True)
    await message.answer(weather, parse_mode=ParseMode.HTML)


@router.message(Command("default"))
async def cmd_default(message: Message):
    """Обработчик команды /default <город>."""
    parts = message.text.split(maxsplit=1)
    if len(parts) < 2 or not parts[1].strip():
        user_id = message.from_user.id
        user = get_user(user_id)

        cities_kb = InlineKeyboardMarkup(inline_keyboard=[
            [InlineKeyboardButton(text="Москва", callback_data="city_Moscow")],
            [InlineKeyboardButton(text="Санкт-Петербург", callback_data="city_Saint Petersburg")],
            [InlineKeyboardButton(text="Казань", callback_data="city_Kazan")],
            [InlineKeyboardButton(text="Екатеринбург", callback_data="city_Yekaterinburg")],
            [InlineKeyboardButton(text="Новый город...", callback_data="city_manual")],
            [InlineKeyboardButton(text="◀️ Назад", callback_data="back_to_main")],
        ])

        await message.answer(
            f"🏙 Текущий город по умолчанию: {user['default_city'] or '(не установлен)'}\n"
            f"Выберите город или введите свой:",
            reply_markup=cities_kb,
        )
        return

    city = parts[1].strip()
    user_id = message.from_user.id

    update_user(user_id, default_city=city)
    await message.answer(f"✅ Город по умолчанию установлен: <b>{city}</b>", parse_mode=ParseMode.HTML)


@router.message(Command("notify"))
async def cmd_notify(message: Message):
    """Обработчик команды /notify [HH:MM]."""
    parts = message.text.split(maxsplit=1)
    user_id = message.from_user.id
    user = get_user(user_id)

    if len(parts) < 2:
        h = user["notify_hour"]
        m = user["notify_minute"]
        enabled = bool(user["notify_enabled"])
        status = "включено" if enabled else "выключено"
        time_str = f"{h:02d}:{m:02d}"
        await message.answer(
            f"⏰ Уведомления: {status}\n"
            f"🕒 Время: {time_str}\n"
            f"🏙 Город: {user['default_city'] or '(не установлен)'}\n\n"
            f"Для установки времени: /notify HH:MM\n"
            f"Например: /notify 7:00"
        )
        return

    time_str = parts[1].strip()
    try:
        if ":" not in time_str:
            hour = int(time_str)
            minute = 0
        else:
            hour_str, minute_str = time_str.split(":", 1)
            hour = int(hour_str)
            minute = int(minute_str)
        if not (0 <= hour <= 23 and 0 <= minute <= 59):
            raise ValueError
    except ValueError:
        await message.answer("❌ Неверный формат времени. Используйте HH:MM (например, 7:00)")
        return

    update_user(user_id, notify_hour=hour, notify_minute=minute, notify_enabled=1)
    await message.answer(
        f"✅ Ежедневные уведомления включены на <b>{hour:02d}:{minute:02d}</b>\n"
        f"🏙 Город: {user['default_city'] or '(установите город: /default <город>)'}",
        parse_mode=ParseMode.HTML,
    )


@router.message(Command("daily_off"))
async def cmd_daily_off(message: Message):
    """Обработчик команды /daily_off."""
    user_id = message.from_user.id
    update_user(user_id, notify_enabled=0)
    await message.answer("🔴 Ежедневные уведомления выключены.")


@router.message(Command("daily_status"))
async def cmd_daily_status(message: Message):
    """Обработчик команды /daily_status."""
    user_id = message.from_user.id
    user = get_user(user_id)
    enabled = bool(user["notify_enabled"])
    h = user["notify_hour"]
    m = user["notify_minute"]
    time_str = f"{h:02d}:{m:02d}"
    await message.answer(
        f"📊 Статус уведомлений:\n"
        f"⏰ Статус: {'включено' if enabled else 'выключено'}\n"
        f"🕒 Время: {time_str}\n"
        f"🏙 Город по умолчанию: {user['default_city'] or '(не установлен)'}"
    )


# ─── Callback-кнопки ──────────────────────────────────────────────

@router.callback_query(F.data == "weather")
async def callback_weather(callback: CallbackQuery):
    """Кнопка «🌤 Погода» — показывает погоду по городу по умолчанию."""
    user_id = callback.from_user.id
    user = get_user(user_id)
    city = user["default_city"]

    if not city:
        await callback.answer(
            "⚠️ Город по умолчанию не установлен.\n"
            "Нажмите «🏙️ Город по умолчанию» или используйте /default <город>",
            show_alert=True,
        )
        return

    await callback.answer("⏳ Получаю погоду...")
    weather = format_weather(get_weather(city, OPENWEATHER_API_KEY), city, for_telegram=True)
    await callback.message.answer(weather, parse_mode=ParseMode.HTML)


@router.callback_query(F.data == "default")
async def callback_default(callback: CallbackQuery):
    """Кнопка «🏙️ Город по умолчанию» — показывает текущий город."""
    user_id = callback.from_user.id
    user = get_user(user_id)
    await callback.answer(
        f"🏙 Текущий город по умолчанию: {user['default_city'] or '(не установлен)'}\n"
        f"Используйте: /default <город>",
        show_alert=True,
    )


@router.callback_query(F.data == "status")
async def callback_status(callback: CallbackQuery):
    """Кнопка «📊 Статус» — показывает статус уведомлений."""
    user_id = callback.from_user.id
    user = get_user(user_id)
    h = user["notify_hour"]
    m = user["notify_minute"]
    enabled = bool(user["notify_enabled"])
    time_str = f"{h:02d}:{m:02d}"
    await callback.answer(
        f"📊 Статус:\n"
        f"⏰ {'включено' if enabled else 'выключено'}\n"
        f"🕒 {time_str}\n"
        f"🏙 {user['default_city'] or '(не установлен)'}",
        show_alert=True,
    )


# ─── Управление уведомлениями ─────────────────────────────────────

@router.callback_query(F.data == "notify_settings")
async def callback_notify_settings(callback: CallbackQuery):
    """Показывает экран настройки уведомлений (выбор времени, вкл/выкл)."""
    user_id = callback.from_user.id
    user = get_user(user_id)
    kb = _build_notify_settings_kb(user)

    status_text = _build_notify_status_text(user)
    await callback.message.edit_text(status_text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer()


@router.callback_query(F.data == "notify_on")
async def callback_notify_on(callback: CallbackQuery):
    """Включает ежедневные уведомления и обновляет клавиатуру настроек."""
    user_id = callback.from_user.id
    update_user(user_id, notify_enabled=1)
    user = get_user(user_id)
    kb = _build_notify_settings_kb(user)

    status_text = _build_notify_status_text(user)
    await callback.message.edit_text(status_text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer("✅ Ежедневные уведомления включены.", show_alert=True)


@router.callback_query(F.data == "notify_off")
async def callback_notify_off(callback: CallbackQuery):
    """Выключает ежедневные уведомления и возвращает в главное меню."""
    user_id = callback.from_user.id
    update_user(user_id, notify_enabled=0)
    user = get_user(user_id)
    kb = _build_main_kb(user)

    await callback.message.edit_text(_build_main_menu_text(), reply_markup=kb)
    await callback.answer("🔴 Ежедневные уведомления выключены.", show_alert=True)


@router.callback_query(F.data == "daily_off")
async def callback_daily_off(callback: CallbackQuery):
    """Кнопка «❌ Отключить уведомления» — выключает уведомления."""
    user_id = callback.from_user.id
    update_user(user_id, notify_enabled=0)
    user = get_user(user_id)
    kb = _build_main_kb(user)

    await callback.message.edit_text(_build_main_menu_text(), reply_markup=kb)
    await callback.answer("🔴 Ежедневные уведомления выключены.", show_alert=True)


@router.callback_query(F.data.startswith("time_"))
async def callback_set_time(callback: CallbackQuery):
    """Устанавливает время уведомлений (например, time_7_0)."""
    parts = callback.data.split("_")
    hour = int(parts[1])
    minute = int(parts[2])
    user_id = callback.from_user.id
    update_user(user_id, notify_hour=hour, notify_minute=minute, notify_enabled=1)
    user = get_user(user_id)
    kb = _build_notify_settings_kb(user)

    status_text = _build_notify_status_text(user)
    await callback.message.edit_text(status_text, reply_markup=kb, parse_mode=ParseMode.HTML)
    await callback.answer(f"✅ Время установлено: {hour:02d}:{minute:02d}\nУведомления включены", show_alert=True)


@router.callback_query(F.data == "notify_custom")
async def callback_notify_custom(callback: CallbackQuery):
    """Кнопка «✏️ Своё время» — запрашивает ввод времени в формате HH:MM."""
    await callback.message.answer(
        "✏️ Введите время в формате <b>HH:MM</b> (например, <b>7:30</b>):",
        parse_mode=ParseMode.HTML,
    )
    await callback.answer()


@router.callback_query(F.data == "back_to_main")
async def callback_back_to_main(callback: CallbackQuery):
    """Кнопка «◀️ Назад» — возвращает в главное меню."""
    user_id = callback.from_user.id
    user = get_user(user_id)
    kb = _build_main_kb(user)

    await callback.message.edit_text(_build_main_menu_text(), reply_markup=kb)
    await callback.answer()


# ─── Выбор города (кнопки из /default) ───────────────────────────

CITY_MAP = {
    "Moscow": "Москва",
    "Saint Petersburg": "Санкт-Петербург",
    "Kazan": "Казань",
    "Yekaterinburg": "Екатеринбург",
}


@router.callback_query(F.data.startswith("city_"))
async def callback_city(callback: CallbackQuery):
    """Обработка кнопок с выбором города."""
    data = callback.data.split("_", 1)
    action = data[1]
    user_id = callback.from_user.id

    if action == "manual":
        await callback.message.answer(
            "✍️ Введите название нового города (латиницей или на русском):",
            reply_markup=ReplyKeyboardBuilder()
            .add(KeyboardButton(text="🏠 Меню"))
            .as_markup(resize_keyboard=True),
        )
        await callback.answer()
        return

    city_code = action
    display_city = CITY_MAP.get(city_code, action)

    weather = get_weather(display_city, OPENWEATHER_API_KEY)
    if "error" in weather:
        await callback.answer(
            f"⚠️ {weather['error']}\n"
            f"Используйте город из списка или введите свой.",
            show_alert=True,
        )
        return

    update_user(user_id, default_city=display_city)
    await callback.answer(
        f"✅ Город по умолчанию установлен: {display_city}",
        show_alert=True,
    )


# ─── Обработка текстовых сообщений (ввод города / времени) ────────

@router.message(F.text)
async def handle_text(message: Message):
    """Обработка текстовых сообщений: ввод города или времени уведомлений."""
    user_id = message.from_user.id
    user = get_user(user_id)
    text = message.text.strip()

    if text == "🏠 Меню":
        kb = _build_main_kb(user)
        await message.answer("🤖 Главное меню:", reply_markup=kb)
        return

    # Проверяем, похоже ли на время HH:MM
    if ":" in text and len(text) <= 5:
        try:
            hour_str, minute_str = text.split(":", 1)
            hour = int(hour_str)
            minute = int(minute_str)
            if 0 <= hour <= 23 and 0 <= minute <= 59:
                update_user(user_id, notify_hour=hour, notify_minute=minute, notify_enabled=1)
                await message.answer(
                    f"✅ Ежедневные уведомления включены на <b>{hour:02d}:{minute:02d}</b>\n"
                    f"🏙 Город: {user['default_city'] or '(не установлен)'}",
                    parse_mode=ParseMode.HTML,
                )
                return
        except ValueError:
            pass

    # Иначе считаем, что это название города
    weather = get_weather(text, OPENWEATHER_API_KEY)
    if "error" not in weather:
        update_user(user_id, default_city=text)
        formatted = format_weather(weather, text, for_telegram=True)
        await message.answer(
            f"✅ Город по умолчанию установлен: <b>{text}</b>\n\n{formatted}",
            parse_mode=ParseMode.HTML,
        )
    else:
        await message.answer(
            f"❌ Не удалось найти город: {text}\n"
            f"Попробуйте другое название или выберите из списка через /default",
        )


# ─── Фоновая задача для ежедневных уведомлений ────────────────────

async def daily_notification_task(bot: Bot):
    """Фоновая задача, проверяющая каждую минуту, не пора ли отправить уведомления."""
    last_run_date = None

    while True:
        try:
            await asyncio.sleep(30)
            now = datetime.now()
            current_minute = now.replace(second=0, microsecond=0)

            if last_run_date == current_minute:
                continue

            enabled_users = get_enabled_users()
            if not enabled_users:
                last_run_date = current_minute
                continue

            for user in enabled_users:
                if (user["notify_hour"] == now.hour and
                    user["notify_minute"] == now.minute):
                    city = user["default_city"].strip() if user["default_city"] else None
                    if not city:
                        await bot.send_message(
                            user["chat_id"],
                            "⚠️ Вы не установили город по умолчанию.\n"
                            "Отправьте /default <город> чтобы указать город для уведомлений.",
                            parse_mode=ParseMode.HTML,
                        )
                        continue

                    weather = format_weather(
                        get_weather(city, OPENWEATHER_API_KEY),
                        city,
                        for_telegram=True,
                    )
                    try:
                        await bot.send_message(
                            user["chat_id"],
                            weather,
                            parse_mode=ParseMode.HTML,
                        )
                        logger.info(
                            f"Отправлено ежедневное уведомление пользователю {user['chat_id']}"
                        )
                    except Exception as e:
                        logger.error(
                            f"Не удалось отправить уведомление {user['chat_id']}: {e}"
                        )

            last_run_date = current_minute

        except asyncio.CancelledError:
            break
        except Exception as e:
            logger.error(f"Ошибка в фоновой задаче: {e}")
            await asyncio.sleep(60)


async def main():
    """Главная функция запуска бота."""
    init_db()

    bot = Bot(token=TELEGRAM_BOT_TOKEN)
    dp = Dispatcher()

    dp.include_router(router)

    task = asyncio.create_task(daily_notification_task(bot))

    try:
        logger.info("Бот запущен...")
        await dp.start_polling(bot)
    finally:
        task.cancel()
        try:
            await task
        except asyncio.CancelledError:
            pass
        await bot.session.close()


if __name__ == "__main__":
    try:
        asyncio.run(main())
    except KeyboardInterrupt:
        logger.info("Бот остановлен")
