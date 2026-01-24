import streamlit as st
from modules.sidebar import render_sidebar
import hashlib
import time
import jwt
import os
from modules.database_handler import authenticate_user, is_instructor, update_password, get_user_id_by_email
from modules.email_service import valid_email, set_password

# Initialize session state variables if they are not already defined
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if 'instructor' not in st.session_state:
    st.session_state['instructor'] = False

if 'set_password_email' not in st.session_state:
    st.session_state['set_password_email'] = ""

if 'login_email' not in st.session_state:
    st.session_state['login_email'] = ""

if 'login_password' not in st.session_state:
    st.session_state['login_password'] = ""

if 'show_set_password_form' not in st.session_state:
    st.session_state['show_set_password_form'] = False

if 'user_id' not in st.session_state:
    st.session_state['user_id'] = ""

# Development auto-login (set DEV_AUTO_LOGIN=1 to enable)
if os.getenv("DEV_AUTO_LOGIN") and not st.session_state['authenticated']:
    st.session_state['authenticated'] = True
    st.session_state['instructor'] = os.getenv("DEV_IS_INSTRUCTOR", "").lower() in ("1", "true")
    st.session_state['user_id'] = os.getenv("DEV_USER_ID", "dev_user")
    st.session_state['login_email'] = os.getenv("DEV_EMAIL", "dev@example.com")

render_sidebar()

# Neutral landing styles and helpers
st.markdown(
    """
    <style>
        .landing-hero {
            padding: 18px 0 6px 0;
        }
        .landing-hero h1 {
            font-size: 34px;
            margin: 0 0 8px 0;
        }
        .landing-hero p {
            font-size: 16px;
            margin: 0;
        }
        .landing-section {
            border: 1px solid rgba(120,120,120,0.25);
            border-radius: 12px;
            padding: 14px 16px;
            margin: 8px 0 16px 0;
        }
        .landing-steps {
            display: grid;
            grid-template-columns: repeat(auto-fit, minmax(160px, 1fr));
            gap: 10px;
            margin-top: 8px;
        }
        .landing-step {
            border: 1px dashed rgba(120,120,120,0.35);
            border-radius: 10px;
            padding: 10px 12px;
        }
        .landing-footer {
            opacity: 0.8;
            font-size: 13px;
            margin-top: 16px;
        }
    </style>
    """,
    unsafe_allow_html=True,
)

def render_landing():
    st.markdown(
        """
        <div class="landing-hero">
            <p>Build negotiation agents, run class games, and review results in one place.</p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="landing-section">
            <h4>For Students</h4>
            <p>Join active games, craft prompts, and review released chats and scores.</p>
            <div class="landing-steps">
                <div class="landing-step">1) Join a game</div>
                <div class="landing-step">2) Use Playground to test variants</div>
                <div class="landing-step">3) Submit prompts</div>
                <div class="landing-step">4) Review chats & results</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        """
        <div class="landing-section">
            <h4>For Instructors</h4>
            <p>Create games, collect submissions, run simulations, and publish results.</p>
            <div class="landing-steps">
                <div class="landing-step">1) Create a game</div>
                <div class="landing-step">2) Collect submissions</div>
                <div class="landing-step">3) Run simulations</div>
                <div class="landing-step">4) Publish results</div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown(
        '<div class="landing-footer">Developed for AI Impact on Business, Nova SBE. Built by students from Instituto Superior Tecnico and Nova School of Business and Economics under the guidance of Professor Rodrigo Belo.</div>',
        unsafe_allow_html=True,
    )
# Get query parameters (like ?set_password=token)
# Using st.query_params (replaces st.experimental_get_query_params())
query_params = st.query_params

# Check if 'show_set_password_form' exists in query params and set session state to True
if 'show_set_password_form' in query_params:
    st.session_state['show_set_password_form'] = True

