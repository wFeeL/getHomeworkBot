from __future__ import annotations

import datetime
from typing import Optional, Sequence

from telegram_bot.database_methods import db


def _where(clauses: list[str]) -> str:
    return (" WHERE " + " AND ".join(clauses)) if clauses else ""


# ----------------------------
# Select helpers
# ----------------------------


async def get_users(telegram_id: int | str | None = None, class_id: int | str | None = None) -> list:
    clauses: list[str] = []
    args: list = []

    if telegram_id is not None:
        clauses.append("telegram_id = $%d" % (len(args) + 1))
        args.append(str(telegram_id))
    if class_id is not None:
        clauses.append("class_id = $%d" % (len(args) + 1))
        args.append(int(class_id))

    q = "SELECT telegram_id, class_id FROM users" + _where(clauses) + " ORDER BY id"
    return await db.fetch(q, *args)


async def get_admins(
    telegram_id: int | str | None = None,
    value: bool | str | None = None,
    super_admin: bool | str | None = None,
    class_id: int | str | None = None,
) -> list:
    clauses: list[str] = []
    args: list = []

    if telegram_id is not None:
        clauses.append("telegram_id = $%d" % (len(args) + 1))
        args.append(str(telegram_id))
    if value is not None:
        clauses.append("value = $%d" % (len(args) + 1))
        args.append(bool(value) if isinstance(value, bool) else str(value).lower() in {"1", "true", "yes"})
    if super_admin is not None:
        clauses.append("super_admin = $%d" % (len(args) + 1))
        args.append(bool(super_admin) if isinstance(super_admin, bool) else str(super_admin).lower() in {"1", "true", "yes"})
    if class_id is not None:
        clauses.append("class_id = $%d" % (len(args) + 1))
        args.append(int(class_id))

    q = "SELECT telegram_id, class_id, value, super_admin FROM admins" + _where(clauses) + " ORDER BY id"
    return await db.fetch(q, *args)


async def get_class(
    id: int | str | None = None,
    letter: str | None = None,
    number: int | str | None = None,
    value: bool | str | None = None,
) -> list:
    clauses: list[str] = []
    args: list = []

    if id is not None:
        clauses.append("id = $%d" % (len(args) + 1))
        args.append(int(id))
    if letter is not None:
        clauses.append("letter = $%d" % (len(args) + 1))
        args.append(str(letter))
    if number is not None:
        clauses.append("number = $%d" % (len(args) + 1))
        args.append(int(number))
    if value is not None:
        clauses.append("value = $%d" % (len(args) + 1))
        args.append(bool(value) if isinstance(value, bool) else str(value).lower() in {"1", "true", "yes"})

    q = "SELECT id, letter, number, value FROM class" + _where(clauses) + " ORDER BY id"
    return await db.fetch(q, *args)


async def get_subject(
    id: int | str | None = None,
    name: str | None = None,
    sticker: str | None = None,
    value: bool | None = None,
    class_ids: int | str | None = None,
) -> list:
    clauses: list[str] = []
    args: list = []

    if id is not None:
        clauses.append("id = $%d" % (len(args) + 1))
        args.append(int(id))
    if name is not None:
        clauses.append("name = $%d" % (len(args) + 1))
        args.append(str(name))
    if sticker is not None:
        clauses.append("sticker = $%d" % (len(args) + 1))
        args.append(str(sticker))
    if value is not None:
        clauses.append("value = $%d" % (len(args) + 1))
        args.append(bool(value))
    if class_ids is not None:
        # array contains
        clauses.append("class_ids @> ARRAY[$%d]::int[]" % (len(args) + 1))
        args.append(int(class_ids))

    q = "SELECT id, name, sticker, value, class_ids FROM subject" + _where(clauses) + " ORDER BY name"
    return await db.fetch(q, *args)


async def get_weekday(
    id: int | str | None = None,
    name: str | None = None,
    class_ids: int | str | None = None,
) -> list:
    clauses: list[str] = []
    args: list = []

    if id is not None:
        clauses.append("id = $%d" % (len(args) + 1))
        args.append(int(id))
    if name is not None:
        clauses.append("name = $%d" % (len(args) + 1))
        args.append(str(name))
    if class_ids is not None:
        clauses.append("class_ids @> ARRAY[$%d]::int[]" % (len(args) + 1))
        args.append(int(class_ids))

    q = "SELECT id, name, class_ids FROM weekday" + _where(clauses) + " ORDER BY id"
    return await db.fetch(q, *args)


