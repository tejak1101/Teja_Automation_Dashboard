import re
import time
from datetime import date, datetime

import pandas as pd
import streamlit as st
import streamlit.components.v1 as components
from sqlalchemy import create_engine, text

st.set_page_config(page_title="Work Tracker // Command Deck", page_icon="🛰️", layout="wide")

STATUSES = ["To Do", "In Progress", "Review", "Done"]
PRIORITIES = ["Low", "Medium", "High"]
ASSIGNEES = ["Teja", "Carl", "Both"]
RESOURCE_CATEGORIES = ["Google Drive", "ClickUp", "Document", "Design", "Credential", "Other"]

# --- automation-specific vocab ---
AUTOMATION_TYPES = [
    "Zapier", "Make (Integromat)", "n8n", "Python Script",
    "Google Apps Script", "API Integration", "Web Scraping", "Cron Job", "Other",
]
TRIGGER_TYPES = ["Manual", "Scheduled", "Webhook", "Event-based"]
DEPLOYMENT_STATUSES = ["Not Deployed", "Testing", "Live", "Deprecated", "Error"]
ENVIRONMENTS = ["Dev", "Staging", "Production"]
AUTOMATION_STATUSES = ["Active", "Paused", "Error", "Draft"]

# ---------------------------------------------------------------------------
# THEME — "COMMAND DECK" (dark & light variants, glassy, neon accents,
# monospace data). The user can flip between them at any time; everything
# below (CSS + chart colors) is derived from whichever mode is active.
# ---------------------------------------------------------------------------

if "theme_mode" not in st.session_state:
    st.session_state.theme_mode = "dark"


def toggle_theme():
    st.session_state.theme_mode = "light" if st.session_state.theme_mode == "dark" else "dark"


IS_DARK = st.session_state.theme_mode == "dark"

if IS_DARK:
    CYAN = "#22d3ee"
    VIOLET = "#8b5cf6"
    PINK = "#ec4899"
    GOLD = "#f5b942"
    SUCCESS = "#34d399"
    AMBER = "#fbbf24"
    NEUTRAL = "#94a3b8"
    NEUTRAL_2 = "#64748b"

    BG_0 = "#05060a"
    BG_1 = "#0a0d16"
    PANEL = "rgba(19, 22, 33, 0.65)"
    BORDER = "rgba(148, 163, 184, 0.16)"
    TEXT_MUTED = "#8891a7"
    TEXT_MAIN = "#eef1f8"
    CARD_TITLE = "#f1f4fa"
    CARD_SUBTEXT = "#dfe4ee"
    CHART_TEXT = "#dfe4ee"
    METRIC_VALUE = "#f4f6fb"
    SIDEBAR_FROM = "#060810"
    SIDEBAR_TO = "#0a0d17"
    BTN_BG = "rgba(30,34,48,0.9)"
    BTN_TEXT = "#dfe4ee"
    GRID_LINE = "rgba(148,163,184,0.05)"
    RADIAL_1 = "rgba(139,92,246,0.16)"
    RADIAL_2 = "rgba(34,211,238,0.12)"
    EMPTY_DASH_BORDER = "rgba(148,163,184,0.25)"
    EMPTY_DASH_TEXT = "#5b6376"
else:
    CYAN = "#0e7490"
    VIOLET = "#7c3aed"
    PINK = "#db2777"
    GOLD = "#b45309"
    SUCCESS = "#059669"
    AMBER = "#d97706"
    NEUTRAL = "#64748b"
    NEUTRAL_2 = "#94a3b8"

    BG_0 = "#f4f6fb"
    BG_1 = "#e7ebf3"
    PANEL = "rgba(255, 255, 255, 0.72)"
    BORDER = "rgba(15, 23, 42, 0.10)"
    TEXT_MUTED = "#5b6376"
    TEXT_MAIN = "#0f172a"
    CARD_TITLE = "#111827"
    CARD_SUBTEXT = "#1f2937"
    CHART_TEXT = "#1f2937"
    METRIC_VALUE = "#0f172a"
    SIDEBAR_FROM = "#ffffff"
    SIDEBAR_TO = "#eef1f8"
    BTN_BG = "rgba(255,255,255,0.9)"
    BTN_TEXT = "#111827"
    GRID_LINE = "rgba(15,23,42,0.05)"
    RADIAL_1 = "rgba(124,58,237,0.10)"
    RADIAL_2 = "rgba(14,116,144,0.08)"
    EMPTY_DASH_BORDER = "rgba(15,23,42,0.16)"
    EMPTY_DASH_TEXT = "#6b7280"

STATUS_COLORS = {"To Do": NEUTRAL, "In Progress": CYAN, "Review": VIOLET, "Done": SUCCESS}
PRIORITY_COLORS = {"Low": SUCCESS, "Medium": AMBER, "High": PINK}
ASSIGNEE_COLORS = {"Teja": VIOLET, "Carl": CYAN, "Both": PINK}
DEPLOYMENT_COLORS = {
    "Not Deployed": NEUTRAL, "Testing": AMBER, "Live": SUCCESS,
    "Deprecated": NEUTRAL_2, "Error": PINK,
}
AUTOMATION_STATUS_COLORS = {"Active": SUCCESS, "Paused": AMBER, "Error": PINK, "Draft": NEUTRAL}


def initials(name: str) -> str:
    parts = [p for p in re.split(r"\s+", name.strip()) if p]
    if not parts:
        return "?"
    if len(parts) == 1:
        return parts[0][:2].upper()
    return (parts[0][0] + parts[-1][0]).upper()


def badge(text_, color):
    return (
        f'<span class="app-badge" style="background:{color}22;color:{color};'
        f'border:1px solid {color}55;">{text_}</span>'
    )


def hex_to_rgba(hex_color: str, alpha: float) -> str:
    hex_color = hex_color.lstrip("#")
    r, g, b = int(hex_color[0:2], 16), int(hex_color[2:4], 16), int(hex_color[4:6], 16)
    return f"rgba({r},{g},{b},{alpha})"


def avatar(name, color):
    return (
        f'<span class="app-avatar" style="background:{color}22;color:{color};'
        f'border:1px solid {color}66;">{initials(name)}</span>'
    )


def status_dot(color):
    return (
        f'<span class="pulse-dot" style="display:inline-block;width:8px;height:8px;'
        f'border-radius:999px;background:{color};margin-right:8px;'
        f'box-shadow:0 0 8px {color}99;"></span>'
    )


def health_badge(overdue_count: int):
    if overdue_count == 0:
        return "🟢 ON TRACK", SUCCESS
    if overdue_count < 3:
        return "🟠 NEEDS ATTENTION", AMBER
    return "🔴 AT RISK", PINK


# ---------------------------------------------------------------------------
# COMMAND DECK HUD — purely decorative widgets for the Dashboard tab.
# These only *display* numbers that are already computed elsewhere; they
# don't touch the database, the cache layer, or any business logic.
# ---------------------------------------------------------------------------

def radial_gauge_html(value_pct, label, sublabel, color):
    value_pct = max(0.0, min(100.0, float(value_pct)))
    track_color = "rgba(148,163,184,0.18)"
    return f"""
    <div class="radial-gauge-wrap">
        <div class="radial-gauge-ring" style="animation-duration:{18 - value_pct/10:.1f}s;"></div>
        <div class="radial-gauge" style="background: conic-gradient(from -90deg, {color} {value_pct}%, {track_color} 0);">
            <div class="radial-gauge-inner">
                <div class="radial-gauge-value" style="color:{color};">{value_pct:.0f}%</div>
                <div class="radial-gauge-label">{label}</div>
            </div>
        </div>
        <div class="radial-gauge-sub">{sublabel}</div>
    </div>
    """


def render_live_clock_hud(project_name, user_name, is_dark):
    """A small self-contained HTML component (runs in its own iframe so the
    clock digits can tick every second with real JS, independent of
    Streamlit's rerun cycle)."""
    bg = "transparent"
    text_main = TEXT_MAIN
    text_muted = TEXT_MUTED
    cyan, violet, pink = CYAN, VIOLET, PINK
    panel = PANEL
    border = BORDER
    html_code = f"""
    <html>
    <head>
    <style>
        @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@700;800&family=JetBrains+Mono:wght@500;700&display=swap');
        html, body {{ margin:0; padding:0; background:{bg}; overflow:hidden; }}
        .hud {{
            display:flex; align-items:center; justify-content:space-between;
            font-family:'Inter', sans-serif; color:{text_main};
            background:{panel}; border:1px solid {border}; border-radius:16px;
            padding:14px 22px; backdrop-filter: blur(10px);
            box-shadow: 0 8px 24px rgba(0,0,0,0.18);
        }}
        .hud-left {{ display:flex; flex-direction:column; gap:2px; }}
        .hud-live {{
            display:inline-flex; align-items:center; gap:6px;
            font-family:'JetBrains Mono', monospace; font-size:10.5px; font-weight:700;
            letter-spacing:.16em; color:{cyan}; text-transform:uppercase;
        }}
        .hud-dot {{
            width:7px; height:7px; border-radius:50%; background:{cyan};
            box-shadow:0 0 8px {cyan}; animation: hudPulse 1.4s ease-in-out infinite;
        }}
        .hud-project {{
            font-family:'Space Grotesk', sans-serif; font-weight:800; font-size:15px;
            background: linear-gradient(90deg, {cyan}, {violet}, {pink});
            -webkit-background-clip:text; -webkit-text-fill-color:transparent;
        }}
        .hud-user {{ font-size:11px; color:{text_muted}; font-family:'JetBrains Mono', monospace; }}
        .hud-right {{ text-align:right; }}
        .hud-time {{
            font-family:'JetBrains Mono', monospace; font-weight:700; font-size:26px;
            letter-spacing:.04em; color:{text_main};
        }}
        .hud-date {{ font-size:11px; color:{text_muted}; font-family:'JetBrains Mono', monospace; margin-top:2px; }}
        @keyframes hudPulse {{ 0%,100% {{ opacity:1; transform:scale(1); }} 50% {{ opacity:.35; transform:scale(1.3); }} }}
    </style>
    </head>
    <body>
        <div class="hud">
            <div class="hud-left">
                <span class="hud-live"><span class="hud-dot"></span>LIVE · COMMAND DECK</span>
                <span class="hud-project">🛰️ {project_name}</span>
                <span class="hud-user">Operator: {user_name}</span>
            </div>
            <div class="hud-right">
                <div class="hud-time" id="hud-time">--:--:--</div>
                <div class="hud-date" id="hud-date">loading...</div>
            </div>
        </div>
        <script>
            function tick() {{
                const now = new Date();
                const t = now.toLocaleTimeString('en-GB', {{hour:'2-digit', minute:'2-digit', second:'2-digit'}});
                const d = now.toLocaleDateString('en-GB', {{weekday:'long', year:'numeric', month:'long', day:'numeric'}});
                document.getElementById('hud-time').innerText = t;
                document.getElementById('hud-date').innerText = d;
            }}
            tick();
            setInterval(tick, 1000);
        </script>
    </body>
    </html>
    """
    components.html(html_code, height=100)


