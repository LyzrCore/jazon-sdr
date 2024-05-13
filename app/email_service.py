import email
import imaplib
import time
from threading import Thread

class EmailMonitoringService:
    def __init__(self, imap_server, username, password):
        self.mail = imaplib.IMAP4_SSL(imap_server)
        self.mail.login(username, password)
        self.mail.select('inbox')
        self.subscribers = []

    def subscribe(self, worker, filter_function):
        self.subscribers.append((worker, filter_function))

    def fetch_emails(self):
        result, data = self.mail.search(None, 'ALL')
        if result != 'OK':
            print("No messages found!")
            return []

        messages = []
        for num in data[0].split():
            result, data = self.mail.fetch(num, '(RFC822)')
            if result != 'OK':
                print("ERROR getting message", num)
                continue

            email_msg = email.message_from_bytes(data[0][1])
            messages.append(email_msg)
        return messages

    def distribute_emails(self):
        while True:
            emails = self.fetch_emails()
            for email_msg in emails:
                for subscriber, filter_func in self.subscribers:
                    if filter_func(email_msg):
                        subscriber.process_email(email_msg)
            time.sleep(60)  # check every minute

    def start(self):
        Thread(target=self.distribute_emails).start()
