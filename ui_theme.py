"""Shared EVOMEC QA/QC design tokens.

Keep this module free of Streamlit imports so pages and utilities can use the
same colours for CSS, charts, tables, and future components without creating
runtime coupling.
"""

FONT_STACK = 'Inter, "Segoe UI", Roboto, Arial, sans-serif'

COLORS = {
    "navy_950": "#071426",
    "navy_900": "#0B1F36",
    "navy_800": "#12304F",
    "blue_700": "#155EEF",
    "blue_600": "#2970FF",
    "blue_100": "#D1E9FF",
    "page": "#F4F7FB",
    "surface": "#FFFFFF",
    "surface_alt": "#F8FAFC",
    "border": "#D8E1EC",
    "text_primary": "#172B4D",
    "text_secondary": "#52667D",
    "text_muted": "#7A8A9E",
    "success": "#168A55",
    "success_bg": "#E8F7EF",
    "warning": "#B76E00",
    "warning_bg": "#FFF4D6",
    "danger": "#C9362B",
    "danger_bg": "#FDECEA",
    "info": "#1769AA",
    "info_bg": "#EAF4FF",
    "purple": "#6941C6",
    "purple_bg": "#F4EBFF",
}

LIGHT_THEME = {
    "bg": COLORS["page"],
    "surface": COLORS["surface"],
    "surface_2": COLORS["surface_alt"],
    "text": COLORS["text_primary"],
    "heading": COLORS["text_primary"],
    "muted": COLORS["text_secondary"],
    "line": COLORS["border"],
    "primary": COLORS["blue_600"],
    "primary_strong": COLORS["blue_700"],
    "success": COLORS["success"],
    "warning": COLORS["warning"],
    "danger": COLORS["danger"],
    "purple": COLORS["purple"],
    "input": COLORS["surface"],
    "sidebar_bg": COLORS["navy_950"],
    "sidebar_text": "#EAF2FF",
    "shadow": "0 14px 32px rgba(15, 23, 42, 0.10)",
}

DARK_THEME = {
    "bg": "#07111F",
    "surface": "#111827",
    "surface_2": "#172033",
    "text": "#E5EDF8",
    "heading": "#F8FAFC",
    "muted": "#AAB8CA",
    "line": "rgba(148, 163, 184, 0.26)",
    "primary": "#60A5FA",
    "primary_strong": "#93C5FD",
    "success": "#4ADE80",
    "warning": "#FBBF24",
    "danger": "#F87171",
    "purple": "#C4B5FD",
    "input": "#0B1220",
    "sidebar_bg": "#050B14",
    "sidebar_text": "#E5EDF8",
    "shadow": "0 18px 42px rgba(0, 0, 0, 0.34)",
}

CHART_COLORS_LIGHT = [
    COLORS["blue_600"],
    COLORS["success"],
    COLORS["warning"],
    COLORS["danger"],
    "#0F9F9A",
    COLORS["purple"],
    COLORS["text_secondary"],
]

CHART_COLORS_DARK = [
    "#60A5FA",
    "#4ADE80",
    "#FBBF24",
    "#F87171",
    "#2DD4BF",
    "#A78BFA",
    "#CBD5E1",
]

SPACING = {
    "xs": "4px",
    "sm": "8px",
    "md": "12px",
    "lg": "16px",
    "xl": "24px",
    "2xl": "32px",
}

RADIUS = {
    "sm": "6px",
    "md": "8px",
    "lg": "10px",
}

BREAKPOINTS = {
    "mobile": 430,
    "tablet": 768,
    "laptop": 1280,
    "desktop": 1440,
}


def css_variables(theme):
    """Return CSS custom properties for a theme token dictionary."""
    return f"""
        --qaqc-bg: {theme["bg"]};
        --qaqc-surface: {theme["surface"]};
        --qaqc-surface-2: {theme["surface_2"]};
        --qaqc-navy: {theme["heading"]};
        --qaqc-blue: {theme["primary"]};
        --qaqc-blue-2: {theme["primary_strong"]};
        --qaqc-text: {theme["text"]};
        --qaqc-muted: {theme["muted"]};
        --qaqc-line: {theme["line"]};
        --qaqc-success: {theme["success"]};
        --qaqc-warning: {theme["warning"]};
        --qaqc-danger: {theme["danger"]};
        --qaqc-purple: {theme["purple"]};
        --qaqc-shadow: {theme["shadow"]};
        --qaqc-input-bg: {theme["input"]};
        --qaqc-sidebar-bg: {theme["sidebar_bg"]};
        --qaqc-sidebar-text: {theme["sidebar_text"]};
        --qaqc-radius: {RADIUS["md"]};
        --qaqc-font: {FONT_STACK};
    """
