"""Streamlit dashboard, styled to match the PitchProb web application."""
import html
import sys
from datetime import date, datetime, timedelta, timezone
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app import (  # noqa: E402
    _team_initials,
    api_insights,
    api_match,
    api_matches,
    api_result_days,
    api_results,
)
from config import LEAGUES  # noqa: E402
from db import DB_PATH, connect  # noqa: E402


st.set_page_config(
    page_title="PitchProb",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=300, show_spinner="Loading fixtures and forecasts...")
def load_dashboard(day: str) -> dict:
    return api_matches(day)


@st.cache_data(ttl=300, show_spinner="Loading match details...")
def load_match_details(match_id: int) -> dict:
    return api_match(match_id)


@st.cache_data(ttl=300, show_spinner="Loading results...")
def load_result_days() -> list[dict]:
    return api_result_days()


@st.cache_data(ttl=300, show_spinner="Loading results...")
def load_results(day: str) -> dict:
    return api_results(day)


@st.cache_data(ttl=300, show_spinner="Loading insights...")
def load_insights(source: str) -> dict:
    return api_insights(source)


def _styles() -> None:
    theme = st.session_state.get("theme", "dark")
    if theme == "light":
        colors = """
          --bg: #f4f5f7; --surface: #ffffff; --surface-2: #eceef2;
          --line: #e2e5ea; --ink: #1c2330; --muted: #4f5a6d;
          --accent: #2750e6; --accent-soft: #e6ecfd;
        """
    else:
        colors = """
          --bg: #0e1116; --surface: #151a21; --surface-2: #1c222b;
          --line: #303844; --ink: #e8ecf2; --muted: #b0bac9;
          --accent: #7fa2ff; --accent-soft: #1b2540;
        """
    st.markdown(
        f"""
        <style>
          :root {{ color-scheme: {theme}; {colors} --hit: #4cc38a; --miss: #ff7b72; }}
          * {{ box-sizing: border-box; }}
          .stApp, [data-testid="stAppViewContainer"] {{ background: var(--bg); color: var(--ink); }}
          [data-testid="stHeader"], [data-testid="stToolbar"], [data-testid="stStatusWidget"], footer {{ display: none; }}
          [data-testid="stMain"] {{ padding-top: 0; }}
          [data-testid="stMainBlockContainer"] {{ max-width: none; padding: 24px 36px 48px; }}
          [data-testid="stSidebar"] {{ min-width: 264px; max-width: 264px; background: var(--surface); border-right: 1px solid var(--line); }}
          [data-testid="stSidebar"] [data-testid="stSidebarContent"] {{ padding: 44px 16px 28px; }}
          [data-testid="stSidebar"] [data-testid="stSidebarHeader"] {{ position: absolute; top: 30px; right: 12px; z-index: 3; width: 44px; height: 44px; margin: 0; padding: 0; }}
          [data-testid="stSidebar"] [data-testid="stLogoSpacer"] {{ display: none; }}
          [data-testid="stSidebar"] [data-testid="stSidebarCollapseButton"] button {{ width: 44px; height: 44px; border: 1px solid var(--line); border-radius: 10px; background: var(--surface); color: var(--muted); }}
          [data-testid="stSidebar"] [data-testid="stMarkdownContainer"] p {{ color: var(--muted); }}
          h1, h2, h3 {{ color: var(--ink); letter-spacing: -.035em; }}
          h1 {{ margin: 0 0 16px; font-size: 24px; font-weight: 650; }}
          h2 {{ font-size: 18px; font-weight: 650; }}
          h3 {{ font-size: 15px; font-weight: 650; }}
          p, label, [data-testid="stCaptionContainer"] {{ color: var(--muted); }}
          div[data-testid="stButton"] > button {{
            min-height: 44px; border: 1px solid var(--line); border-radius: 10px;
            background: var(--surface); color: var(--muted); font-weight: 550;
            transition: background 150ms ease-out, border-color 150ms ease-out, color 150ms ease-out;
          }}
          div[data-testid="stButton"] > button:hover {{ border-color: var(--accent); color: var(--ink); }}
          div[data-testid="stButton"] > button[kind="primary"] {{
            border-color: var(--accent); background: var(--accent-soft); color: var(--accent);
          }}
          [data-testid="stVerticalBlockBorderWrapper"] {{ border-color: var(--line); border-radius: 14px; background: var(--surface); }}
          [data-testid="stExpander"] {{ margin: 8px 0; border: 0; border-bottom: 1px solid var(--line); border-radius: 0; }}
          [data-testid="stExpander"] summary {{ color: var(--ink); font-weight: 650; }}
          [data-testid="stTabs"] button {{ color: var(--muted); }}
          [data-testid="stTabs"] button[aria-selected="true"] {{ color: var(--accent); }}
          [data-testid="stMetric"] {{ padding: 14px; border: 1px solid var(--line); border-radius: 12px; background: var(--surface); }}
          [data-testid="stMetricLabel"] {{ color: var(--muted); }}
          [data-testid="stMetricValue"] {{ color: var(--ink); }}
          [data-testid="stProgressBar"] > div {{ background: var(--surface-2); }}
          [data-testid="stProgressBar"] > div > div {{ background: var(--accent); }}
          [data-testid="stDataFrame"] {{ border: 1px solid var(--line); border-radius: 10px; }}
          .pp-brand {{ margin: 0 0 40px 4px; color: var(--ink); font-size: 21px; font-weight: 750; letter-spacing: -.05em; }}
          .pp-rail-note {{ position: fixed; bottom: 20px; left: 32px; color: var(--muted); font-size: 12px; }}
          .pp-header {{ display: flex; align-items: center; justify-content: space-between; gap: 16px; margin: 0; }}
          .pp-header-brand {{ color: var(--ink); font-size: 15px; font-weight: 700; }}
          .pp-header-copy {{ margin-top: 2px; color: var(--muted); font-size: 12px; }}
          .pp-time {{ color: var(--muted); font-size: 12px; white-space: nowrap; }}
          .st-key-theme-toggle div[data-testid="stButton"] > button {{ width: 44px; height: 44px; margin-left: auto; border-radius: 10px; font-size: 18px; }}
          [class*="st-key-date-arrow-"] div[data-testid="stButton"] > button {{ min-width: 44px; padding: 0; font-size: 20px; }}
          [class*="st-key-date-chip-"] div[data-testid="stButton"] > button {{ min-height: 56px; border-color: transparent; background: transparent; line-height: 1.3; }}
          [class*="st-key-date-chip-"] div[data-testid="stButton"] > button[kind="primary"] {{ border-color: transparent; border-radius: 10px; background: var(--accent-soft); color: var(--accent); }}
          [class*="st-key-date-chip-"] div[data-testid="stButton"] > button:hover {{ background: var(--surface-2); }}
          [class*="st-key-league-chip-"] {{ min-height: 44px; padding: 2px 7px; border: 1px solid var(--line); border-radius: 999px; background: var(--surface); }}
          [class*="st-key-league-chip-"] [data-testid="stHorizontalBlock"] {{ gap: 2px; }}
          [class*="st-key-league-chip-"] div[data-testid="stButton"] > button {{ min-height: 38px; padding: 0 3px; border-color: transparent; background: transparent; white-space: nowrap; }}
          [class*="st-key-league-chip-"]:has(button[kind="primary"]) {{ border-color: var(--accent); background: var(--accent-soft); }}
          [class*="st-key-league-chip-"]:has(button[kind="primary"]) div[data-testid="stButton"] > button {{ color: var(--accent); }}
          .st-key-matches-gap {{ min-height: 40px; }}
          [class*="st-key-nav-"] div[data-testid="stButton"] > button {{ justify-content: flex-start; min-height: 58px; border-color: transparent; background: transparent; text-align: left; }}
          [class*="st-key-nav-"] div[data-testid="stButton"] > button[kind="primary"] {{ border-color: transparent; background: var(--accent-soft); color: var(--accent); }}
          [class*="st-key-match-row-"] {{ padding: 10px 0; border-bottom: 1px solid var(--line); }}
          [class*="st-key-match-row-"] div[data-testid="stButton"] > button {{ min-height: 36px; border-radius: 8px; }}
          .pp-match-heading {{ margin: 22px 0 12px; }}
          .pp-empty {{ padding: 24px 0; }}
          .pp-empty strong {{ display: block; color: var(--ink); font-size: 15px; font-weight: 650; }}
          .pp-empty span {{ display: block; margin-top: 5px; color: var(--muted); }}
          .pp-team {{ display: flex; align-items: center; gap: 8px; min-width: 0; color: var(--ink); font-weight: 600; }}
          .pp-team img {{ flex: 0 0 28px; width: 28px; height: 28px; object-fit: contain; }}
          .pp-badge {{ display: inline-grid; flex: 0 0 28px; place-items: center; width: 28px; height: 28px; overflow: hidden; border: 1px solid var(--line); border-radius: 50%; background: var(--surface-2); color: var(--ink); font-size: 9px; font-weight: 700; }}
          .pp-badge img {{ width: 100%; height: 100%; object-fit: contain; }}
          .pp-prob {{ display: grid; gap: 5px; }}
          .pp-prob-values {{ display: flex; justify-content: space-between; gap: 8px; color: var(--muted); font-size: 10px; }}
          .pp-prob-values .pp-pick {{ color: var(--accent); font-weight: 700; }}
          .pp-prob-track {{ display: flex; height: 8px; overflow: hidden; border-radius: 999px; background: var(--surface-2); }}
          .pp-prob-track span {{ background: #858f9e; }}
          .pp-prob-track span.pp-segment-pick {{ background: var(--accent); }}
          .pp-detail-team {{ display: grid; justify-items: center; gap: 8px; color: var(--ink); font-weight: 650; text-align: center; }}
          .pp-detail-team .pp-badge {{ width: 44px; height: 44px; }}
          .pp-score {{ color: var(--ink); font-size: 24px; font-weight: 750; font-variant-numeric: tabular-nums; text-align: center; }}
          .pp-muted {{ color: var(--muted); font-size: 12px; }}
          .pp-pick-right {{ color: var(--hit); font-weight: 650; }}
          .pp-pick-missed {{ color: var(--miss); font-weight: 650; }}
          .pp-footer {{ margin-top: 48px; padding-top: 14px; border-top: 1px solid var(--line); color: var(--muted); font-size: 11px; }}
          @media (max-width: 1023px) {{
            [data-testid="stSidebar"] {{ min-width: 220px; max-width: 220px; }}
            [data-testid="stMainBlockContainer"] {{ padding: 20px 24px 40px; }}
          }}
          @media (max-width: 760px) {{
            [data-testid="stSidebar"] {{ min-width: 0; max-width: none; }}
            [data-testid="stMainBlockContainer"] {{ padding: 16px 16px 32px; }}
            .pp-header-copy {{ display: none; }}
            .pp-rail-note {{ display: none; }}
          }}
        </style>
        """,
        unsafe_allow_html=True,
    )


