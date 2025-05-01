import streamlit as st
import streamlit.components.v1 as components
import os
from urllib.parse import urlencode
import requests
import json
import logging
from datetime import datetime

# Logging setup
logging.basicConfig(level=logging.INFO)
logger = logging.getLogger(__name__)

# Env variables
BACKEND_URL = os.getenv("BACKEND_URL", "http://localhost:8001")
FRONTEND_URL = os.getenv("FRONTEND_URL", "http://localhost:8501")
# GOOGLE_SCOPES = os.getenv("GOOGLE_SCOPES", "openid,email,profile").split(",")
GOOGLE_SCOPES = sorted([
    "https://www.googleapis.com/auth/calendar",
    "https://www.googleapis.com/auth/documents",
    "https://www.googleapis.com/auth/drive",
    "https://www.googleapis.com/auth/gmail.modify",  # Add this
    "https://www.googleapis.com/auth/gmail.readonly",
    "https://www.googleapis.com/auth/gmail.send",
    "https://www.googleapis.com/auth/spreadsheets",
    "https://www.googleapis.com/auth/userinfo.email",  # Add this
    "https://www.googleapis.com/auth/userinfo.profile",  # Add this
    "openid"  # Add this
])
GOOGLE_REDIRECT_URI = os.getenv("GOOGLE_REDIRECT_URI", f"{BACKEND_URL}/api/auth/google/callback")

# Streamlit page config
st.set_page_config(page_title="Chat with AI", page_icon="💬", layout="wide")

# Session state defaults
for key in ["user_id", "user_info", "chat_history", "session_id", "authenticated"]:
    if key not in st.session_state:
        st.session_state[key] = None if key != "chat_history" else []

def get_auth_url():
    params = {
        "scopes": ",".join(GOOGLE_SCOPES),
        "redirect_uri": GOOGLE_REDIRECT_URI
    }
    return f"{BACKEND_URL}/api/auth/google?{urlencode(params)}"

def send_chat_message(message):
    try:
        headers = {"Content-Type": "application/json"}
        payload = {
            "message": message,
            "session_id": st.session_state.session_id
        }
        response = requests.post(
            f"{BACKEND_URL}/api/chat/send",
            json=payload,
            headers=headers,
            params={"user_id": st.session_state.user_id}
        )
        response.raise_for_status()
        data = response.json()
        st.session_state.session_id = data.get("sessionId")
        return data
    except requests.RequestException as e:
        logger.error(f"Error sending chat message: {e}")
        st.error("Failed to send message. Please try again.")
        return None

def display_chat_history():
    with st.container():
        for msg in st.session_state.chat_history:
            if msg["role"] == "user":
                with st.chat_message("user"):
                    st.markdown(f"**You:** {msg['content']}")
                    st.markdown(f"<small>{msg['timestamp']}</small>", unsafe_allow_html=True)
            else:
                with st.chat_message("assistant"):
                    st.markdown(f"**AI:** {msg['content']}")
                    st.markdown(f"<small>{msg['timestamp']}</small>", unsafe_allow_html=True)

def main():
    query_params = st.experimental_get_query_params()

    # ✅ If redirected back with tokens
    if "provider_token" in query_params and "access_token" in query_params:
        st.session_state.authenticated = True
        st.session_state.user_id = query_params.get("user_id", [""])[0]

        try:
            headers = {"Authorization": f"Bearer {query_params.get('access_token')[0]}"}
            response = requests.get(
                "https://www.googleapis.com/oauth2/v3/userinfo",
                headers=headers
            )
            response.raise_for_status()
            st.session_state.user_info = response.json()
            st.success("Successfully authenticated with Google!")
        except Exception as e:
            logger.error(f"Error fetching user info: {e}")
            st.warning("Authenticated, but failed to fetch user info.")
            st.session_state.user_info = {
                "name": "Unknown",
                "email": "Unknown",
                "sub": "Unknown"
            }

        # ✅ Remove query params after login
        st.experimental_set_query_params()

    if not st.session_state.authenticated:
        st.title("Login with Google")
        st.write("Please sign in to continue.")

        auth_url = get_auth_url()
        if st.button("Login with Google"):
            st.markdown(f"<meta http-equiv='refresh' content='0;URL={auth_url}'>", unsafe_allow_html=True)

        with st.expander("What permissions are requested?"):
            for scope in GOOGLE_SCOPES:
                st.write(f"- {scope}")

    else:
        st.title("Chat with AI")
        col1, col2 = st.columns([3, 1])

        with col2:
            st.subheader("User Info")
            user_info = st.session_state.user_info
            st.write(f"Name: {user_info.get('name', 'N/A')}")
            st.write(f"Email: {user_info.get('email', 'N/A')}")
            st.write(f"Google User ID: {user_info.get('sub', 'N/A')}")
            st.write(f"Local User ID: {st.session_state.user_id}")

            if st.button("Logout"):
                for key in ["authenticated", "user_id", "user_info", "chat_history", "session_id"]:
                    st.session_state[key] = None if key != "chat_history" else []
                st.experimental_set_query_params()
                st.markdown("<meta http-equiv='refresh' content='0;URL=http://localhost:8501/'>", unsafe_allow_html=True)
                st.stop()

        with col1:
            user_input = st.chat_input("Type your message here...")
            if user_input:
                st.session_state.chat_history.append({
                    "role": "user",
                    "content": user_input,
                    "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                })

                response = send_chat_message(user_input)
                if response:
                    st.session_state.chat_history.append({
                        "role": "assistant",
                        "content": response["content"],
                        "timestamp": datetime.utcnow().strftime("%Y-%m-%d %H:%M:%S")
                    })

            display_chat_history()

if __name__ == "__main__":
    main()