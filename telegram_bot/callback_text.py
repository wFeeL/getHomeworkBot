from __future__ import annotations

from aiogram.types import CallbackQuery

from telegram_bot.handlers import bot_commands

CALLBACK = {
    'send_menu': 'menu',
    'send_help': 'help',
    'send_all_homework': 'all_homework',
    'send_tomorrow_homework': 'tomorrow_homework',
    'send_calendar_homework': 'calendar_homework',
    'send_class': 'class',
    'send_choose_class': 'choose_class',
    'send_schedule': 'schedule_menu',
    'send_admin_menu': 'admin_menu',
    'send_adding_states': 'adding_states',
    'send_add_subject': 'adding_subject',
}


async def call_function_from_callback(callback: CallbackQuery, **kwargs) -> None:
    """Route callback payload to a handler in `bot_commands`."""
    for func_name, payload in CALLBACK.items():
        if payload == callback.data:
            func = getattr(bot_commands, func_name)
            await func(callback.message, **kwargs)
            return
