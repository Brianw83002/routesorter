import smtplib
from email.message import EmailMessage

gmailPassword = "yqvh dygo ochf gzvw"

myEmail = "brianw83002@gmail.com"
sendToAdress = "brianw83002@gmail.com"


def sendEmail(subject, body):
    if not (gmailPassword and myEmail and sendToAdress):
        raise RuntimeError(
            "Fill in gmailPassword, myEmail and sendToAdress at the top of Email.py."
        )

    msg = EmailMessage()
    msg["From"] = myEmail
    msg["To"] = sendToAdress
    msg["Subject"] = subject
    msg.set_content(body)

    with smtplib.SMTP_SSL("smtp.gmail.com", 465) as server:
        server.login(myEmail, gmailPassword)
        server.send_message(msg)


if __name__ == "__main__":
    sendEmail("Hello", "Sent via SMTP.")
