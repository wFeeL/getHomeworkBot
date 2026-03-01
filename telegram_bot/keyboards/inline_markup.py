from __future__ import annotations

from datetime import datetime, timedelta

from aiogram.types import InlineKeyboardMarkup, InlineKeyboardButton
from aiogram.utils.keyboard import InlineKeyboardBuilder

from telegram_bot import callback_text, text_message
from telegram_bot.database_methods.database_request import (
    get_class,
    get_homework,
    get_homework_counts_by_subject,
    get_subject,
    get_weekday,
)


# ------------------
# Buttons
# ------------------

def get_homework_menu_button(text: str = '🔄 Главное меню') -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data='menu')]


def get_help_button(text: str = '❓ Помощь') -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data='help')]


def get_support_button(text: str = '🔰 Поддержка') -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, url='https://t.me/wfeels')]


def get_donate_button(text: str = '💰 Донат') -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, url='https://www.tinkoff.ru/rm/saburov.daniil23/TTzup21621')]


def get_choose_class_button(text: str = '👤 Выбрать класс') -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data=callback_text.CALLBACK['send_choose_class'])]


def get_calendar_homework_button(text: str = '🗓 Выбрать дату') -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data=callback_text.CALLBACK['send_calendar_homework'])]


def get_schedule_button(weekday_index: int | None, text: str = '⏰ Показать расписание') -> list[InlineKeyboardButton]:
    if weekday_index is None:
        return [InlineKeyboardButton(text=text, callback_data='None')]
    return [InlineKeyboardButton(text=text, callback_data="{\"weekday_index\":" + str(weekday_index) + ",\"is_homework\":\"True\"}")]


# Admin buttons

def get_admin_menu_button() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text='🔄 Главное меню', callback_data=callback_text.CALLBACK['send_admin_menu'])]


def get_add_homework_button() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text='Добавить домашнее задание', callback_data=callback_text.CALLBACK['send_adding_states'])]


def get_add_subject_button() -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text='Добавить школьный предмет', callback_data=callback_text.CALLBACK['send_add_subject'])]


def get_delete_message_button(text: str = '👀 Скрыть') -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data='delete_message')]


def get_stop_state_button(text: str = '👀 Скрыть') -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data='stop_state')]


def get_edit_class_button(text: str = '📝 Редактировать класс', class_id: int | str = 0) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data="{\"class_id\":" + str(class_id) + ",\"edit\":\"True\"}")]


def get_delete_class_button(text: str = '🗑️ Удалить класс', class_id: int | str = 0) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data="{\"class_id\":" + str(class_id) + ",\"delete\":\"True\"}")]


def get_delete_subject_button(text: str = '🗑️ Удалить предмет', subject_id: int | str = 0) -> list[InlineKeyboardButton]:
    return [InlineKeyboardButton(text=text, callback_data="{\"subject_id\":" + str(subject_id) + ",\"delete\":\"True\"}")]


# ------------------
# Markups: common
# ------------------

def get_start_keyboard(is_class: bool = True) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    if not is_class:
        builder.add(get_choose_class_button()[0])
    else:
        builder.add(get_homework_menu_button('🔍 Открыть меню поиска')[0])

    builder.add(get_donate_button()[0], get_support_button('🔰 Разработчик')[0])
    builder.adjust(1, 2)
    return builder.as_markup()


def get_help_keyboard(is_class: bool = True) -> InlineKeyboardMarkup:
    keyboard = []
    if not is_class:
        keyboard.append(get_choose_class_button())
    keyboard += [get_donate_button('💰Поддержать автора'), get_support_button()]
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_homework_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='✍ Задания на завтра', callback_data=callback_text.CALLBACK['send_tomorrow_homework'])],
            get_calendar_homework_button(text='🗓️ Календарь заданий'),
            [InlineKeyboardButton(text='⚜ Все домашние задания', callback_data=callback_text.CALLBACK['send_all_homework'])],
        ]
    )


