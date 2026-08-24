"""
Evomec QA/QC Command Centre
Access Administration

Admin-only user approval and account management module.

This module is designed for the single-page sections architecture.
Authentication and user persistence remain owned by auth.py.
Shared visual/navigation components remain owned by utils.py.
"""

from __future__ import annotations

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


# ---------------------------------------------------------------------------
# PAGE CONFIGURATION
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Access Admin",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# GLOBAL UI
# ---------------------------------------------------------------------------

inject_global_ui()


# ---------------------------------------------------------------------------
# AUTHENTICATION
# ---------------------------------------------------------------------------

if not auth.login():
    st.stop()


# Admin-only access
if hasattr(auth, "require_role"):
    auth.require_role(["admin"])


# ---------------------------------------------------------------------------
# SHARED NAVIGATION
# ---------------------------------------------------------------------------

render_navigation()
render_top_nav()

if hasattr(auth, "render_user_sidebar"):
    auth.render_user_sidebar()


# ---------------------------------------------------------------------------
# PAGE HEADER
# ---------------------------------------------------------------------------

render_page_header(
    "User Approval Centre",
    (
        "Review registration requests, approve access, assign roles, "
        "and maintain controlled entry to the QA/QC dashboard."
    ),
    "Security Administration",
)


# ---------------------------------------------------------------------------
# AUTH FUNCTION VALIDATION
# ---------------------------------------------------------------------------

REQUIRED_AUTH_FUNCTIONS = [
    "pending_users",
    "all_users",
    "approved_users",
    "restricted_users",
    "rejected_users",
    "approve_user",
    "reject_user",
    "restrict_user",
    "unrestrict_user",
    "delete_user",
    "change_user_role",
]

missing_functions = [
    name
    for name in REQUIRED_AUTH_FUNCTIONS
    if not hasattr(auth, name)
]

if missing_functions:
    st.error(
        "Access administration cannot start because the current auth.py "
        "does not contain the required account-management functions."
    )

    st.code(
        "\n".join(missing_functions),
        language="text",
    )

    st.info(
        "Replace auth.py with the current version used by the migrated "
        "single-page sections architecture."
    )

    st.stop()


# ---------------------------------------------------------------------------
# LOAD USER DATA
# ---------------------------------------------------------------------------

pending = auth.pending_users() or {}
all_accounts = auth.all_users() or {}
approved = auth.approved_users() or {}
restricted = auth.restricted_users() or {}
rejected = auth.rejected_users() or {}


# ---------------------------------------------------------------------------
# CURRENT ADMIN
# ---------------------------------------------------------------------------

auth_state = st.session_state.get("auth", {})

if isinstance(auth_state, dict):
    admin_username = (
        auth_state.get("username")
        or st.session_state.get("username")
        or ""
    )
else:
    admin_username = st.session_state.get("username") or ""


# ---------------------------------------------------------------------------
# KPI SUMMARY
# ---------------------------------------------------------------------------

st.markdown(
    '<div class="section-heading">Access Overview</div>',
    unsafe_allow_html=True,
)

k1, k2, k3, k4, k5 = st.columns(5)

k1.metric(
    "Pending approvals",
    len(pending),
)

k2.metric(
    "Approved users",
    len(approved),
)

k3.metric(
    "Restricted users",
    len(restricted),
)

k4.metric(
    "Rejected requests",
    len(rejected),
)

admin_count = sum(
    1
    for user in approved.values()
    if isinstance(user, dict)
    and user.get("role") == "admin"
)

k5.metric(
    "Admin users",
    admin_count,
)


# ---------------------------------------------------------------------------
# USER STORE / REFRESH
# ---------------------------------------------------------------------------

store_col, refresh_col = st.columns([4, 1])

with store_col:
    st.caption(
        "User store: secured application data store"
    )

with refresh_col:
    if st.button(
        "Refresh",
        key="access_admin_refresh",
        use_container_width=True,
    ):
        st.rerun()


# ===========================================================================
# PENDING REGISTRATION REQUESTS
# ===========================================================================

st.markdown(
    '<div class="section-heading">Pending Registration Requests</div>',
    unsafe_allow_html=True,
)

if not pending:

    st.info(
        "No pending registration requests are currently saved in the "
        "user store."
    )

