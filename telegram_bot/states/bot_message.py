from __future__ import annotations

import asyncio
import logging

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from telegram_bot import text_message
from telegram_bot.database_methods.database_request import get_admins, get_users
from telegram_bot.keyboards import inline_markup


class MessageForm(StatesGroup):
    text = State()


logger = logging.getLogger(__name__)
router = Router()


async def _try_edit_callback_text(callback: CallbackQuery, text: str, reply_markup=None) -> bool:
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest:
        return False


async def register_message(message: Message, state: FSMContext) -> None:
    await message.answer(text=text_message.BOT_MESSAGE_INPUT_TEXT)
    await state.set_state(MessageForm.text)


@router.message(MessageForm.text)
async def process_message_text(message: Message, state: FSMContext) -> None:
    text_to_send = message.text or ""
    await state.update_data(text=text_to_send)
    await message.answer(
        text=text_message.BOT_MESSAGE_TEXT.format(message=text_to_send),
        reply_markup=inline_markup.get_send_message_keyboard(),
    )


@router.callback_query(F.data == 'send_message')
async def send_message(callback: CallbackQuery, state: FSMContext) -> None:
    await _try_edit_callback_text(callback, "⏳ Отправка сообщения...")

    admin_rows = await get_admins(telegram_id=callback.message.chat.id)
    class_id = int(admin_rows[0][1]) if admin_rows else 0

    users_list = await get_users(class_id=class_id)
    data = await state.get_data()
    text_to_send = data.get('text', '')
    await state.clear()

    semaphore = asyncio.Semaphore(20)

    async def _send(tg_id: str) -> None:
        async with semaphore:
            try:
                await callback.message.bot.send_message(chat_id=tg_id, text=text_to_send)
            except Exception as error:
                logger.info("%s while sending to %s", error.__class__.__name__, tg_id)

    await asyncio.gather(*[_send(str(row[0])) for row in users_list])

    if not await _try_edit_callback_text(callback, text_message.BOT_MESSAGE_SUCCESS):
        await callback.message.answer(text=text_message.BOT_MESSAGE_SUCCESS)
