from pathlib import Path
import html

import streamlit as st

import auth
from utils import inject_global_ui, render_navigation, render_top_nav, render_page_header
from database.cloudinary_storage import private_asset_url


st.set_page_config(page_title="User Profile", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

user = getattr(auth, "current_user", lambda: None)()


def render_profile_avatar(user_record):
    photo = user_record.get("profile_photo_asset") or user_record.get("profile_photo")
    if isinstance(photo, dict):
        saved_url = str(photo.get("url") or photo.get("secure_url") or "").strip()
        if saved_url.startswith(("https://", "http://")):
            photo = saved_url
        else:
            try:
                photo = private_asset_url(photo, expires_in=300)
            except Exception:
                photo = ""
    if photo and (str(photo).startswith(("https://", "http://")) or Path(str(photo)).exists()):
        st.image(str(photo), width=180)
        return

    initials = "".join(part[:1] for part in user_record.get("name", "User").split()[:2]).upper() or "U"
    st.markdown(
        '<div class="profile-avatar" style="height: 150px; width: 150px; font-size: 2rem;">'
        + html.escape(initials)
        + "</div>",
        unsafe_allow_html=True,
    )

render_page_header(
    "User Profile",
    "Maintain user identity, discipline, and profile photo for a more accountable QA/QC workflow.",
    "Personal Workspace",
)

if not user:
    st.error("Profile not available.")
    st.stop()

c1, c2 = st.columns([1, 2])
with c1:
    render_profile_avatar(user)
    st.caption(f"Role: {user['role'].title()} | Status: {user['status'].title()}")

with c2:
    name = st.text_input("Full name", value=user.get("name", ""))
    email = st.text_input("Email", value=user.get("email", ""))
    discipline_options = auth.DISCIPLINES
    saved_discipline = user.get("discipline", "Quality Management")
    discipline_choice = st.selectbox(
        "Primary discipline",
        discipline_options + ["Other / custom"],
        index=discipline_options.index(saved_discipline) if saved_discipline in discipline_options else len(discipline_options),
    )
    custom_discipline = st.text_input("Custom discipline", value=saved_discipline if saved_discipline not in discipline_options else "")
    uploaded = st.file_uploader("Profile photo", type=["png", "jpg", "jpeg"])
    saved = st.button("Save profile", type="primary", width="stretch")

    if saved:
        discipline = custom_discipline.strip() if discipline_choice == "Other / custom" else discipline_choice
        update_profile = getattr(auth, "update_profile", None)
        if not discipline:
            st.error("Enter your custom discipline.")
        elif update_profile and update_profile(name, email, discipline, uploaded):
            st.success("Profile updated.")
            st.rerun()
        else:
            st.error("Could not update profile.")

st.markdown('<div class="section-heading">Security Notes</div>', unsafe_allow_html=True)
st.markdown(
    """
<div class="security-card">
    <h3>Account security</h3>
    <p>Use a unique strong password and keep access limited to approved project personnel. For production deployment, place this app behind HTTPS, central identity management or SSO, Exchange Online approval email, backups, audit logs, secrets management, and network firewall controls.</p>
</div>
""",
    unsafe_allow_html=True,
)
