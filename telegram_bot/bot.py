from __future__ import annotations

import asyncio
import logging

from aiogram import Dispatcher, Bot
from aiogram.client.bot import DefaultBotProperties
from aiogram.exceptions import TelegramNetworkError
from aiogram.fsm.storage.memory import MemoryStorage

from telegram_bot.config_reader import config
from telegram_bot.database_methods.db import init_pool, close_pool
from telegram_bot.helpers import check_required_environment, ensure_super_admin
from telegram_bot.handlers import bot_commands


logging.basicConfig(level=logging.INFO)
logger = logging.getLogger("homework_bot")


async def main() -> None:
    # Validate config early
    check_required_environment(logger)

    await init_pool(config.pg_dsn)
    await ensure_super_admin(logger)

    bot = Bot(token=config.bot_token, default=DefaultBotProperties(parse_mode="HTML"))
    dp = Dispatcher(storage=MemoryStorage())

    # Register routers
    dp.include_router(bot_commands.router)

    # Polling loop with backoff for transient network errors
    backoff = 1
    try:
        while True:
            try:
                await dp.start_polling(bot, allowed_updates=dp.resolve_used_update_types())
                break
            except TelegramNetworkError:
                logger.exception("Telegram network error. Reconnecting in %ss", backoff)
                await asyncio.sleep(backoff)
                backoff = min(backoff * 2, 60)
    finally:
        await close_pool()
        await bot.session.close()


if __name__ == "__main__":
    asyncio.run(main())
