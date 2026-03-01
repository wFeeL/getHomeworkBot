from __future__ import annotations

import asyncio
import datetime
import json
import logging
from typing import Iterable

import aiohttp
import pymorphy3
from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters import Command, StateFilter
from aiogram.fsm.context import FSMContext
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove
from aiogram.types.input_media_photo import InputMediaPhoto
from aiogram_dialog import DialogManager, StartMode, setup_dialogs

from telegram_bot import callback_text, text_message
from telegram_bot.config_reader import config
from telegram_bot.database_methods.database_request import (
    add_user,
    delete_class,
    delete_homework,
    delete_subject,
    get_admin_count,
    get_admins,
    get_class,
    get_homework,
    get_homework_count,
    get_homework_page,
    get_homework_with_subject_by_date,
    get_random_quote,
    get_schedule,
    get_subject,
    get_teachers,
    get_timetable,
    get_user_count,
    get_users,
    get_weekday,
    is_admin_active_in_class,
    update_user_class,
)
from telegram_bot.decorators import check_admin, check_class, check_super_admin
from telegram_bot.keyboards import inline_markup
from telegram_bot.states import (
    add_class,
    add_homework,
    add_subject,
    add_teacher,
    bot_message,
    calendar,
    edit_admins,
    edit_class,
    edit_homework,
    edit_subject,
)

router = Router()

# Include state/dialog routers so FSM handlers are actually registered.
# Without this, commands like /add set the state, but subsequent messages are
# not handled by state routers and fall through to the catch-all handler.
router.include_router(add_homework.router)
router.include_router(edit_homework.router)
router.include_router(add_class.router)
router.include_router(edit_class.router)
router.include_router(add_subject.router)
router.include_router(edit_subject.router)
router.include_router(add_teacher.router)
router.include_router(bot_message.router)
router.include_router(edit_admins.router)

router.include_router(calendar.dialog)
setup_dialogs(router)

logger = logging.getLogger(__name__)
MORPH = pymorphy3.MorphAnalyzer()


def _inflect_accs(word: str) -> str:
    """Inflect a word to accusative case when possible.

    `pymorphy3` may return `None` from `.inflect()` for tokens it cannot inflect
    (e.g. non-Russian words, abbreviations, unknown tokens). This helper prevents
    crashes by falling back to the original token.
    """
    if not word:
        return word

    try:
        parsed = MORPH.parse(word)
        if not parsed:
            return word
        p = parsed[0]
        inflected = p.inflect({"accs"})
        return (inflected.word if inflected else p.word) or word
    except Exception:
        return word

WEEKDAY_KEYS = ["monday", "tuesday", "wednesday", "thursday", "friday", "saturday", "sunday"]


async def _get_user_class_id(telegram_id: int) -> int:
    rows = await get_users(telegram_id=telegram_id)
    return int(rows[0][1]) if rows else 0


async def _get_admin_class_id(telegram_id: int) -> int:
    rows = await get_admins(telegram_id=telegram_id)
    return int(rows[0][1]) if rows and rows[0][1] else 0


async def _is_admin_in_class(telegram_id: int, class_id: int) -> bool:
    return await is_admin_active_in_class(telegram_id=telegram_id, class_id=class_id)


async def _is_super_admin_user(telegram_id: int) -> bool:
    rows = await get_admins(telegram_id=telegram_id)
    return bool(rows and rows[0][3])


async def _is_admin_allowed_for_homework(telegram_id: int, homework_id: int) -> bool:
    rows = await get_homework(id=homework_id)
    if not rows:
        return False
    class_id = int(rows[0][5])
    return await _is_admin_in_class(telegram_id, class_id)


async def _load_chat_map(bot, chat_ids: Iterable[int | str], *, concurrency: int = 8) -> dict[str, object]:
    """Fetch Telegram chats concurrently with a conservative concurrency limit."""
    semaphore = asyncio.Semaphore(concurrency)
    result: dict[str, object] = {}

    async def _load(chat_id: int | str) -> None:
        async with semaphore:
            try:
                chat = await bot.get_chat(chat_id=chat_id)
            except TelegramBadRequest:
                logger.info("Chat id %s can't be found", chat_id)
                return
            except Exception as error:
                logger.info("%s while getting chat for %s", error.__class__.__name__, chat_id)
                return
            result[str(chat_id)] = chat

    await asyncio.gather(*(_load(chat_id) for chat_id in chat_ids))
    return result


async def _try_edit_callback_text(
    callback: CallbackQuery,
    text: str,
    reply_markup=None,
) -> bool:
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as error:
        error_message = error.message.lower()
        if "message is not modified" in error_message:
            return True
        if "there is no text in the message to edit" in error_message:
            try:
                await callback.message.delete()
            except TelegramBadRequest as delete_error:
                logger.info(delete_error.message)
            return False
        logger.info(error.message)
        return False


async def _try_edit_callback_media_photo(
    callback: CallbackQuery,
    photo: str,
    caption: str,
    reply_markup=None,
) -> bool:
    if not callback.message.photo:
        return False

    try:
        media = InputMediaPhoto(media=photo, caption=caption)
        await callback.message.edit_media(media=media, reply_markup=reply_markup)
        return True
    except TelegramBadRequest as error:
        if "message is not modified" in error.message.lower():
            return True
        logger.info(error.message)
        return False