def _safe(value: str | None) -> str:
    return html.escape(value or "", quote=True)


def _badge(name: str, crest: str | None, large: bool = False) -> str:
    size_class = " pp-badge-large" if large else ""
    content = f'<img src="{_safe(crest)}" alt="">' if crest else _safe(_team_initials(name))
    return f'<span class="pp-badge{size_class}" aria-hidden="true">{content}</span>'


def _probability_bar(forecast: dict | None) -> None:
    if not forecast:
        st.caption("No forecast available.")
        return
    home, draw, away = (forecast[key] for key in ("p_home", "p_draw", "p_away"))
    pick = forecast["pick"]
    values = (home, draw, away)
    labels = (("H", "Home", home), ("D", "Draw", draw), ("A", "Away", away))
    values_html = "".join(
        f'<span class="{"pp-pick" if code == pick else ""}">{label} '
        f"<strong>{value:.0%}</strong></span>"
        for code, label, value in labels
    )
    widths_html = "".join(
        f'<span class="{"pp-segment-pick" if code == pick else ""}" '
        f'style="width:{value * 100:.2f}%"></span>'
        for code, _, value in labels
    )
    st.markdown(
        f'<div class="pp-prob" role="img" aria-label="Home {home:.0%}, Draw {draw:.0%}, Away {away:.0%}">'
        f'<div class="pp-prob-track">{widths_html}</div><div class="pp-prob-values">{values_html}</div></div>',
        unsafe_allow_html=True,
    )


