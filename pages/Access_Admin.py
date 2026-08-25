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


# ============================================================================
# PAGE CONFIG
# ============================================================================

st.set_page_config(
    page_title="Access Admin",
    page_icon="🔐",
    layout="wide",
    initial_sidebar_state="expanded",
)

inject_global_ui()


# ============================================================================
# AUTHENTICATION
# ============================================================================

if not auth.login():
    st.stop()

auth.require_role(
    ["admin"]
)


# ============================================================================
# GLOBAL NAVIGATION
# ============================================================================

render_navigation()
render_top_nav()

if hasattr(
    auth,
    "render_user_sidebar",
):
    auth.render_user_sidebar()


# ============================================================================
# PAGE HEADER
# ============================================================================

render_page_header(
    "User Approval Centre",
    (
        "Review registration requests, approve access, assign roles, "
        "and maintain controlled entry to the QA/QC dashboard."
    ),
    "Security Administration",
)


# ============================================================================
# LOAD USERS ONCE
# ============================================================================

try:

    all_accounts = auth.all_users()

except Exception as exc:

    st.error(
        f"Unable to load user accounts: {exc}"
    )

    st.stop()


if not isinstance(
    all_accounts,
    dict,
):

    st.error(
        "The authentication system returned an invalid user-store format."
    )

    st.stop()


# ============================================================================
# DERIVE STATUS GROUPS FROM ONE DATABASE SNAPSHOT
# ============================================================================

pending = {
    username: user
    for username, user in all_accounts.items()
    if isinstance(user, dict)
    and user.get("status") == "pending"
}

approved = {
    username: user
    for username, user in all_accounts.items()
    if isinstance(user, dict)
    and user.get("status") == "approved"
}

restricted = {
    username: user
    for username, user in all_accounts.items()
    if isinstance(user, dict)
    and user.get("status") == "restricted"
}

rejected = {
    username: user
    for username, user in all_accounts.items()
    if isinstance(user, dict)
    and user.get("status") == "rejected"
}


# ============================================================================
# CURRENT ADMIN
# ============================================================================

auth_state = st.session_state.get(
    "auth"
)

if isinstance(
    auth_state,
    dict,
):

    admin_username = str(
        auth_state.get(
            "username"
        )
        or ""
    ).strip().lower()

else:

    admin_username = str(
        st.session_state.get(
            "username"
        )
        or ""
    ).strip().lower()


# ============================================================================
# KPI CARDS
# ============================================================================

admin_count = sum(
    1
    for user in approved.values()
    if isinstance(user, dict)
    and str(
        user.get(
            "role",
            "",
        )
    ).lower()
    == "admin"
)


c1, c2, c3, c4, c5 = st.columns(
    5
)

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
    admin_count,
)


# ============================================================================
# STORE / REFRESH
# ============================================================================

store_col, refresh_col = st.columns(
    [3, 1]
)

with store_col:

    st.caption(
        "User store: secured MongoDB application data store"
    )

with refresh_col:

    if st.button(
        "Refresh access requests",
        width="stretch",
        key="access_admin_refresh",
    ):

        st.rerun()


# ============================================================================
# PENDING REQUESTS
# ============================================================================

st.markdown(
    '<div class="section-heading">'
    'Pending Registration Requests'
    '</div>',
    unsafe_allow_html=True,
)


if not pending:

    st.info(
        "No pending registration requests are currently "
        "saved in the user store."
    )

