"""محتوا و راهنماهای آموزشی اتصال به تفکیک سیستم‌عامل و پروتکل."""
from config import settings

# لینک‌های دانلود کلاینت‌ها
CLIENT_DOWNLOADS = {
    "v2rayng_google_play": "https://play.google.com/store/apps/details?id=com.v2ray.ang",
    "v2rayng_github": "https://github.com/2dust/v2rayNG/releases",
    "slipnet_android": "https://play.google.com/store/apps/details?id=net.slipnet.app",
    "singbox_android": "https://play.google.com/store/apps/details?id=io.nekohasekai.sfa",
    "singbox_github": "https://github.com/SagerNet/sing-box/releases",
    "cisco_android": "https://play.google.com/store/apps/details?id=com.cisco.anyconnect.vpn.android.avf",
    "openvpn_android": "https://play.google.com/store/apps/details?id=net.openvpn.openvpn",
    "slowdns_android": "https://play.google.com/store/apps/details?id=com.tunnelguru",
    "http_custom_android": "https://play.google.com/store/apps/details?id=xyz.phdev.httpcustom",

    "streisand_ios": "https://apps.apple.com/us/app/streisand/id6450534064",
    "v2box_ios": "https://apps.apple.com/us/app/v2box-v2ray-client/id6446814042",
    "singbox_ios": "https://apps.apple.com/us/app/sing-box/id6451272673",
    "foxray_ios": "https://apps.apple.com/us/app/foxray/id6448898396",
    "cisco_ios": "https://apps.apple.com/us/app/cisco-secure-client/id1563815907",
    "openvpn_ios": "https://apps.apple.com/us/app/openvpn-connect/id590379981",

    "v2rayn_windows": "https://github.com/2dust/v2rayN/releases",
    "nekoray_windows": "https://github.com/MatsuriDayo/nekoray/releases",
    "openvpn_windows": "https://openvpn.net/client-connect-vpn-for-windows/",
    "cisco_windows": "https://anyconnect.en.softonic.com/",

    # وایرگارد (WireGuard)
    "wireguard_android": "https://play.google.com/store/apps/details?id=com.wireguard.android",
    "wireguard_android_apk": "https://download.wireguard.com/android-client/",
    "wireguard_ios": "https://apps.apple.com/us/app/wireguard/id1441195209",
    "wireguard_windows": "https://download.wireguard.com/windows-client/wireguard-installer.exe",
    "wireguard_macos": "https://apps.apple.com/us/app/wireguard/id1451685025",
    "wireguard_linux": "https://www.wireguard.com/install/",

    # گوگل اسکریپت و کلودفلر (GAS / Goose / Sing-box)
    "goose_github": "https://github.com/mhrv-rs/goose-vpn/releases",
    "singbox_desktop": "https://github.com/SagerNet/sing-box/releases",
    "google_oauth_playground": "https://developers.google.com/oauthplayground",
    "cloudflare_dash": "https://dash.cloudflare.com/profile/api-tokens",
}

