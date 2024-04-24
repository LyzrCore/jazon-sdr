import imaplib

def create_imap_service(imap_server, username, password):
    IMAP_SERVER = imap_server
    EMAIL = username
    PASSWORD = password
    mail = imaplib.IMAP4_SSL(IMAP_SERVER)
    mail.login(EMAIL, PASSWORD)
    return mail