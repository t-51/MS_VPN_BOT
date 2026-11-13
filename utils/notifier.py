"""ماژول ارسال اعلان‌های آن‌تایم و لحظه‌ای به مدیران برای خریدها و دریافت اکانت‌های تستی."""
import logging
from datetime import datetime
from typing import Dict, Any, Optional, List

from aiogram import Bot

from config import settings
from db import database
from utils.helpers import to_toman, to_fa

logger = logging.getLogger("MS_VPN_BOT.notifier")


async def get_all_admin_telegram_ids() -> List[int]:
    """دریافت شناسه‌های عددی کلیه مدیران ربات (مدیران پایه .env + مدیران داینامیک دیتابیس)."""
    admin_ids = set(settings.ADMIN_IDS)
    try:
        admins = await database.get_all_admins()
        for a in admins:
            if a.get("telegram_id"):
                admin_ids.add(int(a["telegram_id"]))
    except Exception as e:
        logger.warning(f"خطا در خواندن لیست ادمین‌ها: {e}")
    return list(admin_ids)


async def is_purchase_notification_enabled() -> bool:
    """بررسی فعال بودن اعلان خرید به مدیران (پیش‌فرض: فعال)."""
    val = await database.get_setting("notify_admin_purchases", "1")
    return val == "1"


async def toggle_purchase_notification() -> bool:
    """تغییر وضعیت فعال/غیرفعال اعلان خرید."""
    curr = await is_purchase_notification_enabled()
    new_val = "0" if curr else "1"
    await database.set_setting("notify_admin_purchases", new_val)
    return new_val == "1"


async def is_trial_notification_enabled() -> bool:
    """بررسی فعال بودن اعلان تست رایگان به مدیران (پیش‌فرض: فعال)."""
    val = await database.get_setting("notify_admin_trials", "1")
    return val == "1"


async def toggle_trial_notification() -> bool:
    """تغییر وضعیت فعال/غیرفعال اعلان اکانت تست."""
    curr = await is_trial_notification_enabled()
    new_val = "0" if curr else "1"
    await database.set_setting("notify_admin_trials", new_val)
    return new_val == "1"


async def notify_admin_purchase(
    bot: Bot,
    telegram_id: int,
    user_info: Optional[Dict[str, Any]],
    plan: Dict[str, Any],
    category_title: str,
    panel_username: str,
    price: int,
):
    """ارسال اعلان آنی و زنده خرید اشتراک به کلیه مدیران ربات."""
    try:
        if not await is_purchase_notification_enabled():
            return

        admin_ids = await get_all_admin_telegram_ids()
        if not admin_ids:
            return

        username = (user_info.get("username") if user_info else "") or "—"
        first_name = (user_info.get("first_name") if user_info else "") or "کاربر"
        plan_name = plan.get("name", "پلن نامشخص")
        traffic_gb = plan.get("traffic_gb", 0)
        duration_days = plan.get("duration_days", 0)
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        text = (
            "🛒 <b>گزارش آنی خرید اشتراک جدید!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>خریدار:</b> <code>{telegram_id}</code> (@{username} | {first_name})\n"
            f"🏷 <b>پلن خریداری‌شده:</b> <b>{plan_name}</b>\n"
            f"📁 <b>دسته‌بندی/پروتکل:</b> <b>{category_title}</b>\n"
            f"💰 <b>مبلغ پرداختی:</b> <b>{to_toman(price)}</b>\n"
            f"📶 <b>حجم ترافیک:</b> <b>{to_fa(traffic_gb)} گیگابایت</b>\n"
            f"⏱ <b>مدت اعتبار:</b> <b>{to_fa(duration_days)} روز</b>\n"
            f"👤 <b>نام کاربری در پنل:</b> <code>{panel_username}</code>\n"
            f"🕒 <b>زمان ثبت خرید:</b> <code>{time_str}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>سرویس با موفقیت صادر و تحویل کاربر گردید.</i>"
        )

        sent_count = 0
        for adm_id in admin_ids:
            try:
                await bot.send_message(adm_id, text, parse_mode="HTML")
                sent_count += 1
            except Exception as e:
                logger.warning(f"خطا در ارسال پیام خرید به مدیر {adm_id}: {e}")
        return sent_count

    except Exception as e:
        logger.error(f"خطای پیش‌بینی‌نشده در اعلان خرید به ادمین: {e}")
        return 0


async def notify_admin_trial(
    bot: Bot,
    telegram_id: int,
    user_info: Optional[Dict[str, Any]],
    mode: str,
    trial_gb: float,
    trial_days: int,
    res: Dict[str, Any],
):
    """ارسال اعلان آنی و زنده دریافت اکانت تستی به کلیه مدیران ربات."""
    try:
        if not await is_trial_notification_enabled():
            return

        admin_ids = await get_all_admin_telegram_ids()
        if not admin_ids:
            return

        username = (user_info.get("username") if user_info else "") or "—"
        first_name = (user_info.get("first_name") if user_info else "") or "کاربر"
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        mode_labels = {
            "all": "🌟 پکیج کامل (تمام حالت‌ها)",
            "singbox": "🚀 Sing-box و V2Ray",
            "system_l2tp": "🛡️ پروتکل‌های سیستمی (Cisco / L2TP)",
            "wireguard": "⚡ وایرگارد (WireGuard)",
            "dnstt": "🌐 تانل ضد فیلتر DNS (SlowDNS / SlipNet)",
        }
        mode_str = mode_labels.get(mode, mode)

        unames = []
        if mode == "all":
            sb_u = res.get("singbox", {}).get("username")
            sys_u = res.get("system_l2tp", {}).get("username")
            wg_u = res.get("wireguard", {}).get("username")
            dns_u = res.get("dnstt", {}).get("username")
            if sb_u: unames.append(f"Singbox: {sb_u}")
            if sys_u: unames.append(f"L2TP: {sys_u}")
            if wg_u: unames.append(f"WG: {wg_u}")
            if dns_u: unames.append(f"DNS: {dns_u}")
        else:
            u = res.get("username")
            if u: unames.append(u)

        uname_text = "\n".join([f"▫️ <code>{u}</code>" for u in unames]) if unames else "—"

        text = (
            "🎁 <b>گزارش آنی صدور اکانت تستی رایگان!</b>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            f"👤 <b>کاربر دریافت‌کننده:</b> <code>{telegram_id}</code> (@{username} | {first_name})\n"
            f"📁 <b>حالت تستی انتخابی:</b> <b>{mode_str}</b>\n"
            f"📶 <b>حجم ترافیک هدیه:</b> <b>{to_fa(trial_gb)} گیگابایت</b>\n"
            f"⏱ <b>مدت اعتبار تست:</b> <b>{to_fa(trial_days)} روز</b>\n"
            f"👤 <b>نام کاربری صادرشده در پنل:</b>\n{uname_text}\n"
            f"🕒 <b>زمان صدور:</b> <code>{time_str}</code>\n"
            "━━━━━━━━━━━━━━━━━━━━\n"
            "💡 <i>این اکانت پس از پایان مهلت تست، به صورت خودکار از پنل حذف خواهد شد.</i>"
        )

        sent_count = 0
        for adm_id in admin_ids:
            try:
                await bot.send_message(adm_id, text, parse_mode="HTML")
                sent_count += 1
            except Exception as e:
                logger.warning(f"خطا در ارسال پیام تست به مدیر {adm_id}: {e}")
        return sent_count

    except Exception as e:
        logger.error(f"خطای پیش‌بینی‌نشده در اعلان تست به ادمین: {e}")
        return 0
