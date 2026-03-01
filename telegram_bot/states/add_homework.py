from __future__ import annotations

import asyncio
import calendar
from datetime import datetime, timedelta, time

from aiogram import F, Router
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message, ReplyKeyboardRemove

from aiogram_calendar import SimpleCalendar, SimpleCalendarCallback
from aiogram_calendar.schemas import SimpleCalAct, highlight, superscript

from telegram_bot import text_message
from telegram_bot.config_reader import config
from aiogram.exceptions import TelegramBadRequest, TelegramNetworkError

from telegram_bot.database_methods.database_request import add_homework_value, get_admins, get_subject
from telegram_bot.keyboards import inline_markup, reply_markup


class HomeworkForm(StatesGroup):
    subject = State()
    date = State()
    description = State()
    file_id = State()
    none_state = State()


router = Router()


class CustomSimpleCalendar(SimpleCalendar):
    async def start_calendar(self, year: int = datetime.now().year, month: int = datetime.now().month, day: int = datetime.now().day) -> InlineKeyboardMarkup:
        today = datetime.now()
        now_weekday = self._labels.days_of_week[today.weekday()]
        now_month, now_year, now_day = today.month, today.year, today.day

        def highlight_month() -> str:
            month_str = self._labels.months[month - 1]
            return highlight(month_str) if (now_month == month and now_year == year) else month_str

        def highlight_weekday(weekday: str) -> str:
            return highlight(weekday) if (now_month == month and now_year == year and now_weekday == weekday) else weekday

        def format_day_string(day_num: int) -> str:
            date_to_check = datetime(year, month, day_num)
            if self.min_date and date_to_check < self.min_date:
                return superscript(str(day_num))
            if self.max_date and date_to_check > self.max_date:
                return superscript(str(day_num))
            return str(day_num)

        def highlight_day(day_num: int) -> str:
            day_string = format_day_string(day_num)
            return highlight(day_string) if (now_month == month and now_year == year and now_day == day_num) else day_string

        kb: list[list[InlineKeyboardButton]] = []

        # Year row
        years_row: list[InlineKeyboardButton] = []
        date_to_check = datetime(year, month, 1)
        if self.min_date and datetime(year - 1, 1, 1) >= datetime(self.min_date.year, 1, 1):
            years_row.append(InlineKeyboardButton(
                text="<<",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.prev_y, year=year, month=month, day=1).pack(),
            ))
        years_row.append(InlineKeyboardButton(text=str(year) if year != now_year else highlight(str(year)), callback_data=self.ignore_callback))
        if self.max_date and datetime(year + 1, 1, 1) <= datetime(self.max_date.year, 12, 31):
            years_row.append(InlineKeyboardButton(
                text=">>",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.next_y, year=year, month=month, day=1).pack(),
            ))
        kb.append(years_row)

        # Month row
        month_row: list[InlineKeyboardButton] = []
        if self.min_date and date_to_check - timedelta(days=31) >= self.min_date:
            month_row.append(InlineKeyboardButton(
                text="<",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.prev_m, year=year, month=month, day=1).pack(),
            ))
        month_row.append(InlineKeyboardButton(text=highlight_month(), callback_data=self.ignore_callback))
        if self.max_date and date_to_check + timedelta(days=31) <= self.max_date:
            month_row.append(InlineKeyboardButton(
                text=">",
                callback_data=SimpleCalendarCallback(act=SimpleCalAct.next_m, year=year, month=month, day=1).pack(),
            ))
        kb.append(month_row)

        # Weekdays row
        kb.append([InlineKeyboardButton(text=highlight_weekday(wd), callback_data=self.ignore_callback) for wd in self._labels.days_of_week])

        # Days
        month_calendar = calendar.monthcalendar(year, month)
        for week in month_calendar:
            days_row: list[InlineKeyboardButton] = []
            for day_num in week:
                if day_num == 0:
                    days_row.append(InlineKeyboardButton(text=" ", callback_data=self.ignore_callback))
                    continue
                days_row.append(
                    InlineKeyboardButton(
                        text=highlight_day(day_num),
                        callback_data=SimpleCalendarCallback(act=SimpleCalAct.day, year=year, month=month, day=day_num).pack(),
                    )
                )
            kb.append(days_row)

        # Cancel / today row
        kb.append([
            InlineKeyboardButton(text=self._labels.cancel_caption, callback_data=SimpleCalendarCallback(act=SimpleCalAct.cancel, year=year, month=month, day=day).pack()),
            InlineKeyboardButton(text=" ", callback_data=self.ignore_callback),
            InlineKeyboardButton(text=self._labels.today_caption, callback_data=SimpleCalendarCallback(act=SimpleCalAct.today, year=year, month=month, day=day).pack()),
        ])

        return InlineKeyboardMarkup(inline_keyboard=kb)


async def _get_admin_class_id(telegram_id: int) -> int:
    admin_rows = await get_admins(telegram_id=telegram_id)
    return int(admin_rows[0][1]) if admin_rows and admin_rows[0][1] else 0


async def _try_edit_callback_text(callback: CallbackQuery, text: str, reply_markup=None) -> bool:
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest:
        return False


