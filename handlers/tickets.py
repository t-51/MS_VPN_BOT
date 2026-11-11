"""هندلر پشتیبانی و تیکتینگ کاربران."""
from aiogram import Router, F, types
from aiogram.fsm.context import FSMContext

from config import settings
from db import database
from filters.auth import IsAuthorized
from keyboards.inline import build_tickets_keyboard, ticket_details_keyboard
from keyboards.reply import main_menu_keyboard, cancel_keyboard
from states.forms import NewTicketStates, ReplyTicketStates
from utils.formatters import format_tickets_list, format_ticket_details

router = Router(name="tickets")
router.message.filter(IsAuthorized())
router.callback_query.filter(IsAuthorized())


@router.message(F.text == "🎫 تیکت‌ها")
async def show_tickets_menu(message: types.Message):
    telegram_id = message.from_user.id
    tickets = await database.get_user_tickets(telegram_id)

    text = format_tickets_list(tickets)
    kb = build_tickets_keyboard(tickets)
    await message.answer(text, reply_markup=kb, parse_mode="HTML")


@router.callback_query(F.data == "tk:list")
async def cb_tickets_list(callback: types.CallbackQuery):
    telegram_id = callback.from_user.id
    tickets = await database.get_user_tickets(telegram_id)

    text = format_tickets_list(tickets)
    kb = build_tickets_keyboard(tickets)
    await callback.message.edit_text(text, reply_markup=kb, parse_mode="HTML")
    await callback.answer()


@router.callback_query(F.data == "tk:new")
async def cb_new_ticket_start(callback: types.CallbackQuery, state: FSMContext):
    await state.set_state(NewTicketStates.waiting_subject)
    await callback.message.answer(
        "📝 لطفاً <b>موضوع تیکت پشتیبانی</b> خود را ارسال فرمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )
    await callback.answer()


@router.message(NewTicketStates.waiting_subject)
async def state_ticket_subject(message: types.Message, state: FSMContext):
    subject = message.text.strip()
    await state.update_data(subject=subject)
    await state.set_state(NewTicketStates.waiting_message)
    await message.answer(
        "💬 اکنون لطفاً <b>متن کامل پیام یا شرح مشکل</b> خود را ارسال نمایید:",
        reply_markup=cancel_keyboard,
        parse_mode="HTML",
    )


@router.message(NewTicketStates.waiting_message)
async def state_ticket_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    subject = data.get("subject", "بدون عنوان")
    content = message.text.strip()
    telegram_id = message.from_user.id
    await state.clear()

    ticket_id = await database.create_ticket(telegram_id, subject, content)

    # اطلاع به ادمین‌ها با دکمه پاسخ مستقیم
    from keyboards.inline import admin_ticket_keyboard
    for admin_id in settings.ADMIN_IDS:
        try:
            admin_msg = (
                f"🎫 <b>تیکت پشتیبانی جدید (#{ticket_id}) ثبت شد!</b>\n\n"
                f"👤 کاربر: <code>{telegram_id}</code> (@{message.from_user.username or '—'})\n"
                f"📝 موضوع: <b>{subject}</b>\n\n"
                f"{content}"
            )
            await message.bot.send_message(
                admin_id, admin_msg, reply_markup=admin_ticket_keyboard(ticket_id), parse_mode="HTML"
            )
        except Exception:
            pass

    await message.answer(
        f"✅ تیکت شما با شماره <b>#{ticket_id}</b> با موفقیت ثبت شد و به زودی توسط کارشناسان ما پاسخ داده خواهد شد.",
        reply_markup=main_menu_keyboard,
        parse_mode="HTML",
    )


@router.callback_query(F.data.startswith("tk:view:"))
async def cb_view_ticket(callback: types.CallbackQuery):
    ticket_id = int(callback.data.split(":")[2])
    telegram_id = callback.from_user.id

    ticket = await database.get_ticket(ticket_id, telegram_id)
    if not ticket:
        return await callback.answer("تیکت یافت نشد.", show_alert=True)

    text = format_ticket_details(ticket)
    can_reply = ticket.get("status") != "closed"
    await callback.message.edit_text(
        text,
        reply_markup=ticket_details_keyboard(ticket_id, can_reply),
        parse_mode="HTML",
    )
    await callback.answer()


@router.callback_query(F.data.startswith("tk:reply:"))
async def cb_reply_ticket_start(callback: types.CallbackQuery, state: FSMContext):
    ticket_id = int(callback.data.split(":")[2])
    await state.set_state(ReplyTicketStates.waiting_message)
    await state.update_data(ticket_id=ticket_id)
    await callback.message.answer(
        f"💬 لطفاً پاسخ خود را برای تیکت #{ticket_id} ارسال نمایید:",
        reply_markup=cancel_keyboard,
    )
    await callback.answer()


@router.message(ReplyTicketStates.waiting_message)
async def state_reply_message(message: types.Message, state: FSMContext):
    data = await state.get_data()
    ticket_id = data.get("ticket_id")
    reply_text = message.text.strip()
    await state.clear()

    await database.reply_ticket(ticket_id, "user", reply_text)
    await message.answer(
        "✅ پاسخ شما با موفقیت ارسال شد.",
        reply_markup=main_menu_keyboard,
    )
