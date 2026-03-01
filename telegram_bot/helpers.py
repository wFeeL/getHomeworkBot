from __future__ import annotations

import datetime
import logging

from telegram_bot.config_reader import config
from telegram_bot.database_methods.database_request import add_admin, add_user, get_admins


def check_required_environment(logger: logging.Logger) -> None:
    """Log missing required env vars.

    We do not attempt to rewrite environment variables here; only diagnostics.
    """
    required = ["BOT_TOKEN", "WEATHER_API"]
    for key in required:
        if not getattr(config, {"BOT_TOKEN": "bot_token", "WEATHER_API": "weather_api"}[key], None):
            logger.error("Missing required environment variable: %s", key)


async def ensure_super_admin(logger: logging.Logger) -> None:
    """Make sure SUPER_ADMIN_TELEGRAM_ID exists in DB as a super-admin.

    If SUPER_ADMIN_TELEGRAM_ID isn't set, this is a no-op.
    """
    tg_id = config.super_admin_telegram_id
    if not tg_id:
        logger.info("SUPER_ADMIN_TELEGRAM_ID is not set; skipping super-admin bootstrap")
        return

    try:
        rows = await get_admins(telegram_id=tg_id)
        if rows and bool(rows[0][3]):
            return

        await add_admin(telegram_id=tg_id, value=True, super_admin=True, class_id=0)
        await add_user(telegram_id=tg_id, class_id=0)
        logger.info("Ensured super-admin exists in DB (telegram_id=%s)", tg_id)
    except Exception:
        logger.exception("Failed to ensure super-admin")


# Kept for compatibility (not used directly by the bot runtime).
TIMETABLE_DEFAULT: dict[int, dict[str, datetime.time]] = {
    1: {"start": datetime.time(hour=8, minute=30), "end": datetime.time(hour=9, minute=10)},
    2: {"start": datetime.time(hour=9, minute=20), "end": datetime.time(hour=10, minute=0)},
    3: {"start": datetime.time(hour=10, minute=20), "end": datetime.time(hour=11, minute=0)},
    4: {"start": datetime.time(hour=11, minute=20), "end": datetime.time(hour=12, minute=0)},
    5: {"start": datetime.time(hour=12, minute=20), "end": datetime.time(hour=13, minute=0)},
    6: {"start": datetime.time(hour=13, minute=20), "end": datetime.time(hour=14, minute=0)},
    7: {"start": datetime.time(hour=14, minute=10), "end": datetime.time(hour=14, minute=50)},
    8: {"start": datetime.time(hour=15, minute=0), "end": datetime.time(hour=15, minute=40)},
}
