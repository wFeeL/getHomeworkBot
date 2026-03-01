from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message, ReplyKeyboardRemove

from telegram_bot import text_message
from telegram_bot.database_methods.database_request import add_class_value
from telegram_bot.keyboards import inline_markup, reply_markup


class AddClassForm(StatesGroup):
    number = State()
    letter = State()


router = Router()


async def _try_edit_callback_text(callback: CallbackQuery, text: str, reply_markup=None) -> bool:
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest:
        return False


async def register_class(message: Message, state: FSMContext) -> None:
    await message.answer(text=text_message.CHOOSE_CLASS_NUMBER, reply_markup=reply_markup.get_choose_class_keyboard())
    await state.set_state(AddClassForm.number)


@router.message(AddClassForm.number)
async def process_class_number(message: Message, state: FSMContext) -> None:
    class_number = (message.text or "").strip()
    try:
        if int(class_number) not in range(1, 12):
            raise ValueError

        await state.update_data(number=class_number)
        await message.answer(text=text_message.CHOOSE_CLASS_LETTER, reply_markup=ReplyKeyboardRemove())
        await state.set_state(AddClassForm.letter)

    except ValueError:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.message(AddClassForm.letter)
async def process_class_letter(message: Message, state: FSMContext) -> None:
    class_letter = (message.text or "").strip()
    try:
        if not class_letter or len(class_letter) > 2:
            raise ValueError

        await state.update_data(letter=class_letter)
        await send_class(message, state)

    except ValueError:
        await message.answer(text_message.WRONG_CLASS_LETTER, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


async def send_class(message: Message, state: FSMContext) -> None:
    try:
        class_data = await state.get_data()
        number = class_data["number"]
        letter = class_data["letter"]

        class_text = text_message.CLASS_DATA_TO_SEND.format(number=number, letter=letter)
        await message.answer(text=class_text, reply_markup=inline_markup.get_send_class_keyboard())

    except Exception:
        await message.answer(text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.callback_query(F.data == 'send_class_data')
async def send_data(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        class_data = await state.get_data()
        number = class_data["number"]
        letter = class_data["letter"]

        await add_class_value(number, letter)

        if not await _try_edit_callback_text(
            callback,
            text_message.ADDING_CLASS_COMPLETE.format(number=number, letter=letter),
            inline_markup.get_admin_menu(),
        ):
            await callback.message.answer(
                text_message.ADDING_CLASS_COMPLETE.format(number=number, letter=letter),
                reply_markup=inline_markup.get_admin_menu(),
            )
        await state.clear()

    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
