import pandas as pd
import streamlit as st

import auth

from utils import (
    inject_global_ui,
    render_navigation,
    render_page_header,
    render_top_nav,
    render_table,
)


st.set_page_config(
    page_title="Access Admin",
    layout="wide",
)


# ---------------------------------------------------------
# GLOBAL UI
# ---------------------------------------------------------

inject_global_ui()


# ---------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------

if not auth.login():
    st.stop()


# ---------------------------------------------------------
# ADMIN SECURITY GATE
# ---------------------------------------------------------

auth.require_role(["admin"])


# ---------------------------------------------------------
# NAVIGATION
# ---------------------------------------------------------



# ---------------------------------------------------------
# PAGE HEADER
# ---------------------------------------------------------

render_page_header(
    "User Approval Centre",
    (
        "Review registration requests, approve access, assign roles, "
        "restrict accounts, and maintain controlled access to the "
        "QA/QC Command Centre."
    ),
    "Security Administration",
)


# ---------------------------------------------------------
# LOAD USER DATA
# ---------------------------------------------------------

pending = auth.pending_users()
all_accounts = auth.all_users()
approved = auth.approved_users()
restricted = auth.restricted_users()
rejected = auth.rejected_users()


# ---------------------------------------------------------
# ADMIN IDENTITY
# ---------------------------------------------------------

current_admin = auth.current_user()

admin_username = (
    current_admin.get("username")
    if current_admin
    else None
)


# ---------------------------------------------------------
# KPI CARDS
# ---------------------------------------------------------

c1, c2, c3, c4, c5 = st.columns(5)

c1.metric(
    "Pending approvals",
    len(pending),
)

c2.metric(
    "Approved users",
    len(approved),
)

c3.metric(
    "Restricted users",
    len(restricted),
)

c4.metric(
    "Rejected requests",
    len(rejected),
)

c5.metric(
    "Admin users",
    sum(
        1
        for user in approved.values()
        if str(user.get("role", "")).lower() == "admin"
    ),
)


# ---------------------------------------------------------
# REFRESH
# ---------------------------------------------------------

st.markdown("")

refresh_col = st.columns([5, 1])[1]

with refresh_col:
    if st.button(
        "Refresh",
        width="stretch",
        key="access_admin_refresh",
    ):
        st.rerun()


# =========================================================
# PENDING REGISTRATION REQUESTS
# =========================================================

st.markdown(
    '<div class="section-heading">Pending Registration Requests</div>',
    unsafe_allow_html=True,
)


if not pending:

    st.info(
        "There are currently no pending registration requests."
    )