TUTORIALS = {
    "main": (
        "📚 <b>مرکز جامع آموزش و راهنمای اتصال MS VPN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "برای مشاهده آموزش گام‌به‌گام اتصال و لینک دانلود مستقیم نرم‌افزارها، "
        "سیستم‌عامل دستگاه یا پروتکل مورد نظر خود را انتخاب فرمایید:"
    ),

    "wireguard": (
        "⚡ <b>راهنمای اتصال فوق‌سریع وایرگارد (WireGuard)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "وایرگارد یکی از مدرن‌ترین و سریع‌ترین پروتکل‌های امنیتی دنیا با کمترین میزان پینگ و مصرف باتری است.\n\n"
        "📱 <b>روش ۱: اسکن بارکد QR در گوشی (سریع‌ترین روش)</b>\n"
        "۱. نرم‌افزار رسمی <b>WireGuard</b> را از Google Play یا App Store نصب نمایید.\n"
        "۲. در ربات وارد منوی «📦 اکانت‌های من» شوید و روی اکانت وایرگارد خود کلیک کرده و دکمه <b>«📷 دریافت بارکد QR»</b> را بزنید.\n"
        "۳. در اپلیکیشن WireGuard علامت + (بعلاوه) را لمس کرده و گزینه <b>«Scan from QR code»</b> را انتخاب فرمایید.\n"
        "۴. دوربین را مقابل بارکد ارسالی ربات گرفته، یک نام دلخواه برای تونل بنویسید و متصل شوید.\n\n"
        "📁 <b>روش ۲: ورود با فایل کانفیگ (.conf)</b>\n"
        "۱. در ربات دکمه <b>«📥 دانلود فایل کانفیگ (.conf)»</b> را بزنید و فایل را در دستگاه ذخیره کنید.\n"
        "۲. در نرم‌افزار WireGuard (گوشی یا ویندوز/مک)، روی + کلیک کرده و گزینه <b>«Import from file or archive»</b> را انتخاب نموده و فایل را لود نمایید.\n"
        "۳. سوئیچ فعال‌سازی تونل را روشن کنید."
    ),

    "gas": (
        "☁️ <b>راهنمای اتصال به تونل گوگل اسکریپت و کلودفلر (GAS / Workers)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "تونل GAS ترافیک اینترنت شما را از سرورهای پردازش ابری شرکت گوگل (Google Apps Script) "
        "و شبکه جهانی Cloudflare عبور می‌دهد. به دلیل استفاده از دامنه‌های رسمی <code>script.google.com</code>، "
        "این روش فیلترناپذیر بوده و بالاترین سطح پایداری را داراست.\n\n"
        "🔑 <b>نحوه دریافت توکن گوگل برای ساخت پروژه اختصاصی:</b>\n"
        "۱. با فیلترشکن وارد <a href='https://developers.google.com/oauthplayground'>Google OAuth 2.0 Playground</a> شوید.\n"
        "۲. در ستون سمت چپ در بخش ورودی اسکوپ‌ها، این آدرس را تایپ کنید:\n"
        "<code>https://www.googleapis.com/auth/script.projects</code>\n"
        "۳. روی <b>Authorize APIs</b> بزنید و دسترسی جیمیل شخصی خود را تأیید کنید.\n"
        "۴. در گام بعدی دکمه آبی <b>«Exchange authorization code for tokens»</b> را لمس کنید.\n"
        "۵. مقدار کادر <b>Access token</b> (که با <code>ya29...</code> شروع می‌شود) را کپی کرده و در ربات ثبت نمایید.\n\n"
        "🚀 <b>روش اتصال:</b>\n"
        "می‌توانید از نرم‌افزار <b>Goose VPN</b> یا هسته <b>Sing-box</b> با کانفیگ ارسال‌شده استفاده کنید."
    ),

    "android": (
        "📱 <b>راهنمای اتصال در گوشی‌های اندروید (Android)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 <b>روش ۱: اتصال با Sing-box و V2Ray (پیشنهادی با بالاترین سرعت)</b>\n"
        "۱. اپلیکیشن <b>v2rayNG</b> یا <b>SlipNet</b> را نصب کنید.\n"
        "۲. در ربات وارد منوی «📦 اکانت‌های من» شوید و لینک سابسکریپشن خود را کپی کنید.\n"
        "۳. در برنامه v2rayNG از منوی سه‌خط (یا علامت +)، گزینه <b>«Import config from Clipboard»</b> یا <b>«Subscription group»</b> را بزنید و لینک را Paste نمایید.\n"
        "۴. دکمه دایره‌ای اتصال را لمس کنید.\n\n"
        "🛡️ <b>روش ۲: اتصال با Cisco AnyConnect (مناسب نت‌های ضعیف)</b>\n"
        "۱. برنامه <b>Cisco Secure Client</b> را نصب کنید.\n"
        "۲. وارد Settings برنامه شوید و تیک گزینه <b>«Block Untrusted Servers» را بردارید (خاموش کنید)</b>.\n"
        f"۳. یک اتصال جدید بسازید و آدرس سرور را به صورت <code>{settings.SERVER_IP}:10443</code> وارد کنید.\n"
        "۴. روی اتصال کلیک کرده و نام کاربری و رمز عبور دریافتی از ربات را وارد فرمایید.\n\n"
        "🔒 <b>روش ۳: اتصال با OpenVPN</b>\n"
        "۱. نرم‌افزار <b>OpenVPN Connect</b> را نصب کنید.\n"
        "۲. در ربات از بخش «📦 اکانت‌های من» روی <b>«📥 دانلود فایل OpenVPN (.ovpn)»</b> کلیک کرده و فایل را در گوشی ذخیره کنید.\n"
        "۳. فایل را با برنامه OpenVPN باز کرده، نام کاربری و پسورد را بزنید و متصل شوید.\n\n"
        "🛡️ <b>روش ۴: اتصال مستقیم سیستمی بدون نرم‌افزار (L2TP/IPsec)</b>\n"
        f"وارد تنظیمات گوشی > اتصالات (Connections) > VPN شوید. نوع اتصال را L2TP/IPsec PSK بگذارید، سرور را <code>{settings.SERVER_IP}</code> و کلید را <code>{settings.IPSEC_PSK}</code> وارد کنید."
    ),

    "ios": (
        "🍏 <b>راهنمای اتصال در آیفون و آیپد (iOS)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 <b>روش ۱: اتصال با Sing-box و V2Ray (پیشنهادی)</b>\n"
        "۱. یکی از اپلیکیشن‌های رایگان <b>Streisand</b>، <b>V2Box</b> یا <b>Sing-box</b> را از App Store نصب کنید.\n"
        "۲. لینک سابسکریپشن اکانت خود را از بخش «📦 اکانت‌های من» در ربات کپی کنید.\n"
        "۳. در برنامه Streisand یا V2Box، علامت + را زده و گزینه <b>«Add Subscription»</b> را لمس کنید و لینک را Paste نمایید.\n"
        "۴. با زدن دکمه Connect متصل شوید.\n\n"
        "🛡️ <b>روش ۲: اتصال با Cisco AnyConnect</b>\n"
        "۱. اپلیکیشن <b>Cisco Secure Client</b> را از App Store نصب کنید.\n"
        "۲. در تنظیمات برنامه (Settings)، تیک <b>«Block Untrusted Servers» را خاموش کنید</b>.\n"
        f"۳. در بخش Connections گزینه Add VPN Connection را بزنید و آدرس سرور را وارد کنید:\n<code>{settings.SERVER_IP}:10443</code>\n"
        "۴. دکمه اتصال را بزنید و Username و Password خود را وارد فرمایید.\n\n"
        "🔒 <b>روش ۳: اتصال با OpenVPN</b>\n"
        "۱. برنامه <b>OpenVPN Connect</b> را از App Store دریافت کنید.\n"
        "۲. فایل <code>.ovpn</code> ارسالی از ربات را در برنامه Share / Open نمایید و پسورد را وارد کنید.\n\n"
        "🛡️ <b>روش ۴: اتصال سیستمی IKEv2 در تنظیمات iOS</b>\n"
        f"وارد Settings > VPN > Add VPN Configuration شوید. Type را روی IKEv2 قرار داده، سرور را <code>{settings.SERVER_IP}</code> وارد کنید و نام کاربری و پسورد خود را بزنید."
    ),

    "windows": (
        "💻 <b>راهنمای اتصال در ویندوز (Windows PC / Laptop)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🚀 <b>روش ۱: کلاینت هوشمند v2rayN یا SlipNet (پیشنهادی)</b>\n"
        "۱. نرم‌افزار <b>v2rayN</b> را دانلود و استخراج (Extract) کنید.\n"
        "۲. لینک سابسکریپشن را از ربات کپی کرده، در نرم‌افزار کلیدهای <code>Ctrl + V</code> را بزنید یا از منوی Subscription Group گزینه Update Subscription را بزنید.\n"
        "۳. روی سرور دلخواه راست‌کلیک کرده و «Set as active server» را انتخاب فرمایید.\n"
        "۴. گزینه System Proxy را روی «Set system proxy» قرار دهید.\n\n"
        "🛡️ <b>روش ۲: اتصال با سیسکو Cisco AnyConnect در ویندوز</b>\n"
        "۱. نرم‌افزار Cisco AnyConnect ویندوز را نصب و اجرا کنید.\n"
        f"۲. آدرس <code>{settings.SERVER_IP}:10443</code> را وارد کرده و Connect را بزنید.\n"
        "۳. در صورت نمایش اخطار گواهی، گزینه «Connect Anyway» را بزنید و نام کاربری و رمز خود را وارد فرمایید.\n\n"
        "🔒 <b>روش ۳: اتصال با OpenVPN GUI</b>\n"
        "فایل کانفیگ <code>.ovpn</code> دریافتی از ربات را در پوشه <code>C:\\Program Files\\OpenVPN\\config</code> کپی کنید و در نوار وظیفه روی آیکون OpenVPN راست‌کلیک کرده و Connect را بزنید."
    ),

    "cisco": (
        "🛡️ <b>راهنمای اختصاصی پروتکل Cisco AnyConnect (OpenConnect)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "پروتکل سازمانی سیسکو یکی از پایدارترین پروتکل‌ها برای عبور از فیلترینگ شدید است.\n\n"
        "▫️ <b>آدرس سرور جهت اتصال:</b>\n"
        f"<code>{settings.SERVER_IP}:10443</code>\n"
        "▫️ <b>نام کاربری و رمز:</b> اطلاعات دریافتی پس از خرید اشتراک سیستمی\n\n"
        "⚠️ <b>نکته بسیار مهم برای اتصال موفق:</b>\n"
        "قبل از اتصال، حتماً وارد بخش تنظیمات (Settings) نرم‌افزار سیسکو در گوشی یا کامپیوتر شوید و تیک گزینه <b>«Block Untrusted Servers» را بردارید (خاموش کنید)</b> تا اجازه اتصال به سرور داده شود."
    ),

    "openvpn": (
        "🔒 <b>راهنمای اختصاصی پروتکل OpenVPN</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "این پروتکل از طریق فایل اختصاصی <code>.ovpn</code> متصل می‌شود که تمامی کدهای امنیتی و کلید رمزنگاری درون آن تعبیه شده است.\n\n"
        "▫️ <b>مراحل اتصال:</b>\n"
        "۱. نرم‌افزار رسمی <b>OpenVPN Connect</b> را روی دستگاه خود نصب کنید.\n"
        "۲. از بخش «📦 اکانت‌های من» در ربات، دکمه <b>«📥 دانلود فایل OpenVPN (.ovpn)»</b> را بزنید.\n"
        "۳. فایل دانلود شده را باز کرده و برنامه OpenVPN را برای اجرا انتخاب نمایید.\n"
        "۴. دکمه Add یا Import را بزنید، پسورد اکانت را وارد کرده و سوئیچ اتصال را روشن کنید."
    ),

    "ssh": (
        "⚡ <b>راهنمای اتصال به تونل مستقیم SSH</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "تونل امن SSH بر بستر پورت‌های استاندارد لینوکس عمل می‌کند و پایداری فوق‌العاده‌ای در شرایط اختلال دارد.\n\n"
        f"▫️ <b>آدرس سرور (Host):</b> <code>{settings.SERVER_IP}</code>\n"
        "▫️ <b>پورت‌های فعال SSH:</b> پورت <code>22</code> و پورت <code>2053</code>\n"
        "▫️ <b>نرم‌افزارهای سازگار:</b>\n"
        "اندروید: HTTP Custom / NapsternetV / SSH Tunnel\n"
        "ویندوز: PuTTY / Bitvise SSH Client / Proxifier\n"
        "آیفون: NapsternetV / Potatso"
    ),

    "slowdns": (
        "🌐 <b>راهنمای تانل اضطراری DNS (SlowDNS / DNSTT)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "این پروتکل مخصوص زمان‌هایی است که اینترنت بین‌الملل به طور کامل قطع شده و فقط اینترنت ملی فعال است.\n\n"
        "▫️ <b>نرم‌افزار مورد نیاز:</b> SlowDNS در اندروید یا SlipNet\n"
        "▫️ <b>دامنه نیم‌سرور (DNS Domain):</b> <code>t.vpn.kigaping.com</code>\n"
        "▫️ <b>کلید عمومی (Public Key):</b>\n<code>b3290012dd13fe7df78551fdfbccfdfce5d3c594522fef40bf8284e4313b3a31</code>\n"
        "▫️ <b>پورت اتصال:</b> <code>53</code>\n\n"
        "تنظیمات بالا را در نرم‌افزار وارد نموده و نام کاربری و رمز عبور خود را ثبت نمایید و متصل شوید."
    ),
}