def render_stat_ticker(items):
    """Pure-CSS infinite marquee (no JS needed) showing quick live stats."""
    row = "  &nbsp;·&nbsp;  ".join(items)
    content = row + "  &nbsp;·&nbsp;  " + row
    return f"""
    <div class="ticker-wrap">
        <div class="ticker-move">{content}</div>
    </div>
    """


st.markdown(
    f"""
    <style>
    @import url('https://fonts.googleapis.com/css2?family=Space+Grotesk:wght@500;600;700;800&family=JetBrains+Mono:wght@400;500;700&family=Inter:wght@400;500;600&display=swap');

    html, body, [class*="css"] {{ font-family: 'Inter', sans-serif; }}

    .stApp {{
        background-color: {BG_0};
        background-image:
            linear-gradient({GRID_LINE} 1px, transparent 1px),
            linear-gradient(90deg, {GRID_LINE} 1px, transparent 1px),
            radial-gradient(900px 500px at 15% -10%, {RADIAL_1} 0%, transparent 60%),
            radial-gradient(900px 500px at 100% 0%, {RADIAL_2} 0%, transparent 55%),
            linear-gradient(180deg, {BG_0} 0%, {BG_1} 100%);
        background-size: 42px 42px, 42px 42px, auto, auto, auto;
        transition: background-color .25s ease;
    }}

    section[data-testid="stSidebar"] {{
        background: linear-gradient(180deg, {SIDEBAR_FROM} 0%, {SIDEBAR_TO} 100%);
        border-right: 1px solid {BORDER};
    }}

    p, span, label, li, div {{ color: {TEXT_MAIN}; }}

    h1, h2, h3, h4, h5 {{
        font-family: 'Space Grotesk', sans-serif;
        letter-spacing: -0.01em;
        color: {TEXT_MAIN};
    }}
    h1 {{
        background: linear-gradient(90deg, {CYAN} 0%, {VIOLET} 55%, {PINK} 100%);
        -webkit-background-clip: text; -webkit-text-fill-color: transparent;
        display: inline-block;
        position: relative;
        padding-bottom: 6px;
    }}
    h1::after {{
        content: "";
        position: absolute; left: 0; bottom: 0;
        height: 3px; width: 100%; border-radius: 999px;
        background: linear-gradient(90deg, {CYAN}, {VIOLET}, {PINK}, {CYAN});
        background-size: 200% 100%;
        animation: titleShimmer 4s linear infinite;
        opacity: .55;
    }}
    @keyframes titleShimmer {{
        0% {{ background-position: 0% 0%; }}
        100% {{ background-position: 200% 0%; }}
    }}

    code, .mono {{ font-family: 'JetBrains Mono', monospace; }}

    [data-testid="stMetric"] {{
        background: {PANEL};
        backdrop-filter: blur(10px);
        border-radius: 14px; padding: 14px 16px;
        border: 1px solid {BORDER};
        box-shadow: 0 0 0 1px rgba(0,0,0,0.02), 0 8px 24px rgba(0,0,0,0.15);
        transition: transform .15s ease, box-shadow .15s ease;
    }}
    [data-testid="stMetric"]:hover {{
        transform: translateY(-2px);
        box-shadow: 0 12px 28px rgba(0,0,0,0.18), 0 0 0 1px {CYAN}33;
    }}
    [data-testid="stMetricLabel"] {{
        color: {TEXT_MUTED} !important; font-weight: 600; font-size: 11px;
        text-transform: uppercase; letter-spacing: .08em;
    }}
    [data-testid="stMetricValue"] {{
        color: {METRIC_VALUE} !important; font-family: 'JetBrains Mono', monospace;
    }}

    [data-testid="stExpander"] {{
        border-radius: 14px; border: 1px solid {BORDER};
        background: {PANEL}; backdrop-filter: blur(8px);
    }}

    [data-testid="stStatusWidget"] {{
        border-radius: 14px; border: 1px solid {BORDER};
        background: {PANEL}; backdrop-filter: blur(8px);
    }}

    div[data-testid="stTabs"] button[role="tab"] {{
        font-family: 'Space Grotesk', sans-serif; font-weight: 600; color: {TEXT_MUTED};
    }}
    div[data-testid="stTabs"] button[aria-selected="true"] {{
        color: {CYAN};
        border-bottom-color: {CYAN} !important;
    }}

    div.stButton > button {{
        border-radius: 9px; font-weight: 600;
        background: {BTN_BG}; color: {BTN_TEXT};
        border: 1px solid {BORDER};
        transition: all .15s ease;
    }}
    div.stButton > button:hover {{
        border-color: {CYAN}99; color: {CYAN};
        box-shadow: 0 0 14px {CYAN}33;
        transform: translateY(-1px);
    }}
    div.stButton > button[kind="primary"] {{
        background: linear-gradient(135deg, {CYAN}33 0%, {VIOLET}33 100%);
        color: {CYAN} !important; border: 1px solid {CYAN}77; font-weight: 700;
        box-shadow: 0 0 14px {CYAN}22;
        text-align: left; justify-content: flex-start;
    }}
    div.stButton > button[kind="secondary"] {{
        text-align: left; justify-content: flex-start;
    }}
    div.stFormSubmitButton > button {{
        background: linear-gradient(135deg, {CYAN} 0%, {VIOLET} 100%);
        color: #05060a; border: none; font-weight: 700;
    }}
    div.stFormSubmitButton > button:hover {{
        filter: brightness(1.12);
        box-shadow: 0 0 18px {VIOLET}55;
    }}
    div.stDownloadButton > button {{
        background: linear-gradient(135deg, {GOLD} 0%, {PINK} 100%);
        color: #05060a; border: none; font-weight: 700;
    }}

    [data-testid="stChatMessage"] {{
        background: {PANEL}; border: 1px solid {BORDER}; border-radius: 14px;
        backdrop-filter: blur(8px);
    }}

    hr, div[data-testid="stDivider"] {{ border-color: {BORDER}; }}

    .app-card {{
        background: {PANEL};
        backdrop-filter: blur(10px);
        border: 1px solid {BORDER};
        border-left: 3px solid {CYAN};
        border-radius: 12px;
        padding: 14px 16px; margin-bottom: 10px;
        box-shadow: 0 6px 20px rgba(0,0,0,0.15);
        transition: transform .12s ease, box-shadow .12s ease;
    }}
    .app-card:hover {{
        transform: translateY(-2px);
        box-shadow: 0 10px 28px rgba(0,0,0,0.22);
    }}
    .app-badge {{
        display:inline-block; padding:3px 10px; border-radius:999px;
        font-size:11px; font-weight:700; margin-right:6px; letter-spacing:.02em;
        font-family: 'JetBrains Mono', monospace;
    }}
    .app-avatar {{
        display:inline-flex; align-items:center; justify-content:center;
        width:22px; height:22px; border-radius:999px;
        font-size:10px; font-weight:800; margin-right:6px; vertical-align:middle;
        font-family: 'JetBrains Mono', monospace;
    }}
    .app-title {{ font-weight:700; font-size:15px; color:{CARD_TITLE}; margin-bottom:8px; }}
    .app-sub {{ color:{TEXT_MUTED}; font-size:12px; margin-top:6px; font-family:'JetBrains Mono', monospace; }}

    .pulse-dot {{ animation: pulseDot 1.8s ease-in-out infinite; }}
    @keyframes pulseDot {{ 0%, 100% {{ opacity: 1; }} 50% {{ opacity: .35; }} }}

    .kanban-head {{
        font-family:'JetBrains Mono', monospace; font-weight:700; font-size:12px;
        letter-spacing:.06em; text-transform:uppercase;
        color:{CARD_TITLE}; padding:6px 2px 10px 2px;
        border-bottom: 2px solid {CYAN}44; margin-bottom: 12px;
    }}

    .resource-cat {{
        font-family:'Space Grotesk', sans-serif; font-weight:700; color:{VIOLET};
        letter-spacing:.02em; margin-top: 8px;
    }}

    .glow-pill {{
        display:inline-block; padding:4px 12px; border-radius:999px;
        font-size:11px; font-weight:700; font-family:'JetBrains Mono', monospace;
        background: linear-gradient(135deg, {CYAN}22, {VIOLET}22);
        border: 1px solid {CYAN}44; color: {CYAN};
    }}

    .side-section-label {{
        font-family:'JetBrains Mono', monospace; font-weight:700; font-size:10.5px;
        letter-spacing:.14em; text-transform:uppercase; color:{TEXT_MUTED};
        margin: 2px 0 6px 2px;
    }}

    .progress-track {{
        background: rgba(148,163,184,0.15); border-radius:999px; height:6px;
        margin-top: 8px; overflow: hidden;
    }}
    .progress-fill {{
        height:100%; background: linear-gradient(90deg, {CYAN}, {VIOLET});
    }}

    .theme-toggle-btn button {{
        border-radius: 999px !important;
    }}

    /* --- Ticker marquee (Dashboard HUD) --- */
    .ticker-wrap {{
        background: {PANEL}; border: 1px solid {BORDER}; border-radius: 999px;
        padding: 9px 0; margin: 12px 0 18px 0; overflow: hidden;
        backdrop-filter: blur(8px); position: relative;
    }}
    .ticker-wrap::before, .ticker-wrap::after {{
        content: ""; position: absolute; top:0; bottom:0; width: 40px; z-index: 2;
    }}
    .ticker-wrap::before {{ left:0; background: linear-gradient(90deg, {BG_0}, transparent); }}
    .ticker-wrap::after {{ right:0; background: linear-gradient(270deg, {BG_0}, transparent); }}
    .ticker-move {{
        display: inline-block; white-space: nowrap;
        font-family: 'JetBrains Mono', monospace; font-size: 12.5px; font-weight: 600;
        letter-spacing: .03em; color: {CARD_SUBTEXT};
        animation: tickerScroll 26s linear infinite;
        padding-left: 100%;
    }}
    @keyframes tickerScroll {{
        0% {{ transform: translateX(0); }}
        100% {{ transform: translateX(-100%); }}
    }}

    /* --- Radial gauges (Dashboard HUD) --- */
    .radial-gauge-wrap {{
        display: flex; flex-direction: column; align-items: center; justify-content: center;
        position: relative; padding: 6px 0 2px 0;
    }}
    .radial-gauge {{
        width: 116px; height: 116px; border-radius: 50%;
        display: flex; align-items: center; justify-content: center;
        padding: 9px; transition: background 0.6s ease;
        box-shadow: 0 6px 22px rgba(0,0,0,0.18);
    }}
    .radial-gauge-ring {{
        position: absolute; width: 132px; height: 132px; border-radius: 50%;
        border: 1.5px dashed {CYAN}55;
        animation: gaugeSpin linear infinite;
    }}
    @keyframes gaugeSpin {{ from {{ transform: rotate(0deg); }} to {{ transform: rotate(360deg); }} }}
    .radial-gauge-inner {{
        width: 100%; height: 100%; border-radius: 50%;
        background: {BG_1}; display: flex; flex-direction: column;
        align-items: center; justify-content: center;
        border: 1px solid {BORDER};
    }}
    .radial-gauge-value {{
        font-family: 'JetBrains Mono', monospace; font-weight: 800; font-size: 20px;
    }}
    .radial-gauge-label {{
        font-family: 'JetBrains Mono', monospace; font-size: 9px; font-weight: 700;
        letter-spacing: .1em; color: {TEXT_MUTED}; text-transform: uppercase; margin-top: 2px;
    }}
    .radial-gauge-sub {{
        font-size: 11.5px; color: {TEXT_MUTED}; margin-top: 8px; text-align: center;
        font-family: 'JetBrains Mono', monospace;
    }}
    </style>
    """,
    unsafe_allow_html=True,
)