def _initial_state() -> None:
    st.session_state.setdefault("page", "Matches")
    st.session_state.setdefault("match_date", datetime.now(timezone.utc).date())
    st.session_state.setdefault("selected_league", "all")
    st.session_state.setdefault("selected_match_id", None)
    st.session_state.setdefault("results_date", None)
    st.session_state.setdefault("insights_source", "live")
    st.session_state.setdefault("theme", "dark")


def _set_page(page: str) -> None:
    st.session_state.page = page


def _set_date(day: date) -> None:
    st.session_state.match_date = day
    st.session_state.selected_match_id = None


def _render_sidebar() -> None:
    with st.sidebar:
        st.markdown('<div class="pp-brand">PitchProb</div>', unsafe_allow_html=True)
        for page, icon in (("Matches", "▦"), ("Results", "▤"), ("Insights", "▥")):
            st.button(
                f"{icon}   {page}",
                key=f"nav-{page}",
                type="primary" if st.session_state.page == page else "secondary",
                use_container_width=True,
                on_click=_set_page,
                args=(page,),
            )
        st.markdown('<div class="pp-rail-note">Statistical estimates.</div>', unsafe_allow_html=True)


def _render_header() -> None:
    brand, actions = st.columns([1, 0.35], vertical_alignment="center")
    with brand:
        st.markdown(
            '<div class="pp-header"><div><div class="pp-header-brand">PitchProb</div>'
            '<div class="pp-header-copy">Statistical forecasts. A clear record.</div></div></div>',
            unsafe_allow_html=True,
        )
    with actions:
        time_col, theme_col = st.columns([1, 0.35], vertical_alignment="center")
        time_col.markdown('<div class="pp-time" style="text-align:right">Times in UTC</div>', unsafe_allow_html=True)
        theme_col.button(
            "☾" if st.session_state.theme == "dark" else "☀",
            key="theme-toggle",
            help="Switch color theme",
            on_click=_toggle_theme,
        )