async def get_homework(
    id: int | str | None = None,
    subject_id: int | str | None = None,
    date: datetime.date | datetime.datetime | str | None = None,
    class_id: int | str | None = None,
) -> list:
    clauses: list[str] = []
    args: list = []

    if id is not None:
        clauses.append("id = $%d" % (len(args) + 1))
        args.append(int(id))
    if subject_id is not None:
        clauses.append("subject_id = $%d" % (len(args) + 1))
        args.append(int(subject_id))
    if date is not None:
        if isinstance(date, str):
            # allow yyyy-mm-dd
            date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
        elif isinstance(date, datetime.datetime):
            date_obj = date.date()
        else:
            date_obj = date
        start_dt = datetime.datetime.combine(date_obj, datetime.time.min)
        end_dt = start_dt + datetime.timedelta(days=1)
        clauses.append("date >= $%d" % (len(args) + 1))
        args.append(start_dt)
        clauses.append("date < $%d" % (len(args) + 1))
        args.append(end_dt)
    if class_id is not None:
        clauses.append("class_id = $%d" % (len(args) + 1))
        args.append(int(class_id))

    q = (
        "SELECT id, subject_id, date, description, file_id, class_id "
        "FROM homework" + _where(clauses) + " ORDER BY date, subject_id"
    )
    return await db.fetch(q, *args)


async def get_schedule(weekday: str, class_id: int | str) -> list:
    q = (
        "SELECT s.name "
        "FROM schedule t "
        "JOIN weekday w ON w.id = t.weekday_id "
        "LEFT JOIN subject s ON s.id = t.subject_id "
        "WHERE w.name = $1 AND t.class_id = $2 "
        "ORDER BY t.weight ASC"
    )
    return await db.fetch(q, weekday, int(class_id))


async def get_teachers(class_id: int | str) -> list:
    q = (
        "SELECT teachers.name, subject.name "
        "FROM teachers "
        "LEFT JOIN subject ON teachers.subject_id = subject.id "
        "WHERE teachers.class_ids @> ARRAY[$1]::int[] "
        "ORDER BY subject.name"
    )
    return await db.fetch(q, int(class_id))


async def get_timetable() -> list:
    return await db.fetch("SELECT id, time FROM timetable ORDER BY id")


async def get_quotes(text: str | None = None, author: str | None = None, value: bool | None = None) -> list:
    clauses: list[str] = []
    args: list = []
    if text is not None:
        clauses.append("text = $%d" % (len(args) + 1))
        args.append(text)
    if author is not None:
        clauses.append("author = $%d" % (len(args) + 1))
        args.append(author)
    if value is not None:
        clauses.append("value = $%d" % (len(args) + 1))
        args.append(bool(value))

    q = "SELECT text, author, value FROM quotes" + _where(clauses) + " ORDER BY id"
    return await db.fetch(q, *args)


async def get_user_count(class_id: int | str) -> int:
    value = await db.fetchval("SELECT COUNT(*) FROM users WHERE class_id = $1", int(class_id))
    return int(value or 0)


async def get_admin_count(class_id: int | str, *, active_only: bool = False) -> int:
    if active_only:
        value = await db.fetchval(
            "SELECT COUNT(*) FROM admins WHERE class_id = $1 AND value = true",
            int(class_id),
        )
    else:
        value = await db.fetchval("SELECT COUNT(*) FROM admins WHERE class_id = $1", int(class_id))
    return int(value or 0)


async def get_homework_counts_by_subject(class_id: int | str) -> dict[int, int]:
    rows = await db.fetch(
        "SELECT subject_id, COUNT(*)::int "
        "FROM homework "
        "WHERE class_id = $1 "
        "GROUP BY subject_id",
        int(class_id),
    )
    return {int(row[0]): int(row[1]) for row in rows}


