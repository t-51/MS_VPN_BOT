"""هندلر پروفایل کاربر — نمایش مشخصات، موجودی، تعداد اشتراک‌ها و آمار زیرمجموعه."""
from aiogram import Router, F, types

from db import database
from filters.auth import IsAuthorized
from utils.formatters import format_profile

router = Router(name="profile")
router.message.filter(IsAuthorized())


@router.message(F.text == "👤 پروفایل")
async def show_profile(message: types.Message):
    telegram_id = message.from_user.id
    user = await database.get_user(telegram_id)
    if not user:
        user = await database.get_or_create_user(telegram_id, message.from_user.username, message.from_user.first_name)

    accounts = await database.get_user_accounts(telegram_id)
    ref_stats = await database.get_referral_stats(telegram_id)

    text = format_profile(user, len(accounts), ref_stats)
    await message.answer(text, parse_mode="HTML")
