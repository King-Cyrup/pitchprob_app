"""Streamlit entry point that renders the canonical PitchProb web template."""
import sys
from pathlib import Path

import streamlit as st

APP_DIR = Path(__file__).resolve().parent
if str(APP_DIR) not in sys.path:
    sys.path.insert(0, str(APP_DIR))

from app import _fixture_days, _ledger, _upcoming, templates
from config import LEAGUES
from db import DB_PATH, connect


st.set_page_config(
    page_title="PitchProb",
    page_icon="⚽",
    layout="wide",
    initial_sidebar_state="collapsed",
)


@st.cache_data(ttl=300, show_spinner="Loading fixtures and forecasts...")
def load_dashboard() -> tuple[list[dict], dict]:
    with connect() as conn:
        fixture_days = _fixture_days(_upcoming(conn))
        ledger = _ledger(conn)
    return fixture_days, ledger


def render_dashboard() -> str:
    fixture_days, ledger = load_dashboard()
    template = templates.env.get_template("index.html")
    return template.render(fixture_days=fixture_days, ledger=ledger, leagues=LEAGUES)


st.html("""
<style>
  .stApp,
  [data-testid="stAppViewContainer"] {
    background: #070b13;
  }
  [data-testid="stHeader"],
  .stAppHeader,
  [data-testid="stToolbar"],
  [data-testid="stStatusWidget"],
  footer {
    display: none !important;
  }
  [data-testid="stMain"] {
    background: #070b13;
    padding: 0 !important;
  }
  [data-testid="stMainBlockContainer"] {
    max-width: none !important;
    padding: 0 !important;
  }
</style>
""")

if not DB_PATH.exists():
    st.error("The match database is missing. Run the daily model refresh workflow and redeploy.")
    st.stop()

st.html(render_dashboard(), unsafe_allow_javascript=True)