async def get_homework_with_subject_by_date(
    class_id: int | str,
    date: datetime.date | datetime.datetime | str,
) -> list:
    if isinstance(date, str):
        date_obj = datetime.datetime.strptime(date, "%Y-%m-%d").date()
    elif isinstance(date, datetime.datetime):
        date_obj = date.date()
    else:
        date_obj = date

    start_dt = datetime.datetime.combine(date_obj, datetime.time.min)
    end_dt = start_dt + datetime.timedelta(days=1)

    q = (
        "SELECT h.id, h.subject_id, h.date, h.description, h.file_id, h.class_id, "
        "COALESCE(s.name, '?') AS subject_name, COALESCE(s.sticker, '📘') AS subject_sticker "
        "FROM homework h "
        "LEFT JOIN subject s ON s.id = h.subject_id AND s.class_ids @> ARRAY[$1]::int[] "
        "WHERE h.class_id = $1 AND h.date >= $2 AND h.date < $3 "
        "ORDER BY h.date, h.subject_id"
    )
    return await db.fetch(q, int(class_id), start_dt, end_dt)


# ----------------------------
# Mutations
# ----------------------------


async def add_user(telegram_id: int | str, class_id: int | str = 0) -> None:
    await db.execute(
        "INSERT INTO users (telegram_id, class_id) VALUES ($1, $2) ON CONFLICT (telegram_id) DO NOTHING",
        str(telegram_id),
        int(class_id),
    )


async def add_admin(
    telegram_id: int | str,
    value: bool = True,
    super_admin: bool = False,
    class_id: int | str | None = 0,
) -> None:
    tg = str(telegram_id)
    existing = await db.fetchrow("SELECT id FROM admins WHERE telegram_id = $1 ORDER BY id LIMIT 1", tg)
    if existing is None:
        await db.execute(
            "INSERT INTO admins (telegram_id, value, super_admin, class_id) VALUES ($1, $2, $3, $4)",
            tg,
            bool(value),
            bool(super_admin),
            None if class_id is None else int(class_id),
        )
    else:
        await db.execute(
            "UPDATE admins SET value = $2, super_admin = $3, class_id = $4 WHERE telegram_id = $1",
            tg,
            bool(value),
            bool(super_admin),
            None if class_id is None else int(class_id),
        )


async def update_user_class(telegram_id: int | str, class_id: int | str) -> None:
    await db.execute("UPDATE users SET class_id = $2 WHERE telegram_id = $1", str(telegram_id), int(class_id))


async def update_admin_class(telegram_id: int | str, class_id: int | str) -> None:
    await db.execute("UPDATE admins SET class_id = $2 WHERE telegram_id = $1", str(telegram_id), int(class_id))


async def add_homework_value(subject: str, date: str, description: str, file_id: str, class_id: int | str) -> None:
    subject_row = await db.fetchrow(
        "SELECT id FROM subject WHERE name = $1 AND class_ids @> ARRAY[$2]::int[] LIMIT 1",
        subject,
        int(class_id),
    )
    if subject_row is None:
        raise ValueError("Subject not found")
    subject_id = int(subject_row[0])

    dt = datetime.datetime.strptime(date, "%d.%m.%Y")

    await db.execute(
        "INSERT INTO homework (subject_id, date, description, file_id, class_id) VALUES ($1, $2, $3, $4, $5)",
        subject_id,
        dt,
        description,
        file_id,
        int(class_id),
    )


async def update_homework(
    homework_id: int | str,
    subject_id: int | str,
    date: str,
    description: str,
    file_id: str,
) -> None:
    dt = datetime.datetime.strptime(date, "%d.%m.%Y")
    await db.execute(
        "UPDATE homework SET subject_id = $2, date = $3, description = $4, file_id = $5 WHERE id = $1",
        int(homework_id),
        int(subject_id),
        dt,
        description,
        file_id,
    )


async def delete_homework(homework_id: int | str) -> None:
    await db.execute("DELETE FROM homework WHERE id = $1", int(homework_id))


async def add_class_value(number: int | str, letter: str | int) -> None:
    await db.execute(
        "INSERT INTO class (number, letter, value) VALUES ($1, $2, true)",
        int(number),
        str(letter),
    )


async def update_class(class_id: int | str, number: int | str, letter: str) -> None:
    await db.execute(
        "UPDATE class SET number = $2, letter = $3 WHERE id = $1",
        int(class_id),
        int(number),
        str(letter),
    )


