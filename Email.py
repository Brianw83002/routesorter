import html
import os
import re
import smtplib
from email.message import EmailMessage

# Set these as environment variables (locally and in Vercel), never in the code.
gmailPassword = os.environ.get("GMAIL_APP_PASSWORD", "")
myEmail = "brianw83002@gmail.com"

EMAIL_RE = re.compile(r"^[^@\s]+@[^@\s]+\.[^@\s]+$")


def sendEmail(subject, body, toAddress):
    if not (gmailPassword and myEmail):
        raise RuntimeError(
            "Set GMAIL_APP_PASSWORD and GMAIL_ADDRESS environment variables."
        )
    if not toAddress or not EMAIL_RE.match(toAddress):
        raise ValueError("Enter a valid email address.")

    msg = EmailMessage()
    msg["From"] = myEmail
    msg["To"] = toAddress
    msg["Subject"] = subject
    msg.set_content(body)  # plain-text fallback for clients that need it

    # Gmail (and most clients) render plain text in a proportional font, so the
    # padded columns won't line up there even though the string is correct.
    # Sending an HTML alternative with a monospace <pre> block fixes that.
    htmlBody = (
        "<pre style=\"font-family: ui-monospace, SFMono-Regular, Menlo, Consolas, monospace; "
        "font-size: 14px; white-space: pre;\">"
        + html.escape(body)
        + "</pre>"
    )
    msg.add_alternative(htmlBody, subtype="html")

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(myEmail, gmailPassword)
        server.send_message(msg)


if __name__ == "__main__":
    sendEmail("Hello", "Sent via SMTP.", myEmail)