# ----------------------------
# User commands
# ----------------------------


@router.message(Command('start'))
async def send_greetings(message: Message, **kwargs) -> None:
    user_telegram_id = message.chat.id
    user_telegram_name = message.chat.first_name

    await authorize_user(message)
    logger.info("%s used /start", user_telegram_name)

    class_id = await _get_user_class_id(user_telegram_id)
    if class_id == 0:
        markup = inline_markup.get_start_keyboard(is_class=False)
        text = text_message.GREETINGS.format(user=user_telegram_name, class_text=text_message.CLASS_NOT_CHOSEN)
    else:
        class_data = await get_class(id=class_id)
        if class_data:
            letter, number = class_data[0][1], class_data[0][2]
            class_text = text_message.CLASS_CHOSEN.format(number=number, letter=letter)
        else:
            class_text = text_message.CLASS_NOT_CHOSEN
        markup = inline_markup.get_start_keyboard()
        text = text_message.GREETINGS.format(user=user_telegram_name, class_text=class_text)

    await message.answer(text=text, reply_markup=markup)


@router.message(Command('help'))
async def send_help(message: Message, **kwargs) -> None:
    await authorize_user(message)
    logger.info("%s used /help", message.chat.username)

    class_id = await _get_user_class_id(message.chat.id)
    if class_id == 0:
        markup = inline_markup.get_help_keyboard(is_class=False)
        text = text_message.HELP.format(class_text=text_message.CLASS_NOT_CHOSEN)
    else:
        class_data = await get_class(id=class_id)
        if class_data:
            letter, number = class_data[0][1], class_data[0][2]
            class_text = text_message.CLASS_CHOSEN.format(number=number, letter=letter)
        else:
            class_text = text_message.CLASS_NOT_CHOSEN
        markup = inline_markup.get_help_keyboard()
        text = text_message.HELP.format(class_text=class_text)

    await message.answer(text=text, reply_markup=markup)


@router.message(Command('menu'))
@check_class
async def send_menu(message: Message, **kwargs) -> None:
    logger.info("%s used /menu", message.chat.username)
    await message.answer(text=text_message.CHOOSE_CATEGORY, reply_markup=inline_markup.get_homework_menu())


@router.message(Command('tomorrow'))
@check_class
async def send_tomorrow_homework(message: Message, **kwargs) -> None:
    logger.info("%s used /tomorrow", message.chat.username)
    tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)
    await send_date_homework(message, tomorrow_date)


@router.message(Command('homework'))
@check_class
async def send_all_homework(message: Message, **kwargs) -> None:
    logger.info("%s used /homework", message.chat.username)
    class_id = await _get_user_class_id(message.chat.id)
    await message.answer(text=text_message.CHOOSE_SUBJECT, reply_markup=await inline_markup.get_all_homework_keyboard(class_id))


@router.message(Command('calendar'))
@check_class
async def send_calendar_homework(message: Message, dialog_manager: DialogManager, **kwargs) -> None:
    logger.info("%s used /calendar", message.chat.username)
    await dialog_manager.start(state=calendar.CalendarHomework.calendar, mode=StartMode.RESET_STACK)


@router.message(Command('choose_class'))
async def send_choose_class(message: Message, **kwargs) -> None:
    await message.answer(text=text_message.CHOOSE_CLASS, reply_markup=await inline_markup.get_choose_class_keyboard())


@router.message(Command('class'))
@check_class
async def send_class(message: Message, *, edit: bool = False, **kwargs) -> None:
    logger.info("%s used /class", message.chat.username)
    await authorize_user(message)

    class_id = await _get_user_class_id(message.chat.id)
    admin_rows, class_len, admin_class_len, class_data = await asyncio.gather(
        get_admins(telegram_id=message.chat.id),
        get_user_count(class_id=class_id),
        get_admin_count(class_id=class_id),
        get_class(id=class_id),
    )
    is_super_admin = bool(admin_rows and admin_rows[0][3])

    markup = inline_markup.get_class_keyboard(class_id=class_id, is_super_admin=is_super_admin)
    if class_data:
        letter, number = class_data[0][1], class_data[0][2]
    else:
        letter, number = "?", "?"

    text = text_message.CLASS.format(number=number, letter=letter, class_len=class_len, admin_class_len=admin_class_len)
    if edit:
        try:
            await message.edit_text(text=text, reply_markup=markup)
            return
        except TelegramBadRequest as error:
            logger.info(error.message)
    await message.answer(text=text, reply_markup=markup)


@router.message(Command('schedule'))
@check_class
async def send_schedule(message: Message, **kwargs) -> None:
    logger.info("%s used /schedule", message.chat.username)
    class_id = await _get_user_class_id(message.chat.id)
    await message.answer(text=text_message.CHOOSE_WEEKDAY, reply_markup=await inline_markup.get_schedule_keyboard(class_id))


