"""
Evomec QA/QC Command Centre
Access Administration Section

IMPORTANT:
- app.py owns authentication.
- app.py owns the global sidebar.
- app.py owns top navigation.
- app.py owns page navigation.
- This section ONLY renders the Access Administration page.
- Only admin / super_admin users may perform account administration.
"""

from __future__ import annotations

import pandas as pd
import streamlit as st

import auth
import utils


# ============================================================================
# ADMIN AUTHORIZATION
# ============================================================================

def _get_current_role() -> str:
    """Safely resolve the currently authenticated user's role."""

    # First try auth.get_role()
    try:
        role = auth.get_role()
    except Exception:
        role = None

    if role:
        return str(role).strip().lower()

    # Then try auth.current_user()
    try:
        user = auth.current_user()
    except Exception:
        user = None

    if isinstance(user, dict):
        role = user.get("role")
        if role:
            return str(role).strip().lower()

    # Finally inspect Streamlit session state.
    session_auth = st.session_state.get("auth")

    if isinstance(session_auth, dict):
        role = session_auth.get("role")
        if role:
            return str(role).strip().lower()

    role = st.session_state.get("role")

    if role:
        return str(role).strip().lower()

    return ""


def _is_admin() -> bool:
    """Return True only for administrator accounts."""

    return _get_current_role() in {
        "admin",
        "super_admin",
    }


# ============================================================================
# SAFE AUTH FUNCTION ACCESS
# ============================================================================

def _get_auth_function(name: str):
    """
    Get an auth function without allowing a missing function to crash
    the entire application.
    """

    function = getattr(auth, name, None)

    if not callable(function):
        st.error(
            f"Authentication function '{name}()' is not available."
        )
        return None

    return function


# ============================================================================
# USER STORE
# ============================================================================

def _safe_user_group(function_name: str) -> dict:
    """Safely load a user group from auth.py."""

    function = _get_auth_function(function_name)

    if function is None:
        return {}

    try:
        result = function()
    except Exception as exc:
        st.error(
            f"Unable to load {function_name}(): {exc}"
        )
        return {}

    if isinstance(result, dict):
        return result

    return {}


def _load_user_store():
    """Load all account groups."""

    pending = _safe_user_group("pending_users")
    all_accounts = _safe_user_group("all_users")
    approved = _safe_user_group("approved_users")
    restricted = _safe_user_group("restricted_users")
    rejected = _safe_user_group("rejected_users")

    return (
        pending,
        all_accounts,
        approved,
        restricted,
        rejected,
    )


# ============================================================================
# USERNAME RESOLUTION
# ============================================================================

def _username_from_record(username, user) -> str:
    """
    Resolve username robustly.

    Normally the dictionary key is the username.
    Older records may store the username inside the record.
    """

    if username:
        return str(username).strip()

    if isinstance(user, dict):

        for field in (
            "username",
            "user",
            "user_name",
            "login",
            "email",
        ):
            value = user.get(field)

            if value:
                return str(value).strip()

    return ""


def _current_admin_username() -> str:
    """Resolve the currently authenticated administrator username."""

    try:
        user = auth.current_user()
    except Exception:
        user = None

    if isinstance(user, dict):

        for field in (
            "username",
            "user",
            "user_name",
            "login",
            "email",
        ):
            value = user.get(field)

            if value:
                return str(value).strip()

    session_auth = st.session_state.get("auth")

    if isinstance(session_auth, dict):

        for field in (
            "username",
            "user",
            "user_name",
            "login",
            "email",
        ):
            value = session_auth.get(field)

            if value:
                return str(value).strip()

    value = st.session_state.get("username")

    return str(value).strip() if value else ""


# ============================================================================
# SAFE ACTION EXECUTION
# ============================================================================

