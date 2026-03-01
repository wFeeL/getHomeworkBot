from __future__ import annotations

from datetime import date, datetime, time

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.filters.callback_data import CallbackData
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, InlineKeyboardButton, InlineKeyboardMarkup, Message
from aiogram_calendar import DialogCalendar, DialogCalendarCallback
from aiogram_calendar.schemas import DialogCalAct, highlight

from telegram_bot import text_message
from telegram_bot.config_reader import config
from telegram_bot.database_methods.database_request import get_admins, get_homework, get_subject, update_homework
from telegram_bot.keyboards import inline_markup


class Homework(StatesGroup):
    homework_id = State()
    subject_id = State()
    date = State()
    description = State()
    file_id = State()


class CustomDialogCalendar(DialogCalendar):
    async def start_calendar(self, year: int = datetime.now().year, month: int | None = None) -> InlineKeyboardMarkup:
        today = datetime.now()
        now_year = today.year

        if month:
            return await self._get_days_kb(year, month)

        kb: list[list[InlineKeyboardButton]] = []

        years_row: list[InlineKeyboardButton] = []
        for value in range(year - 2, year + 3):
            if self.min_date.year <= value <= self.max_date.year:
                years_row.append(
                    InlineKeyboardButton(
                        text=str(value) if value != now_year else highlight(str(value)),
                        callback_data=DialogCalendarCallback(act=DialogCalAct.set_y, year=value, month=-1, day=-1).pack(),
                    )
                )
        kb.append(years_row)

        nav_row: list[InlineKeyboardButton] = []
        if self.min_date.year <= year - 2 <= self.max_date.year:
            nav_row.append(
                InlineKeyboardButton(
                    text='<<',
                    callback_data=DialogCalendarCallback(act=DialogCalAct.prev_y, year=year, month=-1, day=-1).pack(),
                )
            )
        nav_row.append(
            InlineKeyboardButton(
                text=self._labels.cancel_caption,
                callback_data=DialogCalendarCallback(act=DialogCalAct.cancel, year=year, month=1, day=1).pack(),
            )
        )
        if self.min_date.year <= year + 3 <= self.max_date.year:
            nav_row.append(
                InlineKeyboardButton(
                    text='>>',
                    callback_data=DialogCalendarCallback(act=DialogCalAct.next_y, year=year, month=1, day=1).pack(),
                )
            )
        kb.append(nav_row)

        return InlineKeyboardMarkup(inline_keyboard=kb)

    async def _get_month_kb(self, year: int) -> InlineKeyboardMarkup:
        today = datetime.now()
        now_month, now_year = today.month, today.year

        kb: list[list[InlineKeyboardButton]] = []
        kb.append([
            InlineKeyboardButton(
                text=self._labels.cancel_caption,
                callback_data=DialogCalendarCallback(act=DialogCalAct.cancel, year=year, month=1, day=1).pack(),
            ),
            InlineKeyboardButton(
                text=str(year) if year != today.year else highlight(str(year)),
                callback_data=DialogCalendarCallback(act=DialogCalAct.start, year=year, month=-1, day=-1).pack(),
            ),
            InlineKeyboardButton(text=" ", callback_data=self.ignore_callback),
        ])

        def highlight_month(month: int) -> str:
            month_str = self._labels.months[month - 1]
            return highlight(month_str) if (now_month == month and now_year == year) else month_str

        def is_available_month(year: int, month: int) -> bool:
            return self.min_date <= datetime(year, month, 1) <= self.max_date

        row1: list[InlineKeyboardButton] = []
        for m in range(1, 7):
            if is_available_month(year, m):
                row1.append(
                    InlineKeyboardButton(
                        text=highlight_month(m),
                        callback_data=DialogCalendarCallback(act=DialogCalAct.set_m, year=year, month=m, day=-1).pack(),
                    )
                )
        row2: list[InlineKeyboardButton] = []
        for m in range(7, 13):
            if is_available_month(year, m):
                row2.append(
                    InlineKeyboardButton(
                        text=highlight_month(m),
                        callback_data=DialogCalendarCallback(act=DialogCalAct.set_m, year=year, month=m, day=-1).pack(),
                    )
                )
        kb.append(row1)
        kb.append(row2)

        return InlineKeyboardMarkup(inline_keyboard=kb)


router = Router()


async def _get_admin_class_id(telegram_id: int) -> int:
    admin_rows = await get_admins(telegram_id=telegram_id)
    return int(admin_rows[0][1]) if admin_rows and admin_rows[0][1] else 0


async def _try_edit_callback_text(callback: CallbackQuery, text: str, reply_markup=None) -> bool:
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest:
        return False