@router.message(Command('timetable'))
async def send_timetable(message: Message, **kwargs) -> None:
    logger.info("%s used /timetable", message.chat.username)
    await authorize_user(message)

    timetable_rows = await get_timetable()
    # timetable rows come from DB as (id, time)
    # previously we displayed the id twice ("1. 1"), now we show the actual time values.
    lines: list[str] = []
    for row in timetable_rows:
        try:
            lesson_num = int(row[0])
            lesson_time = str(row[1])
        except Exception:
            # Fallback if DB driver returns different shape
            lesson_num = len(lines) + 1
            lesson_time = str(row[0]) if row else ""
        lines.append(f"{lesson_num}. <b>{lesson_time}</b>")
    timetable = "\n".join(lines)
    await message.answer(text=text_message.TIMETABLE.format(timetable=timetable))


@router.message(Command('teachers'))
@check_class
async def send_teachers(message: Message, **kwargs) -> None:
    logger.info("%s used /teachers", message.chat.username)
    class_id = await _get_user_class_id(message.chat.id)

    teachers = await get_teachers(class_id)
    teachers_list = '\n'.join([f"{i+1}. <b>{row[1]}</b> - {row[0]}" for i, row in enumerate(teachers)])
    await message.answer(text=text_message.TEACHERS.format(teachers_list=teachers_list))


@router.message(Command('support'))
async def send_support(message: Message, **kwargs) -> None:
    logger.info("%s used /support", message.chat.username)
    await authorize_user(message)
    await message.answer(text=text_message.SUPPORT, disable_web_page_preview=True)


@router.message(Command('donate'))
async def send_donate(message: Message, **kwargs) -> None:
    logger.info("%s used /donate", message.chat.username)
    await authorize_user(message)
    await message.answer(text=text_message.DONATE)


@router.message(Command('site'))
async def send_site(message: Message, **kwargs) -> None:
    logger.info("%s used /site", message.chat.username)
    await authorize_user(message)
    await message.answer(text=text_message.SITE, reply_markup=inline_markup.get_site_keyboard())


@router.message(Command('weather'))
async def send_weather(message: Message, **kwargs) -> None:
    logger.info("%s used /weather", message.chat.username)
    await authorize_user(message)

    url = "https://api.weatherapi.com/v1/current.json"
    params = {
        "key": config.weather_api,
        "q": "Saint Petersburg",
        "aqi": "no",
        "lang": "ru",
    }

    timeout = aiohttp.ClientTimeout(total=10)
    async with aiohttp.ClientSession(timeout=timeout) as session:
        async with session.get(url, params=params) as resp:
            if resp.status != 200:
                await message.answer(text=text_message.TEXT_ERROR)
                return
            payload = await resp.json()

    data = payload.get('current') or {}
    temperature_c = data.get('temp_c')
    humidity = data.get('humidity')
    wind_speed = data.get('wind_kph')
    wind_dir = data.get('wind_dir')

    condition = data.get('condition') or {}
    weather_icon = condition.get('icon')
    weather_code = condition.get('code')

    if not weather_icon:
        await message.answer(text=text_message.TEXT_ERROR)
        return

    if weather_icon.startswith("http://") or weather_icon.startswith("https://"):
        weather_icon_link = weather_icon
    elif weather_icon.startswith("//"):
        weather_icon_link = f"https:{weather_icon}"
    else:
        weather_icon_link = "https://cdn.weatherapi.com/weather/128x128/" + '/'.join(weather_icon.split('/')[-2:])

    text_weather = text_message.TEXT_WEATHER.format(
        temperature=temperature_c,
        wind_speed=wind_speed,
        humidity=humidity,
        wind_dir=wind_dir,
    )

    if weather_code == 1000:
        text_weather += text_message.CLEAR_SKY_WEATHER
    elif weather_code in [1009, 1030, 1063]:
        text_weather += text_message.OVERCAST_CLOUDS_WEATHER
    elif weather_code in [1072, 1135, 1147, 1150, 1153, 1180, 1183, 1198, 1201, 1261]:
        text_weather += text_message.RAIN_WEATHER
    elif weather_code in [1003, 1006]:
        text_weather += text_message.FEW_CLOUDS_WEATHER
    elif weather_code in [1087, 1186, 1189, 1192, 1195, 1227, 1240, 1243, 1246, 1264, 1273, 1276]:
        text_weather += text_message.SHOWER_RAIN_WEATHER
    elif weather_code in [
        1066, 1069, 1114, 1117, 1168, 1171, 1204, 1207, 1210, 1213, 1216, 1219, 1222, 1225,
        1249, 1252, 1255, 1258, 1279, 1282,
    ]:
        text_weather += text_message.SNOW_WEATHER
    else:
        text_weather += text_message.WEATHER

    await message.bot.send_photo(photo=weather_icon_link, caption=text_weather, chat_id=message.chat.id)


# ----------------------------
# Admin commands
# ----------------------------


@router.message(Command('admin'))
@check_admin
async def send_admin_menu(message: Message, **kwargs) -> None:
    try:
        class_id = await _get_admin_class_id(message.chat.id)
        class_data = await get_class(id=class_id)
        if not class_data:
            raise IndexError
        letter, number = class_data[0][1], class_data[0][2]

        await message.answer(
            text=text_message.ADMIN_GREETINGS.format(
                class_text=text_message.CLASS_CHOSEN.format(number=number, letter=letter)
            ),
            reply_markup=ReplyKeyboardRemove(),
        )
    except IndexError:
        await message.answer(text=text_message.ADMIN_CLASS_ERROR)


