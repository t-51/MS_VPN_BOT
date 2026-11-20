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
                uuid            TEXT,
                custom_name     TEXT,
                user_category_id INTEGER,
                price           INTEGER DEFAULT 0,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        for col, col_t in [
            ("uuid", "TEXT"),
            ("custom_name", "TEXT"),
            ("user_category_id", "INTEGER"),
            ("price", "INTEGER DEFAULT 0"),
        ]:
            try:
                await db.execute(f"ALTER TABLE accounts ADD COLUMN {col} {col_t}")
            except Exception:
                pass

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_categories (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                telegram_id     INTEGER NOT NULL,
                name            TEXT NOT NULL,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )
        await db.execute(
            "CREATE INDEX IF NOT EXISTS idx_user_categories_tg ON user_categories(telegram_id)"
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

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS force_join_channels (
                id              INTEGER PRIMARY KEY AUTOINCREMENT,
                title           TEXT NOT NULL,
                channel_id      TEXT NOT NULL,
                invite_link     TEXT,
                is_active       INTEGER DEFAULT 1,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP
            )
            """
        )

        await db.execute(
            """
            CREATE TABLE IF NOT EXISTS user_seen_locks (
                telegram_id     INTEGER,
                post_url        TEXT,
                created_at      TIMESTAMP DEFAULT CURRENT_TIMESTAMP,
                PRIMARY KEY (telegram_id, post_url)
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
            ("force_join_enabled", "0"),
            ("seen_lock_enabled", "0"),
            ("seen_lock_post_url", ""),
            ("seen_lock_text", "جهت استفاده از خدمات ربات، لطفاً از پست اسپانسر دیدن کرده و دکمه تایید مشاهده را لمس نمایید."),
            ("auto_channel_enabled", "0"),
            ("auto_channel_id", ""),
            ("auto_channel_days", "sat,sun,mon,tue,wed,thu,fri"),
            ("auto_channel_times", "12:00,20:00"),
            ("auto_channel_traffic_gb", "1.0"),
            ("auto_channel_duration_days", "1"),
            ("auto_channel_protocol", "singbox"),
            ("auto_channel_send_qr", "1"),
            ("auto_channel_caption", ""),
            ("auto_channel_last_sent", ""),
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

        # اطمینان از وجود دسته‌های جدید وایرگارد، وایرگارد پیشرفته و گوگل اسکریپت
        await db.execute(
            """
            INSERT OR IGNORE INTO categories (key, title, description, protocol_type, icon, is_active, sort_order)
            VALUES ('amneziawg', 'وایرگارد پیشرفته ضد فیلتر (AmneziaWG)', 'پروتکل فوق‌پیشرفته ضد فیلتر با متدهای پیشرفته مبهم‌سازی داده، پکیج اختصاصی تمام پورت‌ها (فایل ZIP) و کم‌ترین پینگ', 'amneziawg', '🛡️', 1, 2)
            """
        )
        await db.execute(
            """
            INSERT OR IGNORE INTO categories (key, title, description, protocol_type, icon, is_active, sort_order)
            VALUES ('wireguard', 'وایرگارد معمولی (WireGuard)', 'پروتکل استاندارد و پرسرعت وایرگارد با فایل .conf اختصاصی و بارکد QR', 'wireguard', '⚡', 1, 3)
            """
        )
        await db.execute(
            """
            INSERT OR IGNORE INTO categories (key, title, description, protocol_type, icon, is_active, sort_order)
            VALUES ('gas', 'گوگل اسکریپت و کلودفلر (GAS / Workers)', 'تونل نامحدود بر بستر سرورهای ابری گوگل و ورکر کلودفلر (ضد فیلتر پایدار)', 'gas', '☁️', 1, 6)
            """
        )

        # درج پلن‌های پیش‌فرض در صورت عدم وجود
        async with db.execute("SELECT COUNT(*) FROM plans") as cur:
            p_cnt = (await cur.fetchone())[0]
            if p_cnt == 0:
                init_plans = []
                traffic_tiers = [10, 20, 30, 40, 50, 60, 70, 80, 90, 100, 120]
                duration_tiers = [(1, 30), (2, 60), (3, 90)]

                # پروتکل‌های استاندارد (Cisco / OpenVPN / L2TP / IKEv2 / SSH / SSTP) - ۴,۰۰۰ تومان به ازای هر گیگابایت
                for m_num, days in duration_tiers:
                    for gb in traffic_tiers:
                        price = gb * 4000
                        init_plans.append((
                            "system_l2tp",
                            f"اکانت سیستمی {m_num} ماهه ({gb} گیگ) - استاندارد",
                            float(gb),
                            days,
                            price,
                            1,
                        ))

                # کانفیگ‌های Sing-box و V2Ray - ۳,۰۰۰ تومان به ازای هر گیگابایت
                for m_num, days in duration_tiers:
                    for gb in traffic_tiers:
                        price = gb * 3000
                        init_plans.append((
                            "singbox",
                            f"پلن {m_num} ماهه Singbox / V2Ray ({gb} گیگابایت)",
                            float(gb),
                            days,
                            price,
                            1,
                        ))

                # وایرگارد مدرن (WireGuard) - ۳,۰۰۰ تومان به ازای هر گیگابایت
                for m_num, days in duration_tiers:
                    for gb in traffic_tiers:
                        price = gb * 3000
                        init_plans.append((
                            "wireguard",
                            f"پلن {m_num} ماهه وایرگارد ({gb} گیگابایت)",
                            float(gb),
                            days,
                            price,
                            1,
                        ))

                # دسته تانل DNS (SlowDNS)
                init_plans.extend([
                    ("dnstt", "اشتراک تانل SlowDNS ضد فیلتر (۱ ماهه نامحدود)", 0.0, 30, 75000, 1),
                    ("dnstt", "اشتراک تانل SlowDNS ضد فیلتر (۲ ماهه نامحدود)", 0.0, 60, 130000, 1),
                    ("dnstt", "اشتراک تانل SlowDNS ضد فیلتر (۳ ماهه نامحدود)", 0.0, 90, 180000, 1),
                ])

                # دسته گوگل اسکریپت (GAS)
                init_plans.extend([
                    ("gas", "اشتراک ۱ ماهه اختصاصی گوگل اسکریپت (ترافیک نامحدود)", 0.0, 30, 85000, 1),
                    ("gas", "اشتراک ۳ ماهه اختصاصی گوگل اسکریپت (ترافیک نامحدود)", 0.0, 90, 220000, 1),
                ])

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

async def get_plans_by_category(category_key: str, active_only: bool = True, duration_days: Optional[int] = None) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cond = "AND is_active = 1" if active_only else ""
        params = [category_key]
        if duration_days is not None and int(duration_days) > 0:
            cond += " AND duration_days = ?"
            params.append(int(duration_days))
        query = f"SELECT * FROM plans WHERE category_key = ? {cond} ORDER BY duration_days ASC, traffic_gb ASC, price ASC"
        async with db.execute(query, tuple(params)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_plans_by_duration(duration_days: Optional[int] = None, active_only: bool = False) -> List[Dict[str, Any]]:
    """دریافت کلیه پلن‌ها بر اساس مدت زمان اعتبار (۱ ماهه ۳۰ روزه، ۲ ماهه ۶۰ روزه، ۳ ماهه ۹۰ روزه)."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cond = "WHERE is_active = 1" if active_only else "WHERE 1=1"
        params = []
        if duration_days is not None and int(duration_days) > 0:
            cond += " AND duration_days = ?"
            params.append(int(duration_days))
        query = f"SELECT * FROM plans {cond} ORDER BY duration_days ASC, category_key ASC, traffic_gb ASC"
        async with db.execute(query, tuple(params)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_distinct_plan_durations(category_key: Optional[str] = None) -> List[int]:
    """دریافت مدت‌زمان‌های یکتای پلن‌ها (مثلاً [30, 60, 90])."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        if category_key:
            query = "SELECT DISTINCT duration_days FROM plans WHERE category_key = ? ORDER BY duration_days ASC"
            params = (category_key,)
        else:
            query = "SELECT DISTINCT duration_days FROM plans ORDER BY duration_days ASC"
            params = ()
        async with db.execute(query, params) as cur:
            rows = await cur.fetchall()
            return [int(r[0]) for r in rows if r[0]]


async def get_plan_durations_summary(active_only: bool = False) -> List[Dict[str, Any]]:
    """دریافت لیست بازه‌های زمانی پلن‌ها همراه با تعداد پلن در هر بازه."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        cond = "WHERE is_active = 1" if active_only else ""
        query = f"""
            SELECT duration_days, COUNT(*) as count
            FROM plans
            {cond}
            GROUP BY duration_days
            ORDER BY duration_days ASC
        """
        async with db.execute(query) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_accounts_by_duration_summary() -> List[Dict[str, Any]]:
    """گزارش آماری کانفیگ‌های کاربران بر اساس مدت زمان (یک ماهه، دو ماهه و...)."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT duration_days,
                   COUNT(*) as count,
                   COALESCE(SUM(traffic_gb), 0) as total_traffic,
                   COALESCE(SUM(price), 0) as total_revenue
            FROM accounts
            WHERE is_trial = 0
            GROUP BY duration_days
            ORDER BY duration_days ASC
        """
        async with db.execute(query) as cur:
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


async def update_plan(
    plan_id: int,
    name: Optional[str] = None,
    traffic_gb: Optional[float] = None,
    duration_days: Optional[int] = None,
    price: Optional[int] = None,
    is_active: Optional[int] = None,
) -> bool:
    fields = []
    values = []
    if name is not None:
        fields.append("name = ?")
        values.append(name.strip())
    if traffic_gb is not None:
        fields.append("traffic_gb = ?")
        values.append(float(traffic_gb))
    if duration_days is not None:
        fields.append("duration_days = ?")
        values.append(int(duration_days))
    if price is not None:
        fields.append("price = ?")
        values.append(int(price))
    if is_active is not None:
        fields.append("is_active = ?")
        values.append(int(is_active))

    if not fields:
        return False

    values.append(plan_id)
    query = f"UPDATE plans SET {', '.join(fields)} WHERE id = ?"
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(query, tuple(values))
        await db.commit()
    return True


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


async def delete_setting(key: str) -> None:
    """حذف یک کلید از تنظیمات جهت بازنشانی به مقادیر پیش‌فرض."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("DELETE FROM settings WHERE key = ?", (key,))
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


async def get_user_by_username(username: str) -> Optional[Dict[str, Any]]:
    """یافتن کاربر بر اساس یوزرنیم تلگرام بدون حساسیت به بزرگی و کوچکی حروف."""
    clean = username.strip().lstrip("@").lower()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users WHERE LOWER(username) = ? LIMIT 1", (clean,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def find_user_by_id_or_username(query: str) -> Optional[Dict[str, Any]]:
    """یافتن کاربر بر اساس شناسه عددی (Telegram ID) یا یوزرنیم."""
    q = query.strip()
    if q.isdigit():
        return await get_user(int(q))
    return await get_user_by_username(q)


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
    uuid: str = "",
    price: int = 0,
    custom_name: str = "",
    user_category_id: Optional[int] = None,
) -> int:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            """
            INSERT INTO accounts (
                telegram_id, panel_username, panel_password, category, plan_name,
                sub_token, sub_url, sub_b64_url, server_info, is_trial, traffic_gb, duration_days, uuid,
                price, custom_name, user_category_id
            )
            VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?, ?)
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
                uuid,
                price,
                custom_name.strip() if custom_name else None,
                user_category_id,
            ),
        )
        await db.commit()
        return cur.lastrowid


async def get_user_accounts(telegram_id: int, user_category_id: Optional[int] = None) -> List[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT a.*, uc.name as user_category_name
            FROM accounts a
            LEFT JOIN user_categories uc ON a.user_category_id = uc.id
            WHERE a.telegram_id = ?
        """
        params = [telegram_id]
        if user_category_id is not None:
            if user_category_id == -1:
                query += " AND (a.user_category_id IS NULL OR a.user_category_id = 0)"
            else:
                query += " AND a.user_category_id = ?"
                params.append(user_category_id)
        query += " ORDER BY a.id DESC"
        async with db.execute(query, tuple(params)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_account_by_id(account_id: int, telegram_id: Optional[int] = None) -> Optional[Dict[str, Any]]:
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT a.*, uc.name as user_category_name
            FROM accounts a
            LEFT JOIN user_categories uc ON a.user_category_id = uc.id
            WHERE a.id = ?
        """
        params = [account_id]
        if telegram_id:
            query += " AND a.telegram_id = ?"
            params.append(telegram_id)
        async with db.execute(query, tuple(params)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def update_account_custom_name(account_id: int, telegram_id: int, custom_name: str) -> bool:
    """تنظیم یا ویرایش نام دلخواه اکانت توسط کاربر."""
    clean_val = custom_name.strip() if custom_name else None
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            "UPDATE accounts SET custom_name = ? WHERE id = ? AND telegram_id = ?",
            (clean_val, account_id, telegram_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def update_account_user_category(account_id: int, telegram_id: int, user_category_id: Optional[int]) -> bool:
    """تغییر یا اختصاص دسته‌بندی شخصی برای یک اکانت."""
    cat_val = user_category_id if (user_category_id and user_category_id > 0) else None
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            "UPDATE accounts SET user_category_id = ? WHERE id = ? AND telegram_id = ?",
            (cat_val, account_id, telegram_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_user_categories(telegram_id: int) -> List[Dict[str, Any]]:
    """لیست دسته‌بندی‌های شخصی کاربر همراه با تعداد اکانت‌ها."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        query = """
            SELECT c.*,
                   (SELECT COUNT(*) FROM accounts a WHERE a.user_category_id = c.id AND a.telegram_id = c.telegram_id) AS accounts_count
            FROM user_categories c
            WHERE c.telegram_id = ?
            ORDER BY c.id ASC
        """
        async with db.execute(query, (telegram_id,)) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_user_category(category_id: int, telegram_id: int) -> Optional[Dict[str, Any]]:
    """مشخصات یک دسته‌بندی شخصی کاربر."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            """
            SELECT c.*,
                   (SELECT COUNT(*) FROM accounts a WHERE a.user_category_id = c.id AND a.telegram_id = c.telegram_id) AS accounts_count
            FROM user_categories c
            WHERE c.id = ? AND c.telegram_id = ?
            """,
            (category_id, telegram_id),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def create_user_category(telegram_id: int, name: str) -> int:
    """ایجاد یک دسته‌بندی شخصی جدید توسط کاربر."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO user_categories (telegram_id, name) VALUES (?, ?)",
            (telegram_id, name.strip()),
        )
        await db.commit()
        return cur.lastrowid


async def update_user_category_name(category_id: int, telegram_id: int, name: str) -> bool:
    """ویرایش نام یک دسته‌بندی شخصی."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            "UPDATE user_categories SET name = ? WHERE id = ? AND telegram_id = ?",
            (name.strip(), category_id, telegram_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def delete_user_category(category_id: int, telegram_id: int) -> bool:
    """حذف دسته‌بندی شخصی کاربر و آزادسازی اکانت‌های عضو آن به حالت بدون دسته."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "UPDATE accounts SET user_category_id = NULL WHERE user_category_id = ? AND telegram_id = ?",
            (category_id, telegram_id),
        )
        cur = await db.execute(
            "DELETE FROM user_categories WHERE id = ? AND telegram_id = ?",
            (category_id, telegram_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def get_account_by_panel_username(panel_username: str) -> Optional[Dict[str, Any]]:
    """دریافت اطلاعات اکانت بر اساس نام کاربری در پنل."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute(
            "SELECT * FROM accounts WHERE panel_username = ? LIMIT 1",
            (panel_username,),
        ) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def transfer_account(account_id: int, current_owner_id: int, new_owner_id: int) -> bool:
    """انتقال مالکیت یک اکانت از یک کاربر به کاربر دیگر (هدیه دادن کانفیگ)."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            "UPDATE accounts SET telegram_id = ? WHERE id = ? AND telegram_id = ?",
            (new_owner_id, account_id, current_owner_id),
        )
        await db.commit()
        return cur.rowcount > 0


async def find_account_in_db(query: str) -> Optional[Dict[str, Any]]:
    """جستجوی اکانت در دیتابیس محلی با تطبیق شناسه، UUID، ساب‌توکن یا نام کاربری."""
    clean = query.strip()
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = """
            SELECT * FROM accounts
            WHERE panel_username = ?
               OR sub_token = ?
               OR uuid = ?
               OR sub_url LIKE ?
               OR sub_b64_url LIKE ?
               OR server_info LIKE ?
            LIMIT 1
        """
        async with db.execute(
            sql,
            (clean, clean, clean, f"%{clean}%", f"%{clean}%", f"%{clean}%"),
        ) as cur:
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


async def update_account_plan(
    account_id: int,
    plan_name: str,
    traffic_gb: float,
    duration_days: int,
    price: int,
) -> None:
    """بروزرسانی مشخصات پلن (نام، حجم، مدت روزها و قیمت) اکانت در دیتابیس ربات."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            """
            UPDATE accounts
            SET plan_name = ?,
                traffic_gb = ?,
                duration_days = ?,
                price = ?
            WHERE id = ?
            """,
            (plan_name, float(traffic_gb), int(duration_days), int(price), account_id),
        )
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
            sql = "SELECT * FROM users WHERE telegram_id = ? OR telegram_id LIKE ? ORDER BY created_at DESC LIMIT ?"
            params = (int(query), f"%{query}%", limit)
        else:
            sql = "SELECT * FROM users WHERE username LIKE ? OR first_name LIKE ? ORDER BY created_at DESC, telegram_id DESC LIMIT ?"
            params = (f"%{query}%", f"%{query}%", limit)

        async with db.execute(sql, params) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_recent_users(limit: int = 20) -> List[Dict[str, Any]]:
    """دریافت آخرین کاربران ثبت‌نام شده در ربات."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM users ORDER BY created_at DESC, telegram_id DESC LIMIT ?", (limit,)) as cur:
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


async def get_all_trial_accounts() -> List[Dict[str, Any]]:
    """دریافت کلیه اکانت‌های تستی فعال در سیستم."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM accounts WHERE is_trial = 1") as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def reset_user_trial(telegram_id: int) -> None:
    """بازنشانی وضعیت سهمیه تست کاربر (جهت امکان دریافت مجدد تست)."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute("UPDATE users SET trial_used = 0 WHERE telegram_id = ?", (telegram_id,))
        await db.commit()


# ──────────────────────────────────────────────────────────────
#  مدیریت عضویت اجباری (Force Join Channels)
# ──────────────────────────────────────────────────────────────

async def is_force_join_enabled() -> bool:
    """بررسی فعال بودن قفل عضویت اجباری در ربات."""
    val = await get_setting("force_join_enabled", "0")
    return val == "1"


async def set_force_join_enabled(enabled: bool) -> None:
    """فعال یا غیرفعال کردن سراسری عضویت اجباری."""
    await set_setting("force_join_enabled", "1" if enabled else "0")


async def get_force_join_channels(active_only: bool = False) -> List[Dict[str, Any]]:
    """دریافت لیست کانال‌های عضویت اجباری."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        sql = "SELECT * FROM force_join_channels"
        if active_only:
            sql += " WHERE is_active = 1"
        sql += " ORDER BY id ASC"
        async with db.execute(sql) as cur:
            rows = await cur.fetchall()
            return [dict(r) for r in rows]


async def get_force_join_channel(channel_id: int) -> Optional[Dict[str, Any]]:
    """دریافت یک کانال عضویت اجباری بر اساس شناسه دیتابیس."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        db.row_factory = aiosqlite.Row
        async with db.execute("SELECT * FROM force_join_channels WHERE id = ?", (channel_id,)) as cur:
            row = await cur.fetchone()
            return dict(row) if row else None


async def add_force_join_channel(title: str, channel_id: str, invite_link: str = "") -> int:
    """افزودن کانال جدید برای عضویت اجباری."""
    clean_id = channel_id.strip()
    if not clean_id.startswith("@") and not clean_id.startswith("-100") and clean_id.lstrip("-").isdigit():
        clean_id = f"-100{clean_id.lstrip('-')}"
    
    clean_link = invite_link.strip()
    if not clean_link and clean_id.startswith("@"):
        clean_link = f"https://t.me/{clean_id.lstrip('@')}"

    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            "INSERT INTO force_join_channels (title, channel_id, invite_link, is_active) VALUES (?, ?, ?, 1)",
            (title.strip(), clean_id, clean_link),
        )
        await db.commit()
        return cur.lastrowid