def _toggle_theme() -> None:
    st.session_state.theme = "light" if st.session_state.theme == "dark" else "dark"


def _day_label(day: date, today: date) -> str:
    if day == today:
        return "Today"
    if day == today + timedelta(days=1):
        return "Tomorrow"
    return day.strftime("%a")


def _render_date_strip() -> None:
    selected = st.session_state.match_date
    today = datetime.now(timezone.utc).date()
    cells = st.columns([0.35, *([1] * 7), 0.35], vertical_alignment="center")
    with cells[0]:
        with st.container(key="date-arrow-prev"):
            st.button("‹", key="date-prev", help="Previous day", on_click=_set_date,
                      args=(selected - timedelta(days=1),))
    for offset, cell in enumerate(cells[1:8]):
        day = selected + timedelta(days=offset)
        with cell:
            with st.container(key=f"date-chip-{day.isoformat()}"):
                st.button(
                    f"{_day_label(day, today)}\n{day.strftime('%b')} {day.day}",
                    key=f"date-{day.isoformat()}",
                    type="primary" if day == selected else "secondary",
                    use_container_width=True,
                    on_click=_set_date,
                    args=(day,),
                )
    with cells[8]:
        with st.container(key="date-arrow-next"):
            st.button("›", key="date-next", help="Next day", on_click=_set_date,
                      args=(selected + timedelta(days=1),))


def _render_league_filter(fixtures: list[dict]) -> None:
    counts: dict[str, int] = {}
    for fixture in fixtures:
        counts[fixture["league"]] = counts.get(fixture["league"], 0) + 1
    choices = [("all", "All", len(fixtures), None)]
    choices.extend(
        (code, league["name"], counts.get(code, 0), league.get("emblem_url"))
        for code, league in LEAGUES.items()
    )
    columns = st.columns([0.55, 1.35, 1, 1.05, 1.2, 0.9, 1.55])
    for (code, name, count, emblem_url), column in zip(choices, columns):
        with column:
            with st.container(key=f"league-chip-{code}"):
                icon_col, label_col = st.columns([0.22, 1], vertical_alignment="center")
                if emblem_url:
                    icon_col.markdown(
                        f'<img src="{_safe(emblem_url)}" alt="" width="20" height="20" '
                        'style="object-fit:contain">',
                        unsafe_allow_html=True,
                    )
                elif code == "all":
                    icon_col.markdown(
                        '<svg viewBox="0 0 24 24" width="20" height="20" aria-hidden="true" '
                        'style="fill:none;stroke:currentColor;stroke-width:1.6">'
                        '<circle cx="12" cy="12" r="9"/><path d="m12 7 3 2-1 4h-4l-1-4 3-2zm-6 2 4 2'
                        'm8 0 4-2m-9 7 2 4m7-4-2 4"/></svg>',
                        unsafe_allow_html=True,
                    )
                label_col.button(
                    f"{name}  {count}",
                    key=f"league-{code}",
                    type="primary" if st.session_state.selected_league == code else "secondary",
                    use_container_width=True,
                    on_click=lambda selected=code: setattr(st.session_state, "selected_league", selected),
                )