# ---------------------------------------------------------------------------
# BOOT SPLASH — multi-step animation, shown once per session before the app
# ---------------------------------------------------------------------------

if "splash_shown" not in st.session_state:
    st.session_state.splash_shown = False

if not st.session_state.splash_shown:
    splash_slot = st.empty()

    boot_steps = [
        "Connecting to the Postgres database...",
        "Verifying table schema...",
        "Loading projects & tasks...",
        "Syncing automation registry...",
        "Preparing the Command Deck UI...",
        "All systems ready. Let's get to work. ✅",
    ]
    steps_html = "".join(
        f'<div class="boot-step" style="animation-delay:{0.28 * i}s;">'
        f'<span class="boot-check">▸</span> {s}</div>'
        for i, s in enumerate(boot_steps)
    )

    with splash_slot.container():
        st.markdown(
            f"""
            <style>
            .boot-wrap {{
                height: 78vh; display:flex; flex-direction:column;
                align-items:center; justify-content:center; text-align:center;
            }}
            .boot-ring {{
                width:60px; height:60px; border-radius:50%;
                border: 2px solid {CYAN}33; border-top-color:{CYAN};
                animation: bootspin 0.9s linear infinite; margin-bottom: 24px;
            }}
            .boot-logo {{
                font-family:'Space Grotesk', sans-serif; font-weight:800;
                font-size: 40px; letter-spacing:.04em;
                background: linear-gradient(90deg, {CYAN} 0%, {VIOLET} 55%, {PINK} 100%);
                -webkit-background-clip: text; -webkit-text-fill-color: transparent;
                animation: bootflicker 1.6s ease-in-out infinite;
            }}
            .boot-sub {{
                font-family:'JetBrains Mono', monospace; color:{TEXT_MUTED};
                font-size:13px; margin-top:12px; letter-spacing:.14em;
                overflow:hidden; white-space:nowrap; border-right: 2px solid {CYAN};
                width: 30ch; animation: boottyping 2s steps(30, end);
            }}
            .boot-steps {{
                margin-top: 22px; display:flex; flex-direction:column; gap:6px;
                align-items:flex-start;
            }}
            .boot-step {{
                font-family:'JetBrains Mono', monospace; font-size:12px; color:{TEXT_MUTED};
                opacity:0; text-align:left; width:300px;
                animation: bootstepfade .5s ease forwards;
            }}
            .boot-check {{ color:{CYAN}; margin-right:8px; }}
            .boot-bar-track {{
                width: 300px; height: 4px; border-radius: 999px; margin-top: 22px;
                background: rgba(148,163,184,0.15); overflow:hidden;
            }}
            .boot-bar-fill {{
                height:100%; border-radius:999px;
                background: linear-gradient(90deg, {CYAN}, {VIOLET}, {PINK});
                animation: bootfill 2.4s ease forwards;
                box-shadow: 0 0 12px {CYAN}aa;
            }}
            @keyframes bootspin {{ to {{ transform: rotate(360deg); }} }}
            @keyframes bootflicker {{ 0%, 100% {{ opacity:1; }} 50% {{ opacity:.7; }} }}
            @keyframes boottyping {{ from {{ width:0; }} to {{ width:30ch; }} }}
            @keyframes bootfill {{ from {{ width:0%; }} to {{ width:100%; }} }}
            @keyframes bootstepfade {{ from {{opacity:0; transform:translateX(-6px);}} to {{opacity:1; transform:translateX(0);}} }}
            </style>
            <div class="boot-wrap">
                <div class="boot-ring"></div>
                <div class="boot-logo">🛰️ WORK TRACKER</div>
                <div class="boot-sub">INITIALIZING COMMAND DECK...</div>
                <div class="boot-steps">{steps_html}</div>
                <div class="boot-bar-track"><div class="boot-bar-fill"></div></div>
            </div>
            """,
            unsafe_allow_html=True,
        )
    time.sleep(2.7)
    st.session_state.splash_shown = True
    splash_slot.empty()
    st.rerun()

# ---------------------------------------------------------------------------
# DB CONNECTION
# ---------------------------------------------------------------------------

@st.cache_resource
def get_engine():
    db_url = st.secrets["postgres"]["url"]
    return create_engine(db_url, pool_pre_ping=True)


engine = get_engine()


def run_query(query, params=None):
    with engine.begin() as conn:
        result = conn.execute(text(query), params or {})
        rows = result.mappings().all()
        return pd.DataFrame(rows)


def run_exec(query, params=None):
    with engine.begin() as conn:
        conn.execute(text(query), params or {})


