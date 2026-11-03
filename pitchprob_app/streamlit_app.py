"""Streamlit entry point for the hosted PitchProb dashboard."""
import sys
from pathlib import Path

import pandas as pd
import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app import _fixture_days, _ledger, _upcoming
from config import LEAGUES, MODELS_DIR
from db import DB_PATH, connect


st.set_page_config(
    page_title="PitchProb",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="expanded",
)


@st.cache_data(ttl=300, show_spinner="Loading fixtures and forecasts...")
def load_dashboard() -> tuple[list[dict], dict, dict[str, str | None]]:
    with connect() as conn:
        days = _fixture_days(_upcoming(conn))
        ledger = _ledger(conn)
    model_stamps = {}
    for code in LEAGUES:
        stamp = MODELS_DIR / f"{code}.trained_at"
        model_stamps[code] = stamp.read_text(encoding="utf-8").strip() if stamp.exists() else None
    return days, ledger, model_stamps


def _percent(value: float | None) -> str:
    return "—" if value is None else f"{value:.0%}"


def _render_fixture(fixture: dict) -> None:
    home = fixture["home"] or fixture["home_fd"]
    away = fixture["away"] or fixture["away_fd"]

    with st.container(border=True):
        time_col, home_col, draw_col, away_col = st.columns([1, 3, 2, 3])
        time_col.caption(f"{fixture['kickoff_utc'][11:16]} UTC")
        time_col.caption(fixture["kickoff_date"])
        home_col.markdown(f"**{home}**")
        home_col.caption(f"Home win · {_percent(fixture['p_home'])}")
        draw_col.markdown(f"**Draw · {_percent(fixture['p_draw'])}**")
        away_col.markdown(f"**{away}**")
        away_col.caption(f"Away win · {_percent(fixture['p_away'])}")

        if fixture["p_home"] is None:
            st.info(fixture["note"])
        else:
            stat_cols = st.columns(4)
            stat_cols[0].metric("Over 2.5", _percent(fixture["p_over25"]))
            stat_cols[1].metric("Both teams score", _percent(fixture["p_btts"]))
            stat_cols[2].metric("Expected home goals", f"{fixture['xg_home']:.2f}")
            stat_cols[3].metric("Expected away goals", f"{fixture['xg_away']:.2f}")

        with st.expander("Recent form and head-to-head"):
            form_cols = st.columns(2)
            home_form = " · ".join(fixture["home_form"]) or "No recent results"
            away_form = " · ".join(fixture["away_form"]) or "No recent results"
            form_cols[0].write(f"**{home}:** {home_form}")
            form_cols[1].write(f"**{away}:** {away_form}")
            meetings = fixture["h2h"]
            if meetings:
                st.dataframe(
                    pd.DataFrame([
                        {
                            "Date": match["match_date"],
                            "Home": match["home"],
                            "Score": f"{match['home_goals']}–{match['away_goals']}",
                            "Away": match["away"],
                            "Result for this fixture's home team": match["fixture_outcome"],
                        }
                        for match in meetings
                    ]),
                    hide_index=True,
                    use_container_width=True,
                )
            else:
                st.caption("No previous meetings found in the results history.")


def _render_track_record(ledger: dict) -> None:
    st.subheader("Track record")
    summary = ledger["summary"]
    if not summary["n"]:
        st.info("No matches graded yet. The daily refresh grades predictions when results become available.")
        return

    metrics = st.columns(4)
    metrics[0].metric("Graded matches", summary["n"])
    metrics[1].metric("Model log loss", f"{summary['ll']:.3f}" if summary["ll"] is not None else "—")
    metrics[2].metric("Baseline log loss", f"{summary['base_ll']:.3f}" if summary["base_ll"] is not None else "—")
    metrics[3].metric("Correct top pick", _percent(summary["pick_rate"]))

    st.caption("Recent 1X2 forecasts and final scores. Lower log loss is better.")
    st.dataframe(
        pd.DataFrame([
            {
                "Date": match["kickoff_utc"][:10],
                "League": LEAGUES.get(match["league"], {}).get("name", match["league"]),
                "Match": f"{match['home']} vs {match['away']}",
                "Score": f"{match['home_goals']}–{match['away_goals']}",
                "Result": match["outcome"],
                "Home": _percent(match["p_home"]),
                "Draw": _percent(match["p_draw"]),
                "Away": _percent(match["p_away"]),
                "Log loss": f"{match['logloss_1x2']:.3f}",
            }
            for match in ledger["recent"]
        ]),
        hide_index=True,
        use_container_width=True,
    )


st.title("PitchProb")
st.caption("Football match forecasts and their measured results · Times shown in UTC")

if not DB_PATH.exists():
    st.error("The match database is missing. Run the daily model refresh workflow and redeploy.")
    st.stop()

fixture_days, ledger, model_stamps = load_dashboard()
trained_models = sum(stamp is not None for stamp in model_stamps.values())
st.caption(f"{trained_models} of {len(LEAGUES)} league models available")

with st.sidebar:
    st.header("Fixtures")
    day_labels = [
        f"{day['label']} · {day['month']} {day['day']}"
        for day in fixture_days
    ]
    selected_day_label = st.radio("Match day", day_labels, label_visibility="collapsed")
    selected_day = fixture_days[day_labels.index(selected_day_label)]
    selected_leagues = st.multiselect(
        "Competitions",
        options=list(LEAGUES),
        default=list(LEAGUES),
        format_func=lambda code: LEAGUES[code]["name"],
    )
    st.divider()
    st.caption("Forecasts are statistical estimates, not betting advice.")

st.subheader(f"Upcoming fixtures · {selected_day['month']} {selected_day['day']}")
shown = 0
for group in selected_day["leagues"]:
    if group["code"] not in selected_leagues:
        continue
    st.markdown(f"### {group['name']} · {len(group['fixtures'])} matches")
    for fixture in group["fixtures"]:
        _render_fixture(fixture)
        shown += 1
if not shown:
    st.info("No fixtures for the selected day and competitions.")

st.divider()
_render_track_record(ledger)