# ──────────────────────────────────────────────────────────────
#  مرکز دانلود نرم‌افزارها و ماتریس سازگاری پروتکل‌ها
# ──────────────────────────────────────────────────────────────

APP_CENTER_MAIN_TEXT = (
    "📲 <b>مرکز جامع دانلود نرم‌افزارهای اتصال MS VPN</b>\n"
    "━━━━━━━━━━━━━━━━━━━━\n"
    "جهت راحتی شما، برای هر پروتکل و هر سیستم‌عامل، بهترین نرم‌افزارهای سازگار "
    "با لینک دانلود مستقیم از مراجع رسمی (گوگل‌پلی، اپ‌استور و گیت‌هاب) گردآوری شده است.\n\n"
    "👇 لطفاً سیستم‌عامل دستگاه یا پروتکل مورد نظر خود را انتخاب نمایید:"
)

OS_APP_GUIDES = {
    "android": (
        "📱 <b>نرم‌افزارهای سازگار با اندروید (Android)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌟 <b>۱. نرم‌افزار v2rayNG (پیشنهادی همه‌کاره)</b>\n"
        "▫️ پروتکل‌های سازگار: Sing-box, V2Ray, Reality, VMess, VLESS, Trojan\n"
        "▫️ ویژگی‌ها: پشتیبانی از لینک ساب هوشمند، پینگ لحظه‌ای، حالت تونل کل گوشی\n"
        "🔗 <a href='https://play.google.com/store/apps/details?id=com.v2ray.ang'>دانلود از Google Play</a> | <a href='https://github.com/2dust/v2rayNG/releases'>دانلود مستقیم APK از GitHub</a>\n\n"
        "⚡ <b>۲. نرم‌افزار رسمی WireGuard</b>\n"
        "▫️ پروتکل‌های سازگار: وایرگارد اختصاصی (WireGuard)\n"
        "▫️ ویژگی‌ها: کمترین پینگ ممکن (عالی برای گیمینگ و تماس)، فوق‌العاده کم‌مصرف، اسکن مستقیم QR\n"
        "🔗 <a href='https://play.google.com/store/apps/details?id=com.wireguard.android'>دانلود از Google Play</a>\n\n"
        "🛡️ <b>۳. نرم‌افزار Cisco Secure Client (AnyConnect)</b>\n"
        "▫️ پروتکل‌های سازگار: سیسکو سازمانی AnyConnect\n"
        "▫️ ویژگی‌ها: پایداری عالی در سخت‌ترین فیلترینگ‌ها\n"
        "🔗 <a href='https://play.google.com/store/apps/details?id=com.cisco.anyconnect.vpn.android.avf'>دانلود از Google Play</a>\n\n"
        "🔒 <b>۴. نرم‌افزار OpenVPN Connect</b>\n"
        "▫️ پروتکل‌های سازگار: اوپن‌وی‌پی‌ان با ایمپورت فایل .ovpn\n"
        "🔗 <a href='https://play.google.com/store/apps/details?id=net.openvpn.openvpn'>دانلود از Google Play</a>\n\n"
        "🌐 <b>۵. نرم‌افزار SlowDNS / HTTP Custom</b>\n"
        "▫️ پروتکل‌های سازگار: تونل DNS پورت ۵۳ و SSH Tunnel\n"
        "🔗 <a href='https://play.google.com/store/apps/details?id=com.tunnelguru'>دانلود SlowDNS</a>"
    ),

    "ios": (
        "🍏 <b>نرم‌افزارهای سازگار با آیفون و آیپد (iOS / iPadOS)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌟 <b>۱. نرم‌افزار Streisand (پیشنهادی برتر)</b>\n"
        "▫️ پروتکل‌های سازگار: Sing-box, V2Ray, Reality, TUIC, Hysteria 2\n"
        "▫️ ویژگی‌ها: کاملاً رایگان در اپ‌استور، محیط مدرن و اتصال فوق‌العاده سریع\n"
        "🔗 <a href='https://apps.apple.com/us/app/streisand/id6450534064'>دانلود از App Store</a>\n\n"
        "📱 <b>۲. نرم‌افزار V2Box - V2ray Client</b>\n"
        "▫️ پروتکل‌های سازگار: V2Ray، لینک‌های ساب و کانفیگ‌های Reality\n"
        "🔗 <a href='https://apps.apple.com/us/app/v2box-v2ray-client/id6446814042'>دانلود از App Store</a>\n\n"
        "⚡ <b>۳. نرم‌افزار رسمی WireGuard</b>\n"
        "▫️ پروتکل‌های سازگار: وایرگارد اختصاصی\n"
        "▫️ ویژگی‌ها: اسکن سریع بارکد QR، فعال‌سازی با یک لمس، پینگ عالی\n"
        "🔗 <a href='https://apps.apple.com/us/app/wireguard/id1441195209'>دانلود از App Store</a>\n\n"
        "🛡️ <b>۴. نرم‌افزار Cisco Secure Client</b>\n"
        "▫️ پروتکل‌های سازگار: پروتکل AnyConnect سیسکو\n"
        "🔗 <a href='https://apps.apple.com/us/app/cisco-secure-client/id1563815907'>دانلود از App Store</a>\n\n"
        "🔒 <b>۵. نرم‌افزار OpenVPN Connect</b>\n"
        "▫️ پروتکل‌های سازگار: اتصال با ایمپورت فایل .ovpn ارسالی ربات\n"
        "🔗 <a href='https://apps.apple.com/us/app/openvpn-connect/id590379981'>دانلود از App Store</a>"
    ),

    "windows": (
        "💻 <b>نرم‌افزارهای سازگار با ویندوز (Windows PC / Laptop)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌟 <b>۱. نرم‌افزار v2rayN (پیشنهادی کامل)</b>\n"
        "▫️ پروتکل‌های سازگار: تمامی کانفیگ‌های Sing-box، V2Ray، Reality و Hysteria 2\n"
        "▫️ ویژگی‌ها: پشتیبانی از Coreهای جدید Xray و Sing-box، قابلیت پروکسی کل سیستم (Tun Mode)\n"
        "🔗 <a href='https://github.com/2dust/v2rayN/releases'>دانلود مستقیم نسخه جدید از GitHub</a>\n\n"
        "⚡ <b>۲. نرم‌افزار رسمی WireGuard for Windows</b>\n"
        "▫️ پروتکل‌های سازگار: فایل‌های کانفیگ اختصاصی .conf وایرگارد\n"
        "▫️ ویژگی‌ها: راه‌اندازی با فایل .conf، سرعت باورنکردنی و پینگ بسیار پایین برای بازی و ترید\n"
        "🔗 <a href='https://download.wireguard.com/windows-client/wireguard-installer.exe'>دانلود مستقیم نصاب ویندوز (.exe)</a>\n\n"
        "🛡️ <b>۳. کلاینت سیسکو Cisco AnyConnect Desktop</b>\n"
        "▫️ پروتکل‌های سازگار: اتصال امن AnyConnect سیسکو\n"
        "🔗 <a href='https://anyconnect.en.softonic.com/'>دانلود کلاینت AnyConnect</a>\n\n"
        "🔒 <b>۴. نرم‌افزار OpenVPN GUI</b>\n"
        "▫️ پروتکل‌های سازگار: لود فایل .ovpn در ویندوز\n"
        "🔗 <a href='https://openvpn.net/client-connect-vpn-for-windows/'>دانلود OpenVPN برای ویندوز</a>"
    ),

    "macos": (
        "🖥️ <b>نرم‌افزارهای سازگار با مک‌بوک و مک (macOS)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "🌟 <b>۱. نرم‌افزار V2Box / FoXray Mac</b>\n"
        "▫️ پروتکل‌های سازگار: Sing-box, V2Ray, Reality, Trojan\n"
        "▫️ سازگار با تراشه‌های Apple Silicon (M1/M2/M3) و اینتل\n"
        "🔗 <a href='https://apps.apple.com/us/app/v2box-v2ray-client/id6446814042'>دانلود V2Box از Mac App Store</a>\n\n"
        "⚡ <b>۲. نرم‌افزار رسمی WireGuard for Mac</b>\n"
        "▫️ پروتکل‌های سازگار: ایمپورت فایل .conf وایرگارد\n"
        "🔗 <a href='https://apps.apple.com/us/app/wireguard/id1451685025'>دانلود از Mac App Store</a>\n\n"
        "🛡️ <b>۳. سیسکو و اوپن‌وی‌پی‌ان مک</b>\n"
        "▫️ نرم‌افزارهای Cisco Secure Client و Tunnelblick برای مدیریت کانکشن‌های سازمانی و اوپن‌وی‌پی‌ان"
    ),

    "linux": (
        "🐧 <b>ابزارهای سازگار با لینوکس (Linux Ubuntu / Debian / Arch)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n\n"
        "⚡ <b>۱. ابزار رسمی WireGuard Tools</b>\n"
        "▫️ نصب سریع در اوبونتو و دبیان:\n"
        "<code>sudo apt update && sudo apt install -y wireguard</code>\n"
        "▫️ نحوه اتصال با فایل کانفیگ ربات:\n"
        "<code>sudo wg-quick up ./wg_user.conf</code>\n\n"
        "🚀 <b>۲. هسته رسمی Sing-box Core</b>\n"
        "▫️ دریافت باینری رسمی از گیت‌هاب و اجرای مستقیم سابسکریپشن هوشمند\n\n"
        "🛡️ <b>۳. کلاینت OpenConnect (جایگزین سیسکو در لینوکس)</b>\n"
        "<code>sudo apt install openconnect</code>\n"
        f"<code>sudo openconnect {settings.SERVER_IP}:10443</code>"
    ),
}