def _render_match_row(match: dict) -> None:
    kickoff = datetime.fromisoformat(match["kickoff_utc"].replace("Z", "+00:00"))
    with st.container(key=f"match-row-{match['id']}"):
        time_col, teams_col, probs_col, select_col = st.columns([0.78, 1.65, 1.35, 0.5], vertical_alignment="center")
        time_col.markdown(
            f'<div><strong>{kickoff:%H:%M}</strong><br><span class="pp-muted">{kickoff:%b} {kickoff.day}</span></div>',
            unsafe_allow_html=True,
        )
        teams_col.markdown(
            f'<div class="pp-team">{_badge(match["home"], match.get("home_crest"))}'
            f'<span>{_safe(match["home"])}</span></div>'
            f'<div class="pp-team" style="margin-top:7px">{_badge(match["away"], match.get("away_crest"))}'
            f'<span>{_safe(match["away"])}</span></div>',
            unsafe_allow_html=True,
        )
        with probs_col:
            _probability_bar(match["forecast"])
        select_col.button(
            "›",
            key=f"select-match-arrow-{match['id']}",
            help="Show match details in the panel",
            type="tertiary",
            on_click=lambda selected=match["id"]: setattr(st.session_state, "selected_match_id", selected),
        )


def _render_match_detail(match: dict | None) -> None:
    with st.container(border=True):
        st.subheader("Match details")
        if match is None:
            st.caption("Select a fixture to see its match details here.")
            return
        details = load_match_details(match["id"])
        # New API returns home/away as {name, badge_url} and the details without
        # the legacy extras.context; map the two shapes so the legacy renderer works.
        detail = details
        if isinstance(detail.get("home"), dict):
            match["home"] = detail["home"].get("name", match["home"])
            match["home_crest"] = detail["home"].get("badge_url") or match.get("home_crest")
            match["away"] = detail["away"].get("name", match["away"])
            match["away_crest"] = detail["away"].get("badge_url") or match.get("away_crest")
        match["league_name"] = detail.get("league_name") or (detail.get("competition") or {}).get("name")
        extras = detail.get("extras") if isinstance(detail, dict) else None
        context = extras.get("context") if isinstance(extras, dict) else None
        if context is None:
            context = {
                "form_home": [], "form_away": [], "h2h": [],
                "season_ppg_home": None, "season_ppg_away": None, "league_gpm": None,
            }
        kickoff = datetime.fromisoformat(match["kickoff_utc"].replace("Z", "+00:00"))
        st.caption(f"{match['league_name']} · {kickoff:%a %d %b, %H:%M} UTC")
        home, middle, away = st.columns([1, 0.45, 1], vertical_alignment="center")
        home.markdown(
            f'<div class="pp-detail-team">{_badge(match["home"], match["home_crest"], True)}'
            f'<span>{_safe(match["home"])}</span></div>',
            unsafe_allow_html=True,
        )
        score = match["result"]
        middle.markdown(
            f'<div class="pp-score">{score["home_goals"]}–{score["away_goals"]}</div>'
            if score else '<div class="pp-muted" style="text-align:center">vs</div>',
            unsafe_allow_html=True,
        )
        away.markdown(
            f'<div class="pp-detail-team">{_badge(match["away"], match["away_crest"], True)}'
            f'<span>{_safe(match["away"])}</span></div>',
            unsafe_allow_html=True,
        )
        forecast = match["forecast"]
        if forecast:
            st.markdown("#### Outcome probabilities")
            _probability_bar(forecast)
            st.caption(
                f"Expected goals: {forecast['xg_home']:.2f} – {forecast['xg_away']:.2f} · "
                f"Over 2.5: {forecast['p_over25']:.0%} · BTTS: {forecast['p_btts']:.0%}"
            )
        elif match.get("note"):
            st.info(match["note"])

        overview, markets, form = st.tabs(["Overview", "Markets", "Form and H2H"])
        with overview:
            if forecast:
                metrics = st.columns(2)
                metrics[0].metric(f"{match['home']} expected goals", f"{forecast['xg_home']:.2f}")
                metrics[1].metric(f"{match['away']} expected goals", f"{forecast['xg_away']:.2f}")
                metrics[0].metric("Over 2.5 goals", f"{forecast['p_over25']:.0%}")
                metrics[1].metric("Both teams to score", f"{forecast['p_btts']:.0%}")
            else:
                st.caption(match.get("note") or "Forecast not available for this match.")
        with markets:
            if forecast:
                st.metric("Over 2.5 goals", f"{forecast['p_over25']:.0%}")
                st.metric("Both teams to score", f"{forecast['p_btts']:.0%}")
                st.caption("Only probabilities produced and stored by this model are shown.")
            else:
                st.caption("Market probabilities are not available.")
        with form:
            st.write(f"**{match['home']}**  {' · '.join(context['form_home']) or 'No recent results'}")
            st.write(f"**{match['away']}**  {' · '.join(context['form_away']) or 'No recent results'}")
            st.caption(
                f"Season points per match: {context['season_ppg_home'] if context['season_ppg_home'] is not None else '—'} – "
                f"{context['season_ppg_away'] if context['season_ppg_away'] is not None else '—'}"
            )
            st.markdown("**Head-to-head**")
            if context["h2h"]:
                for meeting in context["h2h"]:
                    st.write(
                        f"{meeting['date']} · {meeting['home']} **{meeting['score']}** {meeting['away']}"
                    )
            else:
                st.caption("No previous meetings on record.")


