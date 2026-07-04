import pandas as pd
import streamlit as st

import auth
from utils import inject_global_ui, render_navigation, render_top_nav


st.set_page_config(page_title="Access Admin", layout="wide")
inject_global_ui()

if not auth.login():
    st.stop()

getattr(auth, "require_role", lambda roles: None)(["admin"])
render_navigation()
render_top_nav()
getattr(auth, "render_user_sidebar", lambda: None)()

st.markdown(
    """
<div class="dashboard-hero">
    <div class="hero-eyebrow">Security administration</div>
    <h1>User Approval Centre</h1>
    <p>Review registration requests, approve access, assign roles, and maintain controlled entry to the QA/QC dashboard.</p>
</div>
""",
    unsafe_allow_html=True,
)

pending_users = getattr(auth, "pending_users", lambda: {})
approved_users = getattr(auth, "approved_users", lambda: {})
restricted_users = getattr(auth, "restricted_users", lambda: {})
approve_user = getattr(auth, "approve_user", None)
reject_user = getattr(auth, "reject_user", None)
restrict_user = getattr(auth, "restrict_user", None)
unrestrict_user = getattr(auth, "unrestrict_user", None)
delete_user = getattr(auth, "delete_user", None)

if any(action is None for action in [approve_user, reject_user, restrict_user, unrestrict_user, delete_user]):
    st.error("Access administration needs the latest auth.py file. Please redeploy the latest repository version.")
    st.stop()

pending = pending_users()
approved = approved_users()
restricted = restricted_users()

c1, c2, c3, c4 = st.columns(4)
c1.metric("Pending approvals", len(pending))
c2.metric("Approved users", len(approved))
c3.metric("Restricted users", len(restricted))
c4.metric("Admin users", sum(1 for user in approved.values() if user.get("role") == "admin"))

st.markdown('<div class="section-heading">Pending Registration Requests</div>', unsafe_allow_html=True)
if not pending:
    st.success("No pending registration requests.")
else:
    for username, user in pending.items():
        with st.container(border=True):
            st.subheader(user["name"])
            st.caption(f"Username: {username} | Email: {user['email']} | Discipline: {user.get('discipline', 'Not set')}")
            role = st.selectbox(
                "Role on approval",
                ["user", "viewer", "admin"],
                key=f"role_{username}",
            )
            c_approve, c_reject, c_delete = st.columns(3)
            if c_approve.button("Approve access", key=f"approve_{username}", use_container_width=True):
                ok, message = approve_user(username, role)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            if c_reject.button("Reject", key=f"reject_{username}", use_container_width=True):
                if reject_user(username):
                    st.warning("Registration rejected.")
                    st.rerun()
            confirm_delete = c_delete.checkbox("Confirm delete", key=f"confirm_delete_pending_{username}")
            if c_delete.button("Delete request", key=f"delete_pending_{username}", use_container_width=True, disabled=not confirm_delete):
                ok, message = delete_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)

st.markdown('<div class="section-heading">Approved Users</div>', unsafe_allow_html=True)
if approved:
    approved_df = pd.DataFrame(
        [
            {
                "Username": username,
                "Name": user.get("name"),
                "Email": user.get("email"),
                "Role": user.get("role"),
                "Discipline": user.get("discipline"),
                "Approved by": user.get("approved_by"),
                "Last login": user.get("last_login"),
            }
            for username, user in approved.items()
        ]
    )
    st.dataframe(approved_df, use_container_width=True, hide_index=True)
    st.markdown("#### Manage approved users")
    for username, user in approved.items():
        with st.container(border=True):
            st.subheader(user.get("name", username))
            st.caption(f"Username: {username} | Email: {user.get('email')} | Role: {user.get('role')} | Discipline: {user.get('discipline', 'Not set')}")
            restrict_col, delete_col = st.columns(2)
            if restrict_col.button("Restrict user", key=f"restrict_{username}", use_container_width=True):
                ok, message = restrict_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)
            confirm_delete = delete_col.checkbox("Confirm delete", key=f"confirm_delete_{username}")
            if delete_col.button("Delete user", key=f"delete_{username}", use_container_width=True, disabled=not confirm_delete):
                ok, message = delete_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)
else:
    st.info("No approved users.")

st.markdown('<div class="section-heading">Restricted Users</div>', unsafe_allow_html=True)
if restricted:
    restricted_df = pd.DataFrame(
        [
            {
                "Username": username,
                "Name": user.get("name"),
                "Email": user.get("email"),
                "Role": user.get("role"),
                "Discipline": user.get("discipline"),
                "Restricted by": user.get("restricted_by"),
                "Restricted at": user.get("restricted_at"),
            }
            for username, user in restricted.items()
        ]
    )
    st.dataframe(restricted_df, use_container_width=True, hide_index=True)
    st.markdown("#### Manage restricted users")
    for username, user in restricted.items():
        with st.container(border=True):
            st.subheader(user.get("name", username))
            st.caption(f"Username: {username} | Email: {user.get('email')} | Role: {user.get('role')} | Discipline: {user.get('discipline', 'Not set')}")
            unrestrict_col, delete_col = st.columns(2)
            if unrestrict_col.button("Unrestrict user", key=f"unrestrict_{username}", use_container_width=True):
                ok, message = unrestrict_user(username)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            confirm_delete = delete_col.checkbox("Confirm delete", key=f"confirm_delete_restricted_{username}")
            if delete_col.button("Delete user", key=f"delete_restricted_{username}", use_container_width=True, disabled=not confirm_delete):
                ok, message = delete_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)
else:
    st.info("No restricted users.")

st.markdown('<div class="section-heading">Production Security Checklist</div>', unsafe_allow_html=True)
st.markdown(
    """
<div class="tool-grid">
    <div class="security-card"><h3>Identity</h3><p>Use SSO/MFA where possible. Keep admin accounts separate from normal user accounts.</p></div>
    <div class="security-card"><h3>Transport</h3><p>Run only behind HTTPS with secure cookies and trusted reverse proxy configuration.</p></div>
    <div class="security-card"><h3>Secrets</h3><p>Store SMTP, database, and signing secrets in environment variables or a secrets vault, never in source code.</p></div>
    <div class="security-card"><h3>Audit</h3><p>Retain login, approval, export, and critical data-change logs for project and client audit review.</p></div>
</div>
""",
    unsafe_allow_html=True,
)
