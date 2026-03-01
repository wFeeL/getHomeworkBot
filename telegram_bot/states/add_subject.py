from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from telegram_bot import text_message
from telegram_bot.database_methods.database_request import add_subject_value, get_admins
from telegram_bot.keyboards import inline_markup


class SubjectForm(StatesGroup):
    name = State()
    sticker = State()


router = Router()


async def _try_edit_callback_text(callback: CallbackQuery, text: str, reply_markup=None) -> bool:
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest:
        return False


async def register_subject(message: Message, state: FSMContext) -> None:
    await message.answer(text=text_message.CHOOSE_SUBJECT_NAME)
    await state.set_state(SubjectForm.name)


@router.message(SubjectForm.name)
async def process_subject_name(message: Message, state: FSMContext) -> None:
    subject_name = (message.text or "").strip()
    if not subject_name:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    await state.update_data(name=subject_name)
    await message.answer(text=text_message.CHOOSE_SUBJECT_STICKER)
    await state.set_state(SubjectForm.sticker)


@router.message(SubjectForm.sticker)
async def process_subject_sticker(message: Message, state: FSMContext) -> None:
    subject_sticker = (message.text or "").strip()
    if not subject_sticker:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    await state.update_data(sticker=subject_sticker)
    await send_subject(message, state)


async def send_subject(message: Message, state: FSMContext) -> None:
    try:
        subject_data = await state.get_data()
        name = subject_data["name"]
        sticker = subject_data["sticker"]

        subject_text = text_message.SUBJECT_DATA_TO_SEND.format(sticker=sticker, name=name)
        await message.answer(text=subject_text, reply_markup=inline_markup.get_send_subject_keyboard())

    except Exception:
        await message.answer(text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.callback_query(F.data == 'send_subject_data')
async def send_data(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        subject_data = await state.get_data()
        name = subject_data["name"]
        sticker = subject_data["sticker"]

        admin_rows = await get_admins(telegram_id=callback.message.chat.id)
        if not admin_rows:
            raise ValueError("Admin not found")
        class_id = int(admin_rows[0][1] or 0)

        await add_subject_value(name, sticker, class_id)

        if not await _try_edit_callback_text(
            callback,
            text_message.ADDING_SUBJECT_COMPLETE.format(sticker=sticker, name=name),
            inline_markup.get_admin_menu(),
        ):
            await callback.message.answer(
                text_message.ADDING_SUBJECT_COMPLETE.format(sticker=sticker, name=name),
                reply_markup=inline_markup.get_admin_menu(),
            )
        await state.clear()

    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.callback_query(F.data == 'cancel_send_data')
async def cancel_send_data(callback: CallbackQuery, state: FSMContext) -> None:
    await state.clear()
    if not await _try_edit_callback_text(callback, text_message.CANCEL_ACTION, inline_markup.get_admin_menu()):
        await callback.message.answer(text_message.CANCEL_ACTION, reply_markup=inline_markup.get_admin_menu())
