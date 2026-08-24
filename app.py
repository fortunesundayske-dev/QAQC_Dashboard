"""Evomec QA/QC Command Centre — single-page application.

All operational modules live in ``sections/`` and are rendered on one
Streamlit route.

This entry point owns:
- authentication
- enterprise theme
- global sidebar
- global project filter
- enterprise top navigation
- section navigation
- section execution

Individual sections retain their business logic but do not render duplicate
application-level chrome.
"""

from __future__ import annotations

import html
import runpy
from pathlib import Path

import pandas as pd
import streamlit as st

import auth
import utils


# ---------------------------------------------------------------------------
# STREAMLIT PAGE CONFIG
# ---------------------------------------------------------------------------

st.set_page_config(
    page_title="Evomec QA/QC Command Centre",
    page_icon="✅",
    layout="wide",
    initial_sidebar_state="expanded",
)


# ---------------------------------------------------------------------------
# PATHS
# ---------------------------------------------------------------------------

BASE_DIR = Path(__file__).resolve().parent
SECTIONS_DIR = BASE_DIR / "sections"
DATA_FILE = BASE_DIR / "data" / "QAQC_Master.xlsx"


# ---------------------------------------------------------------------------
# SECTION REGISTER
# ---------------------------------------------------------------------------

SECTIONS = [
    {
        "id": "executive-dashboard",
        "label": "Executive Dashboard",
        "icon": "🏠",
        "group": "Overview",
        "file": "Executive_Dashboard.py",
    },
    {
        "id": "management-summary",
        "label": "Management Summary",
        "icon": "📋",
        "group": "Overview",
        "file": "Management_Executive_Summary.py",
    },
    {
        "id": "kpi-kra",
        "label": "KPI / KRA Register",
        "icon": "🎯",
        "group": "Overview",
        "file": "KPI_KRA_Register.py",
    },
    {
        "id": "daily-reports",
        "label": "Daily Reports",
        "icon": "📅",
        "group": "Reports",
        "file": "Daily_Reports.py",
    },
    {
        "id": "lessons-learned",
        "label": "Lessons Learned",
        "icon": "📘",
        "group": "Reports",
        "file": "Lessons_Learned.py",
    },
    {
        "id": "itr-tracker",
        "label": "ITR Tracker",
        "icon": "📦",
        "group": "Quality Records",
        "file": "ITR_Tracker.py",
    },
    {
        "id": "ncr-tracker",
        "label": "NCR Tracker",
        "icon": "🚫",
        "group": "Quality Records",
        "file": "NCR_Tracker.py",
    },
    {
        "id": "obs-tracker",
        "label": "OBS Tracker",
        "icon": "👁",
        "group": "Quality Records",
        "file": "OBS_Tracker.py",
    },
    {
        "id": "defect-rework",
        "label": "Defect & Rework",
        "icon": "🔧",
        "group": "Quality Records",
        "file": "Defect_Rework_Tracker.py",
    },
    {
        "id": "ctq-dashboard",
        "label": "CTQ Dashboard",
        "icon": "📊",
        "group": "Engineering",
        "file": "CTQ_Dashboard.py",
    },
    {
        "id": "document-status",
        "label": "Document Status",
        "icon": "📄",
        "group": "Engineering",
        "file": "Document_Status.py",
    },
    {
        "id": "standards-library",
        "label": "Standards Library",
        "icon": "📚",
        "group": "Engineering",
        "file": "Standards_Library.py",
    },
    {
        "id": "concrete-tracker",
        "label": "Concrete Tracker",
        "icon": "🏗",
        "group": "Materials",
        "file": "Concrete_Tracker.py",
    },
    {
        "id": "audit-surveillance",
        "label": "Audit & Surveillance",
        "icon": "🔍",
        "group": "Audits",
        "file": "Audit_Surveillance.py",
    },
    {
        "id": "calibration-log",
        "label": "Calibration Log",
        "icon": "⚙",
        "group": "Audits",
        "file": "Calibration_Log.py",
    },
    {
        "id": "quality-tools",
        "label": "Quality Tools",
        "icon": "🧰",
        "group": "Toolkit",
        "file": "Quality_Tools.py",
    },
    {
        "id": "learning-academy",
        "label": "Learning Academy",
        "icon": "🎓",
        "group": "Toolkit",
        "file": "Learning_Academy.py",
    },
    {
        "id": "customer-support",
        "label": "Customer Support",
        "icon": "💬",
        "group": "Workspace",
        "file": "Customer_Support.py",
    },
    {
        "id": "user-profile",
        "label": "My Profile",
        "icon": "👤",
        "group": "Workspace",
        "file": "User_Profile.py",
    },
    {
        "id": "activity-log",
        "label": "Activity Log",
        "icon": "🛡",
        "group": "Administration",
        "file": "Activity_Log.py",
        "admin_only": True,
    },
    {
        "id": "access-admin",
        "label": "Access Admin",
        "icon": "🔐",
        "group": "Administration",
        "file": "Access_Admin.py",
        "admin_only": True,
    },
]


