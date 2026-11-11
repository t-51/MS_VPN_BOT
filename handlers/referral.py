"""هندلر سیستم بازاریابی و زیرمجموعه‌گیری."""
from aiogram import Router, F, types

from config import settings
from db import database
from filters.auth import IsAuthorized
from utils.formatters import format_referral

router = Router(name="referral")
router.message.filter(IsAuthorized())


@router.message(F.text == "🤝 زیرمجموعه")
async def show_referral_menu(message: types.Message):
    telegram_id = message.from_user.id
    ref_stats = await database.get_referral_stats(telegram_id)

    text = format_referral(ref_stats, settings.BOT_USERNAME)
    await message.answer(text, parse_mode="HTML")
