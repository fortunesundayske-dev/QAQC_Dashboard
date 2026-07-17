import pandas as pd
import streamlit as st

import auth
from utils import inject_global_ui, render_navigation, render_top_nav, render_table


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
all_users = getattr(auth, "all_users", lambda: {})
approved_users = getattr(auth, "approved_users", lambda: {})
restricted_users = getattr(auth, "restricted_users", lambda: {})
rejected_users = getattr(auth, "rejected_users", lambda: {})
approve_user = getattr(auth, "approve_user", None)
reject_user = getattr(auth, "reject_user", None)
restrict_user = getattr(auth, "restrict_user", None)
unrestrict_user = getattr(auth, "unrestrict_user", None)
delete_user = getattr(auth, "delete_user", None)
change_user_role = getattr(auth, "change_user_role", None)

if any(action is None for action in [approve_user, reject_user, restrict_user, unrestrict_user, delete_user, change_user_role]):
    st.error("Access administration needs the latest auth.py file. Please redeploy the latest repository version.")
    st.stop()

pending = pending_users()
all_accounts = all_users()
approved = approved_users()
restricted = restricted_users()
rejected = rejected_users()
all_user_groups = {
    "pending": pending,
    "approved": approved,
    "restricted": restricted,
    "rejected": rejected,
}
admin_username = st.session_state.get("auth", {}).get("username") or st.session_state.get("username")

c1, c2, c3, c4, c5 = st.columns(5)
c1.metric("Pending approvals", len(pending))
c2.metric("Approved users", len(approved))
c3.metric("Restricted users", len(restricted))
c4.metric("Rejected requests", len(rejected))
c5.metric("Admin users", sum(1 for user in approved.values() if user.get("role") == "admin"))

st.caption("User store: secured application data store")
if st.button("Refresh access requests", use_container_width=True):
    st.rerun()

st.markdown('<div class="section-heading">Pending Registration Requests</div>', unsafe_allow_html=True)
if not pending:
    st.info("No pending registration requests are saved in the current user store. Ask the user to confirm they saw the 'Registration submitted' success message.")
else:
    st.success(f"{len(pending)} pending request(s) need approval.")
    for username, user in pending.items():
        with st.container(border=True):
            st.subheader(user.get("name", username))
            st.caption(
                f"Username: {username} | Email: {user.get('email', '')} | "
                f"Discipline: {user.get('discipline', 'Not set')} | Requested: {user.get('created_at', '')}"
            )
            role = st.selectbox(
                "Role on approval",
                ["user", "viewer", "admin"],
                key=f"top_role_{username}",
            )
            c_approve, c_reject, c_delete = st.columns(3)
            if c_approve.button("Approve access", key=f"top_approve_{username}", use_container_width=True):
                ok, message = approve_user(username, role)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            if c_reject.button("Reject", key=f"top_reject_{username}", use_container_width=True):
                if reject_user(username):
                    st.warning("Registration rejected.")
                    st.rerun()
            confirm_delete = c_delete.checkbox("Confirm delete", key=f"top_confirm_delete_pending_{username}")
            if c_delete.button("Delete request", key=f"top_delete_pending_{username}", use_container_width=True, disabled=not confirm_delete):
                ok, message = delete_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)

st.markdown('<div class="section-heading">All User Account Status</div>', unsafe_allow_html=True)
if all_accounts:
    accounts_df = pd.DataFrame(
        [
            {
                "Username": username,
                "Name": user.get("name"),
                "Email": user.get("email"),
                "Role": user.get("role"),
                "Status": user.get("status"),
                "Discipline": user.get("discipline"),
                "Created": user.get("created_at"),
                "Approved by": user.get("approved_by"),
                "Rejected at": user.get("rejected_at"),
            }
            for username, user in all_accounts.items()
        ]
    )
    render_table(accounts_df, include_internal=True)
else:
    st.warning("No users were found in the current user store.")

st.markdown('<div class="section-heading">User Access Controls</div>', unsafe_allow_html=True)
managed_users = {**approved, **restricted}
if not managed_users:
    st.info("No approved or restricted users are available for access control.")
else:
    st.caption("Use these controls to restrict access, restore access, or permanently delete an account.")
    for username, user in managed_users.items():
        status = user.get("status", "")
        is_self = username == admin_username
        with st.container(border=True):
            detail_col, action_col, delete_col = st.columns([2.2, 1, 1])
            with detail_col:
                st.markdown(f"**{user.get('name', username)}**")
                st.caption(
                    f"Username: {username} | Email: {user.get('email', '')} | "
                    f"Role: {user.get('role', '')} | Status: {status.title()}"
                )
                if is_self:
                    st.info("This is your active admin account.")
            with action_col:
                if status == "restricted":
                    if st.button("Unrestrict", key=f"quick_unrestrict_{username}", use_container_width=True):
                        ok, message = unrestrict_user(username)
                        if ok:
                            st.success(message)
                            st.rerun()
                        else:
                            st.error(message)
                else:
                    if st.button("Restrict", key=f"quick_restrict_{username}", use_container_width=True, disabled=is_self):
                        ok, message = restrict_user(username)
                        if ok:
                            st.warning(message)
                            st.rerun()
                        else:
                            st.error(message)
            with delete_col:
                confirm_delete = st.checkbox("Confirm delete", key=f"quick_confirm_delete_{username}", disabled=is_self)
                if st.button("Delete", key=f"quick_delete_{username}", use_container_width=True, disabled=is_self or not confirm_delete):
                    ok, message = delete_user(username)
                    if ok:
                        st.warning(message)
                        st.rerun()
                    else:
                        st.error(message)

