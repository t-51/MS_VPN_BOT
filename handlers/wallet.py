"""هندلر کیف پول: نمایش موجودی، شارژ کارت‌به‌کارت و ارسال هشدار آنی فیش به ادمین."""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from config import settings
from db import database
from filters.auth import IsAuthorized
from keyboards.inline import wallet_keyboard, admin_tx_keyboard
from keyboards.reply import cancel_keyboard, get_main_keyboard
from states.forms import ChargeCardStates
from utils.helpers import to_toman, to_fa
from utils.formatters import format_gateways

router = Router(name="wallet")
router.message.filter(IsAuthorized())
router.callback_query.filter(IsAuthorized())


@router.message(F.text == "❌ لغو")
async def cancel_form(message: types.Message, state: FSMContext):
    await state.clear()
    is_admin = settings.is_admin(message.from_user.id)
    await message.answer("عملیات لغو شد.", reply_markup=get_main_keyboard(is_admin))


@router.message(F.text == "💰 کیف پول")
async def show_wallet_menu(message: types.Message):
    telegram_id = message.from_user.id
    user = await database.get_user(telegram_id)
    if not user:
        user = await database.get_or_create_user(telegram_id, message.from_user.username, message.from_user.first_name)

    balance = user.get("wallet_balance", 0)
    text = (
        "💰 <b>کیف پول و مدیریت حساب مالی</b>\n\n"
        f"💵 موجودی فعلی حساب شما: <b>{to_toman(balance)}</b>\n\n"
        "جهت افزایش موجودی، یکی از گزینه‌های زیر را انتخاب فرمایید:"
    )
    await message.answer(text, reply_markup=wallet_keyboard(), parse_mode="HTML")


@router.callback_query(F.data == "wllt:info")
async def cb_wallet_info(callback: types.CallbackQuery):
    card = await database.get_random_bank_card()
    card_num = card.get("card_number")
    card_hl = card.get("card_holder")

    text = format_gateways(card_num, card_hl)
    from aiogram.utils.keyboard import InlineKeyboardBuilder
    kb = InlineKeyboardBuilder()
    kb.button(text="💳 شارژ با کارت‌به‌کارت", callback_data="wllt:card")
    kb.button(text="🔙 بازگشت به کیف پول", callback_data="wllt:menu")
    kb.adjust(1)
    await callback.message.edit_text(text, reply_markup=kb.as_markup(), parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "wllt:card")
async def cb_charge_card_start(callback: types.CallbackQuery, state: FSMContext):
    card = await database.get_random_bank_card()
    card_num = card.get("card_number")
    card_hl = card.get("card_holder")

    await state.set_state(ChargeCardStates.waiting_amount)
    await state.update_data(assigned_card=card_num, assigned_holder=card_hl)

    text = (
        "💳 <b>شارژ موجودی با کارت‌به‌کارت</b>\n\n"
        f"💳 شماره کارت جهت واریز:\n<code>{card_num}</code>\n"
        f"به نام: <b>{card_hl}</b>\n\n"
        "📌 لطفاً مبلغ واریزی خود را به تومان (فقط عدد لاتین) ارسال فرمایید:"
    )
    await callback.message.answer(text, reply_markup=cancel_keyboard, parse_mode="HTML")
    await callback.answer()


@router.message(ChargeCardStates.waiting_amount)
async def state_charge_amount(message: types.Message, state: FSMContext):
    raw = message.text.strip().replace(",", "").replace("،", "")
    if not raw.isdigit() or int(raw) < 1000:
        return await message.answer("❌ لطفاً مبلغ معتبر (حداقل ۱,۰۰۰ تومان) به عدد ارسال کنید:")

    await state.update_data(amount=int(raw))
    await state.set_state(ChargeCardStates.waiting_tracking)
    await message.answer(
        f"✅ مبلغ <b>{to_toman(raw)}</b> ثبت شد.\n\n"
        "🧾 لطفاً <b>تصویر رسید واریزی (عکس فیش)</b> یا <b>شماره پیگیری / کد ارجاع</b> را ارسال فرمایید:",
        parse_mode="HTML",
        reply_markup=cancel_keyboard,
    )


@router.message(ChargeCardStates.waiting_tracking)
async def state_charge_tracking(message: types.Message, state: FSMContext):
    photo_file_id = None
    tracking = ""

    if message.photo:
        photo_file_id = message.photo[-1].file_id
        tracking = message.caption.strip() if message.caption else "تصویر رسید پرداخت پیوست شد"
    elif message.document:
        photo_file_id = message.document.file_id
        tracking = message.caption.strip() if message.caption else f"سند فیش: {message.document.file_name or 'فایل'}"
    elif message.text:
        tracking = message.text.strip()
    else:
        return await message.answer(
            "⚠️ لطفاً تصویر فیش واریزی (عکس رسید) یا متن کد پیگیری را ارسال نمایید:",
            reply_markup=cancel_keyboard,
        )

    data = await state.get_data()
    amount = data.get("amount", 0)
    assigned_card = data.get("assigned_card", "")
    assigned_holder = data.get("assigned_holder", "")
    telegram_id = message.from_user.id
    await state.clear()

    # ثبت تراکنش در وضعیت در انتظار بررسی (pending)
    tx_id = await database.create_transaction(
        telegram_id=telegram_id,
        amount=amount,
        t_type="deposit",
        method="card",
        tracking_code=tracking,
        status="pending",
        receipt_photo_id=photo_file_id,
        card_used=assigned_card,
    )

    # ارسال اعلان و دکمه‌های تایید/رد مستقیم برای ادمین‌ها
    admin_text = (
        "🔔 <b>فیش واریزی جدید دریافت شد!</b>\n\n"
        f"🆔 شماره تراکنش: #{tx_id}\n"
        f"👤 کاربر: <code>{telegram_id}</code> (@{message.from_user.username or '—'})\n"
        f"💰 مبلغ: <b>{to_toman(amount)}</b>\n"
        f"🧾 کد/توضیح: <code>{tracking}</code>\n"
    )
    if assigned_card:
        admin_text += f"💳 واریز به کارت: <code>{assigned_card}</code> ({assigned_holder})\n"
    admin_text += "\nجهت بررسی و تأیید یا رد، از دکمه‌های زیر استفاده فرمایید:"

    for admin_id in settings.ADMIN_IDS:
        try:
            if photo_file_id:
                await message.bot.send_photo(
                    admin_id,
                    photo=photo_file_id,
                    caption=admin_text,
                    reply_markup=admin_tx_keyboard(tx_id, has_photo=True),
                    parse_mode="HTML",
                )
            else:
                await message.bot.send_message(
                    admin_id,
                    text=admin_text,
                    reply_markup=admin_tx_keyboard(tx_id, has_photo=False),
                    parse_mode="HTML",
                )
        except Exception:
            pass

    is_admin = settings.is_admin(telegram_id)
    success_text = (
        "✅ <b>رسید پرداخت شما با موفقیت ثبت شد!</b>\n\n"
        f"💰 مبلغ: <b>{to_toman(amount)}</b>\n"
        f"🧾 پیگیری: <b>{tracking}</b>\n\n"
        "⏳ فیش شما برای مدیریت ارسال شد و پس از بررسی حساب، موجودی شما به صورت خودکار شارژ خواهد شد."
    )
    await message.answer(success_text, reply_markup=get_main_keyboard(is_admin), parse_mode="HTML")