async def update_edit_data(message: Message, state: FSMContext, homework_id: int) -> None:
    class_id = await _get_admin_class_id(message.chat.id)
    if class_id == 0:
        await message.answer(text_message.ADMIN_CLASS_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    homework_rows = await get_homework(id=homework_id, class_id=class_id)
    if not homework_rows:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    homework_data = homework_rows[0]
    subject_id, dt, description, file_id = int(homework_data[1]), homework_data[2], homework_data[3], homework_data[4]
    date_str = dt.strftime("%d.%m.%Y") if not isinstance(dt, str) else dt

    await state.update_data(
        homework_id=int(homework_id),
        subject_id=subject_id,
        date=date_str,
        description=description,
        file_id=file_id,
    )
    await process_edit_homework(message, state, is_edited=False)


async def process_edit_homework(message: Message, state: FSMContext, is_edited: bool = True) -> None:
    try:
        data = await state.get_data()
        homework_id = data["homework_id"]
        subject_id = data["subject_id"]
        date_str = data["date"]
        description = data["description"]
        file_id = data["file_id"]

        subject_rows = await get_subject(id=subject_id)
        subject_name = subject_rows[0][1] if subject_rows else "?"

        homework_text = text_message.EDIT_HOMEWORK.format(subject=subject_name, date=date_str, description=description)

        if file_id != 'None':
            markup = inline_markup.get_edit_homework_keyboard(is_edited=is_edited)
            await message.bot.send_photo(caption=homework_text, reply_markup=markup, photo=file_id, chat_id=message.chat.id)
        else:
            markup = inline_markup.get_edit_homework_keyboard(is_file=False, is_edited=is_edited)
            await message.answer(homework_text, reply_markup=markup)

    except Exception:
        await message.answer(text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.message(Homework.description)
async def process_description(message: Message, state: FSMContext) -> None:
    if message.text is None:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
    else:
        await state.update_data(description=message.text)

    await state.set_state(Homework.subject_id)
    await process_edit_homework(message, state)


@router.message(Homework.file_id)
async def process_file_id(message: Message, state: FSMContext) -> None:
    try:
        if not message.photo:
            raise ValueError
        await state.update_data(file_id=message.photo[-1].file_id)
    except Exception:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
    finally:
        await process_edit_homework(message, state)
        await state.set_state(Homework.subject_id)


@router.callback_query(F.data == 'edit_date')
async def edit_date(callback: CallbackQuery) -> None:
    today = date.today()
    cal = CustomDialogCalendar()
    cal.set_dates_range(
        min_date=datetime.combine(config.min_date, time.min),
        max_date=datetime.combine(config.max_date, time.max),
    )
    calendar_markup = await cal.start_calendar(year=today.year, month=today.month)
    if not await _try_edit_callback_text(callback, text_message.CHOOSE_DATE.format(date=''), calendar_markup):
        await callback.message.answer(
            text=text_message.CHOOSE_DATE.format(date=''),
            reply_markup=calendar_markup,
        )


@router.callback_query(F.data == 'edit_description')
async def edit_description(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _try_edit_callback_text(callback, text_message.CHOOSE_DESCRIPTION):
        await callback.message.answer(text_message.CHOOSE_DESCRIPTION)
    await state.set_state(Homework.description)


@router.callback_query(F.data == 'edit_file')
async def edit_file(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _try_edit_callback_text(callback, text_message.CHOOSE_FILE):
        await callback.message.answer(text_message.CHOOSE_FILE)
    await state.set_state(Homework.file_id)


@router.callback_query(F.data == 'delete_file')
async def delete_file(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.delete()
    await state.update_data(file_id='None')
    await process_edit_homework(callback.message, state)


@router.callback_query(F.data == 'edit_data')
async def edit_data(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        await update_homework(
            homework_id=data["homework_id"],
            subject_id=data["subject_id"],
            date=data["date"],
            description=data["description"],
            file_id=data["file_id"],
        )

        await state.clear()
        if not await _try_edit_callback_text(callback, text_message.EDIT_HOMEWORK_COMPLETE, inline_markup.get_users_keyboard()):
            await callback.message.answer(text_message.EDIT_HOMEWORK_COMPLETE, reply_markup=inline_markup.get_users_keyboard())

    except Exception:
        await callback.message.answer(text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.callback_query(F.data == 'stop_state')
async def stop_state(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _try_edit_callback_text(callback, text_message.CANCEL_ACTION):
        await callback.message.delete()
    await state.clear()


@router.callback_query(DialogCalendarCallback.filter())
async def handle_dialog_calendar(callback: CallbackQuery, callback_data: CallbackData, state: FSMContext) -> None:
    cal = CustomDialogCalendar()
    cal.set_dates_range(
        min_date=datetime.combine(config.min_date, time.min),
        max_date=datetime.combine(config.max_date, time.max),
    )
    selected, picked_date = await cal.process_selection(callback, callback_data)

    if selected:
        await _try_edit_callback_text(callback, text_message.CHOOSE_DATE.format(date=picked_date.strftime("%d.%m.%Y")))
        await state.update_data(date=picked_date.strftime("%d.%m.%Y"))
        await process_edit_homework(callback.message, state)
        await state.set_state(Homework.subject_id)
