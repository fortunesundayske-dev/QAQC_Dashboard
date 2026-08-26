"""
Evomec QA/QC Command Centre
Access Administration Section

ADMIN-ONLY USER ACCESS CONTROL

This section is intentionally designed for the single-page architecture.

Responsibilities:
- Admin-only access
- Review pending registrations
- Approve users
- Reject users
- Restrict/unrestrict users
- Change user roles
- Delete user accounts
- Display normalized user records safely

IMPORTANT:
This module does NOT render:
- st.set_page_config()
- render_navigation()
- render_top_nav()
- render_user_sidebar()
- inject_global_ui()

Those are owned by app.py.
"""

from __future__ import annotations

from typing import Any

import pandas as pd
import streamlit as st

import auth


# ============================================================================
# HELPERS
# ============================================================================


def _safe_dict(value: Any) -> dict:
    """
    Convert an arbitrary user-store record into a dictionary.

    This prevents errors such as:

        AttributeError: 'str' object has no attribute 'get'

    or:

        AttributeError: 'NoneType' object has no attribute 'get'
    """

    if isinstance(value, dict):
        return value

    # Some stores may return objects with __dict__.
    if hasattr(value, "__dict__"):
        try:
            return dict(vars(value))
        except Exception:
            pass

    return {}


def _safe_value(user: Any, *keys: str, default: Any = "") -> Any:
    """
    Safely retrieve the first available value from a user record.

    Example:

        _safe_value(user, "username", "user", "name")
    """

    record = _safe_dict(user)

    for key in keys:
        value = record.get(key)

        if value is not None and value != "":
            return value

    return default


def _username_from_record(fallback: str, user: Any) -> str:
    """
    Safely determine a username regardless of the structure returned
    by auth.py.
    """

    username = _safe_value(
        user,
        "username",
        "user",
        "user_name",
        "login",
        "email",
        default=fallback,
    )

    return str(username or fallback)


def _normalize_user(username: str, user: Any, status: str) -> dict:
    """
    Convert any auth.py user record into one consistent structure.
    """

    record = _safe_dict(user)

    normalized_username = _username_from_record(username, record)

    role = _safe_value(
        record,
        "role",
        "user_role",
        default="user",
    )

    return {
        "username": normalized_username,
        "name": _safe_value(
            record,
            "name",
            "full_name",
            "display_name",
            default=normalized_username,
        ),
        "email": _safe_value(
            record,
            "email",
            "email_address",
            default="",
        ),
        "role": str(role or "user"),
        "status": _safe_value(
            record,
            "status",
            default=status,
        ),
        "discipline": _safe_value(
            record,
            "discipline",
            default="Not set",
        ),
        "created_at": _safe_value(
            record,
            "created_at",
            "registered_at",
            "registration_date",
            default="",
        ),
        "approved_by": _safe_value(
            record,
            "approved_by",
            default="",
        ),
        "rejected_at": _safe_value(
            record,
            "rejected_at",
            default="",
        ),
        "_raw": record,
    }


def _load_store(function_name: str) -> dict:
    """
    Safely call an auth.py user-store function.

    Always returns a dictionary.

    This prevents the section from crashing if auth.py returns:
    - None
    - list
    - tuple
    - unexpected object
    """

    function = getattr(auth, function_name, None)

    if not callable(function):
        return {}

    try:
        result = function()
    except Exception as exc:
        st.error(
            f"Unable to load `{function_name}()` from auth.py: {exc}"
        )
        return {}

    if result is None:
        return {}

    if isinstance(result, dict):
        return result

    # Handle list/tuple style user stores.
    if isinstance(result, (list, tuple)):
        converted = {}

        for index, item in enumerate(result):
            record = _safe_dict(item)

            username = _username_from_record(
                str(index),
                record,
            )

            converted[username] = record

        return converted

    return {}