PROTO_APP_GUIDES = {
    "singbox": (
        "🚀 <b>نرم‌افزارهای سازگار با پروتکل هوشمند Sing-box و V2Ray</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "این دسته شامل کلیه پروتکل‌های VLESS Reality, VMess, Trojan, TUIC v5 و Hysteria 2 می‌باشد.\n\n"
        "📱 <b>اندروید:</b> v2rayNG (پیشنهادی)، SlipNet، NekoBox\n"
        "🍏 <b>آیفون / آیپد:</b> Streisand (پیشنهادی)، V2Box، FoXray، Sing-box\n"
        "💻 <b>ویندوز:</b> v2rayN (پیشنهادی)، Nekoray، Hiddify Next\n"
        "🖥️ <b>مک:</b> V2Box، FoXray، Sing-box\n"
        "🐧 <b>لینوکس:</b> باینری رسمی sing-box"
    ),

    "wireguard": (
        "⚡ <b>نرم‌افزارهای سازگار با وایرگارد (WireGuard)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "پروتکل وایرگارد مستقیماً با نرم‌افزار رسمی WireGuard روی کلیه پلتفرم‌ها کار می‌کند.\n\n"
        "📱 <b>اندروید:</b> اپلیکیشن رسمی WireGuard (اسکن QR یا فایل .conf)\n"
        "🍏 <b>آیفون:</b> اپلیکیشن رسمی WireGuard در App Store\n"
        "💻 <b>ویندوز:</b> نرم‌افزار رسمی WireGuard Installer برای ویندوز\n"
        "🖥️ <b>مک:</b> WireGuard در Mac App Store\n"
        "🐧 <b>لینوکس:</b> ابزار خط فرمانی <code>wg-quick</code>"
    ),

    "standard": (
        "🛡️ <b>نرم‌افزارهای سازگار با پروتکل‌های سیستمی و استاندارد</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "این اکانت همزمان روی چندین پروتکل با یک نام کاربری و رمز کار می‌کند:\n\n"
        "▫️ <b>Cisco AnyConnect:</b> نرم‌افزار Cisco Secure Client در اندروید، iOS، ویندوز و مک\n"
        "▫️ <b>OpenVPN:</b> نرم‌افزار OpenVPN Connect (با فایل .ovpn دریافتی)\n"
        "▫️ <b>L2TP / IKEv2:</b> بدون نیاز به هیچ نرم‌افزاری! مستقیماً از بخش تنظیمات VPN گوشی یا کامپیوتر\n"
        "▫️ <b>SSH Tunnel:</b> نرم‌افزار HTTP Custom در اندروید و PuTTY در ویندوز"
    ),

    "dnstt": (
        "🌐 <b>نرم‌افزارهای سازگار با تانل SlowDNS (DNSTT)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "مخصوص زمان‌های قطعی کامل اینترنت بین‌الملل و عبور از پورت ۵۳:\n\n"
        "📱 <b>اندروید:</b> نرم‌افزار SlowDNS، نرم‌افزار SlipNet، نرم‌افزار HTTP Custom\n"
        "💻 <b>ویندوز:</b> کلاینت SlipNet یا کلاینت خط فرمان dnstt-client"
    ),

    "gas": (
        "☁️ <b>نرم‌افزارهای سازگار با گوگل اسکریپت و کلودفلر (GAS / Workers)</b>\n"
        "━━━━━━━━━━━━━━━━━━━━\n"
        "تونل اختصاصی پردازش ابری شرکت گوگل:\n\n"
        "🚀 <b>کلاینت Goose VPN (تخصصی GAS):</b>\n"
        "دارای نسخه اندروید و ویندوز برای اتصال سریع با Goose Link\n\n"
        "🌐 <b>هسته Sing-box و V2Ray:</b>\n"
        "می‌توانید کدهای کانفیگ SOCKS5 و HTTP ارسال‌شده توسط ربات را در نرم‌افزارهای v2rayNG و v2rayN وارد کنید."
    ),
}
