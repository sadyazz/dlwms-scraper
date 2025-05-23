import os
import json
import requests
from bs4 import BeautifulSoup
import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from datetime import datetime
from dotenv import load_dotenv
import argparse

# load environment variables
load_dotenv()

class FITScraper:
    def __init__(self, test_mode=False):
        self.session = requests.Session()
        self.base_url = "https://www.fit.ba/student"
        self.login_url = f"{self.base_url}/default.aspx"
        self.notifications_file = "seen_notifications.json"
        self.seen_notifications = [] if test_mode else self.load_seen_notifications()
        self.test_mode = test_mode
        
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
        try:
            print("Getting login page...")
            response = self.session.get(self.login_url)
            response.raise_for_status()
            
            soup = BeautifulSoup(response.text, 'html.parser')
            
            form = soup.find('form')
            if not form:
                print("Could not find login form!")
                return False
            
            form_action = form.get('action', self.login_url)
            if not form_action.startswith('http'):
                form_action = f"{self.base_url}/{form_action.lstrip('/')}"
            
            hidden_inputs = form.find_all('input', type='hidden')
            login_data = {input.get('name'): input.get('value') for input in hidden_inputs}
            
            login_data.update({
                'txtBrojDosijea': os.getenv("STUDENT_ID"),
                'txtLozinka': os.getenv("PASSWORD"),
                'btnPrijava': 'Prijava',
                '__EVENTTARGET': '',
                '__EVENTARGUMENT': '',
                '__VIEWSTATE': login_data.get('__VIEWSTATE', ''),
                '__VIEWSTATEGENERATOR': login_data.get('__VIEWSTATEGENERATOR', ''),
                '__EVENTVALIDATION': login_data.get('__EVENTVALIDATION', '')
            })
            
            print("Attempting login...")
            print(f"Using student ID: {os.getenv('STUDENT_ID')}")
            print("Password length:", len(os.getenv("PASSWORD", "")))
            
            headers = {
                'User-Agent': 'Mozilla/5.0 (Macintosh; Intel Mac OS X 10_15_7) AppleWebKit/537.36 (KHTML, like Gecko) Chrome/91.0.4472.124 Safari/537.36',
                'Content-Type': 'application/x-www-form-urlencoded',
                'Origin': 'https://www.fit.ba',
                'Referer': self.login_url
            }
            
            response = self.session.post(
                form_action,
                data=login_data,
                headers=headers,
                allow_redirects=True
            )
            response.raise_for_status()
            
            if "Obavijesti" in response.text:
                print("Login successful!")
                return True
            else:
                print("Login failed. Response content:")
                print(response.text[:500])  # print first 500 chars of response
                return False
                
        except requests.exceptions.RequestException as e:
            print(f"Error during login: {e}")
            return False
        except Exception as e:
            print(f"Unexpected error during login: {e}")
            return False

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

        msg = MIMEMultipart('alternative')
        msg['From'] = self.sender_email
        msg['To'] = self.recipient_email
        msg['Subject'] = f"New FIT Notifications - {datetime.now().strftime('%Y-%m-%d %H:%M')}"

        html = """
        <html>
        <head>
            <style>
                body { font-family: Arial, sans-serif; }
                .notification { 
                    margin-bottom: 20px; 
                    padding: 15px;
                    border-bottom: 1px solid #eee;
                }
                .title { 
                    font-weight: bold;
                    font-size: 16px;
                    color: #2c3e50;
                    margin-bottom: 5px;
                }
                .meta { 
                    color: #7f8c8d;
                    font-size: 12px;
                    margin-bottom: 5px;
                }
                .abstract {
                    color: #34495e;
                    margin-top: 10px;
                }
                .link {
                    color: #3498db;
                    text-decoration: none;
                }
                .link:hover {
                    text-decoration: underline;
                }
            </style>
        </head>
        <body>
            <h2>New notifications from FIT:</h2>
        """

        for notification in new_notifications:
            html += f"""
            <div class="notification">
                <div class="title">{notification['title']}</div>
                <div class="meta">
                    Date: {notification['date']}<br>
                    Subject: {notification['subject']}<br>
                    Author: {notification['author']}
                </div>
                <div class="abstract">{notification['abstract']}</div>
                <a href="{notification['link']}" class="link">Read more →</a>
            </div>
            """

        html += """
        </body>
        </html>
        """

        # plain text version of the email as fallback
        text = "New notifications from FIT:\n\n"
        for notification in new_notifications:
            text += f"Title: {notification['title']}\n"
            text += f"Date: {notification['date']}\n"
            text += f"Subject: {notification['subject']}\n"
            text += f"Author: {notification['author']}\n"
            text += f"Abstract: {notification['abstract']}\n"
            text += f"Link: {notification['link']}\n"
            text += "\n" + "-"*50 + "\n\n"

        msg.attach(MIMEText(text, 'plain'))
        msg.attach(MIMEText(html, 'html'))

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
        
        if self.test_mode:
            print("Running in test mode - will send all current notifications")
            new_notifications = current_notifications
        else:
            new_notifications = [
                n for n in current_notifications 
                if n['id'] not in self.seen_notifications
            ]

        if new_notifications:
            self.send_email(new_notifications)
            if not self.test_mode:
                self.seen_notifications.extend([n['id'] for n in new_notifications])
                self.save_seen_notifications()
            print(f"Found {len(new_notifications)} notifications!")
            if self.test_mode:
                print("Test email sent with current notifications!")
        else:
            print("No notifications found.")

if __name__ == "__main__":
    parser = argparse.ArgumentParser(description='FIT Notification Scraper')
    parser.add_argument('--test', action='store_true', help='Run in test mode - send all current notifications')
    parser.add_argument('--debug', action='store_true', help='Show debug information')
    args = parser.parse_args()

    scraper = FITScraper(test_mode=args.test)
    scraper.run() 