#!/usr/bin/env bash
# ==============================================================================
#                 اسکریپت نصب و مدیریت خودکار MS_VPN_BOT
#                   (ربات فروش متصل به پنل MHPanel)
# ==============================================================================

set -e

RED='\033[0;31m'
GREEN='\033[0;32m'
YELLOW='\033[1;33m'
BLUE='\033[0;34m'
CYAN='\033[0;36m'
BOLD='\033[1m'
NC='\033[0m'

SCRIPT_DIR="$(cd "$(dirname "${BASH_SOURCE[0]}")" && pwd)"
SERVICE_NAME="ms-vpn-bot"
SERVICE_FILE="/etc/systemd/system/${SERVICE_NAME}.service"

print_banner() {
    clear
    echo -e "${CYAN}${BOLD}"
    echo "=================================================================="
    echo "         🤖 نصب و راه‌اندازی ربات فروش MS_VPN_BOT (MHPanel)      "
    echo "=================================================================="
    echo -e "${NC}"
}

check_root() {
    if [ "$EUID" -ne 0 ]; then
        echo -e "${RED}❌ لطفاً این اسکریپت را با دسترسی root اجرا کنید (sudo bash install.sh)${NC}"
        exit 1
    fi
}

install_dependencies() {
    echo -e "\n${BLUE}🔄 در حال بررسی و نصب پکیج‌های پیش‌نیاز سیستم...${NC}"
    if [ -x "$(command -v apt-get)" ]; then
        apt-get update -y
        apt-get install -y python3 python3-pip python3-venv git curl sqlite3
    elif [ -x "$(command -v dnf)" ]; then
        dnf install -y python3 python3-pip git curl sqlite
    elif [ -x "$(command -v yum)" ]; then
        yum install -y python3 python3-pip git curl sqlite
    else
        echo -e "${YELLOW}⚠️ توزیع لینوکس شناخته نشد. فرض بر این است که پایتون ۳ و پیش‌نیازها نصب است.${NC}"
    fi
    echo -e "${GREEN}✅ پکیج‌های سیستمی آماده هستند.${NC}"
}

setup_python_env() {
    echo -e "\n${BLUE}🐍 در حال راه‌اندازی محیط مجازی پایتون (venv)...${NC}"
    mkdir -p "${SCRIPT_DIR}/data"

    if [ ! -d "${SCRIPT_DIR}/venv" ]; then
        python3 -m venv "${SCRIPT_DIR}/venv"
    fi

    echo -e "${BLUE}📦 در حال نصب و به‌روزرسانی کتابخانه‌های پایتون...${NC}"
    "${SCRIPT_DIR}/venv/bin/pip" install --upgrade pip
    "${SCRIPT_DIR}/venv/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt"
    echo -e "${GREEN}✅ وابستگی‌های پایتون با موفقیت نصب شدند.${NC}"
}