async def get_all_homework_keyboard(class_id: int | str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    subjects = await get_subject(value=True, class_ids=class_id)
    homework_counts = await get_homework_counts_by_subject(class_id)

    for subject in subjects:
        subject_id, subject_name, subject_sticker = subject[0], subject[1], subject[2]
        data_length = int(homework_counts.get(int(subject_id), 0))
        start_page = data_length if data_length > 0 else 1

        builder.row(
            InlineKeyboardButton(
                text=f'{subject_sticker} {subject_name}',
                callback_data=(
                    "{\"subject_id\":\"" + str(subject_id) + f"\",\"page\":\"{start_page}\",\"len\":" + str(data_length) + "}"
                ),
            )
        )
    builder.row(get_homework_menu_button()[0])
    return builder.as_markup()


async def get_homework_pagination(
    length: int,
    page: int,
    subject_id: int | str,
    *,
    class_id: int | None = None,
    is_admin: bool = False,
    homework_id: int | None = None,
) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()

    next_button = InlineKeyboardButton(
        text='Вперед ▶',
        callback_data=("{\"subject_id\":\"" + str(subject_id) + "\",\"page\":" + str(page + 1) + ",\"len\":" + str(length) + "}"),
    )
    back_button = InlineKeyboardButton(
        text='◀ Назад',
        callback_data=("{\"subject_id\":\"" + str(subject_id) + "\",\"page\":" + str(page - 1) + ",\"len\":" + str(length) + "}"),
    )

    count_button = InlineKeyboardButton(text=f'{page}/{length}', callback_data='None')

    menu_button = InlineKeyboardButton(text='🔄 К выбору предметов', callback_data=callback_text.CALLBACK['send_all_homework'])

    if length <= 0:
        builder.add(InlineKeyboardButton(text='0/0', callback_data='None'))
    elif page == 1 and length == 1:
        builder.add(count_button)
    elif page == 1:
        builder.add(count_button, next_button)
    elif page == length:
        builder.add(back_button, count_button)
    else:
        builder.add(back_button, count_button, next_button)

    builder.adjust(3, 1)

    if is_admin and class_id is not None and length > 0:
        resolved_homework_id = homework_id
        if resolved_homework_id is None:
            hw_rows = await get_homework(subject_id=subject_id, class_id=class_id)
            if 1 <= page <= len(hw_rows):
                resolved_homework_id = int(hw_rows[page - 1][0])

        if resolved_homework_id is not None:
            edit_button = InlineKeyboardButton(
                text='📝 Изменить домашнее задание',
                callback_data="{\"homework_id\":" + str(resolved_homework_id) + ",\"edit\":\"True\"}",
            )
            delete_button = InlineKeyboardButton(
                text='🗑️ Удалить домашнее задание',
                callback_data="{\"homework_id\":" + str(resolved_homework_id) + ",\"delete\":\"True\"}",
            )
            builder.row(edit_button)
            builder.row(delete_button)

    builder.row(menu_button)
    return builder.as_markup()


def get_back_to_subjects_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='🔄 К выбору предметов', callback_data=callback_text.CALLBACK['send_all_homework'])],
        ]
    )


async def get_schedule_keyboard(class_id: int | str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    weekdays = await get_weekday(class_ids=class_id)
    for i, row in enumerate(weekdays):
        weekday_name = row[1]
        builder.row(
            InlineKeyboardButton(
                text=f"{text_message.SCHEDULE_DICTIONARY_RUS[weekday_name]}".capitalize(),
                callback_data="{\"weekday_index\":\"" + f"{i}" + "\"}",
            )
        )
    return builder.as_markup()


async def get_choose_class_keyboard() -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    classes = await get_class(value=True)
    for elem in classes:
        class_id, letter, number = elem[0], elem[1], elem[2]
        builder.row(InlineKeyboardButton(text=f'{number} {letter}', callback_data="{\"class_id\":\"" + f"{class_id}" + "\"}"))
    return builder.as_markup()


def get_weekday_keyboard(weekday_index: int) -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [
                InlineKeyboardButton(text='◀ Назад', callback_data="{\"weekday_index\":\"" + f"{weekday_index - 1}" + "\"}"),
                InlineKeyboardButton(text='Вперед ▶', callback_data="{\"weekday_index\":\"" + f"{weekday_index + 1}" + "\"}"),
            ],
            [InlineKeyboardButton(text='🔄 Выбрать день', callback_data=callback_text.CALLBACK['send_schedule'])],
        ]
    )


def get_site_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Перейти по ссылке', url='https://petersburgedu.ru/')]])


def get_calendar_keyboard(selected_date, weekday_index: int | None, media_group: tuple[int, int] | None = None) -> InlineKeyboardMarkup:
    next_date = datetime.strftime(selected_date + timedelta(days=1), '%Y-%m-%d')
    previous_date = datetime.strftime(selected_date - timedelta(days=1), '%Y-%m-%d')

    builder = InlineKeyboardBuilder()

    if weekday_index is not None:
        builder.row(get_schedule_button(weekday_index=weekday_index)[0])

    builder.row(get_calendar_homework_button()[0])
    builder.row(get_homework_menu_button()[0])

    if media_group is None:
        builder.row(
            InlineKeyboardButton(text='◀ Назад', callback_data="{\"date\":\"" + f"{previous_date}" + "\"}"),
            InlineKeyboardButton(text='Вперед ▶', callback_data="{\"date\":\"" + f"{next_date}" + "\"}"),
        )
    else:
        first_message_id = media_group[0]
        last_message_id = first_message_id + media_group[1]
        builder.row(
            InlineKeyboardButton(
                text='◀ Назад',
                callback_data="{" + f"\"date\":\"{previous_date}\",\"first_msg\":\"{first_message_id}\",\"last_msg\":\"{last_message_id}\"" + "}",
            ),
            InlineKeyboardButton(
                text='Вперед ▶',
                callback_data="{" + f"\"date\":\"{next_date}\",\"first_msg\":\"{first_message_id}\",\"last_msg\":\"{last_message_id}\"" + "}",
            ),
        )
    return builder.as_markup()