else:

    st.success(
        f"{len(pending)} pending registration request(s) require approval."
    )

    for username, user in pending.items():

        if not isinstance(user, dict):
            user = {}

        with st.container(border=True):

            name = user.get("name") or username
            email = user.get("email") or "Not provided"
            discipline = user.get("discipline") or "Not set"
            created_at = user.get("created_at") or "Not available"

            st.subheader(name)

            st.caption(
                f"Username: {username}  |  "
                f"Email: {email}  |  "
                f"Discipline: {discipline}  |  "
                f"Requested: {created_at}"
            )

            role_key = f"pending_role_{username}"

            selected_role = st.selectbox(
                "Role on approval",
                ["user", "viewer", "admin"],
                index=0,
                key=role_key,
            )

            approve_col, reject_col, delete_col = st.columns(3)

            # ---------------------------------------------------------------
            # APPROVE
            # ---------------------------------------------------------------

            with approve_col:

                if st.button(
                    "Approve Access",
                    key=f"pending_approve_{username}",
                    type="primary",
                    use_container_width=True,
                ):

                    success, message = auth.approve_user(
                        username,
                        selected_role,
                    )

                    if success:
                        st.success(message)
                        st.rerun()

                    st.error(message)

            # ---------------------------------------------------------------
            # REJECT
            # ---------------------------------------------------------------

            with reject_col:

                if st.button(
                    "Reject",
                    key=f"pending_reject_{username}",
                    use_container_width=True,
                ):

                    success = auth.reject_user(username)

                    if success:
                        st.warning(
                            f"Registration request for {username} rejected."
                        )
                        st.rerun()

                    st.error(
                        "The registration request could not be rejected."
                    )

            # ---------------------------------------------------------------
            # DELETE
            # ---------------------------------------------------------------

            with delete_col:

                confirm_key = (
                    f"pending_delete_confirm_{username}"
                )

                delete_confirmed = st.checkbox(
                    "Confirm delete",
                    key=confirm_key,
                )

                if st.button(
                    "Delete Request",
                    key=f"pending_delete_{username}",
                    use_container_width=True,
                    disabled=not delete_confirmed,
                ):

                    success, message = auth.delete_user(username)

                    if success:
                        st.warning(message)
                        st.rerun()

                    st.error(message)


# ===========================================================================
# ALL USER ACCOUNTS
# ===========================================================================

st.markdown(
    '<div class="section-heading">All User Account Status</div>',
    unsafe_allow_html=True,
)

if all_accounts:

    account_rows = []

    for username, user in all_accounts.items():

        if not isinstance(user, dict):
            user = {}

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
                "Rejected at": user.get("rejected_at", ""),
            }
        )

    accounts_df = pd.DataFrame(account_rows)

    render_table(
        accounts_df,
        include_internal=True,
    )

else:

    st.warning(
        "No user accounts were found in the current user store."
    )


# ===========================================================================
# BUILD ACCOUNT CONTROL LIST
# ===========================================================================

user_groups = {
    "pending": pending,
    "approved": approved,
    "restricted": restricted,
    "rejected": rejected,
}

control_options = []

for status, group in user_groups.items():

    for username, user in group.items():

        if not isinstance(user, dict):
            user = {}

        display_name = user.get("name") or username

        control_options.append(
            {
                "label": (
                    f"{display_name} "
                    f"({username}) - "
                    f"{status.title()}"
                ),
                "username": username,
                "status": status,
                "user": user,
            }
        )


# ===========================================================================
# ACCOUNT MANAGEMENT
# ===========================================================================

st.markdown(
    '<div class="section-heading">Account Management</div>',
    unsafe_allow_html=True,
)

