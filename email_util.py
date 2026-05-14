import smtplib
import ssl
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart

def send_email(receiver_email, activity, path, priority_level,
               sender_email="hashshield000@gmail.com", sender_password="ywgn vbnw edlw emrh"):
    # Define subject and body templates based on activity
    subject_templates = {
        'created': "[Hashshield Monitor] New File Created",
        'modified': "[Hashshield Monitor] File Modified",
        'deleted': "[Hashshield Monitor] File Deleted"
    }

    body_templates = {
        'created': f"""\
Hello,

A new file or folder has been created in your monitored directory.

📁 Path: {path}
⚠️ Priority Level: {priority_level}

If this was unexpected, please review the changes.

—
Hashshield File Monitoring System
""",
        'modified': f"""\
Hello,

A file or folder has been modified in your monitored directory.

📁 Path: {path}
⚠️ Priority Level: {priority_level}

Please verify that this change was authorized.

—
Hashshield File Monitoring System
""",
        'deleted': f"""\
Hello,

A file or folder has been deleted from your monitored directory.

📁 Path: {path}
⚠️ Priority Level: {priority_level}

If this was not intentional, we recommend investigating immediately.

—
Hashshield File Monitoring System
"""
    }

    # Normalize keys
    activity = activity.lower()
    subject = subject_templates.get(activity, "[Hashshield Monitor] File Activity Detected")
    body = body_templates.get(activity, f"File activity ({activity}) occurred at: {path}\n\nPriority: {priority_level}")

    # Compose the email
    message = MIMEMultipart()
    message['From'] = sender_email
    message['To'] = receiver_email
    message['Subject'] = subject
    message.attach(MIMEText(body, 'plain'))

    # Send the email
    context = ssl.create_default_context()
    try:
        with smtplib.SMTP_SSL('smtp.gmail.com', 465, context=context) as server:
            server.login(sender_email, sender_password)
            server.sendmail(sender_email, receiver_email, message.as_string())
        print(f"Email sent to {receiver_email} regarding {activity}")
    except Exception as e:
        print(f"Email error: {e}")