def _render_matches() -> None:
    st.title("Matches")
    _render_date_strip()
    selected_day = st.session_state.match_date.isoformat()
    data = load_dashboard(selected_day)
    day_fixtures = data["matches"]
    _render_league_filter(day_fixtures)
    with st.container(key="matches-gap"):
        pass
    visible = [
        item for item in day_fixtures
        if st.session_state.selected_league == "all" or item["league"] == st.session_state.selected_league
    ]
    counts: dict[str, int] = {}
    for fixture in visible:
        counts[fixture["league"]] = counts.get(fixture["league"], 0) + 1
    ordered_codes = [code for code in LEAGUES if counts.get(code)]
    selected = next((item for item in visible if item["id"] == st.session_state.selected_match_id), None)
    if selected is None and visible:
        selected = visible[0]
        st.session_state.selected_match_id = selected["id"]

    list_col, detail_col = st.columns([1.55, 0.9], gap="large")
    with list_col:
        heading, count = st.columns([1, 0.4])
        heading.subheader("Fixtures")
        count.caption(f"{len(visible)} {'match' if len(visible) == 1 else 'matches'}")
        if not visible:
            st.markdown(
                '<div class="pp-empty"><strong>No matches on this day.</strong>'
                '<span>Try tomorrow to see the next fixtures.</span></div>',
                unsafe_allow_html=True,
            )
            st.button(
                "Show tomorrow’s matches",
                key="show-tomorrow",
                type="tertiary",
                on_click=_set_date,
                args=(st.session_state.match_date + timedelta(days=1),),
            )
        for code in ordered_codes:
            league_fixtures = [item for item in visible if item["league"] == code]
            with st.expander(
                f"{LEAGUES[code]['name']} · {len(league_fixtures)} "
                f"{'match' if len(league_fixtures) == 1 else 'matches'}",
                expanded=True,
            ):
                for fixture in league_fixtures:
                    _render_match_row(fixture)
    with detail_col:
        _render_match_detail(selected)


def _render_results() -> None:
    st.title("Results")
    days = load_result_days()
    if not days:
        st.info("No graded matches are available yet.")
        return
    day_options = [item["date"] for item in days]
    default_day = st.session_state.results_date if st.session_state.results_date in day_options else day_options[0]
    result_day = st.selectbox(
        "Choose a results day",
        day_options,
        index=day_options.index(default_day),
        format_func=lambda value: f"{date.fromisoformat(value):%d %b} · "
        f"{next(item['n'] for item in days if item['date'] == value)} matches",
    )
    st.session_state.results_date = result_day
    results = load_results(result_day)
    summary = results["summary"]
    if summary["n"] == 0:
        st.info("No graded matches for this day. Choose another day to review results.")
        return
    hit_rate = summary["accuracy"] or 0
    metrics = st.columns(3)
    metrics[0].metric("Correct picks", f"{summary['hits']} / {summary['n']}")
    metrics[1].metric("Pick accuracy", f"{hit_rate:.0%}")
    metrics[2].metric("Date", date.fromisoformat(result_day).strftime("%d %b %Y"))
    st.progress(hit_rate, text="Most likely outcomes correctly predicted")
    for league in results["leagues"]:
        with st.expander(f"{league['name']} · {len(league['matches'])} matches", expanded=True):
            for match in league["matches"]:
                with st.container(border=True):
                    left, score, outcome = st.columns([2, 0.55, 1])
                    with left:
                        st.write(f"{match['home']}  vs  {match['away']}")
                        _probability_bar(match["forecast"])
                    score.markdown(
                        f'<div class="pp-score">{match["result"]["home_goals"]}–{match["result"]["away_goals"]}</div>',
                        unsafe_allow_html=True,
                    )
                    outcome.markdown(
                        '<span class="pp-pick-right">Pick right</span>' if match["pick_hit"]
                        else '<span class="pp-pick-missed">Pick missed</span>',
                        unsafe_allow_html=True,
                    )