control_options = []
for status, group in all_user_groups.items():
    for username, user in group.items():
        control_options.append(
            {
                "label": f"{user.get('name', username)} ({username}) - {status.title()}",
                "username": username,
                "status": status,
                "user": user,
            }
        )

with st.container(border=True):
    st.markdown("### Admin Control Panel")
    st.caption("Restrict, unrestrict, approve, reject, or delete users from one visible control panel.")
    if not control_options:
        st.info("No user accounts are available for administration.")
    else:
        selected_label = st.selectbox(
            "Select user account",
            [item["label"] for item in control_options],
            key="admin_control_selected_user",
        )
        selected = next(item for item in control_options if item["label"] == selected_label)
        username = selected["username"]
        user = selected["user"]
        status = selected["status"]
        st.write(
            f"**{user.get('name', username)}** | Username: `{username}` | "
            f"Email: `{user.get('email', '')}` | Role: `{user.get('role', '')}` | Status: `{status}`"
        )

        is_self = username == admin_username
        if status == "pending":
            role = st.selectbox("Role on approval", ["user", "viewer", "admin"], key=f"control_role_{username}")
            approve_col, reject_col, delete_col = st.columns(3)
            if approve_col.button("Approve", key=f"control_approve_{username}", use_container_width=True):
                ok, message = approve_user(username, role)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            if reject_col.button("Reject", key=f"control_reject_{username}", use_container_width=True):
                if reject_user(username):
                    st.warning("Registration rejected.")
                    st.rerun()
            confirm_delete = delete_col.checkbox("Confirm delete", key=f"control_confirm_delete_pending_{username}")
            if delete_col.button("Delete", key=f"control_delete_pending_{username}", use_container_width=True, disabled=not confirm_delete):
                ok, message = delete_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)
        elif status == "approved":
            current_role = user.get("role", "user")
            role_options = ["user", "viewer", "admin"]
            new_role = st.selectbox(
                "Account role",
                role_options,
                index=role_options.index(current_role) if current_role in role_options else 0,
                key=f"control_change_role_{username}",
                disabled=is_self,
            )
            if st.button(
                "Save role",
                key=f"control_save_role_{username}",
                use_container_width=True,
                disabled=is_self or new_role == current_role,
            ):
                ok, message = change_user_role(username, new_role)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            restrict_col, delete_col = st.columns(2)
            if restrict_col.button("Restrict", key=f"control_restrict_{username}", use_container_width=True, disabled=is_self):
                ok, message = restrict_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)
            confirm_delete = delete_col.checkbox("Confirm delete", key=f"control_confirm_delete_approved_{username}", disabled=is_self)
            if delete_col.button("Delete", key=f"control_delete_approved_{username}", use_container_width=True, disabled=is_self or not confirm_delete):
                ok, message = delete_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)
            if is_self:
                st.info("You cannot restrict or delete your own active admin account.")
        elif status == "restricted":
            current_role = user.get("role", "user")
            role_options = ["user", "viewer", "admin"]
            new_role = st.selectbox(
                "Account role",
                role_options,
                index=role_options.index(current_role) if current_role in role_options else 0,
                key=f"control_change_role_restricted_{username}",
            )
            if st.button(
                "Save role",
                key=f"control_save_role_restricted_{username}",
                use_container_width=True,
                disabled=new_role == current_role,
            ):
                ok, message = change_user_role(username, new_role)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            unrestrict_col, delete_col = st.columns(2)
            if unrestrict_col.button("Unrestrict", key=f"control_unrestrict_{username}", use_container_width=True):
                ok, message = unrestrict_user(username)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            confirm_delete = delete_col.checkbox("Confirm delete", key=f"control_confirm_delete_restricted_{username}")
            if delete_col.button("Delete", key=f"control_delete_restricted_{username}", use_container_width=True, disabled=not confirm_delete):
                ok, message = delete_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)
        elif status == "rejected":
            role = st.selectbox("Role on approval", ["user", "viewer", "admin"], key=f"control_role_rejected_{username}")
            approve_col, delete_col = st.columns(2)
            if approve_col.button("Approve rejected request", key=f"control_approve_rejected_{username}", use_container_width=True):
                ok, message = approve_user(username, role)
                if ok:
                    st.success(message)
                    st.rerun()
                else:
                    st.error(message)
            confirm_delete = delete_col.checkbox("Confirm delete", key=f"control_confirm_delete_rejected_{username}")
            if delete_col.button("Delete rejected request", key=f"control_delete_rejected_{username}", use_container_width=True, disabled=not confirm_delete):
                ok, message = delete_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)

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
    render_table(approved_df, include_internal=True)
    st.markdown("#### Manage approved users")
    for username, user in approved.items():
        with st.container(border=True):
            is_self = username == admin_username
            st.subheader(user.get("name", username))
            st.caption(f"Username: {username} | Email: {user.get('email')} | Role: {user.get('role')} | Discipline: {user.get('discipline', 'Not set')}")
            restrict_col, delete_col = st.columns(2)
            if restrict_col.button("Restrict user", key=f"restrict_{username}", use_container_width=True, disabled=is_self):
                ok, message = restrict_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)
            confirm_delete = delete_col.checkbox("Confirm delete", key=f"confirm_delete_{username}", disabled=is_self)
            if delete_col.button("Delete user", key=f"delete_{username}", use_container_width=True, disabled=is_self or not confirm_delete):
                ok, message = delete_user(username)
                if ok:
                    st.warning(message)
                    st.rerun()
                else:
                    st.error(message)
            if is_self:
                st.info("You cannot restrict or delete your own active admin account.")
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
    render_table(restricted_df, include_internal=True)
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