# Main login section if the user is not logged in
if not st.session_state['authenticated']:

    if not st.session_state['show_set_password_form'] and 'set_password' not in query_params:
        # Set session state value for email if not already set
        if 'login_email' not in st.session_state:
            st.session_state['login_email'] = ''  # or some default value

        st.title("AI Assistant Platform")
        render_landing()

    # Set password section (when show_set_password_form is True but no token yet)
    elif st.session_state['show_set_password_form'] and 'set_password' not in query_params:
        st.header("Set Password")
        st.write("Enter your email address and we'll send you a link to set a new password.")

        with st.form("request_set_password_form", clear_on_submit=False):
            set_password_email = st.text_input("Enter your email address", key="set_password_email", value=st.session_state['set_password_email'])
            set_password_submitted = st.form_submit_button("Set Password", type="primary")

        if set_password_submitted:
            if valid_email(set_password_email):
                result = set_password(set_password_email)
                if result is True:
                    st.success("Set password link has been sent to your email! Check spam if you don't see it.")
                elif result is False:
                    st.error("Failed to send email. Please try again later or contact support.")
                else:  # result is None - user not found
                    st.error("Email not found. Please check your email and try again.")
            else:
                st.error("Please enter a valid email address (lowercase only).")


    # Handling set password from the link
    SECRET_KEY = str(os.getenv("SECRET_KEY"))

    # Check if there's a set_password token in query parameters
    if 'set_password' in query_params:
        st.markdown("# Set Password")
        token = query_params['set_password']  # st.query_params returns strings directly
        if isinstance(token, bytes): # Handle potential bytes type if coming directly from URL processing
             token = token.decode('utf-8')
        # Removed the check for b'...' as st.query_params typically handles decoding

        try:
            # Decode the JWT token
            decoded_payload = jwt.decode(token, SECRET_KEY, algorithms=["HS256"])
            # Set email from token into session state for display/use, overwrite if necessary
            st.session_state['set_password_email'] = decoded_payload.get('email', '')
            st.info(f"Setting password for: {st.session_state['set_password_email']}") # Show the user which email is being processed

            # Input fields for new password and confirmation
            with st.form("set_new_password_form", clear_on_submit=False):
                password = st.text_input("Enter New Password", type="password", key="new_pw")
                confirm_password = st.text_input("Confirm your New Password", type="password", key="confirm_pw")
                set_new_password_submitted = st.form_submit_button("Set Password", type="primary")

            # When the set password button is clicked
            if set_new_password_submitted:
                if password and confirm_password:
                    if password == confirm_password:
                        # Check if password is strong
                        if (len(password) >= 8 and
                            any(char.isupper() for char in password) and
                            any(char.islower() for char in password) and
                            any(char.isdigit() for char in password) and
                            any(char in '!@#$%^&*()-_=+[]{}|;:,.<>?/`~' for char in password)):

                            # Hash and update password if strong
                            hashed_password = hashlib.sha256(password.encode()).hexdigest()
                            if update_password(st.session_state['set_password_email'], hashed_password):
                                st.success("Password successfully set!")
                                time.sleep(1)
                                st.query_params.clear() # Clear query params (CHANGED)
                                # Reset flags and rerun to go back to login state
                                st.session_state['show_set_password_form'] = False
                                st.session_state['set_password_email'] = ""
                                st.rerun() # (CHANGED)
                            else:
                                st.error("Failed to set password.")
                        else:
                            st.error("Password must be at least 8 characters long and include an uppercase letter, \
                                     a lowercase letter, a number, and a special character.")
                    else:
                        st.error("Passwords do not match. Please try again.")
                else:
                    st.error("Please fill in both password fields.")
        except jwt.ExpiredSignatureError:
            st.error("The set password link has expired. Please request a new one.")
            # Optionally clear the expired token param
            if 'set_password' in st.query_params:
                 del st.query_params['set_password']
            st.session_state['show_set_password_form'] = False # Go back to login/request form
            st.rerun()
        except jwt.InvalidTokenError:
            st.error("Invalid set password link. Please check the link and try again.")
             # Optionally clear the invalid token param
            if 'set_password' in st.query_params:
                 del st.query_params['set_password']
            st.session_state['show_set_password_form'] = False # Go back to login/request form
            st.rerun()


else:
    # If the user is logged in, we provide the following content

    st.title("AI Assistant Platform")
    render_landing()