def init_db():
    with engine.begin() as conn:
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS projects (
                id BIGSERIAL PRIMARY KEY,
                name TEXT NOT NULL,
                description TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS tasks (
                id BIGSERIAL PRIMARY KEY,
                project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                description TEXT,
                status TEXT DEFAULT 'To Do',
                assignee TEXT DEFAULT 'Teja',
                priority TEXT DEFAULT 'Medium',
                due_date DATE,
                created_by TEXT,
                created_at TIMESTAMPTZ DEFAULT now(),
                updated_at TIMESTAMPTZ DEFAULT now()
            );
        """))
        # additional columns specific to automation jobs — safe to run repeatedly
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS automation_type TEXT;"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS trigger_type TEXT;"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS platform_tool TEXT;"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS repo_link TEXT;"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS deployment_status TEXT DEFAULT 'Not Deployed';"))
        conn.execute(text("ALTER TABLE tasks ADD COLUMN IF NOT EXISTS environment TEXT DEFAULT 'Dev';"))

        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS chat_messages (
                id BIGSERIAL PRIMARY KEY,
                project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
                sender TEXT NOT NULL,
                message TEXT NOT NULL,
                created_at TIMESTAMPTZ DEFAULT now()
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS resources (
                id BIGSERIAL PRIMARY KEY,
                project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
                title TEXT NOT NULL,
                url TEXT NOT NULL,
                category TEXT DEFAULT 'Other',
                added_by TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            );
        """))
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS activity_log (
                id BIGSERIAL PRIMARY KEY,
                project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
                actor TEXT NOT NULL,
                action TEXT NOT NULL,
                details TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            );
        """))
        # automation registry — separate from tasks, for tracking running workflows
        conn.execute(text("""
            CREATE TABLE IF NOT EXISTS automations (
                id BIGSERIAL PRIMARY KEY,
                project_id BIGINT REFERENCES projects(id) ON DELETE CASCADE,
                name TEXT NOT NULL,
                description TEXT,
                automation_type TEXT DEFAULT 'Other',
                trigger_type TEXT DEFAULT 'Manual',
                platform_tool TEXT,
                repo_link TEXT,
                webhook_url TEXT,
                status TEXT DEFAULT 'Draft',
                last_run TIMESTAMPTZ,
                created_by TEXT,
                created_at TIMESTAMPTZ DEFAULT now()
            );
        """))


init_db()

# ---------------------------------------------------------------------------
# CACHING LAYER
# ---------------------------------------------------------------------------
# IMPORTANT: the cache-key parameter below must NOT start with an underscore.
# Streamlit's @st.cache_data ignores any argument whose name starts with "_"
# when computing the cache key (that convention exists so you can pass in
# unhashable objects like DB connections without breaking the cache). Naming
# it "_version" in a previous revision silently disabled invalidation —
# every delete/update wrote to Postgres correctly, but the cached read kept
# serving the old snapshot. Fixed here by naming it "version" (no underscore)
# so every mutation genuinely busts the cache.

if "data_version" not in st.session_state:
    st.session_state.data_version = 0


def bump_version():
    st.session_state.data_version += 1


@st.cache_data(show_spinner=False)
def _cached_query(query, params_items, version):
    params = dict(params_items) if params_items else None
    return run_query(query, params)


def cq(query, params=None):
    """Cached query — invalidated automatically whenever data_version bumps."""
    params_items = tuple(sorted(params.items())) if params else None
    return _cached_query(query, params_items, st.session_state.data_version)


def mutate(query, params=None):
    """Write query that also invalidates the cache immediately."""
    run_exec(query, params)
    bump_version()


def log_activity(project_id, actor, action, details=""):
    run_exec(
        "INSERT INTO activity_log (project_id, actor, action, details) VALUES (:pid, :actor, :action, :details)",
        {"pid": project_id, "actor": actor, "action": action, "details": details},
    )
    bump_version()


# ---------------------------------------------------------------------------
# OPTIONAL: MENTION NOTIFICATION VIA ZAPIER WEBHOOK
# ---------------------------------------------------------------------------

def get_webhook_url():
    try:
        return st.secrets.get("notifications", {}).get("webhook_url")
    except Exception:
        return None


def find_mentions(message, users):
    found = []
    for u in users:
        if re.search(rf"@{re.escape(u)}\b", message, re.IGNORECASE):
            found.append(u)
    return found


def highlight_mentions(message, users):
    out = message
    for u in users:
        out = re.sub(rf"(@{re.escape(u)})\b", r"**\1**", out, flags=re.IGNORECASE)
    return out


def send_mention_notification(project_name, sender, mentioned_user, message):
    webhook_url = get_webhook_url()
    if not webhook_url:
        return
    try:
        import requests
        requests.post(
            webhook_url,
            json={
                "project": project_name,
                "sender": sender,
                "mentioned": mentioned_user,
                "message": message,
                "timestamp": datetime.utcnow().isoformat(),
            },
            timeout=5,
        )
    except Exception:
        pass  # a failed notification must never break the chat


# ---------------------------------------------------------------------------
# AUTH
# ---------------------------------------------------------------------------

USERS = st.secrets["users"]

if "user" not in st.session_state:
    st.session_state.user = None

if st.session_state.user is None:
    st.markdown("<br>", unsafe_allow_html=True)
    c1, c2, c3 = st.columns([1, 1.2, 1])
    with c2:
        top_l, top_r = st.columns([3, 1])
        with top_l:
            st.markdown("### 🛰️ Work Tracker — Command Deck")
        with top_r:
            st.markdown('<div class="theme-toggle-btn">', unsafe_allow_html=True)
            if st.button("☀️ Light" if IS_DARK else "🌙 Dark", key="theme_toggle_login", use_container_width=True):
                toggle_theme()
                st.rerun()
            st.markdown("</div>", unsafe_allow_html=True)
        st.caption("Log in to continue")
        with st.form("login_form"):
            username = st.selectbox("Select user", list(USERS.keys()))
            password = st.text_input("Password", type="password")
            submitted = st.form_submit_button("Login", use_container_width=True)
        if submitted:
            if USERS.get(username) == password:
                st.session_state.user = username
                st.rerun()
            else:
                st.error("Incorrect password, please try again.")
    st.stop()

current_user = st.session_state.user

# ---------------------------------------------------------------------------
# SIDEBAR — Projects (Overview / My Projects) + More Menu
# ---------------------------------------------------------------------------

with st.sidebar:
    top_l, top_r = st.columns([2.4, 1])
    with top_l:
        st.markdown(f"### 👤 {current_user}")
    with top_r:
        st.markdown('<div class="theme-toggle-btn">', unsafe_allow_html=True)
        if st.button("☀️" if IS_DARK else "🌙", key="theme_toggle_sidebar", use_container_width=True,
                     help="Switch to light mode" if IS_DARK else "Switch to dark mode"):
            toggle_theme()
            st.rerun()
        st.markdown("</div>", unsafe_allow_html=True)

    if st.button("Logout", use_container_width=True, key="btn_logout"):
        st.session_state.user = None
        st.rerun()

    st.divider()
    st.markdown("#### 📁 Projects")

    projects_df = cq("SELECT * FROM projects ORDER BY created_at ASC")

    if "selected_project" not in st.session_state:
        st.session_state.selected_project = "OVERVIEW"

    # --- Submenu 1: Overview ---
    st.markdown('<div class="side-section-label">🌐 Overview</div>', unsafe_allow_html=True)
    is_overview = st.session_state.selected_project == "OVERVIEW"
    if st.button(
        "🌐 Overview — All Projects",
        use_container_width=True,
        key="nav_overview",
        type="primary" if is_overview else "secondary",
    ):
        st.session_state.selected_project = "OVERVIEW"
        st.rerun()

    st.write("")
    st.markdown('<div class="side-section-label">📂 My Projects</div>', unsafe_allow_html=True)

    if projects_df.empty:
        st.info("No projects yet. Add one below 👇")
        selected_project_id = None
    else:
        for _, prow in projects_df.iterrows():
            is_sel = st.session_state.selected_project == prow["name"]
            if st.button(
                f"{'🟢' if is_sel else '⚪'} {prow['name']}",
                use_container_width=True,
                key=f"nav_proj_{prow['id']}",
                type="primary" if is_sel else "secondary",
            ):
                st.session_state.selected_project = prow["name"]
                st.rerun()

        if st.session_state.selected_project == "OVERVIEW":
            selected_project_id = "OVERVIEW"
        elif st.session_state.selected_project in projects_df["name"].values:
            selected_project_id = int(
                projects_df.loc[projects_df["name"] == st.session_state.selected_project, "id"].iloc[0]
            )
        else:
            st.session_state.selected_project = "OVERVIEW"
            selected_project_id = "OVERVIEW"

    with st.expander("➕ Add new project"):
        with st.form("new_project_form", clear_on_submit=True):
            new_name = st.text_input("Project name")
            new_desc = st.text_area("Description (optional)")
            add_submit = st.form_submit_button("Create project", use_container_width=True)
        if add_submit and new_name.strip():
            mutate(
                "INSERT INTO projects (name, description) VALUES (:n, :d)",
                {"n": new_name.strip(), "d": new_desc.strip()},
            )
            st.session_state.selected_project = new_name.strip()
            st.rerun()

    if isinstance(selected_project_id, int):
        with st.expander("🗑️ Delete this project"):
            st.warning("All tasks, resources & chat in this project will also be deleted.")
            confirm = st.checkbox("I confirm I want to delete this project", key="confirm_del_project")
            if st.button("Delete project", disabled=not confirm, use_container_width=True, key="btn_del_project"):
                mutate("DELETE FROM projects WHERE id = :id", {"id": selected_project_id})
                st.session_state.selected_project = "OVERVIEW"
                st.rerun()

    # --- Submenu 2: More Menu ---
    st.divider()
    st.markdown("#### ⚡ More Menu")

    with st.expander("🔍 Quick search"):
        quick_search = st.text_input(
            "Search task", key="quick_search_input", label_visibility="collapsed",
            placeholder="Search task title across all projects...",
        )
        if quick_search:
            hits = cq(
                """
                SELECT p.name AS project, t.title, t.status, t.assignee, t.due_date
                FROM tasks t JOIN projects p ON p.id = t.project_id
                WHERE t.title ILIKE :q
                ORDER BY t.created_at DESC LIMIT 8
                """,
                {"q": f"%{quick_search}%"},
            )
            if hits.empty:
                st.caption("No results.")
            else:
                for _, hrow in hits.iterrows():
                    st.markdown(
                        f'<div class="app-sub">🔹 <b style="color:{CARD_SUBTEXT};">{hrow["title"]}</b><br>'
                        f'{hrow["project"]} · {hrow["status"]} · {hrow["assignee"]}</div>',
                        unsafe_allow_html=True,
                    )

    with st.expander("📤 Export data"):
        export_scope = st.radio(
            "Export scope", ["All projects", "This project only"],
            key="export_scope", label_visibility="collapsed",
            disabled=not isinstance(selected_project_id, int),
        )
        if export_scope == "This project only" and isinstance(selected_project_id, int):
            export_df = cq(
                "SELECT * FROM tasks WHERE project_id = :pid ORDER BY created_at DESC",
                {"pid": selected_project_id},
            )
        else:
            export_df = cq(
                "SELECT p.name AS project, t.* FROM tasks t JOIN projects p ON p.id = t.project_id"
            )
        if not export_df.empty:
            csv_bytes = export_df.to_csv(index=False).encode("utf-8")
            st.download_button(
                "⬇️ Download tasks (CSV)", data=csv_bytes,
                file_name=f"tasks_export_{date.today()}.csv", mime="text/csv",
                use_container_width=True,
            )
        else:
            st.caption("No data to export yet.")

    with st.expander("⚙️ Preferences"):
        if "pref_compact" not in st.session_state:
            st.session_state.pref_compact = False
        st.session_state.pref_compact = st.toggle(
            "Compact mode (hide descriptions in kanban)",
            value=st.session_state.pref_compact, key="toggle_compact",
        )
        webhook_active = bool(get_webhook_url())
        st.caption(f"🔔 Mention notifications: {'🟢 Active' if webhook_active else '⚪ Inactive'}")
        st.caption(f"👥 Total registered users: {len(USERS)}")
        st.caption(f"🎨 Theme: {'🌙 Dark' if IS_DARK else '☀️ Light'}")

    with st.expander("ℹ️ About this app"):
        st.markdown(
            '<span class="glow-pill">v2.0 · AUTOMATION EDITION</span>',
            unsafe_allow_html=True,
        )
        st.caption("🛰️ Work Tracker — Command Deck")
        st.caption("Built for tracking team tasks & automation workflows.")
        st.caption(f"Logged in as **{current_user}**")

# ---------------------------------------------------------------------------
# NO PROJECT YET
# ---------------------------------------------------------------------------

if projects_df.empty:
    st.title("🛰️ Work Tracker — Command Deck")
    st.write("Create your first project from the sidebar to start tracking work.")
    st.stop()

# ---------------------------------------------------------------------------
# OVERVIEW / COMMAND CENTER (cross-project) — full recap dashboard
# ---------------------------------------------------------------------------

if selected_project_id == "OVERVIEW":

    def _load_overview_data():
        all_tasks_ = cq(
            "SELECT p.name AS project, p.id AS project_id, t.* "
            "FROM tasks t JOIN projects p ON p.id = t.project_id"
        )
        all_automations_ = cq(
            "SELECT p.name AS project, a.* "
            "FROM automations a JOIN projects p ON p.id = a.project_id"
        )
        all_resources_ = cq(
            "SELECT p.name AS project, r.* "
            "FROM resources r JOIN projects p ON p.id = r.project_id"
        )
        all_activity_ = cq(
            "SELECT p.name AS project, al.* FROM activity_log al "
            "JOIN projects p ON p.id = al.project_id "
            "ORDER BY al.created_at DESC LIMIT 15"
        )
        return all_tasks_, all_automations_, all_resources_, all_activity_

    show_progress = not st.session_state.get("overview_loaded_once", False)

    if show_progress:
        with st.status("🛰️ Loading Command Center...", expanded=True) as status:
            st.write("📡 Fetching data for all projects...")
            time.sleep(0.15)
            st.write("📋 Calculating task status & progress...")
            time.sleep(0.15)
            st.write("⚙️ Loading automation status...")
            time.sleep(0.15)
            st.write("🔗 Counting resource library...")
            time.sleep(0.15)
            st.write("🕓 Pulling latest activity log...")
            all_tasks, all_automations, all_resources, all_activity = _load_overview_data()
            time.sleep(0.15)
            status.update(label="✅ Command Center ready.", state="complete", expanded=False)
        st.session_state.overview_loaded_once = True
    else:
        all_tasks, all_automations, all_resources, all_activity = _load_overview_data()

    st.title("🌐 Command Center")
    st.caption("A complete overview of all projects — tasks, automations, resources, and team activity in one screen.")

    today = date.today()
    total_tasks = len(all_tasks)
    done_tasks = int((all_tasks["status"] == "Done").sum()) if not all_tasks.empty else 0
    completion_rate = round((done_tasks / total_tasks) * 100, 1) if total_tasks else 0.0
    overdue_count = 0
    if not all_tasks.empty:
        overdue_count = int(
            ((pd.to_datetime(all_tasks["due_date"]).dt.date < today) & (all_tasks["status"] != "Done")).sum()
        )
    active_automations_count = int((all_automations["status"] == "Active").sum()) if not all_automations.empty else 0
    error_automations_count = int((all_automations["status"] == "Error").sum()) if not all_automations.empty else 0
    total_resources = len(all_resources)

    k1, k2, k3, k4, k5, k6 = st.columns(6)
    k1.metric("📁 Projects", len(projects_df))
    k2.metric("📋 Total Tasks", total_tasks)
    k3.metric("✅ Completion", f"{completion_rate}%")
    k4.metric("⚠️ Overdue", overdue_count)
    k5.metric("🤖 Active Automations", active_automations_count, delta=f"-{error_automations_count} error" if error_automations_count else None, delta_color="inverse")
    k6.metric("🔗 Resources", total_resources)

    st.markdown(
        f'<span class="glow-pill">TEAM_STATUS :: '
        f'{"🟢 ALL CLEAR" if overdue_count == 0 and error_automations_count == 0 else "🟠 NEEDS REVIEW" if overdue_count < 3 and error_automations_count == 0 else "🔴 ACTION REQUIRED"}</span>',
        unsafe_allow_html=True,
    )

    st.divider()

    # --- Project health grid ---
    st.markdown("##### 🩺 Project Health")
    health_cols = st.columns(3)
    for i, (_, prow) in enumerate(projects_df.iterrows()):
        proj_tasks = all_tasks[all_tasks["project_id"] == prow["id"]] if not all_tasks.empty else pd.DataFrame()
        p_total = len(proj_tasks)
        p_done = int((proj_tasks["status"] == "Done").sum()) if p_total else 0
        p_rate = round((p_done / p_total) * 100, 1) if p_total else 0.0
        p_overdue = 0
        if p_total:
            p_overdue = int(
                ((pd.to_datetime(proj_tasks["due_date"]).dt.date < today) & (proj_tasks["status"] != "Done")).sum()
            )
        h_label, h_color = health_badge(p_overdue)
        with health_cols[i % 3]:
            st.markdown(
                f'<div class="app-card" style="border-left-color:{h_color};">'
                f'<div class="app-title">{prow["name"]}</div>'
                f'<div class="app-sub">{p_total} tasks · {p_done} done · {p_overdue} overdue</div>'
                f'<div class="progress-track"><div class="progress-fill" style="width:{p_rate}%;"></div></div>'
                f'<div class="app-sub" style="margin-top:6px;">{h_label} · {p_rate}%</div>'
                f'</div>',
                unsafe_allow_html=True,
            )

    st.divider()

    # --- Charts ---
    try:
        import plotly.graph_objects as go
        import plotly.express as px

        plotly_theme = dict(
            paper_bgcolor="rgba(0,0,0,0)",
            plot_bgcolor="rgba(0,0,0,0)",
            font=dict(color=CHART_TEXT, family="Inter"),
            margin=dict(t=30, l=10, r=10, b=10),
            legend=dict(bgcolor="rgba(0,0,0,0)"),
        )

        r1c1, r1c2 = st.columns([1, 1.3])
        with r1c1:
            st.markdown("##### Status of All Tasks")
            if not all_tasks.empty:
                sc = all_tasks["status"].value_counts().reindex(STATUSES).fillna(0)
                fig = go.Figure(
                    data=[go.Pie(
                        labels=sc.index, values=sc.values, hole=0.62,
                        marker=dict(colors=[STATUS_COLORS[s] for s in sc.index]),
                        textinfo="value", sort=False,
                    )]
                )
                fig.update_layout(
                    **plotly_theme, height=280,
                    annotations=[dict(text=f"{total_tasks}<br>tasks", x=0.5, y=0.5, font_size=16, showarrow=False)],
                )
                st.plotly_chart(fig, use_container_width=True)
            else:
                st.caption("No data yet.")

        with r1c2:
            st.markdown("##### Tasks per Project (by status)")
            if not all_tasks.empty:
                pp = all_tasks.groupby(["project", "status"]).size().reset_index(name="count")
                fig2 = px.bar(
                    pp, x="project", y="count", color="status",
                    color_discrete_map=STATUS_COLORS, barmode="stack",
                    category_orders={"status": STATUSES},
                )
                fig2.update_layout(**plotly_theme, height=280, xaxis_title=None, yaxis_title="Tasks")
                st.plotly_chart(fig2, use_container_width=True)
            else:
                st.caption("No data yet.")

        r2c1, r2c2 = st.columns(2)
        with r2c1:
            st.markdown("##### Workload per Assignee")
            if not all_tasks.empty:
                wl = all_tasks.groupby(["assignee", "status"]).size().reset_index(name="count")
                fig3 = px.bar(
                    wl, x="assignee", y="count", color="status",
                    color_discrete_map=STATUS_COLORS, barmode="stack",
                    category_orders={"status": STATUSES},
                )
                fig3.update_layout(**plotly_theme, height=260, xaxis_title=None, yaxis_title="Tasks")
                st.plotly_chart(fig3, use_container_width=True)
            else:
                st.caption("No data yet.")

        with r2c2:
            st.markdown("##### New Tasks Trend (14 days)")
            if not all_tasks.empty:
                created = pd.to_datetime(all_tasks["created_at"]).dt.date.value_counts().sort_index().tail(14)
                fig4 = go.Figure(
                    data=[go.Scatter(
                        x=created.index, y=created.values, mode="lines+markers",
                        line=dict(color=CYAN, width=3), fill="tozeroy",
                        fillcolor=hex_to_rgba(CYAN, 0.13), marker=dict(color=VIOLET, size=7),
                    )]
                )
                fig4.update_layout(**plotly_theme, height=260, xaxis_title=None, yaxis_title="New tasks")
                st.plotly_chart(fig4, use_container_width=True)
            else:
                st.caption("No data yet.")

    except ImportError:
        st.caption("💡 Install `plotly` (`pip install plotly`) for interactive charts.")
        if not all_tasks.empty:
            st.bar_chart(all_tasks["status"].value_counts())

    st.divider()

    # --- Automation health + Resource library ---
    ac1, ac2 = st.columns([1.3, 1])
    with ac1:
        st.markdown("##### 🤖 Automation Health (all projects)")
        if all_automations.empty:
            st.caption("No automations registered in any project yet.")
        else:
            aa1, aa2, aa3, aa4 = st.columns(4)
            aa1.metric("Total", len(all_automations))
            aa2.metric("🟢 Active", int((all_automations["status"] == "Active").sum()))
            aa3.metric("🟠 Paused", int((all_automations["status"] == "Paused").sum()))
            aa4.metric("🔴 Error", int((all_automations["status"] == "Error").sum()))

            errored = all_automations[all_automations["status"] == "Error"]
            if not errored.empty:
                st.markdown(
                    f'<div class="app-sub" style="color:{PINK};margin-top:6px;">⚠️ Needs immediate attention:</div>',
                    unsafe_allow_html=True,
                )
                for _, erow in errored.iterrows():
                    st.markdown(
                        f'<div class="app-card" style="border-left-color:{PINK};">'
                        f'<b>{erow["name"]}</b> · {erow["project"]}'
                        f'<div class="app-sub">{erow["automation_type"] or "-"} · {erow["trigger_type"] or "-"}</div>'
                        f'</div>',
                        unsafe_allow_html=True,
                    )
    with ac2:
        st.markdown("##### 🔗 Resource Library")
        if all_resources.empty:
            st.caption("No resources saved yet.")
        else:
            rc = all_resources["category"].value_counts()
            pills = "".join(
                f'<span class="glow-pill" style="margin:3px;display:inline-block;">{cat} · {cnt}</span>'
                for cat, cnt in rc.items()
            )
            st.markdown(pills, unsafe_allow_html=True)

    st.divider()

    # --- Upcoming deadlines + Recent activity ---
    dcol, acol = st.columns([1.2, 1])
    with dcol:
        st.markdown("##### 📅 Upcoming Deadlines")
        if not all_tasks.empty:
            upcoming = all_tasks[all_tasks["due_date"].notna() & (all_tasks["status"] != "Done")].copy()
            upcoming = upcoming.sort_values("due_date").head(8)
            if upcoming.empty:
                st.caption("No upcoming deadlines. 🎉")
            for _, row in upcoming.iterrows():
                overdue_flag = row["due_date"] < today
                st.markdown(
                    f'<div class="app-card" style="border-left-color:{PINK if overdue_flag else CYAN};">'
                    f'{avatar(row["assignee"], ASSIGNEE_COLORS.get(row["assignee"], CYAN))}'
                    f'<b>{row["title"]}</b> · {row["project"]}'
                    f'<div class="app-sub">📅 {row["due_date"]}{" · OVERDUE" if overdue_flag else ""}</div></div>',
                    unsafe_allow_html=True,
                )
        else:
            st.caption("No tasks at all yet.")
    with acol:
        st.markdown("##### 🕓 Recent Activity")
        if all_activity.empty:
            st.caption("No activity recorded yet.")
        else:
            for _, row in all_activity.iterrows():
                st.markdown(
                    f'<div class="app-card">'
                    f'<b>{row["actor"]}</b> — {row["action"]} '
                    f'<span class="app-sub" style="margin:0;">({row["project"]})</span>'
                    f'{": " + row["details"] if row["details"] else ""}'
                    f'<div class="app-sub">{row["created_at"]}</div></div>',
                    unsafe_allow_html=True,
                )

    st.stop()

# ---------------------------------------------------------------------------
# MAIN AREA — SELECTED PROJECT
# ---------------------------------------------------------------------------

proj_row = projects_df.loc[projects_df["id"] == selected_project_id].iloc[0]
st.title(f"🛰️ {proj_row['name']}")
if proj_row["description"]:
    st.caption(proj_row["description"])

tab_dash, tab_tracker, tab_automations, tab_resources, tab_chat, tab_activity = st.tabs(
    ["📈 Dashboard", "📋 Task Tracker", "⚙️ Automations", "🔗 Resources", "💬 Chat", "🕓 Activity"]
)

# ---------------------------------------------------------------------------
# TAB 0: DASHBOARD
# ---------------------------------------------------------------------------

with tab_dash:
    # --- Live HUD header: real-time clock/date + operator/project readout ---
    render_live_clock_hud(proj_row["name"], current_user, IS_DARK)

    # cheap, cached lookup used only to enrich the HUD ticker & gauges below
    automations_hud = cq(
        "SELECT * FROM automations WHERE project_id = :pid",
        {"pid": selected_project_id},
    )
    active_automations_hud = int((automations_hud["status"] == "Active").sum()) if not automations_hud.empty else 0
    total_automations_hud = len(automations_hud)

    with st.spinner("📡 Building analytics dashboard..."):
        tasks_df_dash = cq(
            "SELECT * FROM tasks WHERE project_id = :pid ORDER BY created_at DESC",
            {"pid": selected_project_id},
        )

    if tasks_df_dash.empty:
        st.markdown(
            render_stat_ticker([
                "🟢 SYSTEM ONLINE", "📋 0 TASKS TRACKED", "🤖 "
                f"{active_automations_hud}/{total_automations_hud} AUTOMATIONS ACTIVE",
                "🛰️ AWAITING FIRST TASK",
            ]),
            unsafe_allow_html=True,
        )
        st.info("No tasks in this project yet. Add a task in the **Task Tracker** tab first to see analytics.")
    else:
        total = len(tasks_df_dash)
        done = int((tasks_df_dash["status"] == "Done").sum())
        in_progress = int((tasks_df_dash["status"] == "In Progress").sum())
        today = date.today()
        overdue = int(
            (pd.to_datetime(tasks_df_dash["due_date"]).dt.date.lt(today) & (tasks_df_dash["status"] != "Done")).sum()
        )
        completion_rate = round((done / total) * 100, 1) if total else 0.0

        k1, k2, k3, k4 = st.columns(4)
        k1.metric("Total Tasks", total)
        k2.metric("Completion Rate", f"{completion_rate}%")
        k3.metric("In Progress", in_progress)
        k4.metric("⚠️ Overdue", overdue)

        st.markdown(
            f'<span class="glow-pill">PROJECT_HEALTH :: '
            f'{"🟢 ON TRACK" if overdue == 0 else "🟠 NEEDS ATTENTION" if overdue < 3 else "🔴 AT RISK"}</span>',
            unsafe_allow_html=True,
        )

        st.markdown(
            render_stat_ticker([
                "🟢 SYSTEM ONLINE",
                f"📋 {total} TASKS TRACKED",
                f"✅ {completion_rate}% COMPLETE",
                f"⚠️ {overdue} OVERDUE",
                f"🤖 {active_automations_hud}/{total_automations_hud} AUTOMATIONS ACTIVE",
                f"👤 LOGGED IN AS {current_user.upper()}",
            ]),
            unsafe_allow_html=True,
        )

        on_time_rate = round(((total - overdue) / total) * 100, 1) if total else 100.0
        automation_uptime = round((active_automations_hud / total_automations_hud) * 100, 1) if total_automations_hud else 0.0

        g1, g2, g3 = st.columns(3)
        with g1:
            st.markdown(
                radial_gauge_html(completion_rate, "COMPLETION", f"{done}/{total} tasks done", SUCCESS),
                unsafe_allow_html=True,
            )
        with g2:
            st.markdown(
                radial_gauge_html(on_time_rate, "ON TIME", f"{overdue} overdue of {total}", CYAN),
                unsafe_allow_html=True,
            )
        with g3:
            st.markdown(
                radial_gauge_html(automation_uptime, "AUTOMATION UPTIME", f"{active_automations_hud}/{total_automations_hud} active", VIOLET),
                unsafe_allow_html=True,
            )

        st.write("")

        try:
            import plotly.graph_objects as go
            import plotly.express as px

            plotly_theme = dict(
                paper_bgcolor="rgba(0,0,0,0)",
                plot_bgcolor="rgba(0,0,0,0)",
                font=dict(color=CHART_TEXT, family="Inter"),
                margin=dict(t=30, l=10, r=10, b=10),
                legend=dict(bgcolor="rgba(0,0,0,0)"),
            )

            row1c1, row1c2 = st.columns([1, 1.3])

            with row1c1:
                st.markdown("##### Status Breakdown")
                status_counts = tasks_df_dash["status"].value_counts().reindex(STATUSES).fillna(0)
                fig = go.Figure(
                    data=[
                        go.Pie(
                            labels=status_counts.index,
                            values=status_counts.values,
                            hole=0.62,
                            marker=dict(colors=[STATUS_COLORS[s] for s in status_counts.index]),
                            textinfo="value",
                            sort=False,
                        )
                    ]
                )
                fig.update_layout(
                    **plotly_theme,
                    height=280,
                    annotations=[dict(text=f"{total}<br>tasks", x=0.5, y=0.5, font_size=16, showarrow=False)],
                )
                st.plotly_chart(fig, use_container_width=True)

            with row1c2:
                st.markdown("##### Workload per Assignee")
                workload = tasks_df_dash.groupby(["assignee", "status"]).size().reset_index(name="count")
                fig2 = px.bar(
                    workload, x="assignee", y="count", color="status",
                    color_discrete_map=STATUS_COLORS, barmode="stack",
                    category_orders={"status": STATUSES},
                )
                fig2.update_layout(**plotly_theme, height=280, xaxis_title=None, yaxis_title="Tasks")
                st.plotly_chart(fig2, use_container_width=True)

            row2c1, row2c2 = st.columns([1, 1])

            with row2c1:
                st.markdown("##### Priority Distribution")
                prio_counts = tasks_df_dash["priority"].value_counts().reindex(PRIORITIES).fillna(0)
                fig3 = go.Figure(
                    data=[
                        go.Bar(
                            x=prio_counts.index, y=prio_counts.values,
                            marker=dict(color=[PRIORITY_COLORS[p] for p in prio_counts.index]),
                        )
                    ]
                )
                fig3.update_layout(**plotly_theme, height=260, xaxis_title=None, yaxis_title="Tasks")
                st.plotly_chart(fig3, use_container_width=True)

            with row2c2:
                st.markdown("##### Tasks Created (last 14 days)")
                created = pd.to_datetime(tasks_df_dash["created_at"]).dt.date.value_counts().sort_index()
                created = created.tail(14)
                fig4 = go.Figure(
                    data=[
                        go.Scatter(
                            x=created.index, y=created.values, mode="lines+markers",
                            line=dict(color=CYAN, width=3), fill="tozeroy",
                            fillcolor=hex_to_rgba(CYAN, 0.13), marker=dict(color=VIOLET, size=7),
                        )
                    ]
                )
                fig4.update_layout(**plotly_theme, height=260, xaxis_title=None, yaxis_title="New tasks")
                st.plotly_chart(fig4, use_container_width=True)

        except ImportError:
            st.caption("💡 Install `plotly` (`pip install plotly`) for interactive charts. Simple fallback view:")
            st.bar_chart(tasks_df_dash["status"].value_counts())
            st.bar_chart(tasks_df_dash["assignee"].value_counts())

    # --- Automation Health widget, shown even if there are no tasks yet ---
    st.divider()
    st.markdown("##### 🤖 Automation Health")
    automations_dash = cq(
        "SELECT * FROM automations WHERE project_id = :pid",
        {"pid": selected_project_id},
    )
    if automations_dash.empty:
        st.caption("No automations registered yet. Check the **⚙️ Automations** tab to start registering your workflows.")
    else:
        ha1, ha2, ha3, ha4 = st.columns(4)
        ha1.metric("Total Automations", len(automations_dash))
        ha2.metric("🟢 Active", int((automations_dash["status"] == "Active").sum()))
        ha3.metric("🟠 Paused", int((automations_dash["status"] == "Paused").sum()))
        ha4.metric("🔴 Error", int((automations_dash["status"] == "Error").sum()))

# ---------------------------------------------------------------------------
# TAB 1: TASK TRACKER
# ---------------------------------------------------------------------------

if "editing_task_id" not in st.session_state:
    st.session_state.editing_task_id = None


@st.dialog("✏️ Edit Task", width="large")
def edit_task_dialog(row):
    st.markdown(
        f'<span class="glow-pill">TASK_ID :: {int(row["id"])}</span>',
        unsafe_allow_html=True,
    )
    st.write("")
    e_title = st.text_input("Title", value=row["title"], key=f"d_title_{row['id']}")
    e_desc = st.text_area("Description", value=row["description"] or "", key=f"d_desc_{row['id']}", height=110)

    d1, d2 = st.columns(2)
    with d1:
        e_status = st.selectbox(
            "Status", STATUSES, index=STATUSES.index(row["status"]), key=f"d_status_{row['id']}"
        )
        e_assignee = st.selectbox(
            "Assignee", ASSIGNEES,
            index=ASSIGNEES.index(row["assignee"]) if row["assignee"] in ASSIGNEES else 0,
            key=f"d_assignee_{row['id']}",
        )
    with d2:
        e_priority = st.selectbox(
            "Priority", PRIORITIES, index=PRIORITIES.index(row["priority"]), key=f"d_priority_{row['id']}"
        )
        e_due = st.date_input(
            "Due date",
            value=row["due_date"] if pd.notna(row["due_date"]) else None,
            key=f"d_due_{row['id']}",
        )

    st.markdown("**🤖 Automation Details**")
    a1, a2, a3 = st.columns(3)
    with a1:
        e_automation_type = st.selectbox(
            "Automation type", AUTOMATION_TYPES,
            index=AUTOMATION_TYPES.index(row["automation_type"]) if row["automation_type"] in AUTOMATION_TYPES else len(AUTOMATION_TYPES) - 1,
            key=f"d_atype_{row['id']}",
        )
        e_environment = st.selectbox(
            "Environment", ENVIRONMENTS,
            index=ENVIRONMENTS.index(row["environment"]) if row["environment"] in ENVIRONMENTS else 0,
            key=f"d_env_{row['id']}",
        )
    with a2:
        e_trigger = st.selectbox(
            "Trigger", TRIGGER_TYPES,
            index=TRIGGER_TYPES.index(row["trigger_type"]) if row["trigger_type"] in TRIGGER_TYPES else 0,
            key=f"d_trigger_{row['id']}",
        )
        e_deployment = st.selectbox(
            "Deployment status", DEPLOYMENT_STATUSES,
            index=DEPLOYMENT_STATUSES.index(row["deployment_status"]) if row["deployment_status"] in DEPLOYMENT_STATUSES else 0,
            key=f"d_deploy_{row['id']}",
        )
    with a3:
        e_platform = st.text_input("Platform/tool", value=row["platform_tool"] or "", key=f"d_platform_{row['id']}")
        e_repo = st.text_input("Repo/script link", value=row["repo_link"] or "", key=f"d_repo_{row['id']}")

    st.write("")
    save_col, cancel_col = st.columns(2)
    if save_col.button("💾 Save changes", use_container_width=True, type="primary", key=f"d_save_{row['id']}"):
        mutate(
            """UPDATE tasks SET title=:title, description=:desc, status=:status,
               assignee=:assignee, priority=:priority, due_date=:due, updated_at=now(),
               automation_type=:atype, trigger_type=:trigger, platform_tool=:platform,
               repo_link=:repo, deployment_status=:deploy, environment=:env
               WHERE id=:id""",
            {
                "title": e_title.strip(), "desc": e_desc.strip(), "status": e_status,
                "assignee": e_assignee, "priority": e_priority,
                "due": e_due if e_due else None, "id": int(row["id"]),
                "atype": e_automation_type, "trigger": e_trigger, "platform": e_platform.strip(),
                "repo": e_repo.strip(), "deploy": e_deployment, "env": e_environment,
            },
        )
        log_activity(selected_project_id, current_user, "Update task", e_title.strip())
        st.session_state.editing_task_id = None
        st.rerun()
    if cancel_col.button("Close", use_container_width=True, key=f"d_cancel_{row['id']}"):
        st.session_state.editing_task_id = None
        st.rerun()

    st.divider()
    del_confirm_key = f"confirm_delete_{row['id']}"
    if del_confirm_key not in st.session_state:
        st.session_state[del_confirm_key] = False

    if not st.session_state[del_confirm_key]:
        if st.button("🗑️ Delete this task", key=f"d_del_ask_{row['id']}"):
            st.session_state[del_confirm_key] = True
            st.rerun()
    else:
        st.warning("Are you sure you want to delete this task? This action is permanent and cannot be undone.")
        yes_col, no_col = st.columns(2)
        if yes_col.button("Yes, delete permanently", type="primary", use_container_width=True, key=f"d_del_yes_{row['id']}"):
            mutate("DELETE FROM tasks WHERE id=:id", {"id": int(row["id"])})
            log_activity(selected_project_id, current_user, "Delete task", row["title"])
            st.session_state[del_confirm_key] = False
            st.session_state.editing_task_id = None
            st.rerun()
        if no_col.button("Cancel", use_container_width=True, key=f"d_del_no_{row['id']}"):
            st.session_state[del_confirm_key] = False
            st.rerun()


with tab_tracker:
    with st.expander("➕ Add new task", expanded=False):
        with st.form("new_task_form", clear_on_submit=True):
            c1, c2 = st.columns(2)
            with c1:
                t_title = st.text_input("Task title")
                t_assignee = st.selectbox("Assignee", ASSIGNEES)
                t_priority = st.selectbox("Priority", PRIORITIES, index=1)
            with c2:
                t_status = st.selectbox("Status", STATUSES, index=0)
                t_due = st.date_input("Due date", value=None)
            t_desc = st.text_area("Description (optional)")

            st.markdown("**🤖 Automation Details**")
            a1, a2, a3 = st.columns(3)
            with a1:
                t_automation_type = st.selectbox("Automation type", AUTOMATION_TYPES)
                t_environment = st.selectbox("Environment", ENVIRONMENTS)
            with a2:
                t_trigger = st.selectbox("Trigger", TRIGGER_TYPES)
                t_deployment = st.selectbox("Deployment status", DEPLOYMENT_STATUSES)
            with a3:
                t_platform = st.text_input("Platform/tool", placeholder="e.g. n8n self-hosted, Zapier Pro")
                t_repo = st.text_input("Repo/script link", placeholder="https://github.com/...")

            task_submit = st.form_submit_button("Add task", use_container_width=True)
        if task_submit and t_title.strip():
            mutate(
                """INSERT INTO tasks
                   (project_id, title, description, status, assignee, priority, due_date, created_by,
                    automation_type, trigger_type, platform_tool, repo_link, deployment_status, environment)
                   VALUES (:pid, :title, :desc, :status, :assignee, :priority, :due, :by,
                           :atype, :trigger, :platform, :repo, :deploy, :env)""",
                {
                    "pid": selected_project_id, "title": t_title.strip(), "desc": t_desc.strip(),
                    "status": t_status, "assignee": t_assignee, "priority": t_priority,
                    "due": t_due if t_due else None, "by": current_user,
                    "atype": t_automation_type, "trigger": t_trigger, "platform": t_platform.strip(),
                    "repo": t_repo.strip(), "deploy": t_deployment, "env": t_environment,
                },
            )
            log_activity(selected_project_id, current_user, "Add task", t_title.strip())
            st.rerun()
        elif task_submit:
            st.warning("Task title is required.")

    tasks_df = cq(
        "SELECT * FROM tasks WHERE project_id = :pid ORDER BY created_at DESC",
        {"pid": selected_project_id},
    )

    # --- filter bar ---
    f1, f2, f3 = st.columns([2, 1.2, 1])
    search_term = f1.text_input("🔍 Search tasks", placeholder="Search by title...", key="task_search")
    filter_assignee = f2.multiselect("Assignee", ASSIGNEES, key="task_filter_assignee")
    hide_done = f3.checkbox("Hide Done", value=False, key="task_hide_done")

    filtered = tasks_df.copy()
    if not filtered.empty:
        if search_term:
            filtered = filtered[filtered["title"].str.contains(search_term, case=False, na=False)]
        if filter_assignee:
            filtered = filtered[filtered["assignee"].isin(filter_assignee)]
        if hide_done:
            filtered = filtered[filtered["status"] != "Done"]

    m_cols = st.columns(len(STATUSES))
    for i, s in enumerate(STATUSES):
        count = 0 if tasks_df.empty else int((tasks_df["status"] == s).sum())
        m_cols[i].metric(s, count)

    st.divider()

    kanban_cols = st.columns(len(STATUSES))
    today = date.today()
    compact_mode = st.session_state.get("pref_compact", False)
    for col_idx, (col, status) in enumerate(zip(kanban_cols, STATUSES)):
        with col:
            subset = filtered[filtered["status"] == status] if not filtered.empty else filtered
            count = 0 if filtered.empty else len(subset)
            st.markdown(
                f'<div class="kanban-head">'
                f'{status_dot(STATUS_COLORS[status])}'
                f'{status} <span class="glow-pill" style="margin-left:6px;padding:1px 8px;">{count}</span>'
                f'</div>',
                unsafe_allow_html=True,
            )
            if filtered.empty or subset.empty:
                st.markdown(
                    f'<div style="border:1.5px dashed {EMPTY_DASH_BORDER};border-radius:12px;'
                    f'padding:22px 10px;text-align:center;color:{EMPTY_DASH_TEXT};font-size:12px;">'
                    'No tasks here yet</div>',
                    unsafe_allow_html=True,
                )
                continue
            for _, row in subset.iterrows():
                overdue = bool(pd.notna(row["due_date"]) and row["due_date"] < today and status != "Done")
                due_html = ""
                if pd.notna(row["due_date"]):
                    due_color = PINK if overdue else TEXT_MUTED
                    due_label = f"📅 {row['due_date']}" + (" · OVERDUE" if overdue else "")
                    due_html = f'<div class="app-sub" style="color:{due_color};">{due_label}</div>'
                desc_html = ""
                if row["description"] and not compact_mode:
                    short_desc = row["description"][:70] + ("…" if len(row["description"]) > 70 else "")
                    desc_html = f'<div class="app-sub" style="margin-top:2px;opacity:.8;">{short_desc}</div>'

                priority_color = PRIORITY_COLORS[row["priority"]]

                extra_badges = ""
                if row.get("automation_type"):
                    extra_badges += badge(row["automation_type"], VIOLET)
                if row.get("trigger_type"):
                    extra_badges += badge(row["trigger_type"], CYAN)
                if row.get("deployment_status"):
                    extra_badges += badge(
                        row["deployment_status"], DEPLOYMENT_COLORS.get(row["deployment_status"], TEXT_MUTED)
                    )

                card_html = (
                    f'<div class="app-card" style="border-left-color:{priority_color};">'
                    f'<div class="app-title">{row["title"]}</div>'
                    f'{avatar(row["assignee"], ASSIGNEE_COLORS.get(row["assignee"], CYAN))}'
                    f'{badge(row["priority"], priority_color)}'
                    f'{extra_badges}'
                    f'{due_html}'
                    f'{desc_html}'
                    f'</div>'
                )
                st.markdown(card_html, unsafe_allow_html=True)

                b_prev, b_edit, b_next = st.columns([1, 2, 1])
                with b_prev:
                    if st.button("◀", key=f"prev_{row['id']}", use_container_width=True,
                                 disabled=(col_idx == 0), help="Move to previous status"):
                        mutate(
                            "UPDATE tasks SET status=:s, updated_at=now() WHERE id=:id",
                            {"s": STATUSES[col_idx - 1], "id": int(row["id"])},
                        )
                        log_activity(selected_project_id, current_user, "Change status", f"{row['title']} → {STATUSES[col_idx - 1]}")
                        st.rerun()
                with b_edit:
                    if st.button("✏️ Edit", key=f"edit_{row['id']}", use_container_width=True):
                        st.session_state.editing_task_id = int(row["id"])
                        st.rerun()
                with b_next:
                    if st.button("▶", key=f"next_{row['id']}", use_container_width=True,
                                 disabled=(col_idx == len(STATUSES) - 1), help="Move to next status"):
                        mutate(
                            "UPDATE tasks SET status=:s, updated_at=now() WHERE id=:id",
                            {"s": STATUSES[col_idx + 1], "id": int(row["id"])},
                        )
                        log_activity(selected_project_id, current_user, "Change status", f"{row['title']} → {STATUSES[col_idx + 1]}")
                        st.rerun()

                st.markdown("<div style='margin-bottom:14px;'></div>", unsafe_allow_html=True)

    if st.session_state.editing_task_id is not None:
        match = tasks_df[tasks_df["id"] == st.session_state.editing_task_id]
        if not match.empty:
            edit_task_dialog(match.iloc[0])
        else:
            st.session_state.editing_task_id = None

# ---------------------------------------------------------------------------
# TAB 2: AUTOMATIONS — this project's automation workflow registry
# ---------------------------------------------------------------------------

with tab_automations:
    with st.expander("➕ Register new automation", expanded=False):
        with st.form("new_automation_form", clear_on_submit=True):
            au1, au2 = st.columns(2)
            with au1:
                au_name = st.text_input("Automation name")
                au_type = st.selectbox("Type", AUTOMATION_TYPES, key="au_type_new")
                au_trigger = st.selectbox("Trigger", TRIGGER_TYPES, key="au_trigger_new")
            with au2:
                au_status = st.selectbox("Status", AUTOMATION_STATUSES, key="au_status_new")
                au_platform = st.text_input("Platform/tool", key="au_platform_new")
                au_repo = st.text_input("Repo/script link", key="au_repo_new")
            au_webhook = st.text_input(
                "Webhook URL for manual trigger (optional)",
                placeholder="https://hooks.zapier.com/... or your n8n webhook",
            )
            au_desc = st.text_area("Description")
            au_submit = st.form_submit_button("Save automation", use_container_width=True)
        if au_submit and au_name.strip():
            mutate(
                """INSERT INTO automations
                   (project_id, name, description, automation_type, trigger_type, platform_tool,
                    repo_link, webhook_url, status, created_by)
                   VALUES (:pid, :name, :desc, :atype, :trigger, :platform, :repo, :webhook, :status, :by)""",
                {
                    "pid": selected_project_id, "name": au_name.strip(), "desc": au_desc.strip(),
                    "atype": au_type, "trigger": au_trigger, "platform": au_platform.strip(),
                    "repo": au_repo.strip(), "webhook": au_webhook.strip(), "status": au_status,
                    "by": current_user,
                },
            )
            log_activity(selected_project_id, current_user, "Register automation", au_name.strip())
            st.rerun()
        elif au_submit:
            st.warning("Automation name is required.")

    automations_df = cq(
        "SELECT * FROM automations WHERE project_id = :pid ORDER BY created_at DESC",
        {"pid": selected_project_id},
    )

    if automations_df.empty:
        st.caption("No automations registered in this project yet.")
    else:
        automations_df["last_run"] = pd.to_datetime(automations_df["last_run"], errors="coerce")

        ak1, ak2, ak3, ak4 = st.columns(4)
        ak1.metric("Total Automations", len(automations_df))
        ak2.metric("🟢 Active", int((automations_df["status"] == "Active").sum()))
        ak3.metric("🟠 Paused", int((automations_df["status"] == "Paused").sum()))
        ak4.metric("🔴 Error", int((automations_df["status"] == "Error").sum()))
        st.divider()

        # --- quick filter ---
        fa1, fa2 = st.columns([2, 1.4])
        au_search = fa1.text_input("🔍 Search automations", key="au_search")
        au_filter_status = fa2.multiselect("Status", AUTOMATION_STATUSES, key="au_filter_status")

        au_filtered = automations_df.copy()
        if au_search:
            au_filtered = au_filtered[au_filtered["name"].str.contains(au_search, case=False, na=False)]
        if au_filter_status:
            au_filtered = au_filtered[au_filtered["status"].isin(au_filter_status)]

        for _, row in au_filtered.iterrows():
            status_color = AUTOMATION_STATUS_COLORS.get(row["status"], TEXT_MUTED)
            last_run_txt = (
                row["last_run"].strftime("%d %b %Y %H:%M") if pd.notna(row["last_run"]) else "never run"
            )

            meta_bits = []
            if row["platform_tool"]:
                meta_bits.append(row["platform_tool"])
            if row["repo_link"]:
                meta_bits.append(f'<a href="{row["repo_link"]}" target="_blank" style="color:{CYAN};">repo ↗</a>')
            meta_html = " · ".join(meta_bits)

            desc_html = (
                f'<div class="app-sub" style="margin-top:2px;opacity:.85;">{row["description"]}</div>'
                if row["description"] else ""
            )

            card_col, action_col = st.columns([5, 1.5])
            with card_col:
                st.markdown(
                    f'<div class="app-card" style="border-left-color:{status_color};">'
                    f'<div class="app-title">{row["name"]} '
                    f'{status_dot(status_color)}</div>'
                    f'{badge(row["automation_type"], VIOLET)}{badge(row["trigger_type"], CYAN)}{badge(row["status"], status_color)}'
                    f'<div class="app-sub">{meta_html}</div>'
                    f'<div class="app-sub">⏱️ Last run: {last_run_txt}</div>'
                    f'{desc_html}'
                    f'</div>',
                    unsafe_allow_html=True,
                )
            with action_col:
                if row["webhook_url"]:
                    if st.button("▶ Run now", key=f"run_au_{row['id']}", use_container_width=True):
                        try:
                            import requests
                            requests.post(
                                row["webhook_url"],
                                json={"triggered_by": current_user, "automation": row["name"]},
                                timeout=5,
                            )
                            mutate("UPDATE automations SET last_run = now() WHERE id = :id", {"id": int(row["id"])})
                            log_activity(selected_project_id, current_user, "Trigger automation", row["name"])
                            st.success("Triggered ✅")
                        except Exception as e:
                            st.error(f"Failed to trigger: {e}")
                        st.rerun()
                if st.button("🗑️ Delete", key=f"del_au_{row['id']}", use_container_width=True):
                    mutate("DELETE FROM automations WHERE id=:id", {"id": int(row["id"])})
                    log_activity(selected_project_id, current_user, "Delete automation", row["name"])
                    st.rerun()

# ---------------------------------------------------------------------------
# TAB 3: RESOURCES / LINKS
# ---------------------------------------------------------------------------

with tab_resources:
    with st.expander("➕ Add new resource / link", expanded=False):
        with st.form("new_resource_form", clear_on_submit=True):
            r_title = st.text_input("Resource name")
            r_url = st.text_input("URL", placeholder="https://...")
            r_cat = st.selectbox("Category", RESOURCE_CATEGORIES)
            r_submit = st.form_submit_button("Add resource", use_container_width=True)
        if r_submit and r_title.strip() and r_url.strip():
            mutate(
                "INSERT INTO resources (project_id, title, url, category, added_by) VALUES (:pid, :title, :url, :cat, :by)",
                {"pid": selected_project_id, "title": r_title.strip(), "url": r_url.strip(), "cat": r_cat, "by": current_user},
            )
            log_activity(selected_project_id, current_user, "Add resource", r_title.strip())
            st.rerun()
        elif r_submit:
            st.warning("Name and URL are required.")

    resources_df = cq(
        "SELECT * FROM resources WHERE project_id = :pid ORDER BY created_at DESC",
        {"pid": selected_project_id},
    )

    if resources_df.empty:
        st.caption("No resources/links for this project yet.")
    else:
        for cat in RESOURCE_CATEGORIES:
            cat_rows = resources_df[resources_df["category"] == cat]
            if cat_rows.empty:
                continue
            st.markdown(f'<div class="resource-cat">{cat}</div>', unsafe_allow_html=True)
            for _, row in cat_rows.iterrows():
                rc1, rc2 = st.columns([5, 1])
                with rc1:
                    st.markdown(
                        f'<div class="app-card"><a href="{row["url"]}" target="_blank" '
                        f'style="color:{CYAN};text-decoration:none;font-weight:700;">{row["title"]} ↗</a>'
                        f'<div class="app-sub">added by {row["added_by"]}</div></div>',
                        unsafe_allow_html=True,
                    )
                with rc2:
                    if st.button("🗑️", key=f"del_res_{row['id']}"):
                        mutate("DELETE FROM resources WHERE id=:id", {"id": int(row["id"])})
                        log_activity(selected_project_id, current_user, "Delete resource", row["title"])
                        st.rerun()

# ---------------------------------------------------------------------------
# TAB 4: CHAT
# ---------------------------------------------------------------------------

with tab_chat:
    top1, top2 = st.columns([3, 1])
    with top2:
        auto_refresh = st.toggle("Auto-refresh", value=False, key="chat_autorefresh_toggle",
                                  help="When enabled, chat automatically checks for new messages every few seconds.")

    if auto_refresh:
        try:
            from streamlit_autorefresh import st_autorefresh
            st_autorefresh(interval=8000, key=f"chat_refresh_{selected_project_id}")
        except ImportError:
            st.caption("Tip: install `streamlit-autorefresh` so chat auto-updates.")

    if not get_webhook_url():
        st.caption(
            "💡 Mention notifications (@name) aren't active yet — add `notifications.webhook_url` "
            "to secrets to enable them (see README)."
        )

    chat_df = cq(
        "SELECT * FROM chat_messages WHERE project_id = :pid ORDER BY created_at ASC",
        {"pid": selected_project_id},
    )
    if not chat_df.empty:
        chat_df["created_at"] = pd.to_datetime(chat_df["created_at"], errors="coerce")

    chat_container = st.container(height=450)
    with chat_container:
        if chat_df.empty:
            st.caption("No messages yet. Start chatting below 👇 (type @Teja or @Carl to mention)")
        for _, row in chat_df.iterrows():
            role = "user" if row["sender"] == current_user else "assistant"
            ts = row["created_at"]
            ts_str = ts.strftime("%d %b %H:%M") if pd.notna(ts) else ""
            with st.chat_message(role):
                st.markdown(f"**{row['sender']}** · {ts_str}")
                st.markdown(highlight_mentions(row["message"], list(USERS.keys())))

    msg = st.chat_input("Write a message... (use @Teja / @Carl to mention)")
    if msg:
        try:
            mutate(
                "INSERT INTO chat_messages (project_id, sender, message) VALUES (:pid, :sender, :msg)",
                {"pid": selected_project_id, "sender": current_user, "msg": msg},
            )
            mentions = find_mentions(msg, list(USERS.keys()))
            for mentioned in mentions:
                if mentioned != current_user:
                    send_mention_notification(proj_row["name"], current_user, mentioned, msg)
        except Exception as e:
            st.error(f"Failed to send message: {e}")
        else:
            st.rerun()

# ---------------------------------------------------------------------------
# TAB 5: ACTIVITY LOG
# ---------------------------------------------------------------------------

with tab_activity:
    activity_df = cq(
        "SELECT * FROM activity_log WHERE project_id = :pid ORDER BY created_at DESC LIMIT 50",
        {"pid": selected_project_id},
    )
    if activity_df.empty:
        st.caption("No activity recorded yet.")
    else:
        for _, row in activity_df.iterrows():
            st.markdown(
                f'<div class="app-card"><b>{row["actor"]}</b> — {row["action"]}'
                f'{": " + row["details"] if row["details"] else ""}'
                f'<div class="app-sub">{row["created_at"]}</div></div>',
                unsafe_allow_html=True,
            )