async def delete_class(class_id: int | str) -> None:
    cid = int(class_id)

    # Detach users/admins
    await db.execute("UPDATE users SET class_id = 0 WHERE class_id = $1", cid)
    await db.execute("UPDATE admins SET class_id = 0 WHERE class_id = $1", cid)

    # Remove homework and schedule entries for this class
    await db.execute("DELETE FROM homework WHERE class_id = $1", cid)
    await db.execute("DELETE FROM schedule WHERE class_id = $1", cid)

    # Remove class id from arrays
    await db.execute("UPDATE teachers SET class_ids = array_remove(class_ids, $1) WHERE class_ids @> ARRAY[$1]::int[]", cid)
    await db.execute("UPDATE subject SET class_ids = array_remove(class_ids, $1) WHERE class_ids @> ARRAY[$1]::int[]", cid)
    await db.execute("UPDATE weekday SET class_ids = array_remove(class_ids, $1) WHERE class_ids @> ARRAY[$1]::int[]", cid)

    # Finally delete the class
    await db.execute("DELETE FROM class WHERE id = $1", cid)


async def add_subject_value(name: str, sticker: str, class_id: int | str, value: bool = True) -> None:
    cid = int(class_id)

    # If subject exists, just ensure the class_id is in class_ids and update sticker/value
    existing = await db.fetchrow("SELECT id, class_ids FROM subject WHERE name = $1 LIMIT 1", name)
    if existing is None:
        await db.execute(
            "INSERT INTO subject (name, sticker, value, class_ids) VALUES ($1, $2, $3, ARRAY[$4]::int[])",
            name,
            sticker,
            bool(value),
            cid,
        )
    else:
        subject_id = int(existing[0])
        await db.execute(
            "UPDATE subject SET sticker = $2, value = $3, class_ids = (SELECT ARRAY(SELECT DISTINCT unnest(COALESCE(class_ids, '{}'::int[]) || ARRAY[$4]::int[]))) WHERE id = $1",
            subject_id,
            sticker,
            bool(value),
            cid,
        )


async def update_subject(subject_id: int | str, name: str, sticker: str) -> None:
    await db.execute(
        "UPDATE subject SET name = $2, sticker = $3 WHERE id = $1",
        int(subject_id),
        name,
        sticker,
    )


async def delete_subject(subject_id: int | str, class_id: int | str | None = None) -> None:
    sid = int(subject_id)

    if class_id is None:
        # Backward-compatible hard delete.
        await db.execute("DELETE FROM homework WHERE subject_id = $1", sid)
        await db.execute("DELETE FROM schedule WHERE subject_id = $1", sid)
        await db.execute("DELETE FROM teachers WHERE subject_id = $1", sid)
        await db.execute("DELETE FROM subject WHERE id = $1", sid)
        return

    cid = int(class_id)

    # Remove only class-scoped records.
    await db.execute("DELETE FROM homework WHERE subject_id = $1 AND class_id = $2", sid, cid)
    await db.execute("DELETE FROM schedule WHERE subject_id = $1 AND class_id = $2", sid, cid)
    await db.execute(
        "UPDATE teachers SET class_ids = array_remove(class_ids, $2) "
        "WHERE subject_id = $1 AND class_ids @> ARRAY[$2]::int[]",
        sid,
        cid,
    )
    await db.execute(
        "DELETE FROM teachers WHERE subject_id = $1 AND (class_ids IS NULL OR cardinality(class_ids) = 0)",
        sid,
    )

    await db.execute("UPDATE subject SET class_ids = array_remove(class_ids, $2) WHERE id = $1", sid, cid)
    await db.execute("DELETE FROM subject WHERE id = $1 AND (class_ids IS NULL OR cardinality(class_ids) = 0)", sid)


async def add_teacher_value(name: str, subject_id: int | str, class_id: int | str) -> None:
    await db.execute(
        "INSERT INTO teachers (name, subject_id, class_ids) VALUES ($1, $2, ARRAY[$3]::int[])",
        name,
        int(subject_id),
        int(class_id),
    )


# timetable schema stores a single string column `time`.
# Keep backward compatible signatures: store `HH:MM-HH:MM` when start/end are passed.
async def add_timetable(id: int | str, start_time: datetime.time, end_time: datetime.time) -> None:
    time_str = f"{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}"
    await db.execute("INSERT INTO timetable (id, time) VALUES ($1, $2)", int(id), time_str)


async def update_timetable(id: int | str, start_time: datetime.time, end_time: datetime.time) -> None:
    time_str = f"{start_time.strftime('%H:%M')}-{end_time.strftime('%H:%M')}"
    await db.execute("UPDATE timetable SET time = $2 WHERE id = $1", int(id), time_str)
