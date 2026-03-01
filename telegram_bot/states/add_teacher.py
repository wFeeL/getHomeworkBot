from __future__ import annotations

from aiogram import F, Router
from aiogram.exceptions import TelegramBadRequest
from aiogram.fsm.context import FSMContext
from aiogram.fsm.state import State, StatesGroup
from aiogram.types import CallbackQuery, Message

from telegram_bot import text_message
from telegram_bot.database_methods.database_request import add_teacher_value, get_admins, get_subject
from telegram_bot.keyboards import inline_markup, reply_markup


class TeacherForm(StatesGroup):
    name = State()
    surname = State()
    patronymic = State()
    subject = State()


router = Router()


async def _get_admin_class_id(telegram_id: int) -> int:
    admin_rows = await get_admins(telegram_id=telegram_id)
    return int(admin_rows[0][1]) if admin_rows and admin_rows[0][1] else 0


async def _try_edit_callback_text(callback: CallbackQuery, text: str, reply_markup=None) -> bool:
    try:
        await callback.message.edit_text(text=text, reply_markup=reply_markup)
        return True
    except TelegramBadRequest:
        return False


async def register_teacher(message: Message, state: FSMContext) -> None:
    await message.answer(text=text_message.CHOOSE_TEACHER_NAME)
    await state.set_state(TeacherForm.name)


@router.message(TeacherForm.name)
async def process_teacher_name(message: Message, state: FSMContext) -> None:
    teacher_name = (message.text or "").strip()
    if not teacher_name:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    await state.update_data(name=teacher_name)
    await message.answer(text=text_message.CHOOSE_TEACHER_SURNAME)
    await state.set_state(TeacherForm.surname)


@router.message(TeacherForm.surname)
async def process_teacher_surname(message: Message, state: FSMContext) -> None:
    teacher_surname = (message.text or "").strip()
    if not teacher_surname:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    await state.update_data(surname=teacher_surname)
    await message.answer(text=text_message.CHOOSE_TEACHER_PATRONYMIC)
    await state.set_state(TeacherForm.patronymic)


@router.message(TeacherForm.patronymic)
async def process_teacher_patronymic(message: Message, state: FSMContext) -> None:
    teacher_patronymic = (message.text or "").strip()
    if not teacher_patronymic:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    class_id = await _get_admin_class_id(message.chat.id)
    if class_id == 0:
        await message.answer(text_message.ADMIN_CLASS_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    await state.update_data(patronymic=teacher_patronymic)
    await message.answer(
        text=text_message.CHOOSE_SUBJECT,
        reply_markup=await reply_markup.get_subjects_keyboard(class_id),
    )
    await state.set_state(TeacherForm.subject)


@router.message(TeacherForm.subject)
async def process_teacher_subject(message: Message, state: FSMContext) -> None:
    teacher_subject = (message.text or "").strip()
    if not teacher_subject:
        await message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
        return

    await state.update_data(subject=teacher_subject)
    await send_teacher(message, state)


async def send_teacher(message: Message, state: FSMContext) -> None:
    try:
        teacher_data = await state.get_data()
        teacher_name = teacher_data["name"]
        surname = teacher_data["surname"]
        patronymic = teacher_data["patronymic"]
        subject_name = teacher_data["subject"]

        class_id = await _get_admin_class_id(message.chat.id)
        if class_id == 0:
            raise ValueError("Admin class is not set")

        subject_rows = await get_subject(name=subject_name, class_ids=class_id)
        if not subject_rows:
            raise ValueError("Subject not found")
        subject_sticker = subject_rows[0][2]

        teacher_text = text_message.TEACHER_DATA_TO_SEND.format(
            teacher_name=teacher_name,
            surname=surname,
            patronymic=patronymic,
            subject_sticker=subject_sticker,
            subject_name=subject_name,
        )
        await message.answer(text=teacher_text, reply_markup=inline_markup.get_send_teacher_keyboard())

    except Exception:
        await message.answer(text_message.TRY_AGAIN_ERROR, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()


@router.callback_query(F.data == 'send_teacher_data')
async def send_data(callback: CallbackQuery, state: FSMContext) -> None:
    try:
        teacher_data = await state.get_data()
        teacher_name = teacher_data["name"]
        surname = teacher_data["surname"]
        patronymic = teacher_data["patronymic"]
        subject_name = teacher_data["subject"]

        class_id = await _get_admin_class_id(callback.message.chat.id)
        if class_id == 0:
            raise ValueError("Admin not found")

        subject_rows = await get_subject(name=subject_name, class_ids=class_id)
        if not subject_rows:
            raise ValueError("Subject not found")
        subject_id = int(subject_rows[0][0])

        fullname = f"{surname} {teacher_name} {patronymic}".strip()
        await add_teacher_value(fullname, subject_id, class_id)

        done_text = text_message.ADDING_TEACHER_COMPLETE.format(
            teacher_name=teacher_name,
            patronymic=patronymic,
            subject_name=subject_name,
        )
        if not await _try_edit_callback_text(callback, done_text, inline_markup.get_admin_menu()):
            await callback.message.answer(
                done_text,
                reply_markup=inline_markup.get_admin_menu(),
            )
        await state.clear()

    except Exception:
        await callback.message.answer(text_message.INCORRECT_REQUEST, reply_markup=inline_markup.get_delete_message_keyboard())
        await state.clear()
