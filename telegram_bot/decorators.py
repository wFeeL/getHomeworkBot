from __future__ import annotations

from functools import wraps

from aiogram.types import Message

from telegram_bot.database_methods.database_request import get_admins, get_users
from telegram_bot.handlers import bot_commands


def check_admin(func):
    @wraps(func)
    async def wrapper_check_admin(message: Message, **kwargs) -> None:
        admin = await get_admins(telegram_id=message.chat.id)
        if admin and (bool(admin[0][2]) or bool(admin[0][3])):
            await func(message, **kwargs)
        else:
            await bot_commands.handle_text(message, **kwargs)
    return wrapper_check_admin


def check_super_admin(func):
    @wraps(func)
    async def wrapper_check_super_admin(message: Message, **kwargs) -> None:
        admin = await get_admins(telegram_id=message.chat.id)
        if admin and bool(admin[0][3]):
            await func(message, **kwargs)
        else:
            await bot_commands.handle_text(message, **kwargs)
    return wrapper_check_super_admin


def check_class(func):
    @wraps(func)
    async def wrapper_check_class(message: Message, **kwargs) -> None:
        rows = await get_users(telegram_id=message.chat.id)
        if not rows:
            await bot_commands.authorize_user(message)
            rows = await get_users(telegram_id=message.chat.id)
        class_id = int(rows[0][1]) if rows else 0
        if class_id == 0:
            await bot_commands.send_choose_class(message)
        else:
            await func(message, **kwargs)

    return wrapper_check_class