@router.message(Command('add'))
@check_admin
async def send_adding_states(message: Message, state: FSMContext, **kwargs) -> None:
    await add_homework.register_homework(message, state)


@router.message(Command('edit'))
@check_admin
async def send_edit_menu(message: Message, **kwargs) -> None:
    class_id = await _get_admin_class_id(message.chat.id)
    await message.answer(text=text_message.CHOOSE_SUBJECT, reply_markup=await inline_markup.get_all_homework_keyboard(class_id))


@router.message(Command('admins'))
@check_super_admin
async def send_admins_menu(message: Message, **kwargs) -> None:
    admins_rows, class_rows = await asyncio.gather(get_admins(value=True), get_class(value=True))
    admin_ids = [str(row[0]) for row in admins_rows]
    admin_class_map = {str(row[0]): int(row[1] or 0) for row in admins_rows}
    class_map = {int(row[0]): (row[1], row[2]) for row in class_rows}
    chat_map = await _load_chat_map(message.bot, admin_ids, concurrency=6)

    admins_without_class = []
    text = text_message.ADMINS_LIST
    count = 1

    for admin_id in admin_ids:
        admin_chat = chat_map.get(admin_id)
        if admin_chat is None:
            continue
        if admin_chat.username is None:
            continue

        class_id = admin_class_map.get(admin_id, 0)
        class_data = class_map.get(class_id)
        if class_data is None:
            admins_without_class.append(admin_chat)
            continue

        letter, number = class_data
        text += text_message.ADMIN_FORM.format(
            index=count,
            name=admin_chat.first_name,
            username=admin_chat.username,
            telegram_id=admin_chat.id,
            letter=letter,
            number=number,
        )
        count += 1

    if admins_without_class:
        await message.answer(
            text=text_message.ADMINS_WITHOUT_CLASS_ERROR.format(
                admins_list='\n'.join([f"@{a.username} ({a.id})" for a in admins_without_class if a.username])
            )
        )

    await message.answer(text=text, reply_markup=inline_markup.get_admins_keyboard())


@router.message(Command('users'))
@check_admin
async def send_users_list(message: Message, **kwargs) -> None:
    users_rows, admins_rows = await asyncio.gather(get_users(), get_admins(value=True))
    user_ids = [str(row[0]) for row in users_rows]
    admin_id_set = {str(row[0]) for row in admins_rows}
    chat_map = await _load_chat_map(message.bot, user_ids, concurrency=8)

    text = text_message.USERS_LIST
    count = 0

    for user_id in user_ids:
        user_chat = chat_map.get(user_id)
        if user_chat is None:
            continue

        if user_chat.username is None:
            continue

        count += 1
        is_admin = str(user_id) in admin_id_set
        admin_text = text_message.ADMIN_TEXT if is_admin else ''
        text += text_message.USER_FORM.format(
            index=count,
            is_admin=admin_text,
            name=user_chat.first_name,
            username=user_chat.username,
            telegram_id=user_chat.id,
        )

    text += text_message.LEN_USERS.format(len_users_list=count)
    await message.answer(text=text, reply_markup=inline_markup.get_users_keyboard())


@router.message(Command('bot_message'))
@check_admin
async def send_bot_message(message: Message, state: FSMContext, **kwargs) -> None:
    await bot_message.register_message(message, state)


@router.message(Command('add_class'))
@check_super_admin
async def send_add_class(message: Message, state: FSMContext, **kwargs) -> None:
    await add_class.register_class(message, state)


@router.message(Command('subject'))
@check_super_admin
async def send_subject(message: Message, **kwargs) -> None:
    class_id = await _get_admin_class_id(message.chat.id)
    await message.answer(text=text_message.CHOOSE_SUBJECT, reply_markup=await inline_markup.get_all_subject(class_id=class_id))


@router.message(Command('add_subject'))
@check_super_admin
async def send_add_subject(message: Message, state: FSMContext, **kwargs) -> None:
    subjects_limit = 40
    class_id = await _get_admin_class_id(message.chat.id)
    subjects_len = len(await get_subject(value=True, class_ids=class_id))
    if subjects_len >= subjects_limit:
        await message.answer(text=text_message.SUBJECT_LIMIT_ERROR)
        return

    await add_subject.register_subject(message, state)


@router.message(Command('add_teacher'))
@check_super_admin
async def send_add_teacher(message: Message, state: FSMContext, **kwargs) -> None:
    await add_teacher.register_teacher(message, state)


# ----------------------------
# Callbacks
# ----------------------------


