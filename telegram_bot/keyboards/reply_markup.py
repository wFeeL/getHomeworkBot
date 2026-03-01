from __future__ import annotations

from aiogram.types import KeyboardButton, ReplyKeyboardMarkup
from aiogram.utils.keyboard import ReplyKeyboardBuilder

from telegram_bot.database_methods.database_request import get_class, get_subject


async def get_subjects_keyboard(class_id: int | str) -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for elem in await get_subject(value=True, class_ids=class_id):
        builder.row(KeyboardButton(text=elem[1]))
    return builder.as_markup()


async def get_class_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    classes = await get_class(value=True)
    for elem in classes:
        letter, number = elem[1], elem[2]
        builder.row(KeyboardButton(text=f'{number} {letter}'))
    return builder.as_markup()


def get_choose_class_keyboard() -> ReplyKeyboardMarkup:
    builder = ReplyKeyboardBuilder()
    for i in range(1, 12):
        builder.add(KeyboardButton(text=str(i)))
    return builder.as_markup()
