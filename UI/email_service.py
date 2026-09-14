import smtplib
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

# ==========================================
# 🛑 CONFIGURATION REQUIRED 🛑
# ==========================================
# 1. Replace with the Gmail address you want to send FROM
SENDER_EMAIL = "fraud.portal.notifications@gmail.com"

# 2. Replace with your 16-character Google App Password (no spaces)
# How to get an App Password: 
# Go to Google Account -> Security -> 2-Step Verification -> App Passwords
SENDER_PASSWORD = "etwflxayopthdjts"
# ==========================================

def send_verification_email(customer_email, customer_name, transaction_id, amount, txn_type):
    # Format the email content
    subject = f"Action Required: Suspicious Transaction Detected (ID: {transaction_id})"
    
    html_body = f"""
    <html>
    <body style="font-family: Arial, sans-serif; color: #333;">
        <h2 style="color: #4f46e5;">Fraud Security Alert</h2>
        <p>Hello <b>{customer_name}</b>,</p>
        <p>We detected a suspicious transaction on your account that was flagged by our automated security systems.</p>
        
        <div style="background-color: #f8f9fa; padding: 15px; border-left: 4px solid #dc3545; margin: 20px 0;">
            <b>Transaction Type:</b> {txn_type}<br>
            <b>Amount:</b> ${amount:,.2f}<br>
            <b>Transaction ID:</b> {transaction_id}
        </div>
        
        <p>To protect your account, this transaction has been placed under review.</p>
        <p><b>Please reply to this email</b> with a photo of your ID and the receipt to verify this purchase.</p>
        
        <br>
        <p>Stay safe,<br>
        <b>Fraud Detection Team</b></p>
    </body>
    </html>
    """

    msg = MIMEMultipart()
    msg['From'] = f"Fraud Security Team <{SENDER_EMAIL}>"
    msg['To'] = customer_email
    msg['Subject'] = subject
    
    msg.attach(MIMEText(html_body, 'html'))

    # Connect to Gmail SMTP server
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465) as server:
            server.login(SENDER_EMAIL, SENDER_PASSWORD)
            server.send_message(msg)
            return True, "Email sent successfully!"
    except smtplib.SMTPAuthenticationError:
        return False, "Authentication Failed. Please check your App Password."
    except Exception as e:
        return False, f"Failed to send email: {str(e)}"