async def register_homework(message: Message, state: FSMContext) -> None:
    class_id = await _get_admin_class_id(message.chat.id)
    if class_id == 0:
        await state.clear()
        await message.answer(text_message.ADMIN_CLASS_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        return

    # Set the FSM state *before* sending the prompt.
    # If Telegram API temporarily times out/disconnects during `send_message`,
    # the state will still be active and the next user message won't fall into
    # the generic "unknown command" handler.
    await state.set_state(HomeworkForm.subject)

    markup = await reply_markup.get_subjects_keyboard(class_id)

    # Telegram can occasionally time out on the first request; retry a couple times
    # with a shorter timeout so the update doesn't hang for ~60s.
    for attempt in range(3):
        try:
            await message.bot.send_message(
                chat_id=message.chat.id,
                text=text_message.CHOOSE_SUBJECT,
                reply_markup=markup,
                request_timeout=15,
            )
            break
        except TelegramNetworkError:
            if attempt >= 2:
                # Don't crash the update; state is already set.
                return
            await asyncio.sleep(1.5 * (attempt + 1))


@router.message(HomeworkForm.subject)
async def process_subject(message: Message, state: FSMContext) -> None:
    class_id = await _get_admin_class_id(message.chat.id)
    if class_id == 0:
        await message.answer(text_message.ADMIN_CLASS_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    try:
        subjects = await get_subject(value=True, class_ids=class_id)
        if (message.text or "").strip() not in [s[1] for s in subjects]:
            raise ValueError

        await state.update_data(subject=(message.text or "").strip())

        # Remove reply keyboard
        tmp = await message.answer(text='.', reply_markup=ReplyKeyboardRemove())
        await tmp.delete()

        simple_calendar = CustomSimpleCalendar()
        # config min/max are date objects
        simple_calendar.set_dates_range(
            min_date=datetime.combine(config.min_date, time.min),
            max_date=datetime.combine(config.max_date, time.max),
        )
        today = datetime.today()
        await message.answer(
            text=text_message.CHOOSE_DATE.format(date=''),
            reply_markup=await simple_calendar.start_calendar(year=today.year, month=today.month, day=today.day),
        )

    except ValueError:
        await message.answer(text_message.WRONG_SELECTION, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.callback_query(SimpleCalendarCallback.filter())
async def handle_simple_calendar(callback: CallbackQuery, callback_data: CallbackData, state: FSMContext) -> None:
    simple_calendar = CustomSimpleCalendar()
    simple_calendar.set_dates_range(
        min_date=datetime.combine(config.min_date, time.min),
        max_date=datetime.combine(config.max_date, time.max),
    )

    selected, picked_date = await simple_calendar.process_selection(callback, callback_data)
    data = await state.get_data()

    try:
        if selected and data.get('subject'):
            date_str = picked_date.strftime('%d.%m.%Y')
            await state.update_data(date=date_str)
            await callback.message.edit_text(text=text_message.CHOOSE_DATE.format(date=date_str))
            await callback.message.answer(text_message.CHOOSE_DESCRIPTION)
            await state.set_state(HomeworkForm.description)
    except Exception:
        await callback.message.delete()


@router.message(HomeworkForm.description)
async def process_description(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    await state.update_data(description=message.text)
    await message.answer(text_message.CHOOSE_FILE, reply_markup=inline_markup.get_skip_file_keyboard())
    await state.set_state(HomeworkForm.file_id)


@router.message(HomeworkForm.file_id)
async def process_file(message: Message, state: FSMContext) -> None:
    try:
        if not message.photo:
            raise ValueError

        # store file_id directly; no need for get_file()
        await state.update_data(file_id=message.photo[-1].file_id)
        await send_homework(message, state)
        await state.set_state(HomeworkForm.none_state)

    except Exception:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.callback_query(F.data == 'skip_file')
async def skip_sending_file(callback: CallbackQuery, state: FSMContext) -> None:
    await state.update_data(file_id='None')
    await _try_edit_callback_text(callback, text_message.CHOOSE_ACTION)
    await send_homework(callback.message, state)


@router.callback_query(F.data == 'send_data')
async def send_data(callback: CallbackQuery, state: FSMContext) -> None:
    admin_rows = await get_admins(telegram_id=callback.message.chat.id)
    class_id = int(admin_rows[0][1]) if admin_rows and admin_rows[0][1] else 0

    try:
        if class_id == 0:
            raise ValueError

        homework_data = await state.get_data()
        subject = homework_data['subject']
        date_str = homework_data['date']
        description = homework_data['description']
        file_id = homework_data.get('file_id', 'None')

        await add_homework_value(subject, date_str, description, file_id, class_id)

        if not await _try_edit_callback_text(callback, text_message.ADDING_HOMEWORK_COMPLETE, inline_markup.get_admin_menu()):
            await callback.message.answer(text_message.ADDING_HOMEWORK_COMPLETE, reply_markup=inline_markup.get_admin_menu())
        await state.clear()

    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.callback_query(F.data == 'cancel_send_data')
async def cancel_send_data(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not await _try_edit_callback_text(callback, text_message.CANCEL_ACTION, inline_markup.get_admin_menu()):
        await callback.message.answer(text_message.CANCEL_ACTION, reply_markup=inline_markup.get_admin_menu())


async def send_homework(message: Message, state: FSMContext) -> None:
    try:
        homework_data = await state.get_data()
        subject = homework_data['subject']
        date_str = homework_data['date']
        description = homework_data['description']
        file_id = homework_data.get('file_id', 'None')

        await state.set_state(HomeworkForm.none_state)
        homework_text = text_message.DATA_TO_SEND.format(subject=subject, date=date_str, description=description)
        markup = inline_markup.get_send_homework_keyboard()

        if file_id != 'None':
            await message.bot.send_photo(caption=homework_text, reply_markup=markup, photo=file_id, chat_id=message.chat.id)
        else:
            await message.answer(text=homework_text, reply_markup=markup)

    except Exception:
        await message.answer(text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
