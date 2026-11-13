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
    get_app_center_main_text,
    get_os_guide_text,
    get_proto_guide_text,
    get_all_client_downloads,
)

router = Router(name="downloads")
router.message.filter(IsAuthorized())
router.callback_query.filter(IsAuthorized())


@router.message(F.text == "📲 دانلود نرم‌افزارها")
async def show_apps_center_menu(message: types.Message):
    """نمایش منوی اصلی مرکز دانلود نرم‌افزارها."""
    text = await get_app_center_main_text()
    await message.answer(
        text,
        reply_markup=build_apps_center_keyboard(),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "app:center")
async def cb_apps_center_return(callback: types.CallbackQuery):
    """بازگشت به منوی اصلی مرکز دانلود."""
    text = await get_app_center_main_text()
    await callback.message.edit_text(
        text,
        reply_markup=build_apps_center_keyboard(),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("app:os:"))
async def cb_apps_os_detail(callback: types.CallbackQuery):
    """نمایش نرم‌افزارهای سازگار با یک سیستم‌عامل خاص."""
    os_key = callback.data.split(":")[2]
    guide = await get_os_guide_text(os_key)
    if not guide:
        return await callback.answer("سیستم‌عامل مورد نظر یافت نشد.", show_alert=True)

    dl_links = await get_all_client_downloads()
    await callback.message.edit_text(
        guide,
        reply_markup=build_apps_os_detail_keyboard(os_key, dl_links),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()


@router.callback_query(F.data.startswith("app:proto:"))
async def cb_apps_proto_detail(callback: types.CallbackQuery):
    """نمایش نرم‌افزارهای سازگار با یک پروتکل خاص."""
    proto_key = callback.data.split(":")[2]
    guide = await get_proto_guide_text(proto_key)
    if not guide:
        return await callback.answer("پروتکل مورد نظر یافت نشد.", show_alert=True)

    dl_links = await get_all_client_downloads()
    await callback.message.edit_text(
        guide,
        reply_markup=build_apps_proto_detail_keyboard(proto_key, dl_links),
        parse_mode="HTML",
        disable_web_page_preview=True,
    )
    await callback.answer()