def _load_users() -> dict[str, dict]:
    """
    Load and normalize every user group.
    """

    raw_groups = {
        "pending": _load_store("pending_users"),
        "approved": _load_store("approved_users"),
        "restricted": _load_store("restricted_users"),
        "rejected": _load_store("rejected_users"),
    }

    normalized: dict[str, dict] = {}

    for status, group in raw_groups.items():

        normalized[status] = {}

        for key, value in group.items():

            username = _username_from_record(
                str(key),
                value,
            )

            normalized[status][username] = _normalize_user(
                username,
                value,
                status,
            )

    return normalized


def _action(name: str):
    """
    Safely retrieve an auth.py administrative action.
    """

    function = getattr(auth, name, None)

    if callable(function):
        return function

    return None


def _run_action(function, username: str, *args):
    """
    Safely execute an auth administrative function.

    Handles both common return formats:

        True
        False
        (True, "message")
        (False, "message")
    """

    if function is None:
        return False, "The required authentication function is not available."

    try:
        result = function(username, *args)

    except Exception as exc:
        return False, f"Authentication action failed: {exc}"

    if isinstance(result, tuple):

        if len(result) >= 2:
            return bool(result[0]), str(result[1])

        if len(result) == 1:
            return bool(result[0]), ""

    if isinstance(result, bool):
        return result, ""

    if result is None:
        return False, "The authentication function returned no result."

    return bool(result), str(result)


# ============================================================================
# ADMIN AUTHORIZATION
# ============================================================================


def _is_admin() -> bool:
    """
    Verify that the currently authenticated user is an administrator.
    """

    # First try the canonical auth.py role function.
    get_role = getattr(auth, "get_role", None)

    if callable(get_role):

        try:
            role = get_role()

            if str(role or "").strip().lower() in {
                "admin",
                "super_admin",
            }:
                return True

        except Exception:
            pass

    # Fallback to session state.
    session_auth = st.session_state.get("auth")

    if isinstance(session_auth, dict):

        role = session_auth.get("role")

        if str(role or "").strip().lower() in {
            "admin",
            "super_admin",
        }:
            return True

    return False


# ============================================================================
# LOGIN / AUTHORIZATION
# ============================================================================


if not auth.login():
    st.stop()


if not _is_admin():

    st.error(
        "🔐 Access Denied\n\n"
        "Only authorized administrators can access User Approval Centre."
    )

    st.stop()


# ============================================================================
# ADMIN ACTIONS
# ============================================================================


approve_user = _action("approve_user")
reject_user = _action("reject_user")
restrict_user = _action("restrict_user")
unrestrict_user = _action("unrestrict_user")
delete_user = _action("delete_user")
change_user_role = _action("change_user_role")


missing_actions = []

for action_name, action_function in {
    "approve_user": approve_user,
    "reject_user": reject_user,
    "restrict_user": restrict_user,
    "unrestrict_user": unrestrict_user,
    "delete_user": delete_user,
    "change_user_role": change_user_role,
}.items():

    if action_function is None:
        missing_actions.append(action_name)


if missing_actions:

    st.error(
        "Access Administration cannot operate because the following "
        "functions are missing from auth.py:"
    )

    for item in missing_actions:
        st.code(item)

    st.stop()


# ============================================================================
# LOAD USER STORE
# ============================================================================


users = _load_users()

pending = users.get("pending", {})
approved = users.get("approved", {})
restricted = users.get("restricted", {})
rejected = users.get("rejected", {})


# ============================================================================
# ALL USERS
# ============================================================================


all_accounts: dict[str, dict] = {}

for status, group in {
    "pending": pending,
    "approved": approved,
    "restricted": restricted,
    "rejected": rejected,
}.items():

    for username, user in group.items():

        record = dict(user)
        record["status"] = status

        all_accounts[username] = record


# ============================================================================
# CURRENT ADMIN
# ============================================================================


session_auth = st.session_state.get("auth")

if isinstance(session_auth, dict):

    admin_username = (
        session_auth.get("username")
        or session_auth.get("user")
        or session_auth.get("email")
        or ""
    )

else:

    admin_username = (
        st.session_state.get("username")
        or st.session_state.get("user")
        or ""
    )


