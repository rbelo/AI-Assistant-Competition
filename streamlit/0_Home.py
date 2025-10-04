import streamlit as st
import hashlib
import time
import jwt
import os
from modules.database_handler import authenticate_user, is_professor, update_password, get_user_id_by_email
from modules.email_service import valid_email, set_password

# Initialize session state variables if they are not already defined
if 'authenticated' not in st.session_state:
    st.session_state['authenticated'] = False

if 'professor' not in st.session_state:
    st.session_state['professor'] = False

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

# Get query parameters (like ?set_password=token)
# Using st.query_params (replaces st.experimental_get_query_params())
query_params = st.query_params

# Check if 'show_set_password_form' exists in query params and set session state to True
if 'show_set_password_form' in query_params:
    st.session_state['show_set_password_form'] = True

# Main login section if the user is not logged in
if not st.session_state['authenticated']:

    if not st.session_state['show_set_password_form']:
        # Set session state value for email if not already set
        if 'login_email' not in st.session_state:
            st.session_state['login_email'] = ''  # or some default value

        st.title('AI Assistant Competition')

        st.header("Login")

        # Input fields for email and password
        email = st.text_input("**Email**", value=st.session_state['login_email'])
        password = st.text_input("**Password**", type="password", value=st.session_state['login_password'])

        # Create columns to place the buttons
        col1, col2 = st.columns([5, 1])

        with col1:
            # Login button on the left
            login_button = st.button("Login", key="login_button")

        with col2:
            # Set password link that reloads the page with show_set_password_form=true
            st.markdown(
                "<a href='?show_set_password_form=true'>Set Password</a>",
                unsafe_allow_html=True
            )

        # If login button is pressed
        if login_button:
            # Hash password before authentication
            hashed_password = hashlib.sha256(password.encode()).hexdigest()
            st.warning("Please wait...")
            # Authenticate user
            if authenticate_user(email, hashed_password):
                st.session_state['login_email'] = email
                st.session_state['login_password'] = password # Consider clearing this after login for security?
                st.success("Login successful!")
                time.sleep(1)
                # Check if user is a professor
                st.session_state['professor'] = is_professor(email)
                st.session_state['authenticated'] = True
                user_id = get_user_id_by_email(email)  # Default to empty if no user_id is found
                st.session_state.update({'user_id': user_id})
                st.rerun()  # Rerun the page after successful login (CHANGED)
            else:
                st.error("Invalid email or password")

    # Set password section (when show_set_password_form is True but no token yet)
    elif st.session_state['show_set_password_form'] and 'set_password' not in query_params:
        st.header("Set Password")

        set_password_email = st.text_input("Enter your email address", key="set_password_email", value=st.session_state['set_password_email'])

        set_password_button = st.button("Set Password")

        if set_password_button:
            # Update session state with the entered email before validation
            st.session_state['set_password_email'] = set_password_email
            if valid_email(st.session_state['set_password_email']):
                if set_password(st.session_state['set_password_email']):
                    st.success("Set password link has been sent to your email! Please wait up to 10 min before asking for another one.")
                else:
                    st.error("Email not found. Please check your email and try again.")
            else:
                st.error("Please enter a valid email address.")


    # Handling set password from the link
    SECRET_KEY = str(os.getenv("SECRET_KEY"))

    # Check if there's a set_password token in query parameters
    if 'set_password' in query_params:
        st.markdown("# Set Password")
        token = query_params['set_password'][0]  # values are in lists
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
            password = st.text_input("Enter New Password", type="password", key="new_pw")
            confirm_password = st.text_input("Confirm your New Password", type="password", key="confirm_pw")
            set_password_button = st.button("Set Password", key="set_password_button")

            # When the set password button is clicked
            if set_password_button:
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

    # Create a sign-out button
    _, _, col3 = st.columns([2, 8, 2])
    with col3:
        sign_out_btn = st.button("Sign Out", key="sign_out", use_container_width=True)

        if sign_out_btn:
            for key in list(st.session_state.keys()):
                del st.session_state[key]
            st.cache_resource.clear()
            # time.sleep(1) # Usually not needed with rerun
            st.rerun() # (CHANGED)

    st.title('AI Assistant Competition')

    # Display user_id if available, otherwise fallback or show nothing
    welcome_message = "Welcome!"
    if 'user_id' in st.session_state and st.session_state.user_id:
         welcome_message = f"Welcome, {st.session_state.user_id}!"
    st.write(welcome_message)

    if st.session_state.get('professor', False): # Use .get for safer access
        st.markdown("""
                    Here's a brief overview of the content of each section of the app:
                    - **Play**: Submit prompts for ongoing games, and check chats of previous games.
                    - **Control Panel**: A dedicated page accessible only to professors for administrative tasks.
                    - **Profile**: Manage personal information.
                    - **Playground**: Test and refine AI agents in a sandbox environment.
                    - **About**: Learn more about the app's authors and contributors.
                    """)
    else:
        st.markdown("""
                    Here's a brief overview of the content of each section of the app:
                    - **Play**: Submit prompts for ongoing games, and check chats of previous games.
                    - **Control Panel**: A dedicated page accessible only to professors for administrative tasks.
                    - **Profile**: View leaderboards and manage personal information.
                    - **Playground**: Test and refine AI agents in a sandbox environment.
                    - **About**: Learn more about the app's authors and contributors.
                    """);