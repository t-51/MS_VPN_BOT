"""هندلر مرکز دانلود نرم‌افزارها: ارائه ماتریس سازگاری پروتکل‌ها و لینک‌های دانلود رسمی."""
from aiogram import Router, F, types

from filters.auth import IsAuthorized
from keyboards.inline import (
    build_apps_center_keyboard,
    build_apps_os_detail_keyboard,
    build_apps_proto_detail_keyboard,
)
from keyboards.reply import main_menu_keyboard
from utils.tutorials import (
    APP_CENTER_MAIN_TEXT,
    OS_APP_GUIDES,
    PROTO_APP_GUIDES,
)

router = Router(name="downloads")
router.message.filter(IsAuthorized())
router.callback_query.filter(IsAuthorized())


@router.message(F.text == "📲 دانلود نرم‌افزارها")
async def show_apps_center_menu(message: types.Message):
    """نمایش منوی اصلی مرکز دانلود نرم‌افزارها."""
    await message.answer(
        APP_CENTER_MAIN_TEXT,
        reply_markup=build_apps_center_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "app:center")
async def cb_apps_center_return(callback: types.CallbackQuery):
    """بازگشت به منوی اصلی مرکز دانلود."""
    await callback.message.edit_text(
        APP_CENTER_MAIN_TEXT,
        reply_markup=build_apps_center_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("app:os:"))
async def cb_apps_os_detail(callback: types.CallbackQuery):
    """نمایش نرم‌افزارهای سازگار با یک سیستم‌عامل خاص."""
    os_key = callback.data.split(":")[2]
    guide = OS_APP_GUIDES.get(os_key)
    if not guide:
        return await callback.answer("سیستم‌عامل مورد نظر یافت نشد.", show_alert=True)

    await callback.message.edit_text(
        guide,
        reply_markup=build_apps_os_detail_keyboard(os_key),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("app:proto:"))
async def cb_apps_proto_detail(callback: types.CallbackQuery):
    """نمایش نرم‌افزارهای سازگار با یک پروتکل خاص."""
    proto_key = callback.data.split(":")[2]
    guide = PROTO_APP_GUIDES.get(proto_key)
    if not guide:
        return await callback.answer("پروتکل مورد نظر یافت نشد.", show_alert=True)

    await callback.message.edit_text(
        guide,
        reply_markup=build_apps_proto_detail_keyboard(proto_key),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()
