"""هندلرهای اختصاصی مدیریت ارسال خودکار کانفیگ به کانال و عضویت اجباری / قفل سین.

شامل:
  1) مدیریت ارسال خودکار کانفیگ به کانال مقصد (روشن/خاموش، کانال، روزها، ساعت‌ها، مشخصات و تست فوری).
  2) مدیریت عضویت اجباری (Force Join) در کانال‌ها (افزودن، حذف، تغییر وضعیت، تست دسترسی).
  3) مدیریت قفل سین / بازدید پست اسپانسر (Seen Lock).
"""
import logging
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from config import settings
from db import database
from keyboards.inline import (
    admin_auto_channel_keyboard,
    admin_auto_channel_days_keyboard,
    admin_auto_channel_proto_keyboard,
    admin_auto_channel_caption_keyboard,
    admin_fsub_main_keyboard,
    admin_fsub_channels_list_keyboard,
    admin_fsub_channel_detail_keyboard,
    admin_seen_lock_keyboard,
    admin_main_keyboard,
)
from keyboards.reply import cancel_keyboard, get_main_keyboard
from states.forms import (
    AdminAutoChannelStates,
    AdminForceJoinStates,
    AdminSeenLockStates,
)
from utils.channel_poster import (
    check_bot_channel_admin,
    create_and_post_channel_config,
    DAY_NAMES_FA,
    PROTO_TITLES,
)

router = Router(name="admin_channels")
logger = logging.getLogger(__name__)


def _is_admin(event: types.Message | types.CallbackQuery) -> bool:
    return settings.is_admin(event.from_user.id)


# ──────────────────────────────────────────────────────────────
#  ارسال خودکار کانفیگ به کانال مقصد (Auto Config to Channel)
# ──────────────────────────────────────────────────────────────

async def _build_auto_channel_text(conf: dict, test_status_msg: str = "") -> str:
    """تولید متن گزارش و منوی تنظیمات ارسال خودکار کانال."""
    is_on = conf.get("is_enabled", False)
    status_str = "🟢 <b>روشن (فعال)</b>" if is_on else "🔴 <b>خاموش (غیرفعال)</b>"
    ch_id = conf.get("channel_id") or "<i>هنوز تنظیم نشده</i>"

    days_list = conf.get("days_list", [])
    days_names = [DAY_NAMES_FA.get(d, d) for d in days_list]
    days_str = "، ".join(days_names) if days_names else "<i>هیچ روزی انتخاب نشده</i>"

    times_str = conf.get("times_str") or "<i>هنوز تنطیم نشده</i>"
    traffic = conf.get("traffic_gb", 1.0)
    duration = conf.get("duration_days", 1)
    proto_key = conf.get("protocol", "singbox")
    proto_name = PROTO_TITLES.get(proto_key, "Sing-box (Base64)")
    qr_str = "✅ بله (همراه با تصویر بارکد QR)" if conf.get("send_qr", True) else "❌ خیر (فقط پیام متنی)"
    last_sent = conf.get("last_sent") or "—"

    custom_cap = "دارد (سفارشی)" if conf.get("caption", "").strip() else "پیش‌فرض هوشمند سیستم"

    lines = [
        "📡 <b>کنترل پنل ارسال خودکار کانفیگ به کانال مقصد</b>\n",
        f"▫️ <b>وضعیت کلی سیستم:</b> {status_str}",
        f"▫️ <b>کانال مقصد:</b> <code>{ch_id}</code>",
        f"▫️ <b>پروتکل انتخابی:</b> <b>{proto_name}</b>",
        f"▫️ <b>روزهای ارسال:</b> {days_str}",
        f"▫️ <b>ساعات ارسال:</b> <code>{times_str}</code>",
        f"▫️ <b>حجم کانفیگ:</b> <b>{traffic} گیگابایت</b>",
        f"▫️ <b>مدت اعتبار:</b> <b>{duration} روز</b>",
        f"▫️ <b>ارسال بارکد QR:</b> {qr_str}",
        f"▫️ <b>قالب کپشن:</b> {custom_cap}",
        f"▫️ <b>آخرین ارسال موفق:</b> <code>{last_sent}</code>\n",
    ]

    if test_status_msg:
        lines.append(f"🔍 <b>نتیجه بررسی دسترسی:</b>\n{test_status_msg}\n")

    lines.append("👇 <i>از طریق گزینه‌های زیر می‌توانید تنظیمات را تغییر دهید یا فوراً یک کانفیگ تست بفرستید:</i>")
    return "\n".join(lines)