# ---------------------------------------------------------------------------
# SINGLE-PAGE SCROLL STYLING
#
# This styling is deliberately lightweight.
# The main enterprise visual system remains controlled by utils.py.
# ---------------------------------------------------------------------------

def inject_scroll_css() -> None:
    st.markdown(
        """
        <style>

        html,
        body,
        [data-testid="stAppViewContainer"],
        [data-testid="stMain"],
        section.main {
            scroll-behavior: smooth !important;
        }

        .section-anchor {
            display: block;
            height: 0;
            margin: 0;
            padding: 0;
            scroll-margin-top: 105px;
        }

        /*
        Do NOT replace the enterprise dashboard cards/panels.
        This wrapper only provides section-level spacing and animation.
        */
        .qaqc-section-wrap {
            animation: qaqc-fade-slide-up .45s ease both;
        }

        @keyframes qaqc-fade-slide-up {
            from {
                opacity: 0;
                transform: translateY(12px);
            }

            to {
                opacity: 1;
                transform: translateY(0);
            }
        }

        .qaqc-section-divider {
            margin: 2.5rem 0 2rem;
            border: 0;
            border-top: 1px solid rgba(148, 163, 184, .18);
        }

        /*
        Secondary single-page jump navigation.
        The main enterprise navigation from utils.py remains active.
        */
        .evomec-scrollnav {
            position: sticky;
            top: 0;
            z-index: 998;

            display: flex;
            gap: 6px;

            overflow-x: auto;
            white-space: nowrap;

            padding: 8px 10px;
            margin: 0 0 1rem;

            background: rgba(11, 31, 54, .88);
            backdrop-filter: blur(12px);

            border: 1px solid rgba(148, 163, 184, .14);
            border-radius: 12px;

            scrollbar-width: thin;
        }

        .evomec-scrollnav::-webkit-scrollbar {
            height: 5px;
        }

        .evomec-scrollnav::-webkit-scrollbar-thumb {
            background: rgba(148, 163, 184, .32);
            border-radius: 999px;
        }

        .evomec-scrollnav a {
            flex: 0 0 auto;

            display: inline-flex;
            align-items: center;
            gap: 6px;

            padding: 7px 13px;

            border: 1px solid transparent;
            border-radius: 999px;

            background: rgba(255, 255, 255, .055);
            color: #e5edf8;

            font-size: .78rem;
            font-weight: 600;

            text-decoration: none;

            transition:
                transform .18s ease,
                background .18s ease,
                border-color .18s ease;
        }

        .evomec-scrollnav a:hover {
            transform: translateY(-1px);
            background: #2970ff;
            border-color: #2970ff;
            color: #fff;
        }

        .evomec-scrollnav .nav-group-label {
            flex: 0 0 auto;

            display: inline-flex;
            align-items: center;

            padding: 7px 4px 7px 10px;

            color: #7a8a9e;

            font-size: .68rem;
            font-weight: 700;

            letter-spacing: .04em;
            text-transform: uppercase;
        }

        @media (max-width: 900px) {
            .evomec-scrollnav {
                border-radius: 10px;
            }

            .evomec-scrollnav a {
                font-size: .74rem;
                padding: 6px 10px;
            }
        }

        @media (prefers-reduced-motion: reduce) {
            .qaqc-section-wrap {
                animation: none !important;
            }

            html,
            body,
            [data-testid="stAppViewContainer"],
            [data-testid="stMain"],
            section.main {
                scroll-behavior: auto !important;
            }
        }

        </style>
        """,
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# SINGLE-PAGE SECTION NAVIGATION
# ---------------------------------------------------------------------------

def render_scroll_nav(
    sections: list[dict],
    is_admin: bool,
) -> None:
    grouped: dict[str, list[dict]] = {}

    for section in sections:
        if section.get("admin_only") and not is_admin:
            continue

        grouped.setdefault(section["group"], []).append(section)

    parts = [
        '<nav class="evomec-scrollnav" '
        'aria-label="QA/QC section navigation">'
    ]

    for group, items in grouped.items():
        parts.append(
            f'<span class="nav-group-label">'
            f'{html.escape(group)}'
            f'</span>'
        )

        for section in items:
            parts.append(
                f'<a href="#{html.escape(section["id"])}">'
                f'{html.escape(section["icon"])}&nbsp;'
                f'{html.escape(section["label"])}'
                f'</a>'
            )

    parts.append("</nav>")

    st.markdown(
        "".join(parts),
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# SIDEBAR
# ---------------------------------------------------------------------------

def render_shared_sidebar(is_admin: bool) -> None:
    user = st.session_state.get("auth") or {}

    st.sidebar.markdown(
        """
        <div class="side-brand">
            <div>
                <div class="side-brand__name">NLNG</div>
                <div class="side-brand__sub">
                    QA/QC Command Centre
                </div>
            </div>
        </div>
        """,
        unsafe_allow_html=True,
    )

    if user.get("logged_in"):
        account = getattr(
            auth,
            "current_user",
            lambda: None,
        )() or {}

        name = account.get(
            "name",
            user.get("username", "User"),
        )

        role = str(
            account.get(
                "role",
                user.get("role", "user"),
            )
        ).title()

        st.sidebar.caption(
            f"{name} · {role}"
        )

        if st.sidebar.button(
            "Sign out",
            key="single_page_sign_out",
            width="stretch",
        ):
            auth.sign_out()
            st.rerun()

    st.sidebar.markdown(
        '<div class="side-menu-title">Appearance</div>',
        unsafe_allow_html=True,
    )

    if hasattr(utils, "render_theme_selector"):
        utils.render_theme_selector()

    st.sidebar.markdown(
        '<div class="side-menu-title">Jump to section</div>',
        unsafe_allow_html=True,
    )

    for section in SECTIONS:
        if section.get("admin_only") and not is_admin:
            continue

        st.sidebar.markdown(
            f'<a class="side-nav-group" '
            f'style="display:block;text-decoration:none;" '
            f'href="#{html.escape(section["id"])}">'
            f'{html.escape(section["icon"])} '
            f'{html.escape(section["label"])}'
            f'</a>',
            unsafe_allow_html=True,
        )


# ---------------------------------------------------------------------------
# GLOBAL PROJECT FILTER
# ---------------------------------------------------------------------------

def _silent_global_filter(data):
    """Apply the application-level project selection to section data."""

    if not isinstance(data, dict):
        return data

    project = st.session_state.get(
        "global_project",
        "All",
    )

    if project == "All":
        return data

    filtered = {}

    for key, frame in data.items():
        if (
            isinstance(frame, pd.DataFrame)
            and "Project" in frame.columns
        ):
            filtered[key] = frame[
                frame["Project"] == project
            ].copy()
        else:
            filtered[key] = frame

    return filtered


# ---------------------------------------------------------------------------
# SECTION CHROME PATCHING
#
# IMPORTANT:
# We only suppress duplicate chrome.
#
# We DO NOT suppress the enterprise theme.
# The enterprise theme is what gives the application the polished
# appearance shown in the preferred screenshot.
# ---------------------------------------------------------------------------

def patch_section_chrome() -> None:
    """Prevent legacy sections from creating duplicate app-level chrome."""

    # Individual sections must not attempt to reset Streamlit page config.
    st.set_page_config = lambda *args, **kwargs: None

    # The application owns the top-level navigation.
    if hasattr(utils, "render_navigation"):
        utils.render_navigation = lambda: None

    if hasattr(utils, "render_top_nav"):
        utils.render_top_nav = lambda: None

    # IMPORTANT:
    # Do NOT disable inject_enterprise_theme().
    #
    # The enterprise theme is intentionally preserved because it provides
    # the visual system used by the preferred dashboard design.

    # Prevent each section from creating another global filter.
    utils.global_filter_sidebar = _silent_global_filter

    # Authentication is handled once by app.py.
    auth.login = lambda: True
    auth.render_user_sidebar = lambda: None


# ---------------------------------------------------------------------------
# SECTION EXECUTION
# ---------------------------------------------------------------------------

def run_section(section: dict) -> None:
    path = SECTIONS_DIR / section["file"]

    # Anchor used by the single-page navigation.
    st.markdown(
        f'<div id="{html.escape(section["id"])}" '
        f'class="section-anchor"></div>',
        unsafe_allow_html=True,
    )

    if not path.exists():
        st.warning(
            f"{section['label']} is not available yet."
        )
        return

    with st.container():
        st.markdown(
            '<div class="qaqc-section-wrap">',
            unsafe_allow_html=True,
        )

        try:
            runpy.run_path(
                str(path),
                run_name="__section__",
            )

        except BaseException as exc:
            # Streamlit's StopException is expected when a section calls
            # st.stop().
            if type(exc).__name__ == "StopException":
                pass

            elif isinstance(
                exc,
                (KeyboardInterrupt, SystemExit),
            ):
                raise

            else:
                st.error(
                    f"The {section['label']} module "
                    f"was skipped: {exc}"
                )

        st.markdown(
            "</div>",
            unsafe_allow_html=True,
        )

    st.markdown(
        '<hr class="qaqc-section-divider">',
        unsafe_allow_html=True,
    )


# ---------------------------------------------------------------------------
# ENTERPRISE APPLICATION SHELL
# ---------------------------------------------------------------------------

def render_enterprise_shell() -> None:
    """
    Load the existing enterprise UI system from utils.py.

    This is intentionally executed ONCE before sections are loaded.
    """

    if hasattr(
        utils,
        "inject_enterprise_theme",
    ):
        utils.inject_enterprise_theme()

    elif hasattr(
        utils,
        "inject_global_ui",
    ):
        utils.inject_global_ui()


# ---------------------------------------------------------------------------
# TOP NAVIGATION
# ---------------------------------------------------------------------------

def render_enterprise_top_navigation() -> None:
    """
    Render the existing polished top navigation supplied by utils.py.

    The preferred screenshot uses this navigation style, so we preserve it
    rather than replacing it with the simplified section-only navigation.
    """

    if hasattr(
        utils,
        "render_top_nav",
    ):
        try:
            utils.render_top_nav()
            return
        except TypeError:
            # Some versions may expect no arguments while others may not
            # expose a compatible implementation.
            pass
        except Exception:
            # Fall back silently to the single-page navigation below.
            pass


# ---------------------------------------------------------------------------
# MAIN
# ---------------------------------------------------------------------------

def main() -> None:
    # ---------------------------------------------------------------
    # 1. Load the enterprise visual system FIRST.
    # ---------------------------------------------------------------

    render_enterprise_shell()

    # ---------------------------------------------------------------
    # 2. Authenticate once.
    # ---------------------------------------------------------------

    if not auth.login():
        st.stop()

    is_admin = (
        str(auth.get_role() or "").lower()
        == "admin"
    )

    # ---------------------------------------------------------------
    # 3. Inject single-page enhancements.
    # ---------------------------------------------------------------

    inject_scroll_css()

    # ---------------------------------------------------------------
    # 4. Render shared sidebar.
    # ---------------------------------------------------------------

    render_shared_sidebar(is_admin)

    # ---------------------------------------------------------------
    # 5. Load master data.
    # ---------------------------------------------------------------

    source_data = utils.load_master_data(
        DATA_FILE
    )

    # ---------------------------------------------------------------
    # 6. Apply global project filter.
    # ---------------------------------------------------------------

    if hasattr(
        utils,
        "global_filter_sidebar",
    ):
        utils.global_filter_sidebar(
            source_data
        )

    # ---------------------------------------------------------------
    # 7. Render the enterprise top navigation.
    #
    # This is deliberately NOT disabled here.
    # ---------------------------------------------------------------

    render_enterprise_top_navigation()

    # ---------------------------------------------------------------
    # 8. Render single-page section navigation.
    #
    # This is an additional jump navigation and does not replace the
    # enterprise navigation.
    # ---------------------------------------------------------------

    render_scroll_nav(
        SECTIONS,
        is_admin,
    )

    # ---------------------------------------------------------------
    # 9. Prevent individual sections from duplicating global chrome.
    # ---------------------------------------------------------------

    patch_section_chrome()

    # ---------------------------------------------------------------
    # 10. Render every section.
    # ---------------------------------------------------------------

    for section in SECTIONS:
        if (
            section.get("admin_only")
            and not is_admin
        ):
            continue

        run_section(section)

    # ---------------------------------------------------------------
    # 11. Application footer.
    # ---------------------------------------------------------------

    st.sidebar.caption(
        "Evomec QA/QC Command Centre · "
        "single-page build"
    )


# ---------------------------------------------------------------------------
# APPLICATION ENTRY POINT
# ---------------------------------------------------------------------------

if __name__ == "__main__":
    main()