else:

    st.success(
        f"{len(pending)} pending request(s) need approval."
    )

    for username, raw_user in pending.items():

        user = (
            raw_user
            if isinstance(
                raw_user,
                dict,
            )
            else {}
        )

        username = str(
            username
        )

        display_name = (
            user.get(
                "name"
            )
            or username
        )

        with st.container(
            border=True
        ):

            st.subheader(
                display_name
            )

            st.caption(
                f"Username: {username} | "
                f"Email: {user.get('email', '')} | "
                f"Discipline: {user.get('discipline', 'Not set')} | "
                f"Requested: {user.get('created_at', '')}"
            )

            role = st.selectbox(
                "Role on approval",
                [
                    "user",
                    "viewer",
                    "admin",
                ],
                key=(
                    f"pending_role_"
                    f"{username}"
                ),
            )

            approve_col, reject_col, delete_col = st.columns(
                3
            )

            # --------------------------------------------------------------
            # APPROVE
            # --------------------------------------------------------------

            if approve_col.button(
                "Approve access",
                key=(
                    f"pending_approve_"
                    f"{username}"
                ),
                type="primary",
                width="stretch",
            ):

                ok, message = auth.approve_user(
                    username,
                    role,
                )

                if ok:

                    st.success(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )

            # --------------------------------------------------------------
            # REJECT
            # --------------------------------------------------------------

            if reject_col.button(
                "Reject",
                key=(
                    f"pending_reject_"
                    f"{username}"
                ),
                width="stretch",
            ):

                ok = auth.reject_user(
                    username
                )

                if ok:

                    st.warning(
                        "Registration rejected."
                    )

                    st.rerun()

                else:

                    st.error(
                        "Registration could not be rejected."
                    )

            # --------------------------------------------------------------
            # DELETE
            # --------------------------------------------------------------

            confirm_delete = delete_col.checkbox(
                "Confirm delete",
                key=(
                    f"pending_confirm_delete_"
                    f"{username}"
                ),
            )

            if delete_col.button(
                "Delete request",
                key=(
                    f"pending_delete_"
                    f"{username}"
                ),
                width="stretch",
                disabled=not confirm_delete,
            ):

                ok, message = auth.delete_user(
                    username
                )

                if ok:

                    st.warning(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


# ============================================================================
# ALL USER ACCOUNTS
# ============================================================================

st.markdown(
    '<div class="section-heading">'
    'All User Account Status'
    '</div>',
    unsafe_allow_html=True,
)


if all_accounts:

    rows = []

    for username, raw_user in all_accounts.items():

        user = (
            raw_user
            if isinstance(
                raw_user,
                dict,
            )
            else {}
        )

        rows.append(
            {
                "Username": username,
                "Name": user.get(
                    "name",
                    "",
                ),
                "Email": user.get(
                    "email",
                    "",
                ),
                "Role": user.get(
                    "role",
                    "",
                ),
                "Status": user.get(
                    "status",
                    "",
                ),
                "Discipline": user.get(
                    "discipline",
                    "",
                ),
                "Created": user.get(
                    "created_at",
                    "",
                ),
                "Approved by": user.get(
                    "approved_by",
                    "",
                ),
                "Rejected at": user.get(
                    "rejected_at",
                    "",
                ),
            }
        )

    accounts_df = pd.DataFrame(
        rows
    )

    if not accounts_df.empty:

        render_table(
            accounts_df,
            include_internal=True,
        )

else:

    st.warning(
        "No users were found in the current user store."
    )


# ============================================================================
# ACCOUNT MANAGEMENT OPTIONS
# ============================================================================

control_options = []

for status, group in {
    "pending": pending,
    "approved": approved,
    "restricted": restricted,
    "rejected": rejected,
}.items():

    for username, raw_user in group.items():

        user = (
            raw_user
            if isinstance(
                raw_user,
                dict,
            )
            else {}
        )

        display_name = (
            user.get(
                "name"
            )
            or username
        )

        control_options.append(
            {
                "label": (
                    f"{display_name} "
                    f"({username}) - "
                    f"{status.title()}"
                ),
                "username": str(
                    username
                ),
                "status": status,
                "user": user,
            }
        )


control_options.sort(
    key=lambda item: item[
        "label"
    ].lower()
)


# ============================================================================
# ACCOUNT MANAGEMENT
# ============================================================================

st.markdown(
    '<div class="section-heading">'
    'Account Management'
    '</div>',
    unsafe_allow_html=True,
)


with st.container(
    border=True
):

    st.markdown(
        "### Admin control panel"
    )

    st.caption(
        "Select a user to approve, reject, restrict, "
        "unrestrict, change role, or delete the account."
    )

    if not control_options:

        st.info(
            "No user accounts are available for administration."
        )

    else:

        labels = [
            item["label"]
            for item in control_options
        ]

        selected_label = st.selectbox(
            "Select user account",
            labels,
            key="admin_control_selected_user",
        )

        selected = next(
            (
                item
                for item in control_options
                if item["label"]
                == selected_label
            ),
            None,
        )

        if selected is None:

            st.warning(
                "The selected account could not be loaded."
            )

            st.stop()

        username = selected[
            "username"
        ]

        status = selected[
            "status"
        ]

        user = selected[
            "user"
        ]

        display_name = (
            user.get(
                "name"
            )
            or username
        )

        email = user.get(
            "email",
            "",
        )

        current_role = str(
            user.get(
                "role",
                "user",
            )
            or "user"
        ).lower()

        is_self = (
            bool(
                admin_username
            )
            and username
            == admin_username
        )

        st.write(
            f"**{display_name}** | "
            f"Username: `{username}` | "
            f"Email: `{email}` | "
            f"Role: `{current_role}` | "
            f"Status: `{status}`"
        )


        # ==================================================================
        # PENDING
        # ==================================================================

        if status == "pending":

            role = st.selectbox(
                "Role on approval",
                [
                    "user",
                    "viewer",
                    "admin",
                ],
                key=(
                    f"management_pending_role_"
                    f"{username}"
                ),
            )

            approve_col, reject_col, delete_col = st.columns(
                3
            )

            if approve_col.button(
                "Approve",
                key=(
                    f"management_approve_"
                    f"{username}"
                ),
                type="primary",
                width="stretch",
            ):

                ok, message = auth.approve_user(
                    username,
                    role,
                )

                if ok:

                    st.success(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


            if reject_col.button(
                "Reject",
                key=(
                    f"management_reject_"
                    f"{username}"
                ),
                width="stretch",
            ):

                if auth.reject_user(
                    username
                ):

                    st.warning(
                        "Registration rejected."
                    )

                    st.rerun()

                else:

                    st.error(
                        "Registration could not be rejected."
                    )


            confirm_delete = delete_col.checkbox(
                "Confirm delete",
                key=(
                    f"management_confirm_delete_pending_"
                    f"{username}"
                ),
            )

            if delete_col.button(
                "Delete",
                key=(
                    f"management_delete_pending_"
                    f"{username}"
                ),
                width="stretch",
                disabled=not confirm_delete,
            ):

                ok, message = auth.delete_user(
                    username
                )

                if ok:

                    st.warning(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


        # ==================================================================
        # APPROVED
        # ==================================================================

        elif status == "approved":

            role_options = [
                "user",
                "viewer",
                "admin",
            ]

            role_index = (
                role_options.index(
                    current_role
                )
                if current_role
                in role_options
                else 0
            )

            new_role = st.selectbox(
                "Account role",
                role_options,
                index=role_index,
                key=(
                    f"management_approved_role_"
                    f"{username}"
                ),
                disabled=is_self,
            )

            if st.button(
                "Save role",
                key=(
                    f"management_save_role_"
                    f"{username}"
                ),
                type="primary",
                width="stretch",
                disabled=(
                    is_self
                    or new_role
                    == current_role
                ),
            ):

                ok, message = (
                    auth.change_user_role(
                        username,
                        new_role,
                    )
                )

                if ok:

                    st.success(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


            restrict_col, delete_col = st.columns(
                2
            )

            if restrict_col.button(
                "Restrict",
                key=(
                    f"management_restrict_"
                    f"{username}"
                ),
                width="stretch",
                disabled=is_self,
            ):

                ok, message = auth.restrict_user(
                    username
                )

                if ok:

                    st.warning(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


            confirm_delete = delete_col.checkbox(
                "Confirm delete",
                key=(
                    f"management_confirm_delete_approved_"
                    f"{username}"
                ),
                disabled=is_self,
            )

            if delete_col.button(
                "Delete",
                key=(
                    f"management_delete_approved_"
                    f"{username}"
                ),
                width="stretch",
                disabled=(
                    is_self
                    or not confirm_delete
                ),
            ):

                ok, message = auth.delete_user(
                    username
                )

                if ok:

                    st.warning(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


            if is_self:

                st.info(
                    "You cannot restrict or delete "
                    "your own active administrator account."
                )


        # ==================================================================
        # RESTRICTED
        # ==================================================================

        elif status == "restricted":

            role_options = [
                "user",
                "viewer",
                "admin",
            ]

            role_index = (
                role_options.index(
                    current_role
                )
                if current_role
                in role_options
                else 0
            )

            new_role = st.selectbox(
                "Account role",
                role_options,
                index=role_index,
                key=(
                    f"management_restricted_role_"
                    f"{username}"
                ),
            )

            if st.button(
                "Save role",
                key=(
                    f"management_save_restricted_role_"
                    f"{username}"
                ),
                type="primary",
                width="stretch",
                disabled=(
                    new_role
                    == current_role
                ),
            ):

                ok, message = (
                    auth.change_user_role(
                        username,
                        new_role,
                    )
                )

                if ok:

                    st.success(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


            unrestrict_col, delete_col = st.columns(
                2
            )

            if unrestrict_col.button(
                "Unrestrict",
                key=(
                    f"management_unrestrict_"
                    f"{username}"
                ),
                type="primary",
                width="stretch",
            ):

                ok, message = auth.unrestrict_user(
                    username
                )

                if ok:

                    st.success(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


            confirm_delete = delete_col.checkbox(
                "Confirm delete",
                key=(
                    f"management_confirm_delete_restricted_"
                    f"{username}"
                ),
            )

            if delete_col.button(
                "Delete",
                key=(
                    f"management_delete_restricted_"
                    f"{username}"
                ),
                width="stretch",
                disabled=not confirm_delete,
            ):

                ok, message = auth.delete_user(
                    username
                )

                if ok:

                    st.warning(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


        # ==================================================================
        # REJECTED
        # ==================================================================

        elif status == "rejected":

            role = st.selectbox(
                "Role on approval",
                [
                    "user",
                    "viewer",
                    "admin",
                ],
                key=(
                    f"management_rejected_role_"
                    f"{username}"
                ),
            )

            approve_col, delete_col = st.columns(
                2
            )

            if approve_col.button(
                "Approve rejected request",
                key=(
                    f"management_approve_rejected_"
                    f"{username}"
                ),
                type="primary",
                width="stretch",
            ):

                ok, message = auth.approve_user(
                    username,
                    role,
                )

                if ok:

                    st.success(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


            confirm_delete = delete_col.checkbox(
                "Confirm delete",
                key=(
                    f"management_confirm_delete_rejected_"
                    f"{username}"
                ),
            )

            if delete_col.button(
                "Delete rejected request",
                key=(
                    f"management_delete_rejected_"
                    f"{username}"
                ),
                width="stretch",
                disabled=not confirm_delete,
            ):

                ok, message = auth.delete_user(
                    username
                )

                if ok:

                    st.warning(
                        message
                    )

                    st.rerun()

                else:

                    st.error(
                        message
                    )


# ============================================================================
# SECURITY CHECKLIST
# ============================================================================

st.markdown(
    '<div class="section-heading">'
    'Production Security Checklist'
    '</div>',
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
            Run only behind HTTPS with secure cookies and a trusted
            reverse-proxy configuration.
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
            Retain login, approval, role-change, restriction, deletion,
            export, and critical data-change logs for project and
            client audit review.
        </p>
    </div>

</div>
""",
    unsafe_allow_html=True,
)