@router.callback_query(lambda call: call.data in list(callback_text.CALLBACK.values()))
async def handle_callback(callback: CallbackQuery, **kwargs) -> None:
    callback_data = callback.data or ""
    class_id: int | None = None

    async def ensure_class_id() -> int:
        nonlocal class_id
        if class_id is None:
            class_id = await _get_user_class_id(callback.message.chat.id)
        return class_id

    if callback_data == callback_text.CALLBACK['send_choose_class']:
        markup = await inline_markup.get_choose_class_keyboard()
        if not await _try_edit_callback_text(callback, text_message.CHOOSE_CLASS, markup):
            await callback.message.answer(text=text_message.CHOOSE_CLASS, reply_markup=markup)
        return

    if callback_data == callback_text.CALLBACK['send_menu']:
        current_class_id = await ensure_class_id()
        if current_class_id == 0:
            markup = await inline_markup.get_choose_class_keyboard()
            if not await _try_edit_callback_text(callback, text_message.CHOOSE_CLASS, markup):
                await callback.message.answer(text=text_message.CHOOSE_CLASS, reply_markup=markup)
            return
        if not await _try_edit_callback_text(callback, text_message.CHOOSE_CATEGORY, inline_markup.get_homework_menu()):
            await callback.message.answer(text=text_message.CHOOSE_CATEGORY, reply_markup=inline_markup.get_homework_menu())
        return

    if callback_data == callback_text.CALLBACK['send_help']:
        current_class_id = await ensure_class_id()
        if current_class_id == 0:
            markup = inline_markup.get_help_keyboard(is_class=False)
            text = text_message.HELP.format(class_text=text_message.CLASS_NOT_CHOSEN)
        else:
            class_data_rows = await get_class(id=current_class_id)
            if class_data_rows:
                letter, number = class_data_rows[0][1], class_data_rows[0][2]
                class_text = text_message.CLASS_CHOSEN.format(number=number, letter=letter)
            else:
                class_text = text_message.CLASS_NOT_CHOSEN
            markup = inline_markup.get_help_keyboard()
            text = text_message.HELP.format(class_text=class_text)

        if not await _try_edit_callback_text(callback, text, markup):
            await callback.message.answer(text=text, reply_markup=markup)
        return

    if callback_data == callback_text.CALLBACK['send_all_homework']:
        current_class_id = await ensure_class_id()
        if current_class_id == 0:
            markup = await inline_markup.get_choose_class_keyboard()
            if not await _try_edit_callback_text(callback, text_message.CHOOSE_CLASS, markup):
                await callback.message.answer(text=text_message.CHOOSE_CLASS, reply_markup=markup)
            return
        markup = await inline_markup.get_all_homework_keyboard(current_class_id)
        if not await _try_edit_callback_text(callback, text_message.CHOOSE_SUBJECT, markup):
            await callback.message.answer(text=text_message.CHOOSE_SUBJECT, reply_markup=markup)
        return

    if callback_data == callback_text.CALLBACK['send_tomorrow_homework']:
        current_class_id = await ensure_class_id()
        if current_class_id == 0:
            markup = await inline_markup.get_choose_class_keyboard()
            if not await _try_edit_callback_text(callback, text_message.CHOOSE_CLASS, markup):
                await callback.message.answer(text=text_message.CHOOSE_CLASS, reply_markup=markup)
            return
        tomorrow_date = datetime.date.today() + datetime.timedelta(days=1)
        await send_date_homework(callback, tomorrow_date)
        return

    if callback_data == callback_text.CALLBACK['send_schedule']:
        current_class_id = await ensure_class_id()
        if current_class_id == 0:
            markup = await inline_markup.get_choose_class_keyboard()
            if not await _try_edit_callback_text(callback, text_message.CHOOSE_CLASS, markup):
                await callback.message.answer(text=text_message.CHOOSE_CLASS, reply_markup=markup)
            return
        markup = await inline_markup.get_schedule_keyboard(current_class_id)
        if not await _try_edit_callback_text(callback, text_message.CHOOSE_WEEKDAY, markup):
            await callback.message.answer(text=text_message.CHOOSE_WEEKDAY, reply_markup=markup)
        return

    if callback_data == callback_text.CALLBACK['send_class']:
        current_class_id = await ensure_class_id()
        if current_class_id == 0:
            markup = await inline_markup.get_choose_class_keyboard()
            if not await _try_edit_callback_text(callback, text_message.CHOOSE_CLASS, markup):
                await callback.message.answer(text=text_message.CHOOSE_CLASS, reply_markup=markup)
            return
        await send_class(callback.message, edit=True, **kwargs)
        return

    # Fallback for callbacks that still require command-style flows.
    await callback_text.call_function_from_callback(callback, **kwargs)


@router.callback_query(lambda call: 'date' in (call.data or '') and 'True' not in (call.data or ''))
async def handle_date_homework(callback: CallbackQuery) -> None:
    callback_data = json.loads(callback.data)
    date_str = callback_data['date']

    try:
        first_message = int(callback_data['first_msg'])
        last_message = int(callback_data['last_msg'])
        message_ids = list(range(first_message, last_message))
        await callback.message.bot.delete_messages(chat_id=callback.message.chat.id, message_ids=message_ids)
    except KeyError:
        pass
    except TelegramBadRequest as error:
        logger.info(error.message)

    dt = datetime.datetime.strptime(date_str, '%Y-%m-%d').date()
    await send_date_homework(callback, dt)


