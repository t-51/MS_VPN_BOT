"""حالت‌های ماشین وضعیت (FSM) برای بخش‌های تعاملی کاربر و پنل مدیریت."""
from aiogram.fsm.state import State, StatesGroup


# ── تیکت‌های کاربر ───────────────────────────────────────────
class NewTicketStates(StatesGroup):
    waiting_subject = State()
    waiting_message = State()


class ReplyTicketStates(StatesGroup):
    waiting_message = State()


# ── شارژ کیف پول کاربر ────────────────────────────────────────
class ChargeCardStates(StatesGroup):
    waiting_amount = State()
    waiting_tracking = State()


# ── پنل مدیریت: تنظیمات سیستم ────────────────────────────────
class AdminActionStates(StatesGroup):
    waiting_trial_gb = State()
    waiting_trial_days = State()
    waiting_referral_pct = State()
    waiting_server_ip = State()
    waiting_server_psk = State()
    waiting_ticket_reply = State()
    waiting_card_info = State()


# ── پنل مدیریت: دسته‌بندی‌ها و پلن‌ها ────────────────────────
class AdminCategoryStates(StatesGroup):
    waiting_title = State()
    waiting_key = State()
    waiting_proto = State()
    waiting_desc = State()


class AdminPlanStates(StatesGroup):
    waiting_name = State()
    waiting_traffic = State()
    waiting_days = State()
    waiting_price = State()


# ── پنل مدیریت: ارسال پیام همگانی (Broadcast) ───────────────
class AdminBroadcastStates(StatesGroup):
    waiting_message = State()
    waiting_confirm = State()


# ── پنل مدیریت: مدیریت اطلاعات کارت بانکی گردون ──────────────
class AdminCardStates(StatesGroup):
    waiting_card_number = State()
    waiting_card_holder = State()
    waiting_bank_name = State()


# ── راه‌اندازی ویزارد اکانت گوگل اسکریپت و کلودفلر ─────────────
class GASWizardStates(StatesGroup):
    waiting_google_token = State()
    waiting_cf_credentials = State()


# ── پنل مدیریت: مدیریت کاربران ───────────────────────────────
class AdminUserStates(StatesGroup):
    waiting_search_query = State()
    waiting_balance_add = State()
    waiting_balance_sub = State()
    waiting_invoice_amount = State()
    waiting_direct_message = State()


# ── پنل مدیریت: افزودن مدیر جدید ─────────────────────────────
class AdminManageStates(StatesGroup):
    waiting_new_admin_id = State()
