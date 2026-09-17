import asyncio
import smtplib
from email.message import EmailMessage
from typing import Any

import httpx

from app import config
from app.recap import render_html, render_text


def _send_email(subject: str, text_body: str, html_body: str) -> dict[str, Any]:
    message = EmailMessage()
    message["Subject"] = subject
    message["From"] = config.RECAP_EMAIL_FROM
    message["To"] = ", ".join(config.RECAP_EMAIL_TO)
    message.set_content(text_body)
    message.add_alternative(html_body, subtype="html")

    with smtplib.SMTP(config.SMTP_HOST, config.SMTP_PORT, timeout=30) as server:
        if config.SMTP_STARTTLS:
            server.starttls()
        if config.SMTP_USER:
            server.login(config.SMTP_USER, config.SMTP_PASSWORD)
        server.send_message(message)
    return {"ok": True, "recipients": config.RECAP_EMAIL_TO}


async def send_email(subject: str, text_body: str, html_body: str) -> dict[str, Any]:
    if not config.email_configured():
        return {"ok": False, "reason": "smtp not configured"}
    try:
        return await asyncio.to_thread(_send_email, subject, text_body, html_body)
    except (smtplib.SMTPException, OSError) as exc:
        return {"ok": False, "reason": str(exc)}


async def send_webhook(text_body: str) -> dict[str, Any]:
    if not config.webhook_configured():
        return {"ok": False, "reason": "webhook not configured"}
    try:
        async with httpx.AsyncClient() as client:
            response = await client.post(
                config.RECAP_WEBHOOK_URL, json={"text": text_body}, timeout=20
            )
        return {"ok": response.status_code < 300, "status": response.status_code}
    except httpx.HTTPError as exc:
        return {"ok": False, "reason": str(exc)}


async def deliver_recap(recap: dict[str, Any]) -> dict[str, Any]:
    subject = f"Market Brief — {recap['recap_date']}"
    text_body = render_text(recap)
    html_body = render_html(recap)
    email_result, webhook_result = await asyncio.gather(
        send_email(subject, text_body, html_body), send_webhook(text_body)
    )
    return {"email": email_result, "webhook": webhook_result}
