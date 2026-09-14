import asyncio
import imaplib
import email
import json
import base64
import re
import psycopg2
from email.header import decode_header
import sys
import os

# Import credentials from the UI service file to avoid duplication
sys.path.append(os.path.join(os.path.dirname(__file__), '../../'))
try:
    from UI.email_service import SENDER_EMAIL, SENDER_PASSWORD
except ImportError:
    SENDER_EMAIL = ""
    SENDER_PASSWORD = ""

DB_URL = os.getenv("DATABASE_URL", "postgresql://fraud_user:securepassword@db:5432/fraud_db")

def connect_db():
    return psycopg2.connect(DB_URL)

def process_unread_emails():
    if not SENDER_EMAIL or not SENDER_PASSWORD:
        return
        
    try:
        # Connect to Gmail IMAP
        mail = imaplib.IMAP4_SSL("imap.gmail.com")
        mail.login(SENDER_EMAIL, SENDER_PASSWORD)
        mail.select("inbox")

        # Search for unread emails
        status, messages = mail.search(None, "UNSEEN")
        if status != "OK" or not messages[0]:
            mail.logout()
            return

        for num in messages[0].split():
            # Fetch email
            res, msg_data = mail.fetch(num, "(RFC822)")
            for response_part in msg_data:
                if isinstance(response_part, tuple):
                    msg = email.message_from_bytes(response_part[1])
                    
                    # Extract Subject
                    subject, encoding = decode_header(msg["Subject"])[0]
                    if isinstance(subject, bytes):
                        subject = subject.decode(encoding if encoding else "utf-8")
                        
                    # Find Transaction ID in subject: e.g., (ID: d60739fc...)
                    match = re.search(r"\(ID:\s*([a-zA-Z0-9\-]+)\)", subject)
                    if not match:
                        continue
                        
                    txn_id = match.group(1)
                    attachments = []
                    
                    # Parse Attachments
                    if msg.is_multipart():
                        for part in msg.walk():
                            if part.get_content_maintype() == "multipart" or part.get("Content-Disposition") is None:
                                continue
                                
                            filename = part.get_filename()
                            if filename:
                                # Convert to Base64
                                file_data = part.get_payload(decode=True)
                                b64_data = base64.b64encode(file_data).decode('utf-8')
                                attachments.append({
                                    "filename": filename,
                                    "content_type": part.get_content_type(),
                                    "content": b64_data
                                })
                                
                    if attachments:
                        # Update Database
                        conn = connect_db()
                        cur = conn.cursor()
                        
                        # Fetch current results JSON
                        cur.execute("SELECT results FROM transaction_scores WHERE id = %s", (txn_id,))
                        row = cur.fetchone()
                        if row:
                            results_json = row[0]
                            if isinstance(results_json, str):
                                results_json = json.loads(results_json)
                                
                            results_json['attached_documents'] = attachments
                            
                            cur.execute(
                                "UPDATE transaction_scores SET results = %s WHERE id = %s",
                                (json.dumps(results_json), txn_id)
                            )
                            conn.commit()
                            
                        cur.close()
                        conn.close()
                        
    except Exception as e:
        print(f"IMAP Listener Error: {e}")

async def start_email_poller():
    """Background task that polls Gmail every 30 seconds"""
    while True:
        try:
            # Run blocking IMAP task in a thread
            await asyncio.to_thread(process_unread_emails)
        except Exception as e:
            pass
        await asyncio.sleep(30)
