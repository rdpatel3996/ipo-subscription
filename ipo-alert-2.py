import os
import time
import logging
import smtplib
from datetime import datetime
from email.mime.multipart import MIMEMultipart
from email.mime.text import MIMEText
from urllib.parse import urljoin

from bs4 import BeautifulSoup
from selenium import webdriver
from selenium.webdriver.chrome.service import Service
from webdriver_manager.chrome import ChromeDriverManager
from twilio.rest import Client
import ssl

# -------------------------
# CONFIG
# -------------------------

DASHBOARD_URL = "https://www.chittorgarh.com/ipo/ipo_dashboard.asp"

EMAIL = os.environ.get("EMAIL")
SENDER_EMAIL = os.environ.get("EMAIL")
APP_PASSWORD = os.environ.get("APP_PASSWORD")

SMTP_SERVER = "smtp.gmail.com"
SMTP_PORT = 465

TWILIO_ACCOUNT_SID = os.environ.get("TWILIO_ACCOUNT_SID")
TWILIO_AUTH_TOKEN = os.environ.get("TWILIO_AUTH_TOKEN")

FROM_WHATSAPP = "whatsapp:+14155238886"
TO_WHATSAPP = "whatsapp:+917990875608"


# -------------------------
# LOGGING SETUP
# -------------------------

logging.basicConfig(
    level=logging.INFO,
    format="%(asctime)s - %(levelname)s - %(message)s"
)


def log(msg):
    logging.info(msg)


# -------------------------
# WEEKDAY CHECK
# -------------------------

def is_weekday():
    today = datetime.today().weekday()
    return today < 5


# -------------------------
# START CHROME
# -------------------------

def start_browser():

    log("Starting Chrome browser")

    options = webdriver.ChromeOptions()
    options.add_argument("--start-maximized")

    driver = webdriver.Chrome(
        service=Service(ChromeDriverManager().install()),
        options=options
    )

    return driver


# -------------------------
# FIND IPO CLOSING TODAY
# -------------------------

def get_closing_today_ipos(driver):

    log("Opening IPO dashboard")

    driver.get(DASHBOARD_URL)

    time.sleep(5)

    log("Scraping dashboard page")

    soup = BeautifulSoup(driver.page_source, "html.parser")

    ipo_links = []

    rows = soup.find_all("tr")

    for row in rows:

        if "CT" in row.text:

            link = row.find("a")

            if link:

                ipo_name = link.text.strip()
                ipo_url = urljoin(DASHBOARD_URL, link.get("href"))

                log(f"Found IPO closing today: {ipo_name}")

                ipo_links.append({
                    "name": ipo_name,
                    "url": ipo_url
                })

    return ipo_links


# -------------------------
# GET QIB SUBSCRIPTION
# -------------------------

def get_qib_subscription(driver, ipo):

    log(f"Opening IPO page: {ipo['name']}")

    driver.get(ipo["url"])

    time.sleep(5)

    soup = BeautifulSoup(driver.page_source, "html.parser")

    tables = soup.find_all("table")

    for table in tables:

        headers = [h.text.strip() for h in table.find_all("th")]

        if "Subscription (x)" in headers:

            log("Subscription table found")

            rows = table.find_all("tr")

            for row in rows:

                cols = [c.text.strip() for c in row.find_all("td")]

                if not cols:
                    continue

                if "QIB" in cols[0]:

                    qib_subscription = cols[1]

                    log(f"QIB Subscription (X) = {qib_subscription}")

                    return f"{qib_subscription}x"

    log("QIB subscription not found")

    return "Not Found"


# -------------------------
# EMAIL ALERT
# -------------------------

def send_email(data):

    try:

        log("Preparing email alert")

        html_rows = ""

        for ipo in data:

            html_rows += f"""
            <tr>
            <td>{ipo['name']}</td>
            <td>{ipo['qib']}</td>
            <td><a href="{ipo['url']}">View</a></td>
            </tr>
            """

        html = f"""
        <h2>IPO Closing Today</h2>

        <table border="1" cellpadding="10">
        <tr>
        <th>IPO</th>
        <th>QIB Subscription (X)</th>
        <th>Link</th>
        </tr>

        {html_rows}

        </table>
        """

        msg = MIMEMultipart()

        msg["Subject"] = "IPO Closing Today"
        msg["From"] = SENDER_EMAIL
        msg["To"] = EMAIL

        msg.attach(MIMEText(html, "html"))

        log("Connecting to Gmail SMTP SSL")

        context = ssl.create_default_context()

        server = smtplib.SMTP_SSL(
            SMTP_SERVER,
            SMTP_PORT,
            context=context,
            timeout=30
        )

        log("Logging into Gmail")

        server.login(SENDER_EMAIL, APP_PASSWORD)

        log("Sending email")

        server.sendmail(SENDER_EMAIL, EMAIL, msg.as_string())

        server.quit()

        log("Email sent successfully")

    except Exception as e:

        log(f"Email sending failed: {e}")


# -------------------------
# WHATSAPP ALERT
# -------------------------

def send_whatsapp(data):

    log("Sending WhatsApp alert")

    message = "IPO Closing Today\n\n"

    for ipo in data:

        message += f"""
{ipo['name']}
QIB: {ipo['qib']}
{ipo['url']}

"""

    client = Client(TWILIO_ACCOUNT_SID, TWILIO_AUTH_TOKEN)

    client.messages.create(
        body=message,
        from_=FROM_WHATSAPP,
        to=TO_WHATSAPP
    )

    log("WhatsApp message sent")


# -------------------------
# MAIN
# -------------------------

def main():

    log("Script started")

    if not is_weekday():

        log("Weekend detected. Script exiting")

        return

    driver = start_browser()

    ipos = get_closing_today_ipos(driver)

    if not ipos:

        log("No IPO closing today")

        driver.quit()

        return

    results = []

    for ipo in ipos:

        qib = get_qib_subscription(driver, ipo)

        results.append({
            "name": ipo["name"],
            "url": ipo["url"],
            "qib": qib
        })

    send_email(results)

    send_whatsapp(results)

    log("Process completed")

    driver.quit()


if __name__ == "__main__":
    main()
