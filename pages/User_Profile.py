import streamlit as st

import auth
from utils import inject_global_ui, render_navigation, render_top_nav


st.set_page_config(page_title="User Profile", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

user = getattr(auth, "current_user", lambda: None)()

st.markdown(
    """
<div class="dashboard-hero">
    <div class="hero-eyebrow">Personal workspace</div>
    <h1>User Profile</h1>
    <p>Maintain user identity, discipline, and profile photo for a more accountable QA/QC workflow.</p>
</div>
""",
    unsafe_allow_html=True,
)

if not user:
    st.error("Profile not available.")
    st.stop()

c1, c2 = st.columns([1, 2])
with c1:
    photo = user.get("profile_photo")
    if photo:
        st.image(photo, width=180)
    else:
        st.markdown(
            '<div class="profile-avatar" style="height: 150px; width: 150px; font-size: 2rem;">'
            + "".join(part[:1] for part in user["name"].split()[:2]).upper()
            + "</div>",
            unsafe_allow_html=True,
        )
    st.caption(f"Role: {user['role'].title()} | Status: {user['status'].title()}")

with c2:
    with st.form("profile_form"):
        name = st.text_input("Full name", value=user.get("name", ""))
        email = st.text_input("Email", value=user.get("email", ""))
        discipline = st.selectbox(
            "Primary discipline",
            ["Civil", "Mechanical", "Piping", "Welding", "Electrical", "Instrumentation", "NDT", "Quality Management"],
            index=[
                "Civil",
                "Mechanical",
                "Piping",
                "Welding",
                "Electrical",
                "Instrumentation",
                "NDT",
                "Quality Management",
            ].index(user.get("discipline", "Quality Management"))
            if user.get("discipline", "Quality Management")
            in ["Civil", "Mechanical", "Piping", "Welding", "Electrical", "Instrumentation", "NDT", "Quality Management"]
            else 7,
        )
        uploaded = st.file_uploader("Profile photo", type=["png", "jpg", "jpeg"])
        saved = st.form_submit_button("Save profile", use_container_width=True)

    if saved:
        update_profile = getattr(auth, "update_profile", None)
        if update_profile and update_profile(name, email, discipline, uploaded):
            st.success("Profile updated.")
            st.rerun()
        else:
            st.error("Could not update profile.")

st.markdown('<div class="section-heading">Security Notes</div>', unsafe_allow_html=True)
st.markdown(
    """
<div class="security-card">
    <h3>Account security</h3>
    <p>Use a unique strong password and keep access limited to approved project personnel. For production deployment, place this app behind HTTPS, central identity management or SSO, SMTP approval email, backups, audit logs, secrets management, and network firewall controls.</p>
</div>
""",
    unsafe_allow_html=True,
)