configure_env() {
    ENV_PATH="${SCRIPT_DIR}/.env"
    if [ -f "$ENV_PATH" ]; then
        echo -e "\n${GREEN}ℹ️ فایل تنظیمات .env در حال حاضر وجود دارد.${NC}"
        read -p "آیا مایل به بازتنظیم و ویرایش مجدد آن هستید؟ (y/N): " reconfigure
        if [[ ! "$reconfigure" =~ ^[Yy]$ ]]; then
            return
        fi
    fi

    echo -e "\n${YELLOW}⚙️ پیکربندی متغیرهای اساسی ربات:${NC}"

    read -p "1. توکن ربات تلگرام (از @BotFather): " tg_token
    read -p "2. یوزرنیم ربات تلگرام (بدون @): " bot_uname
    read -p "3. کلید وب‌سرویس MHPanel (PANEL_API_KEY): " api_key
    read -p "4. آدرس پنل MHPanel (مثال: https://panel.example.com): " panel_url
    panel_url="${panel_url%/}"
    read -p "5. شناسه عددی تلگرام مدیر (ADMIN_ID): " admin_id
    read -p "6. آی‌پی سرور (SERVER_IP) [پیش‌فرض: خودکار]: " srv_ip
    if [ -z "$srv_ip" ]; then
        srv_ip=$(curl -s -4 ifconfig.me || echo "127.0.0.1")
    fi
    read -p "7. شماره کارت بانکی جهت پرداخت: " card_num
    read -p "8. نام صاحب حساب بانکی: " card_holder

    cat <<EOF > "$ENV_PATH"
# تنظیمات اصلی ربات
TELEGRAM_TOKEN=${tg_token}
BOT_USERNAME=${bot_uname}
ADMIN_ID=${admin_id}
ADMIN_IDS=${admin_id}

# اتصال به سامانه MHPanel
PANEL_API_KEY=${api_key}
PANEL_API_URL=${panel_url}/api
PANEL_SUB_URL=${panel_url}/sub

# اطلاعات سرور و پروتکل‌ها
SERVER_IP=${srv_ip}
SERVER_DOMAIN=${panel_url#https://}
SERVER_DOMAIN=${SERVER_DOMAIN#http://}
IPSEC_PSK=123456789
DNSTT_DOMAIN=t.${SERVER_DOMAIN}
DNSTT_PUBKEY=

# تنظیمات تستی و رفرال
TRIAL_TRAFFIC_GB=1.0
TRIAL_DURATION_DAYS=1
REFERRAL_PERCENT=10

# اطلاعات مالی و پشتیبانی
CARD_NUMBER=${card_num:-6037990000000000}
CARD_HOLDER=${card_holder:-مدیریت ربات}
SUPPORT_ID=@${bot_uname}
CHANNEL_LINK=https://t.me/${bot_uname}
EOF

    echo -e "${GREEN}✅ فایل .env با موفقیت ایجاد شد.${NC}"
}

setup_systemd() {
    echo -e "\n${BLUE}⚙️ در حال ایجاد و راه‌اندازی سرویس systemd...${NC}"

    cat <<EOF > "$SERVICE_FILE"
[Unit]
Description=MS VPN Telegram Bot Service (MHPanel Integration)
After=network.target

[Service]
Type=simple
User=root
WorkingDirectory=${SCRIPT_DIR}
ExecStart=${SCRIPT_DIR}/venv/bin/python ${SCRIPT_DIR}/bot.py
Restart=always
RestartSec=5
Environment=PYTHONUNBUFFERED=1

[Install]
WantedBy=multi-user.target
EOF

    systemctl daemon-reload
    systemctl enable "${SERVICE_NAME}.service"
    systemctl restart "${SERVICE_NAME}.service"

    echo -e "${GREEN}✅ سرویس ${SERVICE_NAME} با موفقیت فعال و اجرا شد.${NC}"
}

check_status() {
    echo -e "\n${BLUE}📊 وضعیت سرویس ربات:${NC}"
    systemctl status "${SERVICE_NAME}.service" --no-pager
}

view_logs() {
    echo -e "\n${BLUE}📜 در حال نمایش لاگ‌های زنده ربات (برای خروج Ctrl+C بزنید)...${NC}\n"
    journalctl -u "${SERVICE_NAME}.service" -f -n 50
}

update_bot() {
    echo -e "\n${BLUE}🔄 در حال دریافت آخرین به‌روزرسانی از گیت‌هاب...${NC}"
    cd "${SCRIPT_DIR}"
    git pull || echo -e "${YELLOW}امکان دریافت خودکار با git وجود نداشت.${NC}"
    "${SCRIPT_DIR}/venv/bin/pip" install -r "${SCRIPT_DIR}/requirements.txt"
    systemctl restart "${SERVICE_NAME}.service"
    echo -e "${GREEN}✅ ربات به‌روزرسانی و مجدداً راه‌اندازی شد.${NC}"
}

uninstall_bot() {
    echo -e "\n${RED}⚠️ عملیات حذف ربات MS_VPN_BOT${NC}"
    read -p "آیا کاملاً مطمئن هستید که می‌خواهید سرویس حذف شود؟ (y/N): " confirm
    if [[ "$confirm" =~ ^[Yy]$ ]]; then
        systemctl stop "${SERVICE_NAME}.service" 2>/dev/null || true
        systemctl disable "${SERVICE_NAME}.service" 2>/dev/null || true
        rm -f "$SERVICE_FILE"
        systemctl daemon-reload
        echo -e "${GREEN}✅ سرویس سیستمی ربات با موفقیت حذف شد.${NC}"
        read -p "آیا می‌خواهید دیتابیس (اطلاعات کاربران) نیز حذف شود؟ (y/N): " rm_db
        if [[ "$rm_db" =~ ^[Yy]$ ]]; then
            rm -rf "${SCRIPT_DIR}/data"
            echo -e "${GREEN}✅ اطلاعات دیتابیس حذف شد.${NC}"
        fi
    fi
}

main_menu() {
    print_banner
    echo -e "محل نصب فعلی: ${CYAN}${SCRIPT_DIR}${NC}\n"
    echo -e "1) 🚀 نصب / راه‌اندازی مجدد کامل (Install / Setup)"
    echo -e "2) 🟢 مشاهده وضعیت سرویس (Status)"
    echo -e "3) 🔄 راه‌اندازی مجدد ربات (Restart)"
    echo -e "4) 🛑 متوقف کردن ربات (Stop)"
    echo -e "5) 📜 مشاهده لاگ‌های زنده (Live Logs)"
    echo -e "6) ⚙️ ویرایش فایل تنظیمات (.env)"
    echo -e "7) 📥 به‌روزرسانی ربات از گیت‌هاب (Update)"
    echo -e "8) ❌ حذف کامل سرویس (Uninstall)"
    echo -e "0) 🚪 خروج"
    echo ""
    read -p "گزینه مورد نظر را وارد کنید [0-8]: " choice

    case "$choice" in
        1)
            install_dependencies
            setup_python_env
            configure_env
            setup_systemd
            check_status
            ;;
        2)
            check_status
            ;;
        3)
            systemctl restart "${SERVICE_NAME}.service"
            echo -e "${GREEN}✅ ربات ری‌استارت شد.${NC}"
            check_status
            ;;
        4)
            systemctl stop "${SERVICE_NAME}.service"
            echo -e "${YELLOW}🛑 ربات متوقف شد.${NC}"
            ;;
        5)
            view_logs
            ;;
        6)
            nano "${SCRIPT_DIR}/.env" || vim "${SCRIPT_DIR}/.env"
            systemctl restart "${SERVICE_NAME}.service"
            echo -e "${GREEN}✅ تنظیمات اعمال و ربات ری‌استارت شد.${NC}"
            ;;
        7)
            update_bot
            ;;
        8)
            uninstall_bot
            ;;
        0)
            exit 0
            ;;
        *)
            echo -e "${RED}گزینه نامعتبر است.${NC}"
            ;;
    esac
}

check_root

# اگر آرگومانی مثل install ارسال شد مستقیماً اجرا شود
if [ "$1" == "install" ]; then
    install_dependencies
    setup_python_env
    configure_env
    setup_systemd
    check_status
elif [ "$1" == "restart" ]; then
    systemctl restart "${SERVICE_NAME}.service"
elif [ "$1" == "status" ]; then
    check_status
elif [ "$1" == "logs" ]; then
    view_logs
elif [ "$1" == "update" ]; then
    update_bot
elif [ "$1" == "uninstall" ]; then
    uninstall_bot
else
    main_menu
fi