with st.container(border=True):

    st.markdown("### Admin Control Panel")

    st.caption(
        "Manage approval, roles, restrictions, and account deletion "
        "from one controlled administration panel."
    )

    if not control_options:

        st.info(
            "No user accounts are currently available for administration."
        )

    else:

        labels = [
            item["label"]
            for item in control_options
        ]

        selected_label = st.selectbox(
            "Select user account",
            labels,
            key="access_admin_selected_account",
        )

        selected_account = next(
            item
            for item in control_options
            if item["label"] == selected_label
        )

        username = selected_account["username"]
        status = selected_account["status"]
        user = selected_account["user"]

        display_name = user.get("name") or username
        email = user.get("email") or "Not provided"
        current_role = user.get("role") or "user"

        st.markdown(
            f"""
            <div class="security-card">
                <h3>{display_name}</h3>
                <p>
                    <strong>Username:</strong> {username}<br>
                    <strong>Email:</strong> {email}<br>
                    <strong>Role:</strong> {current_role}<br>
                    <strong>Status:</strong> {status.title()}
                </p>
            </div>
            """,
            unsafe_allow_html=True,
        )

        st.write("")


        # ===================================================================
        # PENDING
        # ===================================================================

        if status == "pending":

            st.markdown("#### Registration Request")

            role_key = (
                f"management_pending_role_{username}"
            )

            role = st.selectbox(
                "Role on approval",
                ["user", "viewer", "admin"],
                key=role_key,
            )

            approve_col, reject_col, delete_col = st.columns(3)

            with approve_col:

                if st.button(
                    "Approve",
                    key=f"management_approve_{username}",
                    type="primary",
                    use_container_width=True,
                ):

                    success, message = auth.approve_user(
                        username,
                        role,
                    )

                    if success:
                        st.success(message)
                        st.rerun()

                    st.error(message)

            with reject_col:

                if st.button(
                    "Reject",
                    key=f"management_reject_{username}",
                    use_container_width=True,
                ):

                    success = auth.reject_user(username)

                    if success:
                        st.warning(
                            "Registration request rejected."
                        )
                        st.rerun()

                    st.error(
                        "The registration request could not be rejected."
                    )

            with delete_col:

                confirmed = st.checkbox(
                    "Confirm delete",
                    key=(
                        f"management_pending_delete_confirm_"
                        f"{username}"
                    ),
                )

                if st.button(
                    "Delete",
                    key=f"management_delete_pending_{username}",
                    use_container_width=True,
                    disabled=not confirmed,
                ):

                    success, message = auth.delete_user(
                        username
                    )

                    if success:
                        st.warning(message)
                        st.rerun()

                    st.error(message)


        # ===================================================================
        # APPROVED
        # ===================================================================

        elif status == "approved":

            st.markdown("#### Active Account")

            role_options = [
                "user",
                "viewer",
                "admin",
            ]

            current_role_index = (
                role_options.index(current_role)
                if current_role in role_options
                else 0
            )

            is_self = (
                username == admin_username
            )

            new_role = st.selectbox(
                "Account role",
                role_options,
                index=current_role_index,
                key=f"management_approved_role_{username}",
                disabled=is_self,
            )

            save_col, restrict_col, delete_col = st.columns(3)

            # ---------------------------------------------------------------
            # SAVE ROLE
            # ---------------------------------------------------------------

            with save_col:

                if st.button(
                    "Save Role",
                    key=f"management_save_role_{username}",
                    type="primary",
                    use_container_width=True,
                    disabled=(
                        is_self
                        or new_role == current_role
                    ),
                ):

                    success, message = auth.change_user_role(
                        username,
                        new_role,
                    )

                    if success:
                        st.success(message)
                        st.rerun()

                    st.error(message)

            # ---------------------------------------------------------------
            # RESTRICT
            # ---------------------------------------------------------------

            with restrict_col:

                if st.button(
                    "Restrict User",
                    key=f"management_restrict_{username}",
                    use_container_width=True,
                    disabled=is_self,
                ):

                    success, message = auth.restrict_user(
                        username
                    )

                    if success:
                        st.warning(message)
                        st.rerun()

                    st.error(message)

            # ---------------------------------------------------------------
            # DELETE
            # ---------------------------------------------------------------

            with delete_col:

                delete_confirmed = st.checkbox(
                    "Confirm delete",
                    key=(
                        f"management_approved_delete_confirm_"
                        f"{username}"
                    ),
                    disabled=is_self,
                )

                if st.button(
                    "Delete",
                    key=f"management_delete_approved_{username}",
                    use_container_width=True,
                    disabled=(
                        is_self
                        or not delete_confirmed
                    ),
                ):

                    success, message = auth.delete_user(
                        username
                    )

                    if success:
                        st.warning(message)
                        st.rerun()

                    st.error(message)

            if is_self:

                st.info(
                    "You cannot change the role, restrict, or delete "
                    "your own active administrator account."
                )


        # ===================================================================
        # RESTRICTED
        # ===================================================================

        elif status == "restricted":

            st.markdown("#### Restricted Account")

            role_options = [
                "user",
                "viewer",
                "admin",
            ]

            current_role_index = (
                role_options.index(current_role)
                if current_role in role_options
                else 0
            )

            new_role = st.selectbox(
                "Account role",
                role_options,
                index=current_role_index,
                key=f"management_restricted_role_{username}",
            )

            save_col, unrestrict_col, delete_col = st.columns(3)

            # ---------------------------------------------------------------
            # SAVE ROLE
            # ---------------------------------------------------------------

            with save_col:

                if st.button(
                    "Save Role",
                    key=f"management_save_restricted_role_{username}",
                    type="primary",
                    use_container_width=True,
                    disabled=(
                        new_role == current_role
                    ),
                ):

                    success, message = auth.change_user_role(
                        username,
                        new_role,
                    )

                    if success:
                        st.success(message)
                        st.rerun()

                    st.error(message)

            # ---------------------------------------------------------------
            # UNRESTRICT
            # ---------------------------------------------------------------

            with unrestrict_col:

                if st.button(
                    "Unrestrict User",
                    key=f"management_unrestrict_{username}",
                    type="primary",
                    use_container_width=True,
                ):

                    success, message = auth.unrestrict_user(
                        username
                    )

                    if success:
                        st.success(message)
                        st.rerun()

                    st.error(message)

            # ---------------------------------------------------------------
            # DELETE
            # ---------------------------------------------------------------

            with delete_col:

                delete_confirmed = st.checkbox(
                    "Confirm delete",
                    key=(
                        f"management_restricted_delete_confirm_"
                        f"{username}"
                    ),
                )

                if st.button(
                    "Delete",
                    key=f"management_delete_restricted_{username}",
                    use_container_width=True,
                    disabled=not delete_confirmed,
                ):

                    success, message = auth.delete_user(
                        username
                    )

                    if success:
                        st.warning(message)
                        st.rerun()

                    st.error(message)


        # ===================================================================
        # REJECTED
        # ===================================================================

        elif status == "rejected":

            st.markdown("#### Rejected Registration")

            role_key = (
                f"management_rejected_role_{username}"
            )

            role = st.selectbox(
                "Role if approved",
                ["user", "viewer", "admin"],
                key=role_key,
            )

            approve_col, delete_col = st.columns(2)

            # ---------------------------------------------------------------
            # APPROVE AGAIN
            # ---------------------------------------------------------------

            with approve_col:

                if st.button(
                    "Approve Request",
                    key=f"management_approve_rejected_{username}",
                    type="primary",
                    use_container_width=True,
                ):

                    success, message = auth.approve_user(
                        username,
                        role,
                    )

                    if success:
                        st.success(message)
                        st.rerun()

                    st.error(message)

            # ---------------------------------------------------------------
            # DELETE
            # ---------------------------------------------------------------

            with delete_col:

                delete_confirmed = st.checkbox(
                    "Confirm delete",
                    key=(
                        f"management_rejected_delete_confirm_"
                        f"{username}"
                    ),
                )

                if st.button(
                    "Delete Request",
                    key=f"management_delete_rejected_{username}",
                    use_container_width=True,
                    disabled=not delete_confirmed,
                ):

                    success, message = auth.delete_user(
                        username
                    )

                    if success:
                        st.warning(message)
                        st.rerun()

                    st.error(message)


# ===========================================================================
# SECURITY CHECKLIST
# ===========================================================================

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
                Use SSO/MFA where possible. Keep administrator accounts
                separate from normal user accounts.
            </p>
        </div>

        <div class="security-card">
            <h3>Transport</h3>
            <p>
                Run the dashboard behind HTTPS with secure cookies and
                a trusted reverse-proxy configuration.
            </p>
        </div>

        <div class="security-card">
            <h3>Secrets</h3>
            <p>
                Store database credentials, Exchange Online credentials,
                signing secrets, and API keys in environment variables
                or a secrets vault.
            </p>
        </div>

        <div class="security-card">
            <h3>Audit</h3>
            <p>
                Retain login, approval, export, and critical data-change
                logs for project and client audit review.
            </p>
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)