else:

    st.success(
        f"{len(pending)} registration request(s) require approval."
    )

    for username, user in pending.items():

        with st.container(border=True):

            st.subheader(
                user.get("name") or username
            )

            st.caption(
                f"Username: {username}  |  "
                f"Email: {user.get('email', '')}  |  "
                f"Discipline: {user.get('discipline', 'Not set')}  |  "
                f"Requested: {user.get('created_at', '')}"
            )

            role = st.selectbox(
                "Role on approval",
                ["user", "viewer", "admin"],
                key=f"pending_role_{username}",
            )

            approve_col, reject_col, delete_col = st.columns(3)

            with approve_col:

                if st.button(
                    "Approve access",
                    type="primary",
                    width="stretch",
                    key=f"pending_approve_{username}",
                ):

                    ok, message = auth.approve_user(
                        username,
                        role,
                    )

                    if ok:
                        st.success(message)
                        st.rerun()

                    st.error(message)

            with reject_col:

                if st.button(
                    "Reject",
                    width="stretch",
                    key=f"pending_reject_{username}",
                ):

                    ok = auth.reject_user(
                        username
                    )

                    if ok:
                        st.warning(
                            "Registration request rejected."
                        )
                        st.rerun()

                    st.error(
                        "The registration request could not be rejected."
                    )

            with delete_col:

                confirm = st.checkbox(
                    "Confirm delete",
                    key=f"pending_delete_confirm_{username}",
                )

                if st.button(
                    "Delete",
                    width="stretch",
                    disabled=not confirm,
                    key=f"pending_delete_{username}",
                ):

                    ok, message = auth.delete_user(
                        username
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    st.error(message)


# =========================================================
# ALL ACCOUNTS
# =========================================================

st.markdown(
    '<div class="section-heading">All User Account Status</div>',
    unsafe_allow_html=True,
)


if all_accounts:

    account_rows = []

    for username, user in all_accounts.items():

        account_rows.append(
            {
                "Username": username,
                "Name": user.get("name", ""),
                "Email": user.get("email", ""),
                "Role": user.get("role", ""),
                "Status": user.get("status", ""),
                "Discipline": user.get("discipline", ""),
                "Created": user.get("created_at", ""),
                "Approved by": user.get("approved_by", ""),
                "Approved at": user.get("approved_at", ""),
                "Restricted at": user.get("restricted_at", ""),
                "Rejected at": user.get("rejected_at", ""),
            }
        )

    accounts_df = pd.DataFrame(
        account_rows
    )

    render_table(
        accounts_df,
        include_internal=True,
    )

else:

    st.warning(
        "No user accounts were found."
    )


# =========================================================
# ACCOUNT MANAGEMENT
# =========================================================

st.markdown(
    '<div class="section-heading">Account Management</div>',
    unsafe_allow_html=True,
)


account_options = []

for username, user in all_accounts.items():

    account_options.append(
        {
            "username": username,
            "name": user.get("name") or username,
            "status": user.get("status") or "unknown",
            "role": user.get("role") or "user",
            "email": user.get("email") or "",
            "discipline": user.get("discipline") or "",
        }
    )


if not account_options:

    st.info(
        "No user accounts are available."
    )

else:

    with st.container(border=True):

        selected_username = st.selectbox(
            "Select user account",
            [
                item["username"]
                for item in account_options
            ],
            key="admin_selected_username",
        )

        selected = next(
            item
            for item in account_options
            if item["username"] == selected_username
        )

        username = selected["username"]
        status = str(
            selected["status"]
        ).lower()

        role = selected["role"]

        st.markdown(
            f"""
**{selected['name']}**

- Username: `{username}`
- Email: `{selected['email']}`
- Discipline: `{selected['discipline']}`
- Role: `{role}`
- Status: `{status}`
"""
        )

        is_self = (
            username == admin_username
        )


        # -------------------------------------------------
        # APPROVED ACCOUNT
        # -------------------------------------------------

        if status == "approved":

            role_options = [
                "user",
                "viewer",
                "admin",
            ]

            current_role = (
                role
                if role in role_options
                else "user"
            )

            new_role = st.selectbox(
                "Account role",
                role_options,
                index=role_options.index(
                    current_role
                ),
                disabled=is_self,
                key=f"role_{username}",
            )

            if st.button(
                "Save role",
                type="primary",
                width="stretch",
                disabled=(
                    is_self
                    or new_role == current_role
                ),
                key=f"save_role_{username}",
            ):

                ok, message = auth.change_user_role(
                    username,
                    new_role,
                )

                if ok:
                    st.success(message)
                    st.rerun()

                st.error(message)


            restrict_col, delete_col = st.columns(2)

            with restrict_col:

                if st.button(
                    "Restrict account",
                    width="stretch",
                    disabled=is_self,
                    key=f"restrict_{username}",
                ):

                    ok, message = auth.restrict_user(
                        username
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    st.error(message)


            with delete_col:

                confirm = st.checkbox(
                    "Confirm delete",
                    disabled=is_self,
                    key=f"delete_confirm_{username}",
                )

                if st.button(
                    "Delete account",
                    width="stretch",
                    disabled=(
                        is_self
                        or not confirm
                    ),
                    key=f"delete_{username}",
                ):

                    ok, message = auth.delete_user(
                        username
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    st.error(message)


            if is_self:

                st.info(
                    "You cannot restrict, demote, or delete "
                    "your own active administrator account."
                )


        # -------------------------------------------------
        # RESTRICTED ACCOUNT
        # -------------------------------------------------

        elif status == "restricted":

            role_options = [
                "user",
                "viewer",
                "admin",
            ]

            current_role = (
                role
                if role in role_options
                else "user"
            )

            new_role = st.selectbox(
                "Account role",
                role_options,
                index=role_options.index(
                    current_role
                ),
                key=f"restricted_role_{username}",
            )

            if st.button(
                "Save role",
                type="primary",
                width="stretch",
                disabled=(
                    new_role == current_role
                ),
                key=f"restricted_save_role_{username}",
            ):

                ok, message = auth.change_user_role(
                    username,
                    new_role,
                )

                if ok:
                    st.success(message)
                    st.rerun()

                st.error(message)


            unrestrict_col, delete_col = st.columns(2)

            with unrestrict_col:

                if st.button(
                    "Unrestrict",
                    type="primary",
                    width="stretch",
                    key=f"unrestrict_{username}",
                ):

                    ok, message = auth.unrestrict_user(
                        username
                    )

                    if ok:
                        st.success(message)
                        st.rerun()

                    st.error(message)


            with delete_col:

                confirm = st.checkbox(
                    "Confirm delete",
                    key=f"restricted_delete_confirm_{username}",
                )

                if st.button(
                    "Delete",
                    width="stretch",
                    disabled=not confirm,
                    key=f"restricted_delete_{username}",
                ):

                    ok, message = auth.delete_user(
                        username
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    st.error(message)


        # -------------------------------------------------
        # REJECTED ACCOUNT
        # -------------------------------------------------

        elif status == "rejected":

            role = st.selectbox(
                "Role on approval",
                [
                    "user",
                    "viewer",
                    "admin",
                ],
                key=f"rejected_role_{username}",
            )

            approve_col, delete_col = st.columns(2)

            with approve_col:

                if st.button(
                    "Approve request",
                    type="primary",
                    width="stretch",
                    key=f"approve_rejected_{username}",
                ):

                    ok, message = auth.approve_user(
                        username,
                        role,
                    )

                    if ok:
                        st.success(message)
                        st.rerun()

                    st.error(message)


            with delete_col:

                confirm = st.checkbox(
                    "Confirm delete",
                    key=f"rejected_delete_confirm_{username}",
                )

                if st.button(
                    "Delete",
                    width="stretch",
                    disabled=not confirm,
                    key=f"rejected_delete_{username}",
                ):

                    ok, message = auth.delete_user(
                        username
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    st.error(message)


        # -------------------------------------------------
        # PENDING ACCOUNT
        # -------------------------------------------------

        elif status == "pending":

            st.info(
                "This account is waiting for administrator approval. "
                "Use the Pending Registration Requests section above "
                "to approve or reject it."
            )


# =========================================================
# SECURITY CHECKLIST
# =========================================================

st.markdown(
    '<div class="section-heading">Production Security Checklist</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="tool-grid">

<div class="security-card">
<h3>Identity</h3>
<p>
Use SSO/MFA where possible and keep administrator
accounts separate from normal user accounts.
</p>
</div>

<div class="security-card">
<h3>Transport</h3>
<p>
Run the application behind HTTPS with secure cookies
and a trusted reverse proxy.
</p>
</div>

<div class="security-card">
<h3>Secrets</h3>
<p>
Keep MongoDB, Cloudinary, Exchange Online, Gmail,
and signing credentials in Streamlit Secrets or
environment variables.
</p>
</div>

<div class="security-card">
<h3>Audit</h3>
<p>
Retain login, approval, role-change, restriction,
deletion, export, and critical data-change events.
</p>
</div>

</div>
""",
    unsafe_allow_html=True,
)