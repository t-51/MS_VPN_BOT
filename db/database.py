"""لایه‌ی دسترسی به دیتابیس محلی SQLite برای MS_VPN_BOT.

پشتیبانی کامل از:
  1) دسته‌بندی‌های پویا و نامحدود در فروشگاه و مدیریت (Categories)
  2) پلن‌های هر دسته با امکان افزودن، ویرایش و حذف توسط مدیر
  3) ذخیره اشتراک‌ها (Sing-box, V2Ray, L2TP/IKEv2, DNS Tunnel)
  4) گزارشات و تحلیل‌های فروش پیشرفته
  5) تنظیمات سیستم (سرور، اکانت تست، رفرال و...)
"""
import os
import random
import aiosqlite
from datetime import datetime
from typing import Optional, List, Dict, Any

from config import settings

_DB_DIR = os.path.dirname(settings.DB_PATH)
if _DB_DIR:
    os.makedirs(_DB_DIR, exist_ok=True)


async def init_db() -> None:
    """ساخت جداول و مقادیر پیش‌فرض در صورت عدم وجود."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS users (
                telegram_id     INTEGER PRIMARY KEY,
                username        TEXT,
                first_name      TEXT,
                wallet_balance  INTEGER DEFAULT 0,
                trial_used      INTEGER DEFAULT 0,
                referrer_id     INTEGER,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                updated_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS categories (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                key             TEXT UNIQUE NOT NULL,
                title           TEXT NOT NULL,
                description     TEXT,
                protocol_type   TEXT NOT NULL,
                icon            TEXT DEFAULT '⚡',
                is_active       INTEGER DEFAULT 1,
                sort_order      INTEGER DEFAULT 0
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS plans (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                category_key    TEXT NOT NULL,
                name            TEXT NOT NULL,
                traffic_gb      REAL NOT NULL,
                duration_days   INTEGER NOT NULL,
                price           INTEGER NOT NULL,
                is_active       INTEGER DEFAULT 1
            )
            """
        )

        # مایگریشن خودکار فیلدهای قدیمی در صورت وجود
        try:
            await db.execute("ALTER TABLE plans RENAME COLUMN category TO category_key")
        except Exception:
            pass

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS accounts (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER NOT NULL,
                panel_username  TEXT NOT NULL,
                panel_password  TEXT,
                category        TEXT DEFAULT 'singbox',
                plan_name       TEXT,
                sub_token       TEXT,
                sub_url         TEXT,
                sub_b64_url     TEXT,
                server_info     TEXT,
                is_trial        INTEGER DEFAULT 0,
                traffic_gb      REAL DEFAULT 0,
                duration_days   INTEGER DEFAULT 0,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS settings (
                key             TEXT PRIMARY KEY,
                value           TEXT NOT NULL
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS transactions (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER NOT NULL,
                amount          INTEGER NOT NULL,
                type            TEXT NOT NULL,
                method          TEXT NOT NULL,
                tracking_code   TEXT,
                status          TEXT DEFAULT 'pending',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS tickets (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER NOT NULL,
                subject         TEXT NOT NULL,
                message         TEXT NOT NULL,
                status          TEXT DEFAULT 'open',
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS ticket_replies (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                ticket_id       INTEGER NOT NULL,
                sender          TEXT NOT NULL,
                message         TEXT NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS notifications (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER,
                message         TEXT NOT NULL,
                is_read         INTEGER DEFAULT 0,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS bank_cards (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                card_number     TEXT NOT NULL,
                card_holder     TEXT NOT NULL,
                bank_name       TEXT DEFAULT 'بانک',
                is_active       INTEGER DEFAULT 1,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS bot_admins (
                telegram_id     INTEGER PRIMARY KEY,
                added_by        INTEGER DEFAULT 0,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        # درج ادمین‌های ثابت در صورت عدم وجود
        for adm in settings.ADMIN_IDS:
            await db.execute("INSERT OR IGNORE INTO bot_admins (telegram_id, added_by) VALUES (?, 0)", (adm,))

        async with db.execute("SELECT telegram_id FROM bot_admins") as cur:
            for r in await cur.fetchall():
                settings.DYNAMIC_ADMINS.add(r[0])

        # مایگریشن برای تراکنش‌ها
        try:
            await db.execute("ALTER TABLE transactions ADD COLUMN receipt_photo_id TEXT")
        except Exception:
            pass
        try:
            await db.execute("ALTER TABLE transactions ADD COLUMN card_used TEXT")
        except Exception:
            pass

        # درج کارت‌های پیش‌فرض گردون در صورت خالی بودن
        async with db.execute("SELECT COUNT(*) FROM bank_cards") as cur:
            bc_cnt = (await cur.fetchone())[0]
            if bc_cnt == 0:
                await db.execute(
                    "INSERT INTO bank_cards (card_number, card_holder, bank_name, is_active) VALUES (?, ?, ?, 1)",
                    (settings.CARD_NUMBER, settings.CARD_HOLDER, "بانک ملی"),
                )

        # درج تنظیمات پیش‌فرض
        default_settings = [
            ("trial_enabled", "1"),
            ("trial_traffic_gb", str(settings.TRIAL_TRAFFIC_GB)),
            ("trial_duration_days", str(settings.TRIAL_DURATION_DAYS)),
            ("referral_percent", str(settings.REFERRAL_PERCENT)),
            ("server_ip", settings.SERVER_IP),
            ("server_domain", settings.SERVER_DOMAIN),
            ("ipsec_psk", settings.IPSEC_PSK),
            ("dnstt_domain", settings.DNSTT_DOMAIN),
            ("dnstt_pubkey", settings.DNSTT_PUBKEY),
            ("card_number", settings.CARD_NUMBER),
            ("card_holder", settings.CARD_HOLDER),
        ]
        for k, v in default_settings:
            await db.execute("INSERT OR IGNORE INTO settings (key, value) VALUES (?, ?)", (k, v))

        # درج دسته‌بندی‌های پیش‌فرض
        async with db.execute("SELECT COUNT(*) FROM categories") as cur:
            c_cnt = (await cur.fetchone())[0]
            if c_cnt == 0:
                default_cats = [
                    ("singbox", "کانفیگ‌های هوشمند Sing-box و V2Ray", "سوئیت کامل شامل V2Ray (Reality، VMess، VLESS)، Hysteria 2 و TUIC v5 با لینک سابسکریپشن هوشمند", "singbox", "🚀", 1, 1),
                    ("system_l2tp", "پروتکل‌های استاندارد (Cisco / OpenVPN / L2TP / IKEv2 / SSH / SSTP)", "اتصال با سیسکو AnyConnect، اوپن‌وی‌پی‌ان، L2TP، IKEv2، تونل SSH و SSTP با یک نام کاربری و رمز واحد", "system_l2tp", "🛡️", 1, 2),
                    ("dnstt", "تانل ضد فیلتر DNS (SlowDNS)", "مخصوص شرایط فیلترینگ شدید و اینترنت ملی از طریق پورت ۵۳", "dnstt", "🌐", 1, 3),
                    ("wireguard", "وایرگارد مدرن (WireGuard)", "پروتکل پرسرعت، کم‌پینگ و سبک با فایل .conf اختصاصی و بارکد QR", "wireguard", "⚡", 1, 4),
                    ("gas", "گوگل اسکریپت و کلودفلر (GAS / Workers)", "تونل نامحدود بر بستر سرورهای ابری گوگل و ورکر کلودفلر (ضد فیلتر پایدار)", "gas", "☁️", 1, 5),
                ]
                await db.executemany(
                    "INSERT INTO categories (key, title, description, protocol_type, icon, is_active, sort_order) VALUES (?, ?, ?, ?, ?, ?, ?)",
                    default_cats,
                )

        # اطمینان از وجود دسته‌های جدید وایرگارد و گوگل اسکریپت در پایگاه داده‌های موجود
        await db.execute(
            """
            INSERT OR IGNORE INTO categories (key, title, description, protocol_type, icon, is_active, sort_order)
            VALUES ('wireguard', 'وایرگارد مدرن (WireGuard)', 'پروتکل پرسرعت، کم‌پینگ و سبک با فایل .conf اختصاصی و بارکد QR', 'wireguard', '⚡', 1, 4)
            """
        )
        await db.execute(
            """
            INSERT OR IGNORE INTO categories (key, title, description, protocol_type, icon, is_active, sort_order)
            VALUES ('gas', 'گوگل اسکریپت و کلودفلر (GAS / Workers)', 'تونل نامحدود بر بستر سرورهای ابری گوگل و ورکر کلودفلر (ضد فیلتر پایدار)', 'gas', '☁️', 1, 5)
            """
        )

        # درج پلن‌های پیش‌فرض WireGuard در صورت عدم وجود
        async with db.execute("SELECT COUNT(*) FROM plans WHERE category_key = 'wireguard'") as cur:
            wg_cnt = (await cur.fetchone())[0]
            if wg_cnt == 0:
                wg_plans = [
                    ("wireguard", "پلن ۱ ماهه وایرگارد (۳۰ گیگابایت)", 30.0, 30, 70000, 1),
                    ("wireguard", "پلن ۱ ماهه وایرگارد (۶۰ گیگابایت)", 60.0, 30, 110000, 1),
                    ("wireguard", "پلن ۲ ماهه وایرگارد (۱۰۰ گیگابایت)", 100.0, 60, 180000, 1),
                ]
                await db.executemany(
                    "INSERT INTO plans (category_key, name, traffic_gb, duration_days, price, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                    wg_plans,
                )

        # درج پلن‌های پیش‌فرض GAS در صورت عدم وجود
        async with db.execute("SELECT COUNT(*) FROM plans WHERE category_key = 'gas'") as cur:
            gas_cnt = (await cur.fetchone())[0]
            if gas_cnt == 0:
                gas_plans = [
                    ("gas", "اشتراک ۱ ماهه اختصاصی گوگل اسکریپت (ترافیک نامحدود)", 0.0, 30, 85000, 1),
                    ("gas", "اشتراک ۳ ماهه اختصاصی گوگل اسکریپت (ترافیک نامحدود)", 0.0, 90, 220000, 1),
                ]
                await db.executemany(
                    "INSERT INTO plans (category_key, name, traffic_gb, duration_days, price, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                    gas_plans,
                )

        # درج پلن‌های پیش‌فرض
        async with db.execute("SELECT COUNT(*) FROM plans") as cur:
            p_cnt = (await cur.fetchone())[0]
            if p_cnt == 0:
                init_plans = [
                    # دسته سینگ‌باکس و V2Ray کامل
                    ("singbox", "پلن ۱ ماهه Singbox / V2Ray (۳۰ گیگابایت)", 30.0, 30, 65000, 1),
                    ("singbox", "پلن ۱ ماهه Singbox / V2Ray (۵۰ گیگابایت)", 50.0, 30, 95000, 1),
                    ("singbox", "پلن ۱ ماهه Singbox / V2Ray (۱۰۰ گیگابایت)", 100.0, 30, 160000, 1),
                    ("singbox", "پلن ۲ ماهه اقتصادی Singbox / V2Ray (۸۰ گیگابایت)", 80.0, 60, 145000, 1),
                    # دسته پروتکل‌های سیستمی L2TP
                    ("system_l2tp", "اکانت سیستمی ۱ ماهه (۳۰ گیگ) - L2TP/IKEv2", 30.0, 30, 55000, 1),
                    ("system_l2tp", "اکانت سیستمی ۱ ماهه (۶۰ گیگ) - L2TP/IKEv2", 60.0, 30, 85000, 1),
                    ("system_l2tp", "اکانت سیستمی ۲ ماهه (۱۰۰ گیگ) - L2TP/IKEv2", 100.0, 60, 140000, 1),
                    # دسته تانل DNS
                    ("dnstt", "اشتراک تانل SlowDNS ضد فیلتر (۱ ماهه نامحدود)", 0.0, 30, 75000, 1),
                    ("dnstt", "اشتراک تانل SlowDNS ضد فیلتر (۲ ماهه نامحدود)", 0.0, 60, 130000, 1),
                ]
                await db.executemany(
                    "INSERT INTO plans (category_key, name, traffic_gb, duration_days, price, is_active) VALUES (?, ?, ?, ?, ?, ?)",
                    init_plans,
                )

        await db.commit()


# ──────────────────────────────────────────────────────────────
#  مدیریت دسته‌بندی‌ها (Categories Management)
# ──────────────────────────────────────────────────────────────

async def get_active_categories() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM categories WHERE is_active = 1 ORDER BY sort_order ASC, id ASC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_all_categories_admin() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT c.*, COUNT(p.id) as plans_count
            FROM categories c
            LEFT JOIN plans p ON c.key = p.category_key AND p.is_active = 1
            GROUP BY c.id
            ORDER BY c.sort_order ASC, c.id ASC
            """
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_category_by_key(cat_key: str) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM categories WHERE key = ?", (cat_key,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_category(key: str, title: str, description: str, protocol_type: str, icon: str = "⚡") -> int:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO categories (key, title, description, protocol_type, icon, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (key, title, description, protocol_type, icon),
        )
        await db.commit()
        return cur.lastrowid


async def toggle_category(cat_key: str) -> bool:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT is_active FROM categories WHERE key = ?", (cat_key,)) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            new_val = 0 if row[0] == 1 else 1

        await db.execute("UPDATE categories SET is_active = ? WHERE key = ?", (new_val, cat_key))
        await db.commit()
        return bool(new_val)


async def delete_category(cat_key: str) -> None:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM categories WHERE key = ?", (cat_key,))
        await db.execute("DELETE FROM plans WHERE category_key = ?", (cat_key,))
        await db.commit()


# ──────────────────────────────────────────────────────────────
#  مدیریت پلن‌ها (Plans Management)
# ──────────────────────────────────────────────────────────────

async def get_plans_by_category(category_key: str, active_only: bool = True) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cond = "AND is_active = 1" if active_only else ""
        query = f"SELECT * FROM plans WHERE category_key = ? {cond} ORDER BY price ASC"
        async with db.execute(query, (category_key,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_plan_by_id(plan_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM plans WHERE id = ?", (plan_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_plan(category_key: str, name: str, traffic_gb: float, duration_days: int, price: int) -> int:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO plans (category_key, name, traffic_gb, duration_days, price, is_active)
            VALUES (?, ?, ?, ?, ?, 1)
            """,
            (category_key, name, float(traffic_gb), int(duration_days), int(price)),
        )
        await db.commit()
        return cur.lastrowid


async def toggle_plan(plan_id: int) -> bool:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT is_active FROM plans WHERE id = ?", (plan_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            new_val = 0 if row[0] == 1 else 1

        await db.execute("UPDATE plans SET is_active = ? WHERE id = ?", (new_val, plan_id))
        await db.commit()
        return bool(new_val)


async def delete_plan(plan_id: int) -> None:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM plans WHERE id = ?", (plan_id,))
        await db.commit()


# ──────────────────────────────────────────────────────────────
#  تنظیمات سیستم (Settings Key-Value)
# ──────────────────────────────────────────────────────────────

async def get_setting(key: str, default: Optional[str] = None) -> str:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT value FROM settings WHERE key = ?", (key,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else (default or "")


async def set_setting(key: str, value: str) -> None:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT INTO settings (key, value) VALUES (?, ?) ON CONFLICT(key) DO UPDATE SET value = excluded.value",
            (key, str(value)),
        )
        await db.commit()


# ──────────────────────────────────────────────────────────────
#  کاربران
# ──────────────────────────────────────────────────────────────

async def get_or_create_user(
    telegram_id: int,
    username: Optional[str] = None,
    first_name: Optional[str] = None,
    referrer_id: Optional[int] = None,
) -> Dict[str, Any]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cur:
            row = await cur.fetchone()
            if row:
                if username or first_name:
                    await db.execute(
                        "UPDATE users SET username = ?, first_name = ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
                        (username, first_name, telegram_id),
                    )
                    await db.commit()
                return dict(row)

        if referrer_id and referrer_id == telegram_id:
            referrer_id = None

        await db.execute(
            """
            INSERT INTO users (telegram_id, username, first_name, wallet_balance, trial_used, referrer_id)
            VALUES (?, ?, ?, 0, 0, ?)
            """,
            (telegram_id, username, first_name, referrer_id),
        )
        await db.commit()

        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cur:
            new_row = await cur.fetchone()
            return dict(new_row)


async def get_user(telegram_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE telegram_id = ?", (telegram_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def is_logged_in(telegram_id: int) -> bool:
    user = await get_user(telegram_id)
    return user is not None


async def update_wallet_balance(telegram_id: int, delta_amount: int) -> int:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            """
            UPDATE users SET wallet_balance = wallet_balance + ?, updated_at = CURRENT_TIMESTAMP
            WHERE telegram_id = ?
            """,
            (delta_amount, telegram_id),
        )
        await db.commit()
        async with db.execute("SELECT wallet_balance FROM users WHERE telegram_id = ?", (telegram_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


async def set_trial_used(telegram_id: int) -> None:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE users SET trial_used = 1, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
            (telegram_id,),
        )
        await db.commit()


# ──────────────────────────────────────────────────────────────
#  اکانت‌ها
# ──────────────────────────────────────────────────────────────

async def save_account(
    telegram_id: int,
    panel_username: str,
    plan_name: str,
    category: str = "singbox",
    panel_password: Optional[str] = None,
    sub_token: str = "",
    sub_url: str = "",
    sub_b64_url: str = "",
    server_info: str = "",
    is_trial: int = 0,
    traffic_gb: float = 0.0,
    duration_days: int = 0,
) -> int:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO accounts (
                telegram_id, panel_username, panel_password, category, plan_name,
                sub_token, sub_url, sub_b64_url, server_info, is_trial, traffic_gb, duration_days
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (
                telegram_id,
                panel_username,
                panel_password,
                category,
                plan_name,
                sub_token,
                sub_url,
                sub_b64_url,
                server_info,
                is_trial,
                traffic_gb,
                duration_days,
            ),
        )
        await db.commit()
        return cur.lastrowid


async def get_user_accounts(telegram_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE telegram_id = ? ORDER BY id DESC", (telegram_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_account_by_id(account_id: int, telegram_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM accounts WHERE id = ?"
        params = [account_id]
        if telegram_id:
            query += " AND telegram_id = ?"
            params.append(telegram_id)
        async with db.execute(query, tuple(params)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ──────────────────────────────────────────────────────────────
#  تراکنش‌ها و مدیریت واریزی‌ها (تایید/رد فیش)
# ──────────────────────────────────────────────────────────────

async def create_transaction(
    telegram_id: int,
    amount: int,
    t_type: str,
    method: str,
    tracking_code: Optional[str] = None,
    status: str = "pending",
    receipt_photo_id: Optional[str] = None,
    card_used: Optional[str] = None,
) -> int:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO transactions (telegram_id, amount, type, method, tracking_code, status, receipt_photo_id, card_used)
            VALUES (?, ?, ?, ?, ?, ?, ?, ?)
            """,
            (telegram_id, amount, t_type, method, tracking_code, status, receipt_photo_id, card_used),
        )
        await db.commit()
        return cur.lastrowid


async def get_transaction_by_id(tx_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def get_pending_transactions() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT t.*, u.username, u.first_name
            FROM transactions t
            LEFT JOIN users u ON t.telegram_id = u.telegram_id
            WHERE t.status = 'pending'
            ORDER BY t.id DESC
        """
        async with db.execute(query) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def approve_transaction(tx_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)) as cur:
            tx = await cur.fetchone()
            if not tx or tx["status"] != "pending":
                return None
            tx_data = dict(tx)

        await db.execute("UPDATE transactions SET status = 'approved' WHERE id = ?", (tx_id,))
        await db.execute(
            "UPDATE users SET wallet_balance = wallet_balance + ?, updated_at = CURRENT_TIMESTAMP WHERE telegram_id = ?",
            (tx_data["amount"], tx_data["telegram_id"]),
        )
        await db.commit()
        return tx_data


async def reject_transaction(tx_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM transactions WHERE id = ?", (tx_id,)) as cur:
            tx = await cur.fetchone()
            if not tx or tx["status"] != "pending":
                return None
            tx_data = dict(tx)

        await db.execute("UPDATE transactions SET status = 'rejected' WHERE id = ?", (tx_id,))
        await db.commit()
        return tx_data


# ──────────────────────────────────────────────────────────────
#  آمار و تحلیل‌های فروش
# ──────────────────────────────────────────────────────────────

async def get_sales_stats() -> Dict[str, Any]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users") as cur:
            total_users = (await cur.fetchone())[0]

        async with db.execute("SELECT COUNT(*) FROM accounts") as cur:
            total_accounts = (await cur.fetchone())[0]

        async with db.execute("SELECT category, COUNT(*) FROM accounts GROUP BY category") as cur:
            cat_rows = await cur.fetchall()
            cat_stats = {r[0]: r[1] for r in cat_rows}

        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM transactions WHERE type = 'buy' AND status = 'approved'"
        ) as cur:
            row = await cur.fetchone()
            total_revenue = row[0]
            total_orders = row[1]

        async with db.execute(
            """
            SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM transactions
            WHERE type = 'buy' AND status = 'approved' AND date(created_at) = date('now')
            """
        ) as cur:
            row_today = await cur.fetchone()
            today_revenue = row_today[0]
            today_orders = row_today[1]

        async with db.execute(
            """
            SELECT COALESCE(SUM(amount), 0), COUNT(*) FROM transactions
            WHERE type = 'buy' AND status = 'approved' AND created_at >= datetime('now', '-30 days')
            """
        ) as cur:
            row_month = await cur.fetchone()
            month_revenue = row_month[0]
            month_orders = row_month[1]

        async with db.execute(
            "SELECT COUNT(*), COALESCE(SUM(amount), 0) FROM transactions WHERE status = 'pending'"
        ) as cur:
            pend_row = await cur.fetchone()
            pending_count = pend_row[0]
            pending_amount = pend_row[1]

        return {
            "total_users": total_users,
            "total_accounts": total_accounts,
            "cat_stats": cat_stats,
            "total_revenue": total_revenue,
            "total_orders": total_orders,
            "today_revenue": today_revenue,
            "today_orders": today_orders,
            "month_revenue": month_revenue,
            "month_orders": month_orders,
            "pending_count": pending_count,
            "pending_amount": pending_amount,
        }


async def get_top_referrers(limit: int = 10) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT u.telegram_id, u.username, u.first_name,
                   COUNT(r.telegram_id) as ref_count,
                   COALESCE(SUM(t.amount), 0) as total_comm
            FROM users u
            JOIN users r ON u.telegram_id = r.referrer_id
            LEFT JOIN transactions t ON u.telegram_id = t.telegram_id AND t.type = 'commission'
            GROUP BY u.telegram_id
            ORDER BY ref_count DESC, total_comm DESC
            LIMIT ?
        """
        async with db.execute(query, (limit,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_referral_stats(telegram_id: int) -> Dict[str, Any]:
    ref_pct = int(await get_setting("referral_percent", str(settings.REFERRAL_PERCENT)))
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM users WHERE referrer_id = ?", (telegram_id,)) as cur:
            ref_count = (await cur.fetchone())[0]

        async with db.execute(
            "SELECT COALESCE(SUM(amount), 0) FROM transactions WHERE telegram_id = ? AND type = 'commission'",
            (telegram_id,),
        ) as cur:
            comm_sum = (await cur.fetchone())[0]

        return {
            "code": str(telegram_id),
            "total_referrals": ref_count,
            "total_commission": comm_sum,
            "commission_rate_percent": ref_pct,
        }


# ──────────────────────────────────────────────────────────────
#  تیکت‌ها
# ──────────────────────────────────────────────────────────────

async def create_ticket(telegram_id: int, subject: str, message: str) -> int:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO tickets (telegram_id, subject, message) VALUES (?, ?, ?)",
            (telegram_id, subject, message),
        )
        await db.commit()
        return cur.lastrowid


async def get_user_tickets(telegram_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM tickets WHERE telegram_id = ? ORDER BY id DESC", (telegram_id,)
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_open_tickets_admin() -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM tickets WHERE status != 'closed' ORDER BY id DESC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_ticket(ticket_id: int, telegram_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = "SELECT * FROM tickets WHERE id = ?"
        params = [ticket_id]
        if telegram_id:
            query += " AND telegram_id = ?"
            params.append(telegram_id)
        async with db.execute(query, tuple(params)) as cur:
            t_row = await cur.fetchone()
            if not t_row:
                return None
            ticket = dict(t_row)

        async with db.execute(
            "SELECT * FROM ticket_replies WHERE ticket_id = ? ORDER BY id ASC", (ticket_id,)
        ) as cur:
            replies = await cur.fetchall()
            ticket["replies"] = [dict(r) for r in replies]
            return ticket


async def reply_ticket(ticket_id: int, sender: str, message: str) -> None:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT INTO ticket_replies (ticket_id, sender, message) VALUES (?, ?, ?)",
            (ticket_id, sender, message),
        )
        new_status = "open" if sender == "user" else "answered"
        await db.execute("UPDATE tickets SET status = ? WHERE id = ?", (new_status, ticket_id))
        await db.commit()


# ──────────────────────────────────────────────────────────────
#  اعلان‌ها
# ──────────────────────────────────────────────────────────────

async def get_user_notifications(telegram_id: int) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT * FROM notifications
            WHERE telegram_id IS NULL OR telegram_id = ?
            ORDER BY id DESC LIMIT 20
            """,
            (telegram_id,),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def mark_notification_read(notification_id: int) -> None:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("UPDATE notifications SET is_read = 1 WHERE id = ?", (notification_id,))
        await db.commit()


async def get_all_user_ids() -> List[int]:
    """دریافت شناسه‌های تلگرام تمام کاربران ثبت‌شده در ربات."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT telegram_id FROM users") as cur:
            rows = await cur.fetchall()
            return [r[0] for r in rows]


async def create_broadcast_notification(message: str) -> None:
    """ثبت اعلان عمومی در سیستم که در تب اعلان‌های همه کاربران نمایش داده شود."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT INTO notifications (telegram_id, message, is_read) VALUES (NULL, ?, 0)",
            (message,),
        )
        await db.commit()


# ──────────────────────────────────────────────────────────────
#  کارت‌های بانکی گردون (Rotational Bank Cards)
# ──────────────────────────────────────────────────────────────

async def get_active_bank_cards() -> List[Dict[str, Any]]:
    """دریافت کلیه کارت‌های بانکی فعال جهت انتخاب گردون."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bank_cards WHERE is_active = 1 ORDER BY id ASC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_random_bank_card() -> Dict[str, Any]:
    """انتخاب کاملاً تصادفی و چرخشی یکی از کارت‌های بانکی فعال."""
    cards = await get_active_bank_cards()
    if cards:
        return random.choice(cards)

    # فال‌بک در صورت نبود کارت فعال در جدول
    c_num = await get_setting("card_number", settings.CARD_NUMBER)
    c_hl = await get_setting("card_holder", settings.CARD_HOLDER)
    return {"id": 0, "card_number": c_num, "card_holder": c_hl, "bank_name": "بانک", "is_active": 1}


async def get_all_bank_cards_admin() -> List[Dict[str, Any]]:
    """دریافت تمامی کارت‌ها برای پنل مدیریت."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bank_cards ORDER BY id ASC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def add_bank_card(card_number: str, card_holder: str, bank_name: str = "بانک") -> int:
    """افزودن کارت جدید به گردونه کارت‌ها."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO bank_cards (card_number, card_holder, bank_name, is_active) VALUES (?, ?, ?, 1)",
            (card_number, card_holder, bank_name),
        )
        await db.commit()
        return cur.lastrowid


async def toggle_bank_card(card_id: int) -> bool:
    """روشن / خاموش کردن یک کارت بانکی در گردونه."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT is_active FROM bank_cards WHERE id = ?", (card_id,)) as cur:
            row = await cur.fetchone()
            if not row:
                return False
            new_val = 0 if row[0] == 1 else 1

        await db.execute("UPDATE bank_cards SET is_active = ? WHERE id = ?", (new_val, card_id))
        await db.commit()
        return bool(new_val)


async def delete_bank_card(card_id: int) -> None:
    """حذف کارت از گردونه کارت‌ها."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM bank_cards WHERE id = ?", (card_id,))
        await db.commit()


async def get_bank_card_by_id(card_id: int) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM bank_cards WHERE id = ?", (card_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


# ──────────────────────────────────────────────────────────────
#  مدیریت مدیران ربات (Bot Admins Management)
# ──────────────────────────────────────────────────────────────

async def get_all_admins() -> List[Dict[str, Any]]:
    """دریافت لیست تمام مدیران ثبت‌شده ربات."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT a.*, u.username, u.first_name FROM bot_admins a LEFT JOIN users u ON a.telegram_id = u.telegram_id ORDER BY a.created_at ASC") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def add_bot_admin(telegram_id: int, added_by: int = 0) -> bool:
    """افزودن مدیر جدید به ربات."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        try:
            await db.execute(
                "INSERT INTO bot_admins (telegram_id, added_by) VALUES (?, ?) ON CONFLICT(telegram_id) DO NOTHING",
                (telegram_id, added_by),
            )
            await db.commit()
            settings.DYNAMIC_ADMINS.add(telegram_id)
            return True
        except Exception:
            return False


async def remove_bot_admin(telegram_id: int) -> bool:
    """حذف دسترسی مدیریت کاربر."""
    # مدیر اصلی غیرقابل حذف است
    if telegram_id in settings.ADMIN_IDS:
        return False
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM bot_admins WHERE telegram_id = ?", (telegram_id,))
        await db.commit()
        settings.DYNAMIC_ADMINS.discard(telegram_id)
        return True


async def is_admin_user(telegram_id: int) -> bool:
    """بررسی جامع دسترسی مدیریت کاربر از فایل تنظیمات و دیتابیس."""
    if telegram_id in settings.ADMIN_IDS:
        return True
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT 1 FROM bot_admins WHERE telegram_id = ?", (telegram_id,)) as cur:
            row = await cur.fetchone()
            return row is not None


# ──────────────────────────────────────────────────────────────
#  عملیات تکمیلی اکانت‌ها (ویرایش شناسه، حذف، تبدیل)
# ──────────────────────────────────────────────────────────────

async def update_account_credentials(
    account_id: int,
    new_password: Optional[str] = None,
    new_sub_token: Optional[str] = None,
    new_sub_url: Optional[str] = None,
    new_sub_b64_url: Optional[str] = None,
    new_server_info: Optional[str] = None,
) -> None:
    """بروزرسانی مشخصات اتصال (رمز، ساب، سرور) اکانت در دیتابیس پس از ریست یا تغییر شناسه."""
    fields = []
    params = []
    if new_password is not None:
        fields.append("panel_password = ?")
        params.append(new_password)
    if new_sub_token is not None:
        fields.append("sub_token = ?")
        params.append(new_sub_token)
    if new_sub_url is not None:
        fields.append("sub_url = ?")
        params.append(new_sub_url)
    if new_sub_b64_url is not None:
        fields.append("sub_b64_url = ?")
        params.append(new_sub_b64_url)
    if new_server_info is not None:
        fields.append("server_info = ?")
        params.append(new_server_info)

    if not fields:
        return

    params.append(account_id)
    query = f"UPDATE accounts SET {', '.join(fields)} WHERE id = ?"
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(query, tuple(params))
        await db.commit()


async def delete_account(account_id: int) -> None:
    """حذف کامل اکانت از دیتابیس محلی ربات."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM accounts WHERE id = ?", (account_id,))
        await db.commit()


async def get_user_accounts_count(telegram_id: int) -> int:
    """تعداد اکانت‌های فعال یک کاربر."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute("SELECT COUNT(*) FROM accounts WHERE telegram_id = ?", (telegram_id,)) as cur:
            row = await cur.fetchone()
            return row[0] if row else 0


# ──────────────────────────────────────────────────────────────
#  مدیریت کاربران توسط ادمین (Admin Users Management)
# ──────────────────────────────────────────────────────────────

async def search_users(query: str, limit: int = 20) -> List[Dict[str, Any]]:
    """جستجوی پیشرفته کاربران بر اساس شناسه عددی، یوزرنیم یا نام."""
    query = query.strip().lstrip("@")
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        if query.isdigit():
            sql = "SELECT * FROM users WHERE telegram_id = ? OR telegram_id LIKE ? LIMIT ?"
            params = (int(query), f"%{query}%", limit)
        else:
            sql = "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ? ORDER BY id DESC LIMIT ?"
            params = (f"%{query}%", f"%{query}%", limit)

        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_recent_users(limit: int = 20) -> List[Dict[str, Any]]:
    """دریافت آخرین کاربران ثبت‌نام شده در ربات."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY id DESC LIMIT ?", (limit,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_user_transactions(telegram_id: int, limit: int = 20) -> List[Dict[str, Any]]:
    """دریافت لیست تراکنش‌ها و پرداخت‌های یک کاربر خاص."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM transactions WHERE telegram_id = ? ORDER BY id DESC LIMIT ?",
            (telegram_id, limit),
        ) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]