@router.callback_query(lambda call: 'page' in (call.data or '') and 'len' in (call.data or ''))
async def handle_homework_pagination(callback: CallbackQuery) -> None:
    try:
        callback_data = json.loads(callback.data)
        page = int(callback_data['page'])
        subject_id = int(callback_data['subject_id'])

        class_id = await _get_user_class_id(callback.message.chat.id)

        subject_rows = await get_subject(id=subject_id, class_ids=class_id)
        if not subject_rows:
            raise IndexError
        subject_name = subject_rows[0][1]
        subject_sticker = subject_rows[0][2]

        length = await get_homework_count(subject_id=subject_id, class_id=class_id)
        if length == 0:
            if not await _try_edit_callback_text(
                callback,
                text_message.SUBJECT_HOMEWORK_IS_NULL.format(subject_sticker=subject_sticker, subject_name=subject_name),
                inline_markup.get_back_to_subjects_keyboard(),
            ):
                await callback.message.answer(
                    text=text_message.SUBJECT_HOMEWORK_IS_NULL.format(subject_sticker=subject_sticker, subject_name=subject_name),
                    reply_markup=inline_markup.get_back_to_subjects_keyboard(),
                )
            return

        page = min(max(page, 1), length)
        current_row = await get_homework_page(subject_id=subject_id, class_id=class_id, page=page)
        if current_row is None:
            raise IndexError

        homework_id = int(current_row[0])
        date_val, description, file_id = current_row[2], current_row[3], current_row[4]
        date_text = date_val.strftime("%d.%m.%Y") if hasattr(date_val, "strftime") else str(date_val)

        is_admin = await _is_admin_in_class(callback.message.chat.id, class_id)
        text = text_message.HOMEWORK_PAGINATION_TEXT.format(
            subject_sticker=subject_sticker,
            subject_name=subject_name,
            date=date_text,
            description=description,
        )

        markup = await inline_markup.get_homework_pagination(
            length=length,
            page=page,
            subject_id=subject_id,
            is_admin=is_admin,
            class_id=class_id,
            homework_id=homework_id,
        )

        if file_id != 'None':
            if not await _try_edit_callback_media_photo(callback, str(file_id), text, markup):
                try:
                    await callback.message.delete()
                except TelegramBadRequest as error:
                    logger.info(error.message)
                await callback.message.bot.send_photo(
                    caption=text,
                    reply_markup=markup,
                    photo=file_id,
                    chat_id=callback.message.chat.id,
                )
        else:
            if not await _try_edit_callback_text(callback, text, markup):
                if callback.message.photo:
                    try:
                        await callback.message.delete()
                    except TelegramBadRequest as error:
                        logger.info(error.message)
                await callback.message.answer(text=text, reply_markup=markup)

    except Exception:
        await callback.message.answer(text_message.TEXT_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())


@router.callback_query(lambda call: 'weekday_index' in (call.data or ''))
async def handle_schedule(callback: CallbackQuery) -> None:
    callback_data = json.loads(callback.data)
    weekday_index = int(callback_data['weekday_index'])
    is_homework = str(callback_data.get('is_homework', '')).lower() in {"1", "true", "yes"}

    class_id = await _get_user_class_id(callback.message.chat.id)
    class_weekdays = await get_weekday(class_ids=class_id)
    if not class_weekdays:
        await callback.message.answer(text_message.TEXT_ERROR)
        return

    max_weekday_index = len(class_weekdays)
    if weekday_index == max_weekday_index:
        weekday_index = 0
    elif weekday_index == -1:
        weekday_index = max_weekday_index - 1

    weekday_key = class_weekdays[weekday_index][1]
    weekday_name_rus = text_message.SCHEDULE_DICTIONARY_RUS.get(weekday_key, weekday_key)
    weekday_name_rus_accs = _inflect_accs(weekday_name_rus)

    schedule_rows = await get_schedule(weekday_key, class_id)
    schedule_data: list[str] = []
    for idx, row in enumerate(schedule_rows):
        subject_name = row[0] if row and row[0] is not None else 'Нет урока'
        schedule_data.append(f"{idx + 1}. {subject_name}")
    schedule_text = '\n'.join(schedule_data)

    if not is_homework:
        text = text_message.SCHEDULE_TEXT.format(weekday_name=weekday_name_rus_accs, schedule=schedule_text)
        markup = inline_markup.get_weekday_keyboard(weekday_index)
        if not await _try_edit_callback_text(callback, text, markup):
            await callback.message.answer(text=text, reply_markup=markup)
    else:
        await callback.message.answer(
            text=text_message.SCHEDULE_TEXT.format(weekday_name=weekday_name_rus_accs, schedule=schedule_text),
            reply_markup=inline_markup.get_delete_message_keyboard(),
        )


@router.callback_query(
    lambda call: 'class_id' in (call.data or '') and ('edit' not in (call.data or '') and 'delete' not in (call.data or ''))
)
async def handle_class(callback: CallbackQuery, **kwargs) -> None:
    callback_data = json.loads(callback.data)
    class_id = int(callback_data['class_id'])

    await update_user_class(telegram_id=callback.message.chat.id, class_id=class_id)
    await send_class(callback.message, edit=True, **kwargs)


@router.callback_query(lambda call: 'class_id' in (call.data or '') and 'edit' in (call.data or ''))
async def handle_edit_class(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _is_super_admin_user(callback.message.chat.id):
        await callback.message.answer(
            text_message.INCORRECT_REQUEST,
            reply_markup=inline_markup.get_delete_message_keyboard(),
        )
        return

    try:
        callback_data = json.loads(callback.data)
        class_id = int(callback_data['class_id'])

        await state.clear()
        await _try_edit_callback_text(callback, text_message.CHOOSE_ACTION)
        await edit_class.update_edit_data(callback.message, state, class_id)
    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())


