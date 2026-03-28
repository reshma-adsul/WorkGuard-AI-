"""
WorkGuard AI - Alert System
Sends desktop notifications and optional email alerts on anomaly detection
"""

import smtplib
import threading
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime

try:
    from plyer import notification
    PLYER_OK = True
except ImportError:
    PLYER_OK = False


class AlertManager:
    def __init__(self, email_config: dict = None):
        """
        email_config = {
            "sender": "your@gmail.com",
            "password": "app_password",
            "receiver": "owner@gmail.com",
            "smtp_host": "smtp.gmail.com",
            "smtp_port": 587
        }
        """
        self.email_config = email_config
        self.alert_log = []

    def send_desktop(self, title: str, message: str):
        """Windows desktop notification"""
        if PLYER_OK:
            try:
                notification.notify(
                    title=f"🔴 WorkGuard AI: {title}",
                    message=message,
                    app_name="WorkGuard AI",
                    timeout=10
                )
            except Exception:
                pass
        self._log_alert(title, message, "desktop")

    def send_email(self, subject: str, body: str):
        """Send email alert in background thread"""
        if not self.email_config:
            return
        thread = threading.Thread(
            target=self._send_email_sync,
            args=(subject, body),
            daemon=True
        )
        thread.start()

    def _send_email_sync(self, subject: str, body: str):
        try:
            cfg = self.email_config
            msg = MIMEMultipart()
            msg['From']    = cfg['sender']
            msg['To']      = cfg['receiver']
            msg['Subject'] = f"[WorkGuard AI] {subject}"
            msg.attach(MIMEText(body, 'html'))

            with smtplib.SMTP(cfg['smtp_host'], cfg['smtp_port']) as server:
                server.starttls()
                server.login(cfg['sender'], cfg['password'])
                server.sendmail(cfg['sender'], cfg['receiver'], msg.as_string())
        except Exception as e:
            print(f"[Alert] Email failed: {e}")

    def fire_anomaly_alert(self, anomaly_type: str, score: float, details: dict):
        """Fire all alerts for a detected anomaly"""
        time_str = datetime.now().strftime("%Y-%m-%d %H:%M:%S")

        desktop_msg = (
            f"Anomaly: {anomaly_type}\n"
            f"Score: {score:.2f} | {time_str}"
        )
        self.send_desktop(anomaly_type, desktop_msg)

        if self.email_config:
            html_body = f"""
            <h2 style="color:red">⚠️ WorkGuard AI Alert</h2>
            <table border="1" cellpadding="8" style="border-collapse:collapse">
              <tr><td><b>Time</b></td><td>{time_str}</td></tr>
              <tr><td><b>Anomaly Type</b></td><td>{anomaly_type}</td></tr>
              <tr><td><b>Confidence Score</b></td><td>{score:.2%}</td></tr>
              <tr><td><b>Active Window</b></td><td>{details.get('window','?')}</td></tr>
              <tr><td><b>Process</b></td><td>{details.get('process','?')}</td></tr>
              <tr><td><b>Typing Speed</b></td><td>{details.get('wpm','?')} WPM</td></tr>
            </table>
            <p>Check your WorkGuard AI dashboard immediately.</p>
            """
            self.send_email(f"ALERT: {anomaly_type}", html_body)

        self._log_alert(anomaly_type, str(details), "anomaly")

    def _log_alert(self, title, message, alert_type):
        self.alert_log.append({
            "time": datetime.now().isoformat(),
            "type": alert_type,
            "title": title,
            "message": message,
        })

    def get_alert_log(self):
        return self.alert_log
