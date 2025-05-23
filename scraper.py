import os
import json
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv

# Load environment variables
load_dotenv()

class FITScraper:
    def __init__(self):
        self.session = requests.Session()
        self.base_url = "https://www.fit.ba/student"
        self.login_url = f"{self.base_url}/default.aspx"
        self.notifications_file = "seen_notifications.json"
        self.seen_notifications = self.load_seen_notifications()
        
        # Email configuration
        self.smtp_server = "smtp.gmail.com"
        self.smtp_port = 587
        self.sender_email = os.getenv("SENDER_EMAIL")
        self.sender_password = os.getenv("SENDER_PASSWORD")
        self.recipient_email = os.getenv("RECIPIENT_EMAIL")

    def load_seen_notifications(self):
        if os.path.exists(self.notifications_file):
            with open(self.notifications_file, 'r') as f:
                return json.load(f)
        return []

    def save_seen_notifications(self):
        with open(self.notifications_file, 'w') as f:
            json.dump(self.seen_notifications, f)

    def login(self):
        login_data = {
            'txtBrojDosijea': os.getenv("STUDENT_ID"),
            'txtLozinka': os.getenv("PASSWORD"),
            'btnPrijava': 'Prijava'
        }
        
        response = self.session.post(self.login_url, data=login_data)
        return "Obavijesti" in response.text  # Check if login was successful

    def get_notifications(self):
        response = self.session.get(self.login_url)
        soup = BeautifulSoup(response.text, 'html.parser')
        
        notifications = []
        news_items = soup.select('ul.newslist li')
        
        for item in news_items:
            title_elem = item.select_one('a.linkButton')
            date_elem = item.select_one('span#lblDatum')
            subject_elem = item.select_one('span#lblPredmet')
            author_elem = item.select_one('a.meta[href^="mailto:"]')
            abstract_elem = item.select_one('div.abstract')
            
            if title_elem:
                notification = {
                    'title': title_elem.text.strip(),
                    'date': date_elem.text.strip() if date_elem else '',
                    'subject': subject_elem.text.strip() if subject_elem else '',
                    'author': author_elem.text.strip() if author_elem else '',
                    'abstract': abstract_elem.text.strip() if abstract_elem else '',
                    'link': f"{self.base_url}/{title_elem['href']}" if title_elem.get('href') else '',
                    'id': f"{title_elem.text.strip()}_{date_elem.text.strip()}" if date_elem else title_elem.text.strip()
                }
                notifications.append(notification)
        
        return notifications

    def send_email(self, new_notifications):
        if not new_notifications:
            return

        msg = MIMEMultipart()
        msg['From'] = self.sender_email
        msg['To'] = self.recipient_email
        msg['Subject'] = f"New FIT Notifications - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        body = "New notifications from FIT:\n\n"
        for notification in new_notifications:
            body += f"Title: {notification['title']}\n"
            body += f"Date: {notification['date']}\n"
            body += f"Subject: {notification['subject']}\n"
            body += f"Author: {notification['author']}\n"
            body += f"Abstract: {notification['abstract']}\n"
            body += f"Link: {notification['link']}\n"
            body += "\n" + "-"*50 + "\n\n"

        msg.attach(MIMEText(body, 'plain'))

        try:
            server = smtplib.SMTP(self.smtp_server, self.smtp_port)
            server.starttls()
            server.login(self.sender_email, self.sender_password)
            server.send_message(msg)
            server.quit()
            print("Email sent successfully!")
        except Exception as e:
            print(f"Failed to send email: {e}")

    def run(self):
        if not self.login():
            print("Login failed!")
            return

        current_notifications = self.get_notifications()
        new_notifications = [
            n for n in current_notifications 
            if n['id'] not in self.seen_notifications
        ]

        if new_notifications:
            self.send_email(new_notifications)
            self.seen_notifications.extend([n['id'] for n in new_notifications])
            self.save_seen_notifications()
            print(f"Found {len(new_notifications)} new notifications!")
        else:
            print("No new notifications found.")

if __name__ == "__main__":
    scraper = FITScraper()
    scraper.run() 