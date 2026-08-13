import smtplib, imaplib, email as email_lib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from config.settings import get


def send(to: str, subject: str, body: str) -> str:
    addr = get("email_address")
    pw = get("email_password")
    smtp = get("email_smtp")
    if not addr or not pw:
        return "Email not configured. Run setup."
    try:
        msg = MIMEMultipart()
        msg['From'] = addr
        msg['To'] = to
        msg['Subject'] = subject
        msg.attach(MIMEText(body, 'plain'))
        server = smtplib.SMTP(smtp, 587)
        server.starttls()
        server.login(addr, pw)
        server.sendmail(addr, to, msg.as_string())
        server.quit()
        return f"Email sent to {to}"
    except Exception as e:
        return f"Email error: {e}"


def read(count: int = 5) -> str:
    addr = get("email_address")
    pw = get("email_password")
    imap = get("email_imap")
    if not addr or not pw:
        return "Email not configured. Run setup."
    try:
        m = imaplib.IMAP4_SSL(imap)
        m.login(addr, pw)
        m.select("INBOX")
        _, data = m.search(None, "ALL")
        ids = data[0].split()[-count:]
        results = []
        for i in reversed(ids):
            _, msg_data = m.fetch(i, "(RFC822)")
            msg = email_lib.message_from_bytes(msg_data[0][1])
            subject = msg.get("Subject", "")
            sender = msg.get("From", "")
            body = ""
            if msg.is_multipart():
                for part in msg.walk():
                    if part.get_content_type() == "text/plain":
                        body = part.get_payload(decode=True).decode(errors='ignore')[:200]
                        break
            else:
                body = msg.get_payload(decode=True).decode(errors='ignore')[:200]
            results.append(f"From: {sender}\nSubject: {subject}\n{body}")
        m.close()
        m.logout()
        return "\n\n---\n\n".join(results)
    except Exception as e:
        return f"Email read error: {e}"