def get_random_text_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            get_homework_menu_button('🔍 Поиск домашнего задания'),
            get_help_button(),
            get_support_button(),
            get_delete_message_button(),
        ]
    )


def get_delete_message_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[get_delete_message_button()])


def get_class_keyboard(class_id: int = 0, is_super_admin: bool = False) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    builder.add(get_choose_class_button()[0], get_homework_menu_button('🔍 Открыть меню поиска')[0])
    if is_super_admin:
        builder.add(get_edit_class_button(class_id=class_id)[0])
    builder.adjust(1, 1)
    return builder.as_markup()


# ------------------
# Markups: admin
# ------------------

def get_admins_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='Добавить администратора', callback_data='add_admin')],
            [InlineKeyboardButton(text='Удалить администратора', callback_data='delete_admin')],
            get_admin_menu_button(),
        ]
    )


def get_admin_menu() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[get_add_homework_button(), get_admin_menu_button()])


def get_send_homework_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='✅ Сохранить данные', callback_data='send_data')],
            [InlineKeyboardButton(text='🚫 Отмена', callback_data='cancel_send_data')],
        ]
    )


def get_send_class_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='✅ Сохранить данные', callback_data='send_class_data')],
            [InlineKeyboardButton(text='🚫 Отмена', callback_data='cancel_send_data')],
        ]
    )


def get_send_subject_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='✅ Сохранить данные', callback_data='send_subject_data')],
            [InlineKeyboardButton(text='🚫 Отмена', callback_data='cancel_send_data')],
        ]
    )


def get_send_teacher_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(
        inline_keyboard=[
            [InlineKeyboardButton(text='✅ Сохранить данные', callback_data='send_teacher_data')],
            [InlineKeyboardButton(text='🚫 Отмена', callback_data='cancel_send_data')],
        ]
    )


def get_edit_homework_keyboard(is_file: bool = True, is_edited: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text='🗓️ Редактировать дату', callback_data='edit_date')],
        [InlineKeyboardButton(text='📝 Редактировать описание', callback_data='edit_description')],
        [InlineKeyboardButton(text='🖼️ Прикрепить изображение', callback_data='edit_file')],
    ]
    if is_file:
        keyboard.append([InlineKeyboardButton(text='🗑️ Удалить изображение', callback_data='delete_file')])
    if is_edited:
        keyboard.append([InlineKeyboardButton(text='✅ Сохранить данные', callback_data='edit_data')])
        keyboard.append(get_stop_state_button())
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_edit_class_keyboard(class_id: int | str, is_edited: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text='🗓️ Редактировать номер', callback_data='edit_number')],
        [InlineKeyboardButton(text='📝 Редактировать литер', callback_data='edit_letter')],
        get_delete_class_button(class_id=class_id),
    ]
    if is_edited:
        keyboard.append([InlineKeyboardButton(text='✅ Сохранить данные', callback_data='edit_class_data')])
        keyboard.append(get_stop_state_button())
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_edit_subject_keyboard(subject_id: int | str, is_edited: bool = False) -> InlineKeyboardMarkup:
    keyboard = [
        [InlineKeyboardButton(text='📝 Редактировать название', callback_data='edit_name')],
        [InlineKeyboardButton(text='🗓️ Редактировать стикер', callback_data='edit_sticker')],
        get_delete_subject_button(subject_id=subject_id),
    ]
    if is_edited:
        keyboard.append([InlineKeyboardButton(text='✅ Сохранить данные', callback_data='edit_subject_data')])
        keyboard.append(get_stop_state_button())
    return InlineKeyboardMarkup(inline_keyboard=keyboard)


def get_skip_file_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='Пропустить выбор фото ⏩', callback_data='skip_file')]])


def get_send_message_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[[InlineKeyboardButton(text='✅ Отправить сообщение', callback_data='send_message')]])


def get_users_keyboard() -> InlineKeyboardMarkup:
    return InlineKeyboardMarkup(inline_keyboard=[get_admin_menu_button()])


async def get_all_subject(class_id: int | str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    subjects = await get_subject(value=True, class_ids=class_id)
    for subject in subjects:
        subject_name = subject[1]
        subject_sticker = subject[2]
        subject_id = subject[0]
        builder.add(InlineKeyboardButton(text=f'{subject_sticker} {subject_name}', callback_data="{\"subject_id\":\"" + f"{subject_id}" + "\"}"))

    if len(subjects) < 40:
        builder.add(get_add_subject_button()[0])

    builder.adjust(1, 1)
    return builder.as_markup()


def get_subject_keyboard(subject_id: int | str) -> InlineKeyboardMarkup:
    builder = InlineKeyboardBuilder()
    edit_button = InlineKeyboardButton(text='📝 Редактировать предмет', callback_data="{\"subject_id\":" + str(subject_id) + ",\"edit\":\"True\"}")
    delete_button = InlineKeyboardButton(text='🗑️ Удалить предмет', callback_data="{\"subject_id\":" + str(subject_id) + ",\"delete\":\"True\"}")
    builder.add(edit_button, delete_button)
    builder.adjust(1, 1)
    return builder.as_markup()
