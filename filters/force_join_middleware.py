"""میدلور سراسری جهت اعمال قفل عضویت اجباری در کانال‌ها و قفل سین (Seen Lock).

این میدلور مانع از اجرای هرگونه فعالیت کاربری (دریافت تست، خرید اشتراک، مشاهده کیف پول و...)
تا زمان احراز عضویت کامل در کانال‌های اعلامی توسط مدیریت و گذراندن قفل سین می‌گردد.
مدیران ربات از این قفل معاف هستند.
"""
import logging
from typing import Callable, Dict, Any, Awaitable

from aiogram import BaseMiddleware
from aiogram.types import TelegramObject, Message, CallbackQuery

from config import settings
from utils.force_join import (
    check_user_membership,
    build_force_join_keyboard,
    get_force_join_message_text,
)

logger = logging.getLogger("MS_VPN_BOT.ForceJoinMiddleware")

# کال‌بک‌هایی که برای تایید عضویت هستند و نباید بلاک شوند
EXEMPT_CALLBACKS = {"check_fsub", "seen:confirm"}


class ForceJoinMiddleware(BaseMiddleware):
    async def __call__(
        self,
        handler: Callable[[TelegramObject, Dict[str, Any]], Awaitable[Any]],
        event: TelegramObject,
        data: Dict[str, Any],
    ) -> Any:
        bot = data.get("bot")
        if not bot:
            return await handler(event, data)

        # دریافت کاربر فرستنده
        user = getattr(event, "from_user", None)
        if not user:
            return await handler(event, data)

        user_id = user.id

        # ۱. ادمین‌های ربات همواره اجازه عبور دارند
        if settings.is_admin(user_id):
            return await handler(event, data)

        # ۲. بررسی کال‌بک‌های مجاز مربوط به بررسی قفل
        if isinstance(event, CallbackQuery):
            if event.data in EXEMPT_CALLBACKS or (event.data and event.data.startswith("seen:")):
                return await handler(event, data)

        # ۳. اعتبارسنجی عضویت و قفل سین
        try:
            is_allowed, unjoined_channels, seen_needed, seen_settings = await check_user_membership(bot, user_id)
        except Exception as e:
            logger.error(f"خطا در اعتبارسنجی عضویت اجباری: {e}")
            return await handler(event, data)

        if is_allowed:
            return await handler(event, data)

        # کاربر شرایط لازم را ندارد؛ نمایش پیام هشدار و متوقف‌سازی جریان
        text = get_force_join_message_text(unjoined_channels, seen_needed, seen_settings)
        kb = build_force_join_keyboard(unjoined_channels, seen_needed, seen_settings)

        if isinstance(event, Message):
            await event.answer(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
        elif isinstance(event, CallbackQuery):
            await event.answer("⚠️ لطفاً ابتدا در کانال‌های تعیین‌شده عضو شوید یا پست را تایید کنید.", show_alert=True)
            try:
                await event.message.edit_text(text, reply_markup=kb, parse_mode="HTML", disable_web_page_preview=True)
            except Exception:
                pass

        # متوقف کردن ادامه فرآیند برای کاربر غیرمجاز
        return
