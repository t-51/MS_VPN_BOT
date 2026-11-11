"""ماژول مدیریت سرتیفیکیت‌ها و تولید فایل‌های کانفیگ OpenVPN."""
import os
from typing import Optional

OPENVPN_CA_PATH = "/etc/openvpn/ca.crt"
OPENVPN_TC_PATH = "/etc/openvpn/tc.key"
CISCO_CA_PATH = "/etc/ocserv/certs/ca.crt"
IKEV2_CA_PATH = "/etc/vpn-ca/ca.crt"
SSTP_CA_PATH = "/etc/sstp-ca/ca.crt"


def get_ovpn_content(server_ip: str, username: str = "", password: str = "", proto: str = "udp", port: int = 1194) -> str:
    """تولید محتوای فایل اتصال OpenVPN (.ovpn) با گواهی CA و کلید tls-crypt تعبیه‌شده."""
    ca_content = ""
    tc_content = ""

    if os.path.exists(OPENVPN_CA_PATH):
        try:
            with open(OPENVPN_CA_PATH, "r", encoding="utf-8") as f:
                ca_content = f.read().strip()
        except Exception:
            pass

    if os.path.exists(OPENVPN_TC_PATH):
        try:
            with open(OPENVPN_TC_PATH, "r", encoding="utf-8") as f:
                tc_content = f.read().strip()
        except Exception:
            pass

    proto_name = "udp" if proto == "udp" else "tcp-client"
    lines = [
        "client",
        "dev tun",
        f"proto {proto_name}",
        f"remote {server_ip} {port}",
        "resolv-retry infinite",
        "nobind",
        "persist-key",
        "persist-tun",
        "remote-cert-tls server",
        "auth-user-pass",
        "cipher AES-256-GCM",
        "data-ciphers AES-256-GCM:AES-128-GCM:CHACHA20-POLY1305",
        "auth SHA256",
        "verb 3",
        "redirect-gateway def1 bypass-dhcp",
        "dhcp-option DNS 1.1.1.1",
        "dhcp-option DNS 8.8.8.8",
        "mssfix 1360",
    ]

    if username and password:
        lines.append(f"<auth-user-pass>\n{username}\n{password}\n</auth-user-pass>")

    if ca_content:
        lines.append(f"<ca>\n{ca_content}\n</ca>")

    if tc_content:
        lines.append(f"<tls-crypt>\n{tc_content}\n</tls-crypt>")

    return "\n".join(lines) + "\n"
