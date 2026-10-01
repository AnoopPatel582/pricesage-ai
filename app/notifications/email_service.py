import smtplib
import logging
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from app.utils.config import settings

logger = logging.getLogger("price_tracker.notifications")


class EmailService:
    @staticmethod
    def send_password_reset_code(to_email: str, code: str) -> bool:
        msg = MIMEText(f"Your PriceSage AI password reset code is {code}. It expires in 10 minutes.")
        msg["Subject"] = "PriceSage AI password reset"
        msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
        msg["To"] = to_email
        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [to_email], msg.as_string())
            return True
        except Exception:
            logger.exception("Failed to send password reset email")
            return False

    @staticmethod
    def send_price_drop_alert(
        to_email: str,
        user_name: str,
        product_name: str,
        current_price: float,
        target_price: float,
        currency: str,
        product_url: str,
    ) -> bool:
        """Sends an HTML-styled email notification when price target is reached."""
        if not settings.SMTP_USER or not settings.SMTP_PASSWORD:
            logger.info(
                f"[DRY-RUN ALERT] Email skipped (No SMTP configured). Target met for '{product_name}': "
                f"Now {current_price} {currency} <= Target {target_price} {currency} -> Would notify: {to_email}"
            )
            return True

        subject = f"Price Drop Alert: '{product_name}' dropped to {current_price} {currency}!"

        text_content = (
            f"Hello {user_name},\n\n"
            f"Great news! The product '{product_name}' has reached your target price.\n\n"
            f"Current Price: {current_price} {currency}\n"
            f"Target Price:  {target_price} {currency}\n"
            f"Check it out here: {product_url}\n\n"
            f"- PriceSage AI"
        )

        html_content = f"""
        <!DOCTYPE html>
        <html>
        <head>
            <style>
                body {{ font-family: -apple-system, BlinkMacSystemFont, 'Segoe UI', Roboto, sans-serif; background-color: #f4f6f8; margin: 0; padding: 20px; }}
                .container {{ max-width: 560px; margin: 0 auto; background: #ffffff; border-radius: 10px; padding: 24px; box-shadow: 0 4px 6px rgba(0,0,0,0.05); }}
                .badge {{ display: inline-block; background-color: #10b981; color: white; padding: 4px 12px; border-radius: 20px; font-weight: bold; font-size: 13px; }}
                .title {{ font-size: 20px; font-weight: 700; color: #1f2937; margin-top: 12px; }}
                .price-box {{ background: #f9fafb; border: 1px solid #e5e7eb; border-radius: 8px; padding: 16px; margin: 20px 0; }}
                .price-current {{ font-size: 26px; font-weight: 800; color: #059669; }}
                .price-target {{ font-size: 14px; color: #6b7280; text-decoration: line-through; }}
                .btn {{ display: inline-block; background-color: #2563eb; color: #ffffff; text-decoration: none; padding: 12px 24px; border-radius: 6px; font-weight: 600; margin-top: 10px; }}
            </style>
        </head>
        <body>
            <div class="container">
                <span class="badge">PRICE DROP ALERT</span>
                <div class="title">{product_name}</div>
                <p>Hello {user_name}, an item on your tracking list just dropped to your target price!</p>
                <div class="price-box">
                    <div class="price-target">Target: {target_price} {currency}</div>
                    <div class="price-current">{current_price} {currency}</div>
                </div>
                <a href="{product_url}" class="btn" target="_blank">View Product Now</a>
            </div>
        </body>
        </html>
        """

        msg = MIMEMultipart("alternative")
        msg["Subject"] = subject
        msg["From"] = settings.EMAIL_FROM or settings.SMTP_USER
        msg["To"] = to_email

        msg.attach(MIMEText(text_content, "plain"))
        msg.attach(MIMEText(html_content, "html"))

        try:
            with smtplib.SMTP(settings.SMTP_HOST, settings.SMTP_PORT) as server:
                server.starttls()
                server.login(settings.SMTP_USER, settings.SMTP_PASSWORD)
                server.sendmail(msg["From"], [to_email], msg.as_string())
            logger.info(f"Price drop email successfully dispatched to {to_email}")
            return True
        except Exception as exc:
            logger.error(f"Failed to dispatch alert email to {to_email}: {exc}")
            return False
