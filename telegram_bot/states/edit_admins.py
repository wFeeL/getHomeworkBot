from __future__ import annotations

from aiogram import Router
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import Message, ReplyKeyboardRemove

from telegram_bot import text_message
from telegram_bot.database_methods.database_request import add_admin, get_admins, get_class
from telegram_bot.keyboards import inline_markup, reply_markup


class AdminForm(StatesGroup):
    telegram_id = State()
    class_id = State()
    is_admin = State()


router = Router()


async def edit_admins(message: Message, state: FSMContext, is_admin: bool) -> None:
    await message.edit_text(text_message.CHOOSE_ADMIN_ID)
    await state.update_data(is_admin=bool(is_admin))
    await state.set_state(AdminForm.telegram_id)


@router.message(AdminForm.telegram_id)
async def process_telegram_id(message: Message, state: FSMContext) -> None:
    try:
        telegram_id = (message.text or "").strip()
        if not telegram_id.isdigit() or not (6 <= len(telegram_id) <= 10):
            raise ValueError

        prev_admin_rows = await get_admins(telegram_id=telegram_id)
        is_super_admin = bool(prev_admin_rows[0][3]) if prev_admin_rows else False

        await state.update_data(telegram_id=telegram_id)
        data = await state.get_data()
        make_admin = bool(data.get("is_admin", False))

        if make_admin:
            await state.set_state(AdminForm.class_id)
            await message.answer(text_message.CHOOSE_CLASS, reply_markup=await reply_markup.get_class_keyboard())
        else:
            await add_admin(telegram_id, value=False, super_admin=is_super_admin, class_id=0)
            await message.answer(text_message.EDIT_ADMINS)
            await state.clear()

    except Exception:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.message(AdminForm.class_id)
async def process_class_id(message: Message, state: FSMContext) -> None:
    try:
        raw = (message.text or "").strip()
        number_str, letter = raw.split(maxsplit=1)
        class_rows = await get_class(letter=letter, number=number_str)
        if not class_rows:
            raise ValueError
        class_id = int(class_rows[0][0])

        data = await state.get_data()
        telegram_id = data["telegram_id"]

        prev_admin_rows = await get_admins(telegram_id=telegram_id)
        is_super_admin = bool(prev_admin_rows[0][3]) if prev_admin_rows else False

        await add_admin(telegram_id=telegram_id, value=True, super_admin=is_super_admin, class_id=class_id)

        await message.answer(text_message.EDIT_ADMINS.format(telegram_id), reply_markup=ReplyKeyboardRemove())

    except Exception:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())

    await state.clear()