@router.callback_query(lambda call: 'class_id' in (call.data or '') and 'delete' in (call.data or ''))
async def handle_delete_class(callback: CallbackQuery) -> None:
    if not await _is_super_admin_user(callback.message.chat.id):
        await callback.message.answer(
            text_message.INCORRECT_REQUEST,
            reply_markup=inline_markup.get_delete_message_keyboard(),
        )
        return

    try:
        callback_data = json.loads(callback.data)
        await delete_class(int(callback_data['class_id']))
        if not await _try_edit_callback_text(callback, text_message.DELETE_CLASS):
            await callback.message.answer(text_message.DELETE_CLASS)
    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())


@router.callback_query(lambda call: 'admin' in (call.data or ''))
async def handle_edit_admins(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _is_super_admin_user(callback.message.chat.id):
        await callback.message.answer(
            text_message.INCORRECT_REQUEST,
            reply_markup=inline_markup.get_delete_message_keyboard(),
        )
        return
    is_active = callback.data == 'add_admin'
    await edit_admins.edit_admins(callback.message, state, is_active)


@router.callback_query(lambda call: 'homework_id' in (call.data or '') and 'edit' in (call.data or ''))
async def handle_edit_data(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        callback_data = json.loads(callback.data)
        homework_id = int(callback_data['homework_id'])
        if not await _is_admin_allowed_for_homework(callback.message.chat.id, homework_id):
            raise PermissionError

        await state.clear()
        await _try_edit_callback_text(callback, text_message.CHOOSE_ACTION)
        await edit_homework.update_edit_data(callback.message, state, homework_id)

    except TelegramBadRequest as error:
        logger.info(error.message)
    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())


@router.callback_query(lambda call: 'homework_id' in (call.data or '') and 'delete' in (call.data or ''))
async def handle_delete_homework_data(callback: CallbackQuery) -> None:
    try:
        callback_data = json.loads(callback.data)
        homework_id = int(callback_data['homework_id'])
        if not await _is_admin_allowed_for_homework(callback.message.chat.id, homework_id):
            raise PermissionError
        await delete_homework(homework_id)
        if not await _try_edit_callback_text(callback, text_message.DELETE_HOMEWORK):
            await callback.message.answer(text_message.DELETE_HOMEWORK)

    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())


@router.callback_query(
    lambda call: 'subject_id' in (call.data or '') and ('edit' not in (call.data or '') and 'delete' not in (call.data or ''))
)
async def handle_select_subject(callback: CallbackQuery) -> None:
    try:
        if not await _is_super_admin_user(callback.message.chat.id):
            raise PermissionError

        callback_data = json.loads(callback.data)
        subject_id = int(callback_data['subject_id'])
        admin_class_id = await _get_admin_class_id(callback.message.chat.id)
        if admin_class_id == 0:
            raise PermissionError

        subject_rows = await get_subject(id=subject_id, class_ids=admin_class_id)
        if not subject_rows:
            raise IndexError
        subject_name, subject_sticker = subject_rows[0][1], subject_rows[0][2]

        if not await _try_edit_callback_text(
            callback,
            text=text_message.EDIT_SUBJECT.format(sticker=subject_sticker, name=subject_name),
            reply_markup=inline_markup.get_subject_keyboard(subject_id=subject_id),
        ):
            await callback.message.answer(
                text=text_message.EDIT_SUBJECT.format(sticker=subject_sticker, name=subject_name),
                reply_markup=inline_markup.get_subject_keyboard(subject_id=subject_id),
            )

    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())


@router.callback_query(lambda call: 'subject_id' in (call.data or '') and 'edit' in (call.data or ''))
async def handle_edit_subject(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        if not await _is_super_admin_user(callback.message.chat.id):
            raise PermissionError

        callback_data = json.loads(callback.data)
        subject_id = int(callback_data['subject_id'])
        admin_class_id = await _get_admin_class_id(callback.message.chat.id)
        if admin_class_id == 0:
            raise PermissionError
        subject_rows = await get_subject(id=subject_id, class_ids=admin_class_id)
        if not subject_rows:
            raise PermissionError

        await state.clear()
        await _try_edit_callback_text(callback, text_message.CHOOSE_ACTION)
        await edit_subject.update_edit_data(callback.message, state, subject_id)

    except TelegramBadRequest as error:
        logger.info(error.message)
    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())


@router.callback_query(lambda call: 'subject_id' in (call.data or '') and 'delete' in (call.data or ''))
async def handle_delete_subject_data(callback: CallbackQuery) -> None:
    try:
        if not await _is_super_admin_user(callback.message.chat.id):
            raise PermissionError

        callback_data = json.loads(callback.data)
        subject_id = int(callback_data['subject_id'])
        admin_class_id = await _get_admin_class_id(callback.message.chat.id)
        if admin_class_id == 0:
            raise PermissionError
        subject_rows = await get_subject(id=subject_id, class_ids=admin_class_id)
        if not subject_rows:
            raise PermissionError

        await delete_subject(subject_id, class_id=admin_class_id)
        if not await _try_edit_callback_text(callback, text_message.DELETE_SUBJECT):
            await callback.message.answer(text_message.DELETE_SUBJECT)

    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())


