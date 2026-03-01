from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from telegram_bot import text_message
from telegram_bot.database_methods.database_request import get_class, update_class
from telegram_bot.keyboards import inline_markup, reply_markup


class EditClassForm(StatesGroup):
    class_id = State()
    number = State()
    letter = State()


router = Router()


async def _try_edit_callback_text(callback: CallbackQuery, text: str, reply_markup=None) -> bool:
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest:
        return False


async def update_edit_data(message: Message, state: FSMContext, class_id: int | str) -> None:
    class_rows = await get_class(id=class_id)
    if not class_rows:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    class_data = class_rows[0]
    await state.update_data(class_id=int(class_id), letter=class_data[1], number=class_data[2])
    await process_edit_class(message, state, is_edited=False)


async def process_edit_class(message: Message, state: FSMContext, is_edited: bool = True) -> None:
    try:
        data = await state.get_data()
        class_id = data["class_id"]
        number = data["number"]
        letter = data["letter"]

        class_text = text_message.EDIT_CLASS.format(number=number, letter=letter)
        await message.answer(
            text=class_text,
            reply_markup=inline_markup.get_edit_class_keyboard(class_id=class_id, is_edited=is_edited),
        )

    except Exception:
        await message.answer(text=text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.message(EditClassForm.number)
async def process_number(message: Message, state: FSMContext) -> None:
    try:
        class_number = (message.text or "").strip()
        if int(class_number) not in range(1, 12):
            raise ValueError
        await state.update_data(number=int(class_number))
    except Exception:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
    finally:
        await process_edit_class(message, state)
        await state.set_state(EditClassForm.class_id)


@router.message(EditClassForm.letter)
async def process_letter(message: Message, state: FSMContext) -> None:
    try:
        letter = (message.text or "").strip()
        if not letter or len(letter) > 2:
            raise ValueError
        await state.update_data(letter=letter)
    except Exception:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
    finally:
        await state.set_state(EditClassForm.class_id)
        await process_edit_class(message, state)


@router.callback_query(F.data == 'edit_number')
async def edit_number(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.delete()
    await callback.message.answer(text_message.CHOOSE_CLASS_NUMBER, reply_markup=reply_markup.get_choose_class_keyboard())
    await state.set_state(EditClassForm.number)


@router.callback_query(F.data == 'edit_letter')
async def edit_letter(callback: CallbackQuery, state: FSMContext) -> None:
    await callback.message.delete()
    await callback.message.answer(text_message.CHOOSE_CLASS_LETTER, reply_markup=ReplyKeyboardRemove())
    await state.set_state(EditClassForm.letter)


@router.callback_query(F.data == 'edit_class_data')
async def edit_class_data(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        data = await state.get_data()
        class_id = data["class_id"]
        number = data["number"]
        letter = data["letter"]

        await update_class(class_id, number, letter)

        await state.clear()
        if not await _try_edit_callback_text(callback, text_message.EDIT_CLASS_COMPLETE, inline_markup.get_users_keyboard()):
            await callback.message.answer(text_message.EDIT_CLASS_COMPLETE, reply_markup=inline_markup.get_users_keyboard())

    except Exception:
        await callback.message.answer(text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
