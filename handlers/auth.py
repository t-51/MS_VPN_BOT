"""هندلر احراز هویت و شروع به کار ربات MS_VPN_BOT."""
import logging
from aiogram import Router, F, types
from aiogram.filters import Command, CommandStart

from config import settings
from db import database
from keyboards.reply import get_main_keyboard

router = Router(name="auth")
logger = logging.getLogger(__name__)

_REF_PREFIX = "ref_"


@router.message(CommandStart())
async def cmd_start(message: types.Message):
    """شروع به کار ربات و پردازش لینک معرف (زیرمجموعه‌گیری)."""
    telegram_id = message.from_user.id
    username = message.from_user.username
    first_name = message.from_user.first_name

    referrer_id = None
    parts = message.text.split(maxsplit=1)
    if len(parts) > 1 and parts[1].startswith(_REF_PREFIX):
        raw_ref = parts[1][len(_REF_PREFIX):].strip()
        if raw_ref.isdigit() and int(raw_ref) != telegram_id:
            referrer_id = int(raw_ref)

    user = await database.get_or_create_user(
        telegram_id=telegram_id,
        username=username,
        first_name=first_name,
        referrer_id=referrer_id,
    )

    is_admin = settings.is_admin(telegram_id)
    kb = get_main_keyboard(is_admin)

    welcome_text = (
        f"👋 سلام <b>{first_name or 'کاربر گرامی'}</b>، به ربات <b>MS VPN</b> خوش آمدید!\n\n"
        "🚀 <b>مرکز جامع ارائه اشتراک‌های ضد فیلترینگ متصل به سامانه سازمانی MHPanel</b>\n\n"
        "⚡ <b>سرویس‌های قابل ارائه:</b>\n"
        "▫️ <b>سوئیت هوشمند Sing-box:</b> پروتکل‌های VLESS Reality, VMess, Trojan, Hysteria 2 و TUIC v5 با لینک هوشمند سابسکریپشن\n"
        "▫️ <b>پروتکل‌های سیستمی مستقیم:</b> بدون نرم‌افزار جانبی بر بستر L2TP, IKEv2 و IPsec\n"
        "▫️ <b>تانل اضطراری DNS (SlowDNS):</b> برای دور زدن فیلترینگ شدید و اینترنت ملی\n"
        "▫️ دریافت آنی اکانت تستی رایگان (۱ روزه)\n"
        "▫️ شارژ کیف پول و تحویل خودکار و فوری اشتراک\n\n"
        "👇 لطفاً از منوی زیر گزینه مورد نظر را انتخاب فرمایید:"
    )

    await message.answer(welcome_text, reply_markup=kb, parse_mode="HTML")


from keyboards.inline import build_tutorials_main_keyboard, build_tutorial_back_keyboard
from utils.tutorials import get_tutorial_text, get_all_client_downloads


@router.message(Command("help"))
@router.message(F.text == "❓ راهنمای اتصال")
async def show_connection_help(message: types.Message):
    text = await get_tutorial_text("main")
    await message.answer(
        text,
        reply_markup=build_tutorials_main_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "tut:main")
async def cb_tut_main(callback: types.CallbackQuery):
    text = await get_tutorial_text("main")
    await callback.message.edit_text(
        text,
        reply_markup=build_tutorials_main_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tut:view:"))
async def cb_tut_view(callback: types.CallbackQuery):
    tut_key = callback.data.split(":")[2]
    text = await get_tutorial_text(tut_key)
    dl_links = await get_all_client_downloads()
    await callback.message.edit_text(
        text,
        reply_markup=build_tutorial_back_keyboard(tut_key, dl_links),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()



@router.callback_query(F.data == "tut:close")
async def cb_tut_close(callback: types.CallbackQuery):
    await callback.message.delete()
    await callback.answer()


@router.callback_query(F.data == "menu:home")
async def cb_menu_home(callback: types.CallbackQuery):
    """بازگشت به صفحه اصلی و راهنمای منو."""
    is_admin = settings.is_admin(callback.from_user.id)
    kb = get_main_keyboard(is_admin)
    try:
        await callback.message.delete()
    except Exception:
        pass
    await callback.message.answer(
        "🏠 <b>به منوی اصلی بازگشتید.</b>\nجهت استفاده از خدمات، یکی از دکمه‌های زیر را لمس فرمایید:",
        reply_markup=kb,
        parse_mode="HTML",
    )
    await callback.answer()


# ── هندلرهای تایید عضویت اجباری و قفل سین ───────────────────

@router.callback_query(F.data == "seen:confirm")
async def cb_seen_confirm(callback: types.CallbackQuery):
    """تایید مشاهده پست اسپانسر توسط کاربر و ثبت در دیتابیس."""
    from utils.force_join import check_user_membership, build_force_join_keyboard, get_force_join_message_text

    user_id = callback.from_user.id
    seen_settings = await database.get_seen_lock_settings()
    post_url = seen_settings.get("post_url", "").strip()

    if post_url:
        await database.record_user_seen(user_id, post_url)

    is_allowed, unjoined_channels, seen_needed, seen_settings = await check_user_membership(callback.bot, user_id)
    if is_allowed:
        await callback.answer("✅ مشاهده پست و عضویت شما تایید گردید!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        kb = get_main_keyboard(settings.is_admin(user_id))
        return await callback.message.answer(
            "🎉 <b>قفل ربات با موفقیت باز شد!</b>\nاکنون می‌توانید از تمامی امکانات و اشتراک‌ها استفاده فرمایید:",
            reply_markup=kb,
            parse_mode="HTML",
        )

    await callback.answer("✅ مشاهده پست تایید شد، اما هنوز در کانال‌های تعیین‌شده عضو نشده‌اید.", show_alert=True)
    text = get_force_join_message_text(unjoined_channels, seen_needed, seen_settings)
    new_kb = build_force_join_keyboard(unjoined_channels, seen_needed, seen_settings)
    try:
        await callback.message.edit_text(text, reply_markup=new_kb, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass


@router.callback_query(F.data == "check_fsub")
async def cb_check_fsub(callback: types.CallbackQuery):
    """بررسی مجدد وضعیت عضویت کاربر در کانال‌ها و وضعیت قفل سین."""
    from utils.force_join import check_user_membership, build_force_join_keyboard, get_force_join_message_text

    user_id = callback.from_user.id
    is_allowed, unjoined_channels, seen_needed, seen_settings = await check_user_membership(callback.bot, user_id)

    if is_allowed:
        await callback.answer("✅ عضویت شما با موفقیت تأیید شد. خوش آمدید!", show_alert=True)
        try:
            await callback.message.delete()
        except Exception:
            pass
        kb = get_main_keyboard(settings.is_admin(user_id))
        return await callback.message.answer(
            "🎉 <b>خوش آمدید! قفل ربات با موفقیت باز شد.</b>\nلطفاً از منوی زیر گزینه‌ی مورد نظر خود را انتخاب کنید:",
            reply_markup=kb,
            parse_mode="HTML",
        )

    await callback.answer(
        "❌ شما هنوز در تمامی کانال‌ها عضو نشده‌اید یا پست را تایید نکرده‌اید! لطفاً ابتدا اقدام نمایید.",
        show_alert=True,
    )
    text = get_force_join_message_text(unjoined_channels, seen_needed, seen_settings)
    new_kb = build_force_join_keyboard(unjoined_channels, seen_needed, seen_settings)
    try:
        await callback.message.edit_text(text, reply_markup=new_kb, parse_mode="HTML", disable_web_page_preview=True)
    except Exception:
        pass