def _render_insights() -> None:
    st.title("Insights")
    old, live = st.columns(2)
    old.button(
        "Old matches",
        key="insights-backtest",
        type="primary" if st.session_state.insights_source == "backtest" else "secondary",
        on_click=lambda: setattr(st.session_state, "insights_source", "backtest"),
        use_container_width=True,
    )
    live.button(
        "Live forecasts",
        key="insights-live",
        type="primary" if st.session_state.insights_source == "live" else "secondary",
        on_click=lambda: setattr(st.session_state, "insights_source", "live"),
        use_container_width=True,
    )
    data = load_insights(st.session_state.insights_source)
    if not data["available"]:
        st.info(data.get("note") or "Backtest results are not available.")
        return
    if data["n"] == 0:
        st.info("No graded live forecasts yet. Insights appear after forecast results are recorded.")
        return
    st.caption(
        f"{data['n']} graded live {'forecast' if data['n'] == 1 else 'forecasts'}. "
        "These summaries describe recorded predictions, not future outcomes."
    )
    if data["n"] < 100:
        st.warning("Early sample: fewer than 100 graded matches. Treat these patterns as provisional.")
    if data["confidence"]:
        st.subheader("Pick accuracy by confidence")
        confidence = data["confidence"]
        chart = {
            f"{band['from']:.0%}–{band['to']:.0%}": {
                "Observed pick accuracy": band["hit_rate"],
                "Average confidence": band["confidence"],
            }
            for band in confidence
        }
        st.bar_chart(chart)
        st.dataframe(
            [{
                "Confidence band": f"{band['from']:.0%}–{band['to']:.0%}",
                "Matches": band["n"],
                "Pick accuracy": f"{band['hit_rate']:.0%}",
                "Average confidence": f"{band['confidence']:.0%}",
            } for band in confidence],
            hide_index=True,
            use_container_width=True,
        )
    if data["thresholds"]:
        st.subheader("Does a bigger lead mean a safer pick?")
        st.caption("Lead is the top probability minus the next-highest probability.")
        st.dataframe(
            [{
                "Probability lead": f"{band['from']:.0%}–{band['to']:.0%}",
                "Matches": band["n"],
                "Pick accuracy": f"{band['hit_rate']:.0%}",
            } for band in data["thresholds"]],
            hide_index=True,
            use_container_width=True,
        )
    if data["comparison"]:
        st.subheader("Model comparison")
        st.dataframe(
            [{
                "Forecast source": item["model"],
                "Matches": item["n"],
                "Log loss": f"{item['logloss']:.3f}",
                "Top picks right": "—" if item["pick_rate"] is None else f"{item['pick_rate']:.0%}",
            } for item in data["comparison"]],
            hide_index=True,
            use_container_width=True,
        )
    if data["leagues"]:
        st.subheader("Goals per match by league")
        st.dataframe(
            [{
                "League": league["league_name"],
                "Matches": league["n"],
                "Goals per match": f"{league['goals_per_match']:.2f}",
            } for league in data["leagues"]],
            hide_index=True,
            use_container_width=True,
        )


_initial_state()
_styles()
_render_sidebar()

if not DB_PATH.exists():
    st.error("The match database is missing. Run the daily model refresh workflow and redeploy.")
    st.stop()

_render_header()
if st.session_state.page == "Matches":
    _render_matches()
elif st.session_state.page == "Results":
    _render_results()
else:
    _render_insights()

st.markdown(
    '<div class="pp-footer">Times in UTC · Forecasts are statistical estimates, not betting advice. 18+ only.</div>',
    unsafe_allow_html=True,
)
