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
