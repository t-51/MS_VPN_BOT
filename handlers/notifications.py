"""هندلر سیستم اعلان‌ها و پیام‌های همگانی."""
from aiogram import Router, F, types

from db import database
from filters.auth import IsAuthorized
from keyboards.inline import build_notifications_keyboard
from utils.formatters import format_notifications_list

router = Router(name="notifications")
router.message.filter(IsAuthorized())
router.callback_query.filter(IsAuthorized())


@router.message(F.text == "🔔 اعلان‌ها")
async def show_notifications(message: types.Message):
    telegram_id = message.from_user.id
    notifications = await database.get_user_notifications(telegram_id)

    text = format_notifications_list(notifications)
    kb = build_notifications_keyboard(notifications)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data.startswith("ntf:read:"))
async def cb_mark_read(callback: types.CallbackQuery):
    ntf_id = int(callback.data.split(":")[2])
    await database.mark_notification_read(ntf_id)
    await callback.answer("علامت‌گذاری شد.")

    telegram_id = callback.from_user.id
    notifications = await database.get_user_notifications(telegram_id)
    text = format_notifications_list(notifications)
    kb = build_notifications_keyboard(notifications)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
