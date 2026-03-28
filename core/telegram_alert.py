"""
WorkGuard AI - Telegram Alert Module
Sends real-time alerts with screenshots to owner's Telegram
"""

import requests
import datetime
from pathlib import Path


class TelegramAlert:
    """
    Sends Telegram messages and photos to owner.
    
    Setup:
    1. Open Telegram → search @BotFather
    2. Send /newbot → get BOT_TOKEN
    3. Start your bot → send any message
    4. Visit: https://api.telegram.org/bot<TOKEN>/getUpdates
    5. Copy your chat_id
    """

    API_BASE = "https://api.telegram.org/bot{token}"

    def __init__(self, bot_token: str, chat_id: str):
        self.bot_token = bot_token
        self.chat_id   = chat_id
        self.base_url  = self.API_BASE.format(token=bot_token)
        self.enabled   = bool(bot_token and chat_id)

    def send_message(self, text: str) -> bool:
        """Send text message"""
        if not self.enabled:
            return False
        try:
            url  = f"{self.base_url}/sendMessage"
            data = {"chat_id": self.chat_id, "text": text, "parse_mode": "HTML"}
            r    = requests.post(url, data=data, timeout=10)
            return r.status_code == 200
        except Exception as e:
            print(f"  [Telegram] Message failed: {e}")
            return False

    def send_photo(self, image_path: str, caption: str = "") -> bool:
        """Send photo with caption"""
        if not self.enabled:
            return False
        try:
            url = f"{self.base_url}/sendPhoto"
            with open(image_path, "rb") as photo:
                data  = {"chat_id": self.chat_id, "caption": caption, "parse_mode": "HTML"}
                files = {"photo": photo}
                r     = requests.post(url, data=data, files=files, timeout=15)
            return r.status_code == 200
        except Exception as e:
            print(f"  [Telegram] Photo failed: {e}")
            return False

    def send_alert(self, alert_type: str, score: float, screenshot_path: str = None, details: dict = None):
        """Send full alert — message + screenshot"""
        if not self.enabled:
            return

        time_str = datetime.datetime.now().strftime("%d %b %Y, %I:%M:%S %p")
        details  = details or {}

        # Build message
        if alert_type == "STRANGER_DETECTED":
            emoji = "🔴"
            title = "UNAUTHORIZED PERSON DETECTED"
        elif alert_type == "ANOMALY":
            emoji = "⚠️"
            title = "SUSPICIOUS ACTIVITY DETECTED"
        elif alert_type == "SESSION_START":
            emoji = "🟢"
            title = "WorkGuard AI Session Started"
        else:
            emoji = "🔔"
            title = alert_type

        msg = f"""{emoji} <b>WorkGuard AI Alert</b>

<b>{title}</b>

🕐 Time: {time_str}
📊 Threat Score: {int(score * 100)}%
🪟 Active Window: {details.get('window', 'Unknown')}
💻 Process: {details.get('process', 'Unknown')}

<i>Check your laptop immediately.</i>"""

        # Send photo first if available, else just message
        if screenshot_path and Path(screenshot_path).exists():
            self.send_photo(screenshot_path, caption=msg)
        else:
            self.send_message(msg)

        print(f"  📱 Telegram alert sent: {title}")

    def test_connection(self) -> dict:
        """Test if bot token and chat_id are valid"""
        if not self.enabled:
            return {"success": False, "error": "Token or chat_id not configured"}
        try:
            url = f"{self.base_url}/getMe"
            r   = requests.get(url, timeout=10)
            if r.status_code == 200:
                bot_name = r.json()["result"]["username"]
                # Send test message
                self.send_message(
                    f"✅ <b>WorkGuard AI Connected!</b>\n\nBot: @{bot_name}\nTime: {datetime.datetime.now().strftime('%d %b %Y, %I:%M %p')}\n\nYou will receive alerts here."
                )
                return {"success": True, "bot": bot_name}
            return {"success": False, "error": f"HTTP {r.status_code}"}
        except Exception as e:
            return {"success": False, "error": str(e)}


def setup_telegram() -> dict:
    """
    Interactive setup for Telegram bot.
    Returns config dict.
    """
    print("\n  📱 TELEGRAM ALERT SETUP")
    print("  ─────────────────────────────────────")
    print("  Step 1: Open Telegram")
    print("  Step 2: Search @BotFather")
    print("  Step 3: Send /newbot and follow steps")
    print("  Step 4: Copy the BOT TOKEN given")
    print()

    token = input("  Paste your BOT TOKEN here: ").strip()
    if not token:
        return {"enabled": False}

    print()
    print("  Now:")
    print("  Step 5: Start your new bot (send /start to it)")
    print("  Step 6: Visit this URL in browser:")
    print(f"  https://api.telegram.org/bot{token}/getUpdates")
    print("  Step 7: Copy your 'id' number from the result")
    print()

    chat_id = input("  Paste your CHAT ID here: ").strip()
    if not chat_id:
        return {"enabled": False}

    # Test connection
    tg = TelegramAlert(token, chat_id)
    print("\n  Testing connection...")
    result = tg.test_connection()

    if result["success"]:
        print(f"  ✅ Connected! Bot: @{result['bot']}")
        print("  ✅ Test message sent to your Telegram!")
        return {"enabled": True, "token": token, "chat_id": chat_id}
    else:
        print(f"  ❌ Failed: {result['error']}")
        return {"enabled": False}