def _run_action(
    function_name: str,
    username: str,
    *args,
):
    """
    Execute an account-management action.

    Supports both:

        function(username)

    and:

        function(username, value)

    Also normalizes different return styles.
    """

    function = _get_auth_function(function_name)

    if function is None:
        return False, (
            f"Authentication function "
            f"'{function_name}()' is unavailable."
        )

    try:
        result = function(username, *args)

    except TypeError:

        # Compatibility with older auth.py implementations.
        try:
            result = function(username)

        except Exception as exc:
            return False, str(exc)

    except Exception as exc:
        return False, str(exc)

    # Standard:
    # (True, "message")
    if isinstance(result, tuple):

        if len(result) >= 2:
            return bool(result[0]), str(result[1])

        if len(result) == 1:
            return bool(result[0]), ""

    # Boolean API.
    if isinstance(result, bool):

        return (
            result,
            "Operation completed successfully."
            if result
            else "Operation failed.",
        )

    # String API.
    if isinstance(result, str):

        return True, result

    # Truthy fallback.
    return (
        bool(result),
        "Operation completed successfully."
        if result
        else "Operation failed.",
    )


# ============================================================================
# PAGE
# ============================================================================

def render():
    """
    Render the Access Administration section.

    app.py must already have authenticated the user.
    """

    # ------------------------------------------------------------------
    # HARD ADMIN GATE
    # ------------------------------------------------------------------

    if not _is_admin():

        st.error(
            "Access denied. Only Admin or Super Admin accounts "
            "can access the User Approval Centre."
        )

        st.info(
            "If you require access, contact an authorized administrator."
        )

        return

    # ------------------------------------------------------------------
    # LOAD AUTH ACTIONS
    # ------------------------------------------------------------------

    approve_user = _get_auth_function("approve_user")
    reject_user = _get_auth_function("reject_user")
    restrict_user = _get_auth_function("restrict_user")
    unrestrict_user = _get_auth_function("unrestrict_user")
    delete_user = _get_auth_function("delete_user")
    change_user_role = _get_auth_function("change_user_role")

    required_actions = {
        "approve_user": approve_user,
        "reject_user": reject_user,
        "restrict_user": restrict_user,
        "unrestrict_user": unrestrict_user,
        "delete_user": delete_user,
        "change_user_role": change_user_role,
    }

    missing_actions = [
        name
        for name, function in required_actions.items()
        if function is None
    ]

    if missing_actions:

        st.error(
            "The authentication module is missing the following "
            "account-management functions:"
        )

        for name in missing_actions:
            st.code(name)

        st.stop()

    # ------------------------------------------------------------------
    # HEADER
    # ------------------------------------------------------------------

    st.markdown(
        """
        <div class="dashboard-hero">
            <div class="hero-eyebrow">
                Security Administration
            </div>

            <h1>
                User Approval Centre
            </h1>

            <p>
                Review registration requests, approve access,
                assign roles, restrict accounts and maintain
                controlled entry to the QA/QC Command Centre.
            </p>
        </div>
        """,
        unsafe_allow_html=True,
    )

    st.markdown("")

    # ------------------------------------------------------------------
    # USER STORE
    # ------------------------------------------------------------------

    (
        pending,
        all_accounts,
        approved,
        restricted,
        rejected,
    ) = _load_user_store()

    all_user_groups = {
        "pending": pending,
        "approved": approved,
        "restricted": restricted,
        "rejected": rejected,
    }

    admin_username = _current_admin_username()

    # ------------------------------------------------------------------
    # KPI CARDS
    # ------------------------------------------------------------------

    admin_count = sum(
        1
        for user in approved.values()
        if isinstance(user, dict)
        and str(user.get("role", "")).strip().lower()
        in {"admin", "super_admin"}
    )

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
        admin_count,
    )

    # ------------------------------------------------------------------
    # REFRESH
    # ------------------------------------------------------------------

    st.markdown("")

    refresh_col, info_col = st.columns([1, 3])

    with refresh_col:

        if st.button(
            "Refresh access requests",
            key="access_admin_refresh",
            width="stretch",
        ):
            st.rerun()

    with info_col:

        st.caption(
            "Only approved administrators can modify account access."
        )

    # ==================================================================
    # PENDING REGISTRATION REQUESTS
    # ==================================================================

    st.markdown(
        '<div class="section-heading">'
        'Pending Registration Requests'
        '</div>',
        unsafe_allow_html=True,
    )

    if not pending:

        st.info(
            "No pending registration requests are currently "
            "available."
        )

    else:

        st.success(
            f"{len(pending)} pending registration request(s) "
            "require administrator review."
        )

        for username, user in pending.items():

            if not isinstance(user, dict):
                user = {}

            safe_username = _username_from_record(
                username,
                user,
            )

            if not safe_username:
                safe_username = str(username)

            with st.container(border=True):

                st.subheader(
                    user.get(
                        "name",
                        safe_username,
                    )
                )

                st.caption(
                    f"Username: {safe_username} | "
                    f"Email: {user.get('email', '')} | "
                    f"Discipline: "
                    f"{user.get('discipline', 'Not set')} | "
                    f"Requested: "
                    f"{user.get('created_at', '')}"
                )

                role = st.selectbox(
                    "Role on approval",
                    [
                        "user",
                        "viewer",
                        "admin",
                    ],
                    key=f"pending_role_{safe_username}",
                )

                approve_col, reject_col, delete_col = st.columns(3)

                # ------------------------------------------------------
                # APPROVE
                # ------------------------------------------------------

                if approve_col.button(
                    "Approve access",
                    key=f"pending_approve_{safe_username}",
                    type="primary",
                    width="stretch",
                ):

                    ok, message = _run_action(
                        "approve_user",
                        safe_username,
                        role,
                    )

                    if ok:
                        st.success(message)
                        st.rerun()

                    else:
                        st.error(message)

                # ------------------------------------------------------
                # REJECT
                # ------------------------------------------------------

                if reject_col.button(
                    "Reject",
                    key=f"pending_reject_{safe_username}",
                    width="stretch",
                ):

                    ok, message = _run_action(
                        "reject_user",
                        safe_username,
                    )

                    if ok:
                        st.warning(
                            message or
                            "Registration rejected."
                        )
                        st.rerun()

                    else:
                        st.error(message)

                # ------------------------------------------------------
                # DELETE
                # ------------------------------------------------------

                confirm_delete = delete_col.checkbox(
                    "Confirm delete",
                    key=f"pending_confirm_delete_{safe_username}",
                )

                if delete_col.button(
                    "Delete request",
                    key=f"pending_delete_{safe_username}",
                    width="stretch",
                    disabled=not confirm_delete,
                ):

                    ok, message = _run_action(
                        "delete_user",
                        safe_username,
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    else:
                        st.error(message)

    # ==================================================================
    # ALL USER ACCOUNTS
    # ==================================================================

    st.markdown(
        '<div class="section-heading">'
        'All User Account Status'
        '</div>',
        unsafe_allow_html=True,
    )

    if all_accounts:

        rows = []

        for username, user in all_accounts.items():

            if not isinstance(user, dict):
                user = {}

            safe_username = _username_from_record(
                username,
                user,
            )

            rows.append(
                {
                    "Username": safe_username,
                    "Name": user.get("name"),
                    "Email": user.get("email"),
                    "Role": user.get("role"),
                    "Status": user.get("status"),
                    "Discipline": user.get("discipline"),
                    "Created": user.get("created_at"),
                    "Approved by": user.get("approved_by"),
                    "Rejected at": user.get("rejected_at"),
                }
            )

        accounts_df = pd.DataFrame(rows)

        if hasattr(utils, "render_table"):

            utils.render_table(
                accounts_df,
                include_internal=True,
            )

        else:

            st.dataframe(
                accounts_df,
                width="stretch",
                hide_index=True,
            )

    else:

        st.warning(
            "No user accounts were found."
        )

    # ==================================================================
    # ACCOUNT MANAGEMENT
    # ==================================================================

    st.markdown(
        '<div class="section-heading">'
        'Account Management'
        '</div>',
        unsafe_allow_html=True,
    )

    control_options = []

    for status, group in all_user_groups.items():

        if not isinstance(group, dict):
            continue

        for username, user in group.items():

            if not isinstance(user, dict):
                user = {}

            safe_username = _username_from_record(
                username,
                user,
            )

            if not safe_username:
                safe_username = str(username)

            control_options.append(
                {
                    "label": (
                        f"{user.get('name', safe_username)} "
                        f"({safe_username}) - "
                        f"{status.title()}"
                    ),
                    "username": safe_username,
                    "status": status,
                    "user": user,
                }
            )

    with st.container(border=True):

        st.markdown(
            "### Administrator Control Panel"
        )

        st.caption(
            "Use this panel to approve, reject, restrict, "
            "unrestrict, change roles or delete accounts."
        )

        if not control_options:

            st.info(
                "No accounts are currently available "
                "for administration."
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

            selected = next(
                item
                for item in control_options
                if item["label"] == selected_label
            )

            username = selected["username"]
            user = selected["user"]
            status = selected["status"]

            st.write(
                f"**{user.get('name', username)}**  \n"
                f"Username: `{username}`  \n"
                f"Email: `{user.get('email', '')}`  \n"
                f"Role: `{user.get('role', '')}`  \n"
                f"Status: `{status}`"
            )

            is_self = (
                bool(admin_username)
                and username.lower()
                == admin_username.lower()
            )

            # ==========================================================
            # PENDING
            # ==========================================================

            if status == "pending":

                role = st.selectbox(
                    "Role on approval",
                    [
                        "user",
                        "viewer",
                        "admin",
                    ],
                    key=f"control_pending_role_{username}",
                )

                approve_col, reject_col, delete_col = st.columns(3)

                if approve_col.button(
                    "Approve",
                    key=f"control_approve_{username}",
                    type="primary",
                    width="stretch",
                ):

                    ok, message = _run_action(
                        "approve_user",
                        username,
                        role,
                    )

                    if ok:
                        st.success(message)
                        st.rerun()

                    else:
                        st.error(message)

                if reject_col.button(
                    "Reject",
                    key=f"control_reject_{username}",
                    width="stretch",
                ):

                    ok, message = _run_action(
                        "reject_user",
                        username,
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    else:
                        st.error(message)

                confirm_delete = delete_col.checkbox(
                    "Confirm delete",
                    key=f"control_confirm_delete_{username}",
                )

                if delete_col.button(
                    "Delete",
                    key=f"control_delete_{username}",
                    width="stretch",
                    disabled=not confirm_delete,
                ):

                    ok, message = _run_action(
                        "delete_user",
                        username,
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    else:
                        st.error(message)

            # ==========================================================
            # APPROVED
            # ==========================================================

            elif status == "approved":

                current_role = str(
                    user.get(
                        "role",
                        "user",
                    )
                ).strip().lower()

                role_options = [
                    "user",
                    "viewer",
                    "admin",
                ]

                role_index = (
                    role_options.index(current_role)
                    if current_role in role_options
                    else 0
                )

                new_role = st.selectbox(
                    "Account role",
                    role_options,
                    index=role_index,
                    key=f"approved_role_{username}",
                    disabled=is_self,
                )

                if st.button(
                    "Save role",
                    key=f"approved_save_role_{username}",
                    type="primary",
                    width="stretch",
                    disabled=(
                        is_self
                        or new_role == current_role
                    ),
                ):

                    ok, message = _run_action(
                        "change_user_role",
                        username,
                        new_role,
                    )

                    if ok:
                        st.success(message)
                        st.rerun()

                    else:
                        st.error(message)

                restrict_col, delete_col = st.columns(2)

                if restrict_col.button(
                    "Restrict user",
                    key=f"approved_restrict_{username}",
                    width="stretch",
                    disabled=is_self,
                ):

                    ok, message = _run_action(
                        "restrict_user",
                        username,
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    else:
                        st.error(message)

                confirm_delete = delete_col.checkbox(
                    "Confirm delete",
                    key=f"approved_confirm_delete_{username}",
                    disabled=is_self,
                )

                if delete_col.button(
                    "Delete user",
                    key=f"approved_delete_{username}",
                    width="stretch",
                    disabled=(
                        is_self
                        or not confirm_delete
                    ),
                ):

                    ok, message = _run_action(
                        "delete_user",
                        username,
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    else:
                        st.error(message)

                if is_self:

                    st.info(
                        "You cannot restrict or delete "
                        "your own active administrator account."
                    )

            # ==========================================================
            # RESTRICTED
            # ==========================================================

            elif status == "restricted":

                current_role = str(
                    user.get(
                        "role",
                        "user",
                    )
                ).strip().lower()

                role_options = [
                    "user",
                    "viewer",
                    "admin",
                ]

                role_index = (
                    role_options.index(current_role)
                    if current_role in role_options
                    else 0
                )

                new_role = st.selectbox(
                    "Account role",
                    role_options,
                    index=role_index,
                    key=f"restricted_role_{username}",
                )

                if st.button(
                    "Save role",
                    key=f"restricted_save_role_{username}",
                    type="primary",
                    width="stretch",
                    disabled=(
                        new_role == current_role
                    ),
                ):

                    ok, message = _run_action(
                        "change_user_role",
                        username,
                        new_role,
                    )

                    if ok:
                        st.success(message)
                        st.rerun()

                    else:
                        st.error(message)

                unrestrict_col, delete_col = st.columns(2)

                if unrestrict_col.button(
                    "Unrestrict user",
                    key=f"unrestrict_{username}",
                    type="primary",
                    width="stretch",
                ):

                    ok, message = _run_action(
                        "unrestrict_user",
                        username,
                    )

                    if ok:
                        st.success(message)
                        st.rerun()

                    else:
                        st.error(message)

                confirm_delete = delete_col.checkbox(
                    "Confirm delete",
                    key=f"restricted_confirm_delete_{username}",
                )

                if delete_col.button(
                    "Delete user",
                    key=f"restricted_delete_{username}",
                    width="stretch",
                    disabled=not confirm_delete,
                ):

                    ok, message = _run_action(
                        "delete_user",
                        username,
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    else:
                        st.error(message)

            # ==========================================================
            # REJECTED
            # ==========================================================

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

                if approve_col.button(
                    "Approve rejected request",
                    key=f"approve_rejected_{username}",
                    type="primary",
                    width="stretch",
                ):

                    ok, message = _run_action(
                        "approve_user",
                        username,
                        role,
                    )

                    if ok:
                        st.success(message)
                        st.rerun()

                    else:
                        st.error(message)

                confirm_delete = delete_col.checkbox(
                    "Confirm delete",
                    key=f"rejected_confirm_delete_{username}",
                )

                if delete_col.button(
                    "Delete rejected request",
                    key=f"delete_rejected_{username}",
                    width="stretch",
                    disabled=not confirm_delete,
                ):

                    ok, message = _run_action(
                        "delete_user",
                        username,
                    )

                    if ok:
                        st.warning(message)
                        st.rerun()

                    else:
                        st.error(message)

    # ==================================================================
    # SECURITY CHECKLIST
    # ==================================================================

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
                    Use SSO/MFA where possible and maintain
                    separate administrator accounts.
                </p>
            </div>

            <div class="security-card">
                <h3>Transport</h3>
                <p>
                    Run the application only through HTTPS
                    with secure session configuration.
                </p>
            </div>

            <div class="security-card">
                <h3>Secrets</h3>
                <p>
                    Keep authentication secrets, database
                    credentials and signing keys outside source code.
                </p>
            </div>

            <div class="security-card">
                <h3>Audit</h3>
                <p>
                    Retain login, approval, role-change,
                    restriction and deletion events for audit review.
                </p>
            </div>

        </div>
        """,
        unsafe_allow_html=True,
    )


# ============================================================================
# SECTION ENTRY POINT
# ============================================================================

render()