@router.callback_query(F.data == 'delete_message')
async def delete_message(callback: CallbackQuery) -> None:
    try:
        await callback.message.delete()
    except TelegramBadRequest as error:
        logger.info(error.message)


@router.callback_query(F.data == 'stop_state')
async def stop_state(callback: CallbackQuery, state: FSMContext) -> None:
    """Stop any active FSM state and hide the current message."""
    try:
        await callback.message.delete()
    except TelegramBadRequest as error:
        logger.info(error.message)
    await state.clear()


@router.message(StateFilter(None))
async def handle_text(message: Message, **kwargs) -> None:
    await message.answer(text=text_message.RANDOM_TEXT_FROM_USER, reply_markup=inline_markup.get_random_text_keyboard())


# ----------------------------
# Utility
# ----------------------------


async def send_date_homework(message: Message | CallbackQuery, date_value: datetime.date | datetime.datetime, **kwargs) -> None:
    if isinstance(message, CallbackQuery):
        msg = message.message
        callback = message
    else:
        msg = message
        callback = None

    # normalize to date
    if isinstance(date_value, datetime.datetime):
        target_date = date_value.date()
    else:
        target_date = date_value

    class_id = await _get_user_class_id(msg.chat.id)
    homework_data = await get_homework_with_subject_by_date(class_id=class_id, date=target_date)

    weekday_key = WEEKDAY_KEYS[target_date.weekday()] if target_date.weekday() < len(WEEKDAY_KEYS) else ""
    weekday_ru = text_message.SCHEDULE_DICTIONARY_RUS.get(weekday_key, weekday_key)
    weekday_name = _inflect_accs(weekday_ru) if weekday_ru else weekday_key
    date_text = target_date.strftime("%d.%m.%Y")

    class_weekday_keys = [row[1] for row in await get_weekday(class_ids=class_id)]
    weekday_index = class_weekday_keys.index(weekday_key) if weekday_key in class_weekday_keys else None

    markup = inline_markup.get_calendar_keyboard(target_date, weekday_index=weekday_index, media_group=None)

    if homework_data:
        homework_text = text_message.HOMEWORK_TO_SELECTED_DATE.format(f"{weekday_name} {date_text}")

        for i, hw in enumerate(homework_data, start=1):
            subject_name, subject_sticker = str(hw[6]), str(hw[7])

            homework_text += text_message.HOMEWORK_TEXT.format(
                sequence_number=i,
                subject_sticker=subject_sticker,
                subject_name=subject_name,
                subject_description=str(hw[3]),
            )

        photos = [row[4] for row in homework_data if row[4] != 'None']

        if len(photos) == 1:
            if callback is not None and await _try_edit_callback_media_photo(callback, str(photos[0]), homework_text, markup):
                return

            if callback is not None:
                try:
                    await callback.message.delete()
                except TelegramBadRequest as error:
                    logger.info(error.message)
            await msg.bot.send_photo(chat_id=msg.chat.id, photo=photos[0], caption=homework_text, reply_markup=markup)

        elif len(photos) > 1:
            if callback is not None:
                try:
                    await callback.message.delete()
                except TelegramBadRequest as error:
                    logger.info(error.message)
            media_group = [InputMediaPhoto(media=photos[0], caption=homework_text)] + [
                InputMediaPhoto(media=p) for p in photos[1:]
            ]
            sent = await msg.bot.send_media_group(chat_id=msg.chat.id, media=media_group)
            media_group_id = sent[0].message_id
            media_group_len = len(sent)

            markup = inline_markup.get_calendar_keyboard(
                target_date,
                weekday_index=weekday_index,
                media_group=(media_group_id, media_group_len),
            )
            await msg.answer(text=text_message.CHOOSE_ACTION, reply_markup=markup)

        else:
            if callback is not None:
                if not await _try_edit_callback_text(callback, homework_text, markup):
                    if callback.message.photo:
                        try:
                            await callback.message.delete()
                        except TelegramBadRequest as error:
                            logger.info(error.message)
                    await msg.answer(text=homework_text, reply_markup=markup)
            else:
                await msg.answer(text=homework_text, reply_markup=markup)

    else:
        quote_data = await get_random_quote()
        if quote_data is None:
            quote, author = "", ""
        else:
            quote, author = quote_data
        text = text_message.HOMEWORK_IS_NULL.format(date=f"{weekday_name} {date_text}", quote=quote, author=author)
        if callback is not None:
            if not await _try_edit_callback_text(callback, text, markup):
                if callback.message.photo:
                    try:
                        await callback.message.delete()
                    except TelegramBadRequest as error:
                        logger.info(error.message)
                await msg.answer(text=text, reply_markup=markup)
        else:
            await msg.answer(text=text, reply_markup=markup)


async def authorize_user(message: Message) -> None:
    user_telegram_id = message.chat.id
    try:
        users = await get_users(telegram_id=user_telegram_id)
        if not users:
            await add_user(telegram_id=user_telegram_id)
    except Exception as e:
        logger.info("DB error in authorize_user: %s", e)
