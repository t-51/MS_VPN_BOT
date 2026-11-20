"""ماژول جامع مدیریت عضویت اجباری (Force Join) و قفل سین (Seen Lock).

این ماژول وظیفه اعتبارسنجی عضویت کاربران در کانال‌های تعیین‌شده توسط مدیر
و همچنین بررسی قفل بازدید از پست‌های اسپانسر (سین زدن) را بر عهده دارد.
"""
import logging
from typing import Dict, Any, List, Tuple

from aiogram import Bot
from aiogram.types import InlineKeyboardMarkup
from aiogram.utils.keyboard import InlineKeyboardBuilder

from config import settings
from db import database

logger = logging.getLogger("MS_VPN_BOT.force_join")

ALLOWED_CHAT_STATUSES = {"member", "administrator", "creator", "restricted"}


async def check_user_membership(
    bot: Bot,
    user_id: int,
) -> Tuple[bool, List[Dict[str, Any]], bool, Dict[str, Any]]:
    """بررسی کامل عضویت کاربر در کانال‌ها و وضعیت قفل سین.

    خروجی:
      - is_allowed: آیا کاربر اجازه دسترسی دارد؟ (bool)
      - unjoined_channels: لیست کانال‌هایی که کاربر هنوز در آن‌ها عضو نشده است.
      - seen_needed: آیا کاربر نیاز به مشاهده و تایید پست سین دارد؟ (bool)
      - seen_settings: اطلاعات قفل سین فعلی.
    """
    # ادمین‌های ربات همواره معاف هستند و دسترسی نامحدود دارند
    if settings.is_admin(user_id):
        return True, [], False, {}

    unjoined_channels: List[Dict[str, Any]] = []
    seen_needed = False
    seen_settings = await database.get_seen_lock_settings()

    # ۱. بررسی عضویت اجباری در کانال‌ها
    if await database.is_force_join_enabled():
        channels = await database.get_force_join_channels(active_only=True)
        for ch in channels:
            ch_id = ch.get("channel_id")
            try:
                member = await bot.get_chat_member(chat_id=ch_id, user_id=user_id)
                status = getattr(member, "status", "")
                # در وضعیت restricted بررسی شود که آیا واقعا عضو است
                if status == "restricted":
                    is_member = getattr(member, "is_member", False)
                    if not is_member:
                        unjoined_channels.append(ch)
                elif status not in ALLOWED_CHAT_STATUSES:
                    unjoined_channels.append(ch)
            except Exception as e:
                # در صورتی که کاربر عضو نباشد خطای ChatNotFound یا UserNotParticipant می‌دهد
                err_str = str(e).lower()
                if "not a member" in err_str or "user not found" in err_str or "participant" in err_str:
                    unjoined_channels.append(ch)
                else:
                    logger.warning(f"خطا در بررسی عضویت کاربر {user_id} در کانال {ch_id}: {e}")
                    # در خطاهای سیستمی تلگرام کاربر را مسدود نکنیم مگر اینکه خطای قطعی عدم عضویت باشد

    # ۲. بررسی قفل سین (Seen Lock)
    if seen_settings.get("is_enabled"):
        post_url = seen_settings.get("post_url", "").strip()
        if post_url:
            has_seen = await database.has_user_seen(user_id, post_url)
            if not has_seen:
                seen_needed = True

    is_allowed = (len(unjoined_channels) == 0) and (not seen_needed)
    return is_allowed, unjoined_channels, seen_needed, seen_settings


def build_force_join_keyboard(
    unjoined_channels: List[Dict[str, Any]],
    seen_needed: bool,
    seen_settings: Dict[str, Any],
) -> InlineKeyboardMarkup:
    """ساخت کیبورد شیشه‌ای عضویت در کانال‌ها و تایید قفل سین."""
    kb = InlineKeyboardBuilder()

    # ۱. دکمه‌های عضویت در کانال‌ها
    for idx, ch in enumerate(unjoined_channels, start=1):
        title = ch.get("title") or f"کانال شماره {idx}"
        link = ch.get("invite_link")
        if not link:
            ch_id = ch.get("channel_id", "")
            if ch_id.startswith("@"):
                link = f"https://t.me/{ch_id.lstrip('@')}"
            else:
                link = settings.CHANNEL_LINK
        kb.button(text=f"📢 {idx}. عضویت در {title}", url=link)

    # ۲. دکمه‌های مربوط به قفل سین
    if seen_needed:
        post_url = seen_settings.get("post_url", "")
        if post_url:
            kb.button(text="👁 ۱. مشاهده و بازدید پست اسپانسر", url=post_url)
        kb.button(text="✅ ۲. تایید مشاهده پست", callback_data="seen:confirm")

    # ۳. دکمه اصلی بررسی مجدد
    kb.button(text="🔄 بررسی عضویت و ورود به ربات", callback_data="check_fsub")

    # چیدمان تک‌ستونه برای راحتی کاربر
    kb.adjust(1)
    return kb.as_markup()


def get_force_join_message_text(
    unjoined_channels: List[Dict[str, Any]],
    seen_needed: bool,
    seen_settings: Dict[str, Any],
) -> str:
    """متن راهنمای قفل عضویت اجباری و قفل سین."""
    lines = [
        "⚠️ <b>کاربر گرامی، دسترسی به ربات موقتاً محدود است!</b>\n",
    ]

    if unjoined_channels:
        lines.append("📌 برای حمایت از ما و استفاده رایگان از خدمات، لطفاً ابتدا در کانال(های) زیر عضو شوید:")
        for idx, ch in enumerate(unjoined_channels, start=1):
            lines.append(f"▫️ {idx}. <b>{ch.get('title')}</b>")
        lines.append("")

    if seen_needed:
        custom_txt = seen_settings.get("lock_text") or "لطفاً روی دکمه مشاهده پست کلیک کرده و پس از دیدن پست، دکمه تایید را لمس نمایید."
        lines.append("👁 <b>قفل بازدید پست (اسپانسر):</b>")
        lines.append(f"▫️ {custom_txt}\n")

    lines.append("👇 <i>پس از عضویت و مشاهده پست، دکمه‌ی «🔄 بررسی عضویت و ورود به ربات» را لمس کنید:</i>")
    return "\n".join(lines)
