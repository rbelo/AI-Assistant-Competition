import streamlit as st
import smtplib
import re
import jwt
import os
import datetime
from email.mime.text import MIMEText
from email.mime.multipart import MIMEMultipart
from .database_handler import exists_user

def get_mail():
    try:
        return st.secrets["mail"]["email"]
    except (KeyError, AttributeError):
        return None

def get_mail_api_pass():
    try:
        return st.secrets["mail"]["api_key"]
    except (KeyError, AttributeError):
        return None

def get_app_link():
    # Auto-detect local development environment
    try:
        host = st.context.headers.get("Host", "")
        if "localhost" in host or "127.0.0.1" in host:
            return f"http://{host}"
    except Exception:
        pass  # st.context may not be available in all contexts

    # Fall back to configured production URL
    try:
        return st.secrets["app"]["link"]
    except (KeyError, AttributeError):
        return None

# Validate email format (lowercase only)
def valid_email(email):
    if any(char.isupper() for char in email):
        return False
    email_pattern = r'^[a-z0-9_.+-]+@[a-z0-9-]+\.[a-z0-9-.]+$'
    return bool(re.match(email_pattern, email))

# Initiate set password
# Returns: True if email sent successfully, False if email failed, None if user not found
def set_password(email):
    if exists_user(email):
        set_password_link = generate_set_password_link(email)
        return send_set_password_email(email, set_password_link)
    return None

# Send email with set password link
def send_set_password_email(email, set_password_link):
    message = MIMEMultipart()
    message['Subject'] = "AI-Assistant Competition: Set Your Password"
    message['From'] = get_mail()
    message['To'] = email
    body = MIMEText(f"Click here to set your password: {set_password_link}", 'plain')
    message.attach(body)

    try:
        with smtplib.SMTP('smtp.gmail.com', 587) as server:
            server.starttls()
            server.login(get_mail(), get_mail_api_pass())
            server.sendmail(get_mail(), email, message.as_string())
            print("Set password email sent successfully")
            return True
    except Exception as e:
        print(f"Error sending email: {e}")
        return False

# Secret key for JWT
SECRET_KEY = str(os.getenv("SECRET_KEY"))

def get_base_url():
    return get_app_link()

# Generate set password link with JWT
def generate_set_password_link(email):
    expiration_time = datetime.datetime.now(datetime.timezone.utc) + datetime.timedelta(hours=1)
    payload = {'email': email, 'exp': expiration_time}
    token = jwt.encode(payload, SECRET_KEY, algorithm="HS256")
    
    if isinstance(token, bytes):
        token = token.decode('utf-8')
    
    set_password_url = f"{get_base_url()}?set_password={token}"
    return set_password_url