@router.callback_query(F.data == "adm:autochannel")
async def cb_admin_autochannel(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    await state.clear()

    conf = await database.get_auto_channel_settings()
    text = await _build_auto_channel_text(conf)
    await callback.message.edit_text(text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:autochannel:toggle")
async def cb_admin_autochannel_toggle(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    is_on = await database.toggle_auto_channel()
    msg = "✅ ارسال خودکار کانفیگ فعال گردید." if is_on else "🛑 ارسال خودکار کانفیگ متوقف شد."
    await callback.answer(msg, show_alert=False)

    conf = await database.get_auto_channel_settings()
    text = await _build_auto_channel_text(conf)
    await callback.message.edit_text(text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")


@router.callback_query(F.data == "adm:autochannel:toggle_qr")
async def cb_admin_autochannel_toggle_qr(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    is_qr = await database.toggle_auto_channel_qr()
    msg = "📷 ارسال تصویر QR کد فعال شد." if is_qr else "📝 ارسال فقط متنی شد."
    await callback.answer(msg)

    conf = await database.get_auto_channel_settings()
    text = await _build_auto_channel_text(conf)
    await callback.message.edit_text(text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")


@router.callback_query(F.data == "adm:autochannel:proto")
async def cb_admin_autochannel_proto(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    conf = await database.get_auto_channel_settings()
    cur_proto = conf.get("protocol", "singbox")
    text = (
        "🌐 <b>انتخاب نوع پروتکل ارسالی به کانال مقصد:</b>\n\n"
        "لطفاً یکی از پروتکل‌های زیر را جهت ساخت و ارسال خودکار به کانال انتخاب فرمایید:\n\n"
        "▫️ <b>Sing-box هوشمند:</b> پروتکل‌های VLESS Reality, VMess با لینک سابسکریپشن هوشمند <b>Base64</b> و تصویر بارکد QR.\n"
        "▫️ <b>کانفیگ‌های SlipNet:</b> تانل‌های ضد فیلتر DNS (SlowDNS / Slipstream / Tor) مخصوص اینترنت ملی و اختلالات شدید.\n"
        "▫️ <b>پروتکل‌های استاندارد:</b> اتصال مستقیم سیسکو Cisco AnyConnect، اوپن‌وی‌پی‌ان (OpenVPN)، L2TP و IKEv2.\n"
        "▫️ <b>پکیج کامل همگانی:</b> ارسال همزمان کانفیگ‌های هر سه حالت برای اعضای کانال."
    )
    await callback.message.edit_text(text, reply_markup=admin_auto_channel_proto_keyboard(cur_proto), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:autochannel:set_proto:"))
async def cb_admin_autochannel_set_proto(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    new_proto = callback.data.split(":")[3]
    await database.set_auto_channel_setting("protocol", new_proto)

    proto_name = PROTO_TITLES.get(new_proto, new_proto)
    await callback.answer(f"✅ پروتکل ارسالی بر روی «{proto_name}» تنظیم شد.", show_alert=False)

    conf = await database.get_auto_channel_settings()
    text = await _build_auto_channel_text(conf)
    await callback.message.edit_text(text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")


@router.callback_query(F.data == "adm:autochannel:test_admin")
async def cb_admin_autochannel_test_admin(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    conf = await database.get_auto_channel_settings()
    ch_id = conf.get("channel_id")
    if not ch_id:
        return await callback.answer("⚠️ ابتدا کانال مقصد را تنظیم فرمایید.", show_alert=True)

    await callback.answer("⏳ در حال استعلام وضعیت دسترسی ربات در تلگرام...")
    is_ok, status_msg = await check_bot_channel_admin(callback.bot, ch_id)

    text = await _build_auto_channel_text(conf, test_status_msg=status_msg)
    await callback.message.edit_text(text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")


@router.callback_query(F.data == "adm:autochannel:set_target")
async def cb_admin_autochannel_set_target(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await state.set_state(AdminAutoChannelStates.waiting_channel_id)
    text = (
        "📢 <b>تنظیم کانال مقصد ارسال خودکار کانفیگ:</b>\n\n"
        "لطفاً یوزرنیم یا شناسه عددی کانال مورد نظر را ارسال فرمایید.\n"
        "مثال‌ها:\n"
        "▫️ <code>@MyChannel</code>\n"
        "▫️ <code>-1001234567890</code>\n\n"
        "⚠️ <b>نکته مهم:</b> ربات حتماً باید در این کانال عضو بوده و دسترسی مدیریت (Admin) با قابلیت «ارسال پیام» داشته باشد."
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AdminAutoChannelStates.waiting_channel_id)
async def msg_admin_autochannel_target(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    if message.text in ("❌ انصراف", "❌ لغو"):
        await state.clear()
        return await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    target = message.text.strip()
    await database.set_auto_channel_target(target)
    await state.clear()

    # تست فوری دسترسی
    is_ok, test_msg = await check_bot_channel_admin(message.bot, target)

    conf = await database.get_auto_channel_settings()
    res_text = (
        f"✅ <b>کانال مقصد با موفقیت بر روی <code>{conf.get('channel_id')}</code> تنظیم شد.</b>\n\n"
        f"نتیجه بررسی دسترسی:\n{test_msg}"
    )
    await message.answer(res_text, reply_markup=get_main_keyboard(True), parse_mode="HTML")

    menu_text = await _build_auto_channel_text(conf, test_status_msg=test_msg)
    await message.answer(menu_text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")


@router.callback_query(F.data == "adm:autochannel:days")
async def cb_admin_autochannel_days(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    conf = await database.get_auto_channel_settings()
    days_list = conf.get("days_list", [])
    text = (
        "📅 <b>تنظیم روزهای هفته برای ارسال خودکار کانفیگ:</b>\n\n"
        "برای فعال یا غیرفعال کردن هر روز، روی دکمه‌ی آن کلیک کنید.\n"
        "علامت ✅ نشان‌دهنده‌ی روزهای فعال ارسال است:"
    )
    await callback.message.edit_text(text, reply_markup=admin_auto_channel_days_keyboard(days_list), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data.startswith("adm:autochannel:toggle_day:"))
async def cb_admin_autochannel_toggle_day(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    day_code = callback.data.split(":")[3]
    await database.toggle_auto_channel_day(day_code)

    conf = await database.get_auto_channel_settings()
    days_list = conf.get("days_list", [])
    await callback.message.edit_reply_markup(reply_markup=admin_auto_channel_days_keyboard(days_list))
    await callback.answer()


@router.callback_query(F.data == "adm:autochannel:days_all")
async def cb_admin_autochannel_days_all(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    all_days = "sat,sun,mon,tue,wed,thu,fri"
    await database.set_auto_channel_setting("days", all_days)
    conf = await database.get_auto_channel_settings()
    await callback.message.edit_reply_markup(reply_markup=admin_auto_channel_days_keyboard(conf.get("days_list", [])))
    await callback.answer("✅ تمام روزهای هفته فعال شدند.")


@router.callback_query(F.data == "adm:autochannel:days_none")
async def cb_admin_autochannel_days_none(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await database.set_auto_channel_setting("days", "")
    conf = await database.get_auto_channel_settings()
    await callback.message.edit_reply_markup(reply_markup=admin_auto_channel_days_keyboard([]))
    await callback.answer("❌ تمام روزها غیرفعال شدند.")


@router.callback_query(F.data == "adm:autochannel:times")
async def cb_admin_autochannel_times(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    conf = await database.get_auto_channel_settings()
    cur_times = conf.get("times_str", "12:00,20:00")
    await state.set_state(AdminAutoChannelStates.waiting_times)

    text = (
        "⏰ <b>تنظیم ساعات ارسال خودکار کانفیگ به کانال:</b>\n\n"
        f"ساعات فعلی تنظیم‌شده: <code>{cur_times}</code>\n\n"
        "لطفاً ساعات مورد نظر را با فرمت <code>HH:MM</code> و با کاما از یکدیگر جدا کرده و ارسال نمایید.\n"
        "مثال:\n"
        "▫️ <code>10:00, 14:30, 21:00</code>\n"
        "▫️ <code>12:00, 18:00</code>"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AdminAutoChannelStates.waiting_times)
async def msg_admin_autochannel_times(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    if message.text in ("❌ انصراف", "❌ لغو"):
        await state.clear()
        return await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    raw = message.text.strip()
    await database.set_auto_channel_times(raw)
    await state.clear()

    conf = await database.get_auto_channel_settings()
    await message.answer(
        f"✅ ساعات ارسال با موفقیت بر روی <code>{conf.get('times_str')}</code> تنظیم شد.",
        reply_markup=get_main_keyboard(True),
        parse_mode="HTML",
    )
    menu_text = await _build_auto_channel_text(conf)
    await message.answer(menu_text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")


@router.callback_query(F.data == "adm:autochannel:specs")
async def cb_admin_autochannel_specs(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    conf = await database.get_auto_channel_settings()
    await state.set_state(AdminAutoChannelStates.waiting_traffic)
    text = (
        "⚡ <b>تنظیم حجم و مدت زمان اعتبار کانفیگ‌های ارسالی به کانال:</b>\n\n"
        f"حجم فعلی: <b>{conf.get('traffic_gb')} گیگابایت</b>\n\n"
        "لطفاً ترافیک دلخواه برای هر کانفیگ را به عدد (گیگابایت) وارد کنید:\n"
        "مثال: <code>1</code> یا <code>2.5</code> یا <code>5</code>"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AdminAutoChannelStates.waiting_traffic)
async def msg_admin_autochannel_traffic(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    if message.text in ("❌ انصراف", "❌ لغو"):
        await state.clear()
        return await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    try:
        val = float(message.text.strip().replace("/", "."))
        if val <= 0:
            raise ValueError()
    except ValueError:
        return await message.answer("⚠️ لطفاً یک عدد معتبر و مثبت برای حجم وارد فرمایید (مثلاً 1 یا 2):")

    await state.update_data(traffic=val)
    await state.set_state(AdminAutoChannelStates.waiting_days)
    await message.answer("⏳ لطفاً مدت اعتبار زمانی کانفیگ را به عدد (تعداد روز) وارد کنید (مثلاً 1 یا 2):", reply_markup=cancel_keyboard)


@router.message(AdminAutoChannelStates.waiting_days)
async def msg_admin_autochannel_duration(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    if message.text in ("❌ انصراف", "❌ لغو"):
        await state.clear()
        return await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    try:
        days = int(message.text.strip())
        if days <= 0:
            raise ValueError()
    except ValueError:
        return await message.answer("⚠️ لطفاً یک عدد معتبر برای روز وارد فرمایید (مثلاً 1 یا 3):")

    data = await state.get_data()
    traffic = data.get("traffic", 1.0)
    await database.set_auto_channel_specs(traffic, days)
    await state.clear()

    conf = await database.get_auto_channel_settings()
    await message.answer(
        f"✅ مشخصات با موفقیت ذخیره شد:\nحجم: {traffic}GB | اعتبار: {days} روز",
        reply_markup=get_main_keyboard(True),
    )
    menu_text = await _build_auto_channel_text(conf)
    await message.answer(menu_text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")


@router.callback_query(F.data == "adm:autochannel:caption")
async def cb_admin_autochannel_caption(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    conf = await database.get_auto_channel_settings()
    cap = conf.get("caption") or ""
    has_custom = bool(cap.strip())

    text = (
        "📝 <b>مدیریت متن کپشن پست کانال:</b>\n\n"
        f"وضعیت فعلی: {'سفارشی شده' if has_custom else 'پیش‌فرض استاندارد ربات'}\n\n"
        "متن فعلی:\n"
        f"<code>{cap if has_custom else 'پیش‌فرض هوشمند (شامل حجم، انقضا، لینک ساب، QR و آیدی ربات)'}</code>"
    )
    await callback.message.edit_text(text, reply_markup=admin_auto_channel_caption_keyboard(has_custom), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:autochannel:caption_edit")
async def cb_admin_autochannel_caption_edit(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await state.set_state(AdminAutoChannelStates.waiting_caption)
    text = (
        "✏️ <b>متن کپشن دلخواه خود را ارسال فرمایید.</b>\n\n"
        "می‌توانید از متغیرهای خودکار زیر در متن استفاده کنید:\n"
        "▫️ <code>{traffic}</code>: حجم کانفیگ (گیگابایت)\n"
        "▫️ <code>{duration}</code>: مدت زمان اعتبار (روز)\n"
        "▫️ <code>{sub_url}</code>: لینک سابسکریپشن هوشمند\n"
        "▫️ <code>{direct}</code>: کانفیگ مستقیم VLESS/VMess\n"
        "▫️ <code>{bot}</code>: یوزرنیم ربات\n"
        "▫️ <code>{date}</code>: تاریخ و ساعت انتشار"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AdminAutoChannelStates.waiting_caption)
async def msg_admin_autochannel_caption(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    if message.text in ("❌ انصراف", "❌ لغو"):
        await state.clear()
        return await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    new_cap = message.text.strip()
    await database.set_auto_channel_setting("caption", new_cap)
    await state.clear()

    await message.answer("✅ متن کپشن پست کانال با موفقیت ذخیره شد.", reply_markup=get_main_keyboard(True))
    conf = await database.get_auto_channel_settings()
    menu_text = await _build_auto_channel_text(conf)
    await message.answer(menu_text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")


@router.callback_query(F.data == "adm:autochannel:caption_reset")
async def cb_admin_autochannel_caption_reset(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await database.set_auto_channel_setting("caption", "")
    await callback.answer("🔄 کپشن به قالب استاندارد پیش‌فرض بازنشانی شد.", show_alert=True)

    conf = await database.get_auto_channel_settings()
    text = await _build_auto_channel_text(conf)
    await callback.message.edit_text(text, reply_markup=admin_auto_channel_keyboard(conf), parse_mode="HTML")


@router.callback_query(F.data == "adm:autochannel:send_now")
async def cb_admin_autochannel_send_now(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    conf = await database.get_auto_channel_settings()
    ch_id = conf.get("channel_id")
    if not ch_id:
        return await callback.answer("⚠️ ابتدا کانال مقصد را تنظیم فرمایید.", show_alert=True)

    await callback.answer("⏳ در حال ساخت کانفیگ در MHPanel و ارسال مستقیم به کانال...", show_alert=False)

    res = await create_and_post_channel_config(callback.bot, force=True)
    if res.get("success"):
        await callback.message.answer(
            f"🎉 <b>کانفیگ با موفقیت در کانال {ch_id} ارسال گردید!</b>\n"
            f"▫️ اکانت پنل: <code>{res.get('username')}</code>\n"
            f"▫️ شناسه پیام ارسالی: <code>{res.get('message_id')}</code>",
            parse_mode="HTML",
        )
    else:
        err = res.get("error", "خطای ناشناخته")
        await callback.message.answer(
            f"❌ <b>خطا در ارسال به کانال:</b>\n{err}",
            parse_mode="HTML",
        )


# ──────────────────────────────────────────────────────────────
#  مدیریت عضویت اجباری (Force Join) و قفل سین (Seen Lock)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:fsub_menu")
async def cb_admin_fsub_menu(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    await state.clear()

    is_fsub_on = await database.is_force_join_enabled()
    is_seen_on = await database.is_seen_lock_enabled()
    channels = await database.get_force_join_channels(active_only=False)

    text = (
        "🔒 <b>کنترل پنل مدیریت عضویت اجباری و قفل سین (Seen Lock)</b>\n\n"
        f"▫️ <b>قفل عضویت اجباری:</b> {'🟢 فعال' if is_fsub_on else '🔴 غیرفعال'}\n"
        f"▫️ <b>تعداد کانال‌های ثبت‌شده:</b> {len(channels)} کانال\n"
        f"▫️ <b>قفل سین / اسپانسر:</b> {'🟢 فعال' if is_seen_on else '🔴 غیرفعال'}\n\n"
        "<i>با فعال بودن این قابلیت، کاربران تا زمانی که در کانال‌های تعیین‌شده عضو نشوند "
        "یا پست سین را مشاهده نکنند، امکان دریافت تست، خرید یا استفاده از دکمه‌های ربات را نخواهند داشت.</i>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_fsub_main_keyboard(is_fsub_on, is_seen_on, len(channels)),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data == "adm:fsub:toggle")
async def cb_admin_fsub_toggle(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    cur = await database.is_force_join_enabled()
    await database.set_force_join_enabled(not cur)
    new_status = not cur

    msg = "✅ قفل عضویت اجباری فعال گردید." if new_status else "🛑 قفل عضویت اجباری غیرفعال شد."
    await callback.answer(msg)

    channels = await database.get_force_join_channels(active_only=False)
    is_seen_on = await database.is_seen_lock_enabled()
    text = (
        "🔒 <b>کنترل پنل مدیریت عضویت اجباری و قفل سین</b>\n\n"
        f"▫️ <b>قفل عضویت اجباری:</b> {'🟢 فعال' if new_status else '🔴 غیرفعال'}\n"
        f"▫️ <b>تعداد کانال‌های ثبت‌شده:</b> {len(channels)} کانال\n"
        f"▫️ <b>قفل سین / اسپانسر:</b> {'🟢 فعال' if is_seen_on else '🔴 غیرفعال'}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_fsub_main_keyboard(new_status, is_seen_on, len(channels)),
        parse_mode="HTML",
    )


@router.callback_query(F.data == "adm:fsub:channels")
async def cb_admin_fsub_channels_list(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    channels = await database.get_force_join_channels(active_only=False)
    text = (
        "📢 <b>لیست کانال‌های عضویت اجباری:</b>\n\n"
        "برای مشاهده جزئیات، فعال/غیرفعال کردن یا تست دسترسی ربات در هر کانال، روی آن کلیک کنید:"
    )
    if not channels:
        text += "\n\n<i>هیچ کانالی ثبت نشده است. از دکمه زیر کانال جدید اضافه کنید.</i>"

    await callback.message.edit_text(text, reply_markup=admin_fsub_channels_list_keyboard(channels), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:fsub:add_channel")
async def cb_admin_fsub_add_channel(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await state.set_state(AdminForceJoinStates.waiting_channel_title)
    text = (
        "➕ <b>افزودن کانال جدید برای عضویت اجباری:</b>\n\n"
        "لطفاً یک عنوان یا نام نمایشی برای کانال ارسال فرمایید (مثال: کانال رسمی MS VPN):"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AdminForceJoinStates.waiting_channel_title)
async def msg_admin_fsub_title(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    if message.text in ("❌ انصراف", "❌ لغو"):
        await state.clear()
        return await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    title = message.text.strip()
    await state.update_data(channel_title=title)
    await state.set_state(AdminForceJoinStates.waiting_channel_id)

    text = (
        f"📌 عنوان کانال: <b>{title}</b>\n\n"
        "لطفاً یوزرنیم یا شناسه عددی کانال را ارسال کنید:\n"
        "مثال‌ها:\n"
        "▫️ <code>@MyChannel</code>\n"
        "▫️ <code>-100192837465</code>\n\n"
        "⚠️ <i>حتماً توجه داشته باشید ربات باید در این کانال عضو و ترجیحاً ادمین باشد تا بتواند وضعیت عضویت کاربران را استعلام کند.</i>"
    )
    await message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")


@router.message(AdminForceJoinStates.waiting_channel_id)
async def msg_admin_fsub_id(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    if message.text in ("❌ انصراف", "❌ لغو"):
        await state.clear()
        return await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    ch_id = message.text.strip()
    data = await state.get_data()
    title = data.get("channel_title", "کانال جدید")

    # تست دسترسی در کانال
    is_ok, test_msg = await check_bot_channel_admin(message.bot, ch_id)

    # افزودن به دیتابیس
    pk = await database.add_force_join_channel(title=title, channel_id=ch_id)
    await state.clear()

    res_text = (
        f"✅ <b>کانال «{title}» با موفقیت به لیست عضویت اجباری افزوده شد.</b>\n\n"
        f"▫️ شناسه: <code>{ch_id}</code>\n"
        f"▫️ وضعیت دسترسی ربات:\n{test_msg}"
    )
    await message.answer(res_text, reply_markup=get_main_keyboard(True), parse_mode="HTML")

    channels = await database.get_force_join_channels(active_only=False)
    await message.answer("📢 لیست به‌روزشده کانال‌ها:", reply_markup=admin_fsub_channels_list_keyboard(channels))


@router.callback_query(F.data.startswith("adm:fsub:view_ch:"))
async def cb_admin_fsub_view_ch(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    pk = int(callback.data.split(":")[3])
    ch = await database.get_force_join_channel(pk)
    if not ch:
        return await callback.answer("کانال یافت نشد.", show_alert=True)

    is_active = ch.get("is_active", 1) == 1
    text = (
        f"📢 <b>مشخصات کانال: {ch.get('title')}</b>\n\n"
        f"▫️ شناسه کانال: <code>{ch.get('channel_id')}</code>\n"
        f"▫️ وضعیت: {'🟢 فعال' if is_active else '🔴 غیرفعال'}\n"
        f"▫️ لینک عضویت: <code>{ch.get('invite_link') or 'لینک خودکار'}</code>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_fsub_channel_detail_keyboard(pk, is_active),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("adm:fsub:toggle_ch:"))
async def cb_admin_fsub_toggle_ch(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    pk = int(callback.data.split(":")[3])
    await database.toggle_force_join_channel(pk)
    ch = await database.get_force_join_channel(pk)
    is_active = ch.get("is_active", 1) == 1

    msg = "🟢 کانال فعال گردید." if is_active else "🔴 کانال غیرفعال شد."
    await callback.answer(msg)

    text = (
        f"📢 <b>مشخصات کانال: {ch.get('title')}</b>\n\n"
        f"▫️ شناسه کانال: <code>{ch.get('channel_id')}</code>\n"
        f"▫️ وضعیت: {'🟢 فعال' if is_active else '🔴 غیرفعال'}\n"
        f"▫️ لینک عضویت: <code>{ch.get('invite_link') or 'لینک خودکار'}</code>"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_fsub_channel_detail_keyboard(pk, is_active),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm:fsub:test_ch:"))
async def cb_admin_fsub_test_ch(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    pk = int(callback.data.split(":")[3])
    ch = await database.get_force_join_channel(pk)
    if not ch:
        return await callback.answer("کانال یافت نشد.", show_alert=True)

    ch_id = ch.get("channel_id")
    is_ok, test_msg = await check_bot_channel_admin(callback.bot, ch_id)
    await callback.answer("استعلام انجام شد.", show_alert=False)

    text = (
        f"📢 <b>مشخصات کانال: {ch.get('title')}</b>\n\n"
        f"▫️ شناسه: <code>{ch_id}</code>\n"
        f"▫️ نتیجه بررسی زنده تلگرام:\n{test_msg}"
    )
    await callback.message.edit_text(
        text,
        reply_markup=admin_fsub_channel_detail_keyboard(pk, ch.get("is_active", 1) == 1),
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("adm:fsub:del_ch:"))
async def cb_admin_fsub_del_ch(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    pk = int(callback.data.split(":")[3])
    await database.delete_force_join_channel(pk)
    await callback.answer("🗑 کانال با موفقیت حذف گردید.", show_alert=True)

    channels = await database.get_force_join_channels(active_only=False)
    await callback.message.edit_text(
        "📢 کانال حذف شد. لیست کانال‌های باقیمانده:",
        reply_markup=admin_fsub_channels_list_keyboard(channels),
    )


# ──────────────────────────────────────────────────────────────
#  مدیریت قفل سین (Seen Lock / Sponsor Post)
# ──────────────────────────────────────────────────────────────

@router.callback_query(F.data == "adm:seen:menu")
async def cb_admin_seen_menu(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)
    await state.clear()

    data = await database.get_seen_lock_settings()
    is_on = data.get("is_enabled", False)
    post_url = data.get("post_url") or "<i>هنوز تنطیم نشده</i>"
    lock_text = data.get("lock_text") or "پیش‌فرض"

    text = (
        "👁 <b>کنترل پنل تنظیمات قفل سین پست (Seen Lock / اسپانسر)</b>\n\n"
        f"▫️ <b>وضعیت قفل:</b> {'🟢 فعال' if is_on else '🔴 غیرفعال'}\n"
        f"▫️ <b>لینک پست هدف:</b> <code>{post_url}</code>\n"
        f"▫️ <b>متن راهنما:</b>\n<i>{lock_text}</i>\n\n"
        "💡 <i>در این حالت کاربر موظف است ابتدا روی لینک پست کلیک کرده و سپس دکمه تایید مشاهده را بزند تا قفل خدمات ربات باز شود.</i>"
    )
    await callback.message.edit_text(text, reply_markup=admin_seen_lock_keyboard(data), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "adm:seen:toggle")
async def cb_admin_seen_toggle(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    cur = await database.is_seen_lock_enabled()
    await database.set_seen_lock_enabled(not cur)
    new_val = not cur

    msg = "🟢 قفل سین فعال شد." if new_val else "🛑 قفل سین غیرفعال شد."
    await callback.answer(msg)

    data = await database.get_seen_lock_settings()
    post_url = data.get("post_url") or "<i>هنوز تنطیم نشده</i>"
    lock_text = data.get("lock_text") or "پیش‌فرض"
    text = (
        "👁 <b>کنترل پنل تنظیمات قفل سین پست (Seen Lock / اسپانسر)</b>\n\n"
        f"▫️ <b>وضعیت قفل:</b> {'🟢 فعال' if new_val else '🔴 غیرفعال'}\n"
        f"▫️ <b>لینک پست هدف:</b> <code>{post_url}</code>\n"
        f"▫️ <b>متن راهنما:</b>\n<i>{lock_text}</i>"
    )
    await callback.message.edit_text(text, reply_markup=admin_seen_lock_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "adm:seen:set_url")
async def cb_admin_seen_set_url(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await state.set_state(AdminSeenLockStates.waiting_post_url)
    text = (
        "🔗 <b>تنظیم آدرس لینک پست جهت قفل سین:</b>\n\n"
        "لطفاً لینک کامل پست کانال را ارسال فرمایید.\n"
        "مثال‌ها:\n"
        "▫️ <code>https://t.me/MyChannel/1234</code>\n"
        "▫️ <code>https://t.me/c/1234567890/567</code>"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AdminSeenLockStates.waiting_post_url)
async def msg_admin_seen_url(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    if message.text in ("❌ انصراف", "❌ لغو"):
        await state.clear()
        return await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    url = message.text.strip()
    if not url.startswith("http://") and not url.startswith("https://") and not url.startswith("t.me/"):
        return await message.answer("⚠️ لطفاً یک لینک معتبر تلگرامی ارسال نمایید (مثلاً https://t.me/channel/123):")

    await database.set_seen_lock_settings(post_url=url)
    await state.clear()

    await message.answer(f"✅ لینک پست با موفقیت ذخیره شد:\n<code>{url}</code>", reply_markup=get_main_keyboard(True), parse_mode="HTML")
    data = await database.get_seen_lock_settings()
    text = (
        "👁 <b>تنظیمات قفل سین بروزرسانی شد:</b>\n\n"
        f"▫️ وضعیت: {'🟢 فعال' if data.get('is_enabled') else '🔴 غیرفعال'}\n"
        f"▫️ لینک پست: <code>{data.get('post_url')}</code>"
    )
    await message.answer(text, reply_markup=admin_seen_lock_keyboard(data), parse_mode="HTML")


@router.callback_query(F.data == "adm:seen:set_text")
async def cb_admin_seen_set_text(callback: types.CallbackQuery, state: FSMContext):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    await state.set_state(AdminSeenLockStates.waiting_lock_text)
    text = (
        "📝 <b>ویرایش متن پیام راهنمای قفل سین:</b>\n\n"
        "لطفاً متنی که می‌خواهید به عنوان راهنما هنگام قفل بودن به کاربران نمایش داده شود را ارسال کنید:"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(AdminSeenLockStates.waiting_lock_text)
async def msg_admin_seen_text(message: types.Message, state: FSMContext):
    if not _is_admin(message):
        return
    if message.text in ("❌ انصراف", "❌ لغو"):
        await state.clear()
        return await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(True))

    new_text = message.text.strip()
    await database.set_seen_lock_settings(lock_text=new_text)
    await state.clear()

    await message.answer("✅ متن راهنمای قفل سین با موفقیت ذخیره شد.", reply_markup=get_main_keyboard(True))
    data = await database.get_seen_lock_settings()
    await message.answer("👁 تنظیمات قفل سین:", reply_markup=admin_seen_lock_keyboard(data))


@router.callback_query(F.data == "adm:seen:reset_text")
async def cb_admin_seen_reset_text(callback: types.CallbackQuery):
    if not _is_admin(callback):
        return await callback.answer("دسترسی غیرمجاز", show_alert=True)

    default_txt = "جهت استفاده از خدمات ربات، لطفاً از پست اسپانسر دیدن کرده و دکمه تایید مشاهده را لمس نمایید."
    await database.set_seen_lock_settings(lock_text=default_txt)
    await callback.answer("🔄 متن به حالت پیش‌فرض بازگردانده شد.", show_alert=True)

    data = await database.get_seen_lock_settings()
    text = (
        "👁 <b>کنترل پنل تنظیمات قفل سین پست</b>\n\n"
        f"▫️ وضعیت: {'🟢 فعال' if data.get('is_enabled') else '🔴 غیرفعال'}\n"
        f"▫️ لینک پست: <code>{data.get('post_url') or 'تنظیم نشده'}</code>\n"
        f"▫️ متن راهنما: <i>{data.get('lock_text')}</i>"
    )
    await callback.message.edit_text(text, reply_markup=admin_seen_lock_keyboard(data), parse_mode="HTML")