admin_username = str(admin_username or "")


# ============================================================================
# PAGE HEADER
# ============================================================================


st.markdown(
    """
    <div class="section-heading">
        User Approval Centre
    </div>
    """,
    unsafe_allow_html=True,
)

st.caption(
    "Security Administration · Review registration requests, "
    "approve users, assign roles, and control dashboard access."
)


# ============================================================================
# KPI CARDS
# ============================================================================


admin_count = sum(
    1
    for user in approved.values()
    if str(user.get("role", "")).strip().lower()
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


# ============================================================================
# REFRESH
# ============================================================================


_, refresh_col = st.columns([4, 1])

with refresh_col:

    if st.button(
        "↻ Refresh",
        width="stretch",
        key="access_admin_refresh",
    ):
        st.rerun()


# ============================================================================
# PENDING REGISTRATION REQUESTS
# ============================================================================


st.markdown(
    '<div class="section-heading">Pending Registration Requests</div>',
    unsafe_allow_html=True,
)


if not pending:

    st.info(
        "No pending registration requests are currently waiting "
        "for administrator approval."
    )

else:

    st.success(
        f"{len(pending)} registration request(s) require administrator action."
    )

    for username, user in pending.items():

        name = user.get("name") or username
        email = user.get("email") or ""
        discipline = user.get("discipline") or "Not set"
        created = user.get("created_at") or ""

        with st.container(border=True):

            st.subheader(str(name))

            st.caption(
                f"Username: {username} · "
                f"Email: {email} · "
                f"Discipline: {discipline} · "
                f"Requested: {created}"
            )

            role = st.selectbox(
                "Role on approval",
                ["user", "viewer", "admin"],
                key=f"pending_role_{username}",
            )

            approve_col, reject_col, delete_col = st.columns(3)

            if approve_col.button(
                "✓ Approve access",
                key=f"approve_pending_{username}",
                type="primary",
                width="stretch",
            ):

                ok, message = _run_action(
                    approve_user,
                    username,
                    role,
                )

                if ok:
                    st.success(
                        message or "User approved successfully."
                    )
                    st.rerun()

                else:
                    st.error(message)

            if reject_col.button(
                "✕ Reject",
                key=f"reject_pending_{username}",
                width="stretch",
            ):

                ok, message = _run_action(
                    reject_user,
                    username,
                )

                if ok:
                    st.warning(
                        message or "Registration rejected."
                    )
                    st.rerun()

                else:
                    st.error(message)

            confirm_delete = delete_col.checkbox(
                "Confirm delete",
                key=f"confirm_delete_pending_{username}",
            )

            if delete_col.button(
                "Delete",
                key=f"delete_pending_{username}",
                width="stretch",
                disabled=not confirm_delete,
            ):

                ok, message = _run_action(
                    delete_user,
                    username,
                )

                if ok:
                    st.warning(
                        message or "Registration deleted."
                    )
                    st.rerun()

                else:
                    st.error(message)


# ============================================================================
# ALL ACCOUNT STATUS
# ============================================================================


st.markdown(
    '<div class="section-heading">All User Account Status</div>',
    unsafe_allow_html=True,
)


if all_accounts:

    table_rows = []

    for username, user in all_accounts.items():

        table_rows.append(
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

    accounts_df = pd.DataFrame(table_rows)

    st.dataframe(
        accounts_df,
        width="stretch",
        hide_index=True,
    )

else:

    st.info("No user accounts are currently available.")


# ============================================================================
# ACCOUNT MANAGEMENT
# ============================================================================


st.markdown(
    '<div class="section-heading">Account Management</div>',
    unsafe_allow_html=True,
)


control_options = []

for status, group in {
    "pending": pending,
    "approved": approved,
    "restricted": restricted,
    "rejected": rejected,
}.items():

    for username, user in group.items():

        control_options.append(
            {
                "username": username,
                "status": status,
                "user": user,
                "label": (
                    f"{user.get('name', username)} "
                    f"({username}) — {status.title()}"
                ),
            }
        )


if not control_options:

    st.info("No accounts are available for administration.")

else:

    with st.container(border=True):

        st.markdown("### 🔐 Administrator Control Panel")

        st.caption(
            "Only administrators can approve, restrict, "
            "unrestrict, change roles, or delete accounts."
        )

        labels = [
            item["label"]
            for item in control_options
        ]

        selected_label = st.selectbox(
            "Select user account",
            labels,
            key="access_admin_selected_user",
        )

        selected = next(
            item
            for item in control_options
            if item["label"] == selected_label
        )

        username = selected["username"]
        status = selected["status"]
        user = selected["user"]

        name = user.get("name", username)
        email = user.get("email", "")
        current_role = user.get("role", "user")

        st.markdown(
            f"""
            **{name}**

            Username: `{username}`

            Email: `{email}`

            Current role: `{current_role}`

            Status: `{status}`
            """
        )

        is_self = (
            str(username).strip().lower()
            == str(admin_username).strip().lower()
        )

        # --------------------------------------------------------------
        # PENDING
        # --------------------------------------------------------------

        if status == "pending":

            role = st.selectbox(
                "Role on approval",
                ["user", "viewer", "admin"],
                key=f"management_pending_role_{username}",
            )

            c1, c2, c3 = st.columns(3)

            if c1.button(
                "✓ Approve",
                key=f"management_approve_{username}",
                type="primary",
                width="stretch",
            ):

                ok, message = _run_action(
                    approve_user,
                    username,
                    role,
                )

                if ok:
                    st.success(
                        message or "User approved."
                    )
                    st.rerun()

                else:
                    st.error(message)

            if c2.button(
                "✕ Reject",
                key=f"management_reject_{username}",
                width="stretch",
            ):

                ok, message = _run_action(
                    reject_user,
                    username,
                )

                if ok:
                    st.warning(
                        message or "User rejected."
                    )
                    st.rerun()

                else:
                    st.error(message)

            confirm = c3.checkbox(
                "Confirm delete",
                key=f"management_confirm_delete_{username}",
            )

            if c3.button(
                "Delete",
                key=f"management_delete_{username}",
                disabled=not confirm,
                width="stretch",
            ):

                ok, message = _run_action(
                    delete_user,
                    username,
                )

                if ok:
                    st.warning(
                        message or "User deleted."
                    )
                    st.rerun()

                else:
                    st.error(message)

        # --------------------------------------------------------------
        # APPROVED
        # --------------------------------------------------------------

        elif status == "approved":

            role_options = [
                "user",
                "viewer",
                "admin",
            ]

            current_role = (
                str(current_role)
                if current_role in role_options
                else "user"
            )

            new_role = st.selectbox(
                "Account role",
                role_options,
                index=role_options.index(current_role),
                key=f"management_role_{username}",
                disabled=is_self,
            )

            if st.button(
                "Save role",
                key=f"management_save_role_{username}",
                type="primary",
                width="stretch",
                disabled=(
                    is_self
                    or new_role == current_role
                ),
            ):

                ok, message = _run_action(
                    change_user_role,
                    username,
                    new_role,
                )

                if ok:
                    st.success(
                        message or "User role updated."
                    )
                    st.rerun()

                else:
                    st.error(message)

            restrict_col, delete_col = st.columns(2)

            if restrict_col.button(
                "🔒 Restrict access",
                key=f"management_restrict_{username}",
                width="stretch",
                disabled=is_self,
            ):

                ok, message = _run_action(
                    restrict_user,
                    username,
                )

                if ok:
                    st.warning(
                        message or "User access restricted."
                    )
                    st.rerun()

                else:
                    st.error(message)

            confirm = delete_col.checkbox(
                "Confirm delete",
                key=f"management_confirm_delete_approved_{username}",
                disabled=is_self,
            )

            if delete_col.button(
                "Delete account",
                key=f"management_delete_approved_{username}",
                width="stretch",
                disabled=is_self or not confirm,
            ):

                ok, message = _run_action(
                    delete_user,
                    username,
                )

                if ok:
                    st.warning(
                        message or "User deleted."
                    )
                    st.rerun()

                else:
                    st.error(message)

            if is_self:

                st.info(
                    "🛡️ Your active administrator account cannot "
                    "be restricted or deleted from this panel."
                )

        # --------------------------------------------------------------
        # RESTRICTED
        # --------------------------------------------------------------

        elif status == "restricted":

            role_options = [
                "user",
                "viewer",
                "admin",
            ]

            current_role = (
                str(current_role)
                if current_role in role_options
                else "user"
            )

            new_role = st.selectbox(
                "Account role",
                role_options,
                index=role_options.index(current_role),
                key=f"management_restricted_role_{username}",
            )

            if st.button(
                "Save role",
                key=f"management_restricted_save_role_{username}",
                type="primary",
                width="stretch",
                disabled=new_role == current_role,
            ):

                ok, message = _run_action(
                    change_user_role,
                    username,
                    new_role,
                )

                if ok:
                    st.success(
                        message or "User role updated."
                    )
                    st.rerun()

                else:
                    st.error(message)

            c1, c2 = st.columns(2)

            if c1.button(
                "🔓 Unrestrict access",
                key=f"management_unrestrict_{username}",
                type="primary",
                width="stretch",
            ):

                ok, message = _run_action(
                    unrestrict_user,
                    username,
                )

                if ok:
                    st.success(
                        message or "User access restored."
                    )
                    st.rerun()

                else:
                    st.error(message)

            confirm = c2.checkbox(
                "Confirm delete",
                key=f"management_confirm_delete_restricted_{username}",
            )

            if c2.button(
                "Delete account",
                key=f"management_delete_restricted_{username}",
                width="stretch",
                disabled=not confirm,
            ):

                ok, message = _run_action(
                    delete_user,
                    username,
                )

                if ok:
                    st.warning(
                        message or "User deleted."
                    )
                    st.rerun()

                else:
                    st.error(message)

        # --------------------------------------------------------------
        # REJECTED
        # --------------------------------------------------------------

        elif status == "rejected":

            role = st.selectbox(
                "Role on approval",
                ["user", "viewer", "admin"],
                key=f"management_rejected_role_{username}",
            )

            c1, c2 = st.columns(2)

            if c1.button(
                "✓ Approve request",
                key=f"management_approve_rejected_{username}",
                type="primary",
                width="stretch",
            ):

                ok, message = _run_action(
                    approve_user,
                    username,
                    role,
                )

                if ok:
                    st.success(
                        message or "User approved."
                    )
                    st.rerun()

                else:
                    st.error(message)

            confirm = c2.checkbox(
                "Confirm delete",
                key=f"management_confirm_delete_rejected_{username}",
            )

            if c2.button(
                "Delete request",
                key=f"management_delete_rejected_{username}",
                width="stretch",
                disabled=not confirm,
            ):

                ok, message = _run_action(
                    delete_user,
                    username,
                )

                if ok:
                    st.warning(
                        message or "Request deleted."
                    )
                    st.rerun()

                else:
                    st.error(message)


# ============================================================================
# SECURITY INFORMATION
# ============================================================================


st.markdown(
    '<div class="section-heading">Production Security Controls</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
    <div class="tool-grid">

        <div class="security-card">
            <h3>🔐 Identity</h3>
            <p>
                User access is controlled through the authenticated
                application identity and administrator approval.
            </p>
        </div>

        <div class="security-card">
            <h3>👤 Administrator Approval</h3>
            <p>
                New registrations remain pending until an authorized
                administrator approves the account.
            </p>
        </div>

        <div class="security-card">
            <h3>🛡️ Access Restriction</h3>
            <p>
                Administrators can restrict active users without deleting
                their account.
            </p>
        </div>

        <div class="security-card">
            <h3>📋 Auditability</h3>
            <p>
                Approval, rejection, role changes, restriction and deletion
                actions should remain traceable in the authentication store.
            </p>
        </div>

    </div>
    """,
    unsafe_allow_html=True,
)