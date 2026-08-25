from __future__ import annotations

import html

import streamlit as st

import auth
from database.cloudinary_storage import private_asset_url
from utils import (
    inject_global_ui,
    render_navigation,
    render_page_header,
    render_top_nav,
)


st.set_page_config(
    page_title="User Profile",
    layout="wide",
)


# ============================================================
# GLOBAL UI
# ============================================================

inject_global_ui()


# ============================================================
# AUTHENTICATION
# ============================================================

if not auth.login():
    st.stop()


# ============================================================
# NAVIGATION
# ============================================================


# ============================================================
# CURRENT USER
# ============================================================

user = auth.current_user()

if not user:
    st.error(
        "Your profile could not be loaded."
    )
    st.stop()


# ============================================================
# PHOTO RESOLUTION
# ============================================================

def resolve_profile_photo(user_record):
    photo = (
        user_record.get("profile_photo_asset")
        or user_record.get("profile_photo")
    )

    if not photo:
        return ""

    if isinstance(photo, dict):

        direct_url = str(
            photo.get("secure_url")
            or photo.get("url")
            or ""
        ).strip()

        if direct_url.startswith(
            (
                "https://",
                "http://",
            )
        ):
            return direct_url

        try:
            resolved = private_asset_url(
                photo,
                expires_in=300,
            )

            return str(
                resolved or ""
            ).strip()

        except Exception:
            return ""

    photo_string = str(
        photo
    ).strip()

    if photo_string.startswith(
        (
            "https://",
            "http://",
            "data:image/",
        )
    ):
        return photo_string

    try:
        resolved = private_asset_url(
            photo_string,
            expires_in=300,
        )

        return str(
            resolved or ""
        ).strip()

    except Exception:
        return ""


# ============================================================
# AVATAR
# ============================================================

def render_profile_avatar(user_record):

    photo_url = resolve_profile_photo(
        user_record
    )

    if photo_url:

        safe_url = html.escape(
            photo_url,
            quote=True,
        )

        st.markdown(
            f"""
<div style="
    display:flex;
    justify-content:center;
    align-items:center;
    margin-bottom:12px;
">
    <img
        src="{safe_url}"
        alt="Profile photo"
        style="
            width:180px;
            height:180px;
            object-fit:cover;
            border-radius:50%;
            border:4px solid rgba(255,255,255,.9);
            box-shadow:0 8px 30px rgba(0,0,0,.15);
        "
    >
</div>
""",
            unsafe_allow_html=True,
        )

        return

    name = str(
        user_record.get(
            "name",
            "User",
        )
    ).strip()

    initials = "".join(
        part[:1]
        for part in name.split()
        if part
    )[:2].upper() or "U"

    st.markdown(
        f"""
<div style="
    display:flex;
    justify-content:center;
    align-items:center;
">
    <div
        class="profile-avatar"
        style="
            height:150px;
            width:150px;
            font-size:2rem;
            display:flex;
            align-items:center;
            justify-content:center;
            border-radius:50%;
        "
    >
        {html.escape(initials)}
    </div>
</div>
""",
        unsafe_allow_html=True,
    )


# ============================================================
# HEADER
# ============================================================

render_page_header(
    "User Profile",
    (
        "Maintain user identity, discipline, and profile photo "
        "for a more accountable QA/QC workflow."
    ),
    "Personal Workspace",
)


# ============================================================
# PROFILE LAYOUT
# ============================================================

c1, c2 = st.columns(
    [1, 2],
    gap="large",
)


# ============================================================
# IDENTITY CARD
# ============================================================

with c1:

    render_profile_avatar(
        user
    )

    role = str(
        user.get(
            "role",
            "user",
        )
    ).replace(
        "_",
        " ",
    ).title()

    status = str(
        user.get(
            "status",
            "approved",
        )
    ).replace(
        "_",
        " ",
    ).title()

    st.caption(
        f"Role: {role} | Status: {status}"
    )

    username = str(
        user.get(
            "username",
            "",
        )
    )

    if username:
        st.caption(
            f"Username: {username}"
        )


# ============================================================
# EDIT PROFILE
# ============================================================

with c2:

    name = st.text_input(
        "Full name",
        value=str(
            user.get(
                "name",
                "",
            )
        ),
        key="profile_full_name",
    )

    email = st.text_input(
        "Email",
        value=str(
            user.get(
                "email",
                "",
            )
        ),
        key="profile_email",
    )

    discipline_options = list(
        auth.DISCIPLINES
    )

    saved_discipline = str(
        user.get(
            "discipline",
            "Quality Management",
        )
    )

    if saved_discipline in discipline_options:
        discipline_index = (
            discipline_options.index(
                saved_discipline
            )
        )
    else:
        discipline_index = len(
            discipline_options
        )

    discipline_choice = st.selectbox(
        "Primary discipline",
        discipline_options
        + [
            "Other / custom"
        ],
        index=discipline_index,
        key="profile_discipline",
    )

    custom_discipline = st.text_input(
        "Custom discipline",
        value=(
            saved_discipline
            if saved_discipline
            not in discipline_options
            else ""
        ),
        key="profile_custom_discipline",
    )

    uploaded = st.file_uploader(
        "Profile photo",
        type=[
            "png",
            "jpg",
            "jpeg",
        ],
        key="profile_photo_upload",
        help=(
            "Upload a PNG or JPG profile image. "
            "The image will be stored securely."
        ),
    )

    saved = st.button(
        "Save profile",
        type="primary",
        width="stretch",
        key="profile_save",
    )

    if saved:

        if discipline_choice == "Other / custom":
            discipline = (
                custom_discipline.strip()
            )
        else:
            discipline = discipline_choice

        if not discipline:
            st.error(
                "Enter your custom discipline."
            )

        else:

            success = auth.update_profile(
                name,
                email,
                discipline,
                uploaded,
            )

            if success:
                st.success(
                    "Profile updated successfully."
                )

                # Reload the live MongoDB record
                # before rerendering the page.
                st.rerun()


# ============================================================
# SECURITY NOTES
# ============================================================

st.markdown(
    '<div class="section-heading">Security Notes</div>',
    unsafe_allow_html=True,
)

st.markdown(
    """
<div class="security-card">
    <h3>Account security</h3>
    <p>
        Use a unique strong password and keep access limited to
        approved project personnel. For production deployment,
        place this app behind HTTPS, central identity management
        or SSO, Exchange Online approval email, backups, audit
        logs, secrets management, and network firewall controls.
    </p>
</div>
""",
    unsafe_allow_html=True,
)