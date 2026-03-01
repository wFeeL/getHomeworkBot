from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from telegram_bot import text_message
from telegram_bot.database_methods.database_request import get_subject, update_subject
from telegram_bot.keyboards import inline_markup


class EditSubjectForm(StatesGroup):
    subject_id = State()
    name = State()
    sticker = State()


router = Router()


async def _try_edit_callback_text(callback: CallbackQuery, text: str, reply_markup=None) -> bool:
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest:
        return False


async def update_edit_data(message: Message, state: FSMContext, subject_id: int | str) -> None:
    subject_rows = await get_subject(id=subject_id)
    if not subject_rows:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    subject_data = subject_rows[0]
    await state.update_data(subject_id=int(subject_id), name=subject_data[1], sticker=subject_data[2])
    await process_edit_subject(message, state, is_edited=False)


async def process_edit_subject(message: Message, state: FSMContext, is_edited: bool = True) -> None:
    try:
        data = await state.get_data()
        subject_id = data["subject_id"]
        name = data["name"]
        sticker = data["sticker"]

        subject_text = text_message.EDIT_SUBJECT.format(sticker=sticker, name=name)
        await message.answer(
            text=subject_text,
            reply_markup=inline_markup.get_edit_subject_keyboard(subject_id=subject_id, is_edited=is_edited),
        )

    except Exception:
        await message.answer(text=text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.message(EditSubjectForm.name)
async def process_name(message: Message, state: FSMContext) -> None:
    try:
        subject_name = (message.text or "").strip()
        if not subject_name or len(subject_name) > 20:
            raise ValueError
        await state.update_data(name=subject_name)
    except Exception:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
    finally:
        await state.set_state(EditSubjectForm.subject_id)
        await process_edit_subject(message, state)


@router.message(EditSubjectForm.sticker)
async def process_sticker(message: Message, state: FSMContext) -> None:
    try:
        subject_sticker = (message.text or "").strip()
        if not subject_sticker or len(subject_sticker) > 3:
            raise ValueError
        await state.update_data(sticker=subject_sticker)
    except Exception:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
    finally:
        await state.set_state(EditSubjectForm.subject_id)
        await process_edit_subject(message, state)


@router.callback_query(F.data == 'edit_name')
async def edit_name(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _try_edit_callback_text(callback, text_message.CHOOSE_SUBJECT_NAME):
        await callback.message.answer(text_message.CHOOSE_SUBJECT_NAME)
    await state.set_state(EditSubjectForm.name)


@router.callback_query(F.data == 'edit_sticker')
async def edit_sticker(callback: CallbackQuery, state: FSMContext) -> None:
    if not await _try_edit_callback_text(callback, text_message.CHOOSE_SUBJECT_STICKER):
        await callback.message.answer(text_message.CHOOSE_SUBJECT_STICKER)
    await state.set_state(EditSubjectForm.sticker)


@router.callback_query(F.data == 'edit_subject_data')
async def edit_subject_data(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        await update_subject(subject_id=data["subject_id"], name=data["name"], sticker=data["sticker"])

        await state.clear()
        if not await _try_edit_callback_text(callback, text_message.EDIT_SUBJECT_COMPLETE):
            await callback.message.answer(text_message.EDIT_SUBJECT_COMPLETE)

    except Exception:
        await callback.message.answer(text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