async def delete_force_join_channel(channel_id: int) -> bool:
    """حذف کانال عضویت اجباری."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute("DELETE FROM force_join_channels WHERE id = ?", (channel_id,))
        await db.commit()
        return cur.rowcount > 0


async def toggle_force_join_channel(channel_id: int) -> bool:
    """تغییر وضعیت فعال/غیرفعال کانال عضویت اجباری."""
    async with aiosqlite.connect(settings.DB_PATH) as db:
        cur = await db.execute(
            "UPDATE force_join_channels SET is_active = CASE WHEN is_active = 1 THEN 0 ELSE 1 END WHERE id = ?",
            (channel_id,),
        )
        await db.commit()
        return cur.rowcount > 0


# ──────────────────────────────────────────────────────────────
#  مدیریت قفل سین / بازدید پست (Seen Lock)
# ──────────────────────────────────────────────────────────────

async def is_seen_lock_enabled() -> bool:
    """بررسی فعال بودن قفل سین پست."""
    val = await get_setting("seen_lock_enabled", "0")
    return val == "1"


async def set_seen_lock_enabled(enabled: bool) -> None:
    """تغییر فعال بودن قفل سین."""
    await set_setting("seen_lock_enabled", "1" if enabled else "0")


async def get_seen_lock_settings() -> Dict[str, Any]:
    """دریافت تنظیمات فعلی قفل سین."""
    return {
        "is_enabled": await is_seen_lock_enabled(),
        "post_url": await get_setting("seen_lock_post_url", ""),
        "lock_text": await get_setting(
            "seen_lock_text",
            "جهت استفاده از خدمات ربات، لطفاً از پست اسپانسر دیدن کرده و دکمه تایید مشاهده را لمس نمایید.",
        ),
    }


async def set_seen_lock_settings(
    post_url: Optional[str] = None,
    lock_text: Optional[str] = None,
    enabled: Optional[bool] = None,
) -> None:
    """بروزرسانی مشخصات قفل سین."""
    if enabled is not None:
        await set_seen_lock_enabled(enabled)
    if post_url is not None:
        await set_setting("seen_lock_post_url", post_url.strip())
    if lock_text is not None:
        await set_setting("seen_lock_text", lock_text.strip())


async def has_user_seen(telegram_id: int, post_url: str) -> bool:
    """بررسی اینکه آیا کاربر پست مورد نظر را مشاهده و تایید کرده است یا خیر."""
    if not post_url:
        return True
    async with aiosqlite.connect(settings.DB_PATH) as db:
        async with db.execute(
            "SELECT 1 FROM user_seen_locks WHERE telegram_id = ? AND post_url = ? LIMIT 1",
            (telegram_id, post_url),
        ) as cur:
            row = await cur.fetchone()
            return row is not None


async def record_user_seen(telegram_id: int, post_url: str) -> None:
    """ثبت مشاهده و سین پست توسط کاربر."""
    if not post_url:
        return
    async with aiosqlite.connect(settings.DB_PATH) as db:
        await db.execute(
            "INSERT OR IGNORE INTO user_seen_locks (telegram_id, post_url) VALUES (?, ?)",
            (telegram_id, post_url),
        )
        await db.commit()


# ──────────────────────────────────────────────────────────────
#  ارسال خودکار کانفیگ به کانال مقصد (Auto Config to Channel)
# ──────────────────────────────────────────────────────────────

async def get_auto_channel_settings() -> Dict[str, Any]:
    """دریافت تمامی تنظیمات ارسال خودکار کانفیگ به کانال."""
    raw_enabled = await get_setting("auto_channel_enabled", "0")
    channel_id = await get_setting("auto_channel_id", "")
    days_str = await get_setting("auto_channel_days", "sat,sun,mon,tue,wed,thu,fri")
    times_str = await get_setting("auto_channel_times", "12:00,20:00")
    traffic_gb = float(await get_setting("auto_channel_traffic_gb", "1.0") or 1.0)
    duration_days = int(await get_setting("auto_channel_duration_days", "1") or 1)
    protocol = await get_setting("auto_channel_protocol", "singbox")
    send_qr = (await get_setting("auto_channel_send_qr", "1")) == "1"
    caption = await get_setting("auto_channel_caption", "")
    last_sent = await get_setting("auto_channel_last_sent", "")

    # لیست روزها و ساعت‌ها
    days_list = [d.strip().lower() for d in days_str.split(",") if d.strip()]
    times_list = [t.strip() for t in times_str.split(",") if t.strip()]

    return {
        "is_enabled": raw_enabled == "1",
        "channel_id": channel_id,
        "days_list": days_list,
        "days_str": days_str,
        "times_list": times_list,
        "times_str": times_str,
        "traffic_gb": traffic_gb,
        "duration_days": duration_days,
        "protocol": protocol,
        "send_qr": send_qr,
        "caption": caption,
        "last_sent": last_sent,
    }


async def set_auto_channel_setting(key: str, value: str) -> None:
    """تنظیم یک فیلد مربوط به ارسال خودکار کانال."""
    await set_setting(f"auto_channel_{key}", value)


async def toggle_auto_channel() -> bool:
    """تغییر وضعیت فعال/غیرفعال ارسال خودکار کانفیگ به کانال."""
    cur = await get_setting("auto_channel_enabled", "0")
    new_val = "1" if cur != "1" else "0"
    await set_setting("auto_channel_enabled", new_val)
    return new_val == "1"


async def toggle_auto_channel_qr() -> bool:
    """تغییر وضعیت ارسال QR Code در کانال."""
    cur = await get_setting("auto_channel_send_qr", "1")
    new_val = "1" if cur != "1" else "0"
    await set_setting("auto_channel_send_qr", new_val)
    return new_val == "1"


async def toggle_auto_channel_day(day_code: str) -> str:
    """تغییر فعال بودن یک روز خاص از هفته برای ارسال کانفیگ."""
    day_code = day_code.strip().lower()
    days_str = await get_setting("auto_channel_days", "sat,sun,mon,tue,wed,thu,fri")
    days_list = [d.strip().lower() for d in days_str.split(",") if d.strip()]
    if day_code in days_list:
        days_list.remove(day_code)
    else:
        days_list.append(day_code)
    new_days_str = ",".join(days_list)
    await set_setting("auto_channel_days", new_days_str)
    return new_days_str


async def set_auto_channel_times(times_str: str) -> None:
    """تنظیم ساعات ارسال خودکار کانفیگ."""
    # استانداردسازی و تمیز کردن ورودی‌ها
    parts = [t.strip() for t in times_str.replace("،", ",").split(",") if t.strip()]
    valid_times = []
    for p in parts:
        if ":" in p:
            sub = p.split(":")
            if len(sub) == 2 and sub[0].isdigit() and sub[1].isdigit():
                h = int(sub[0])
                m = int(sub[1])
                if 0 <= h <= 23 and 0 <= m <= 59:
                    valid_times.append(f"{h:02d}:{m:02d}")
    valid_times = sorted(list(set(valid_times)))
    await set_setting("auto_channel_times", ",".join(valid_times))


async def set_auto_channel_target(channel_id: str) -> None:
    """تنظیم کانال مقصد ارسال خودکار."""
    clean = channel_id.strip()
    if clean and not clean.startswith("@") and not clean.startswith("-100") and clean.lstrip("-").isdigit():
        clean = f"-100{clean.lstrip('-')}"
    await set_setting("auto_channel_id", clean)


async def set_auto_channel_specs(traffic_gb: float, duration_days: int) -> None:
    """تنظیم حجم و مدت زمان اعتبار کانفیگ‌های ارسالی به کانال."""
    await set_setting("auto_channel_traffic_gb", str(traffic_gb))
    await set_setting("auto_channel_duration_days", str(duration_days))


async def set_auto_channel_last_sent(timestamp_str: str) -> None:
    """ثبت آخرین برچسب زمانی ارسال شده جهت جلوگیری از ارسال تکراری."""
    await set_setting("auto_channel_last_sent", timestamp_str)


