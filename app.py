import streamlit as st
from pathlib import Path
import requests
import math

from engine import build_shortlist_from_djdownload

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="DJ AI Shortlist",
    layout="centered",
)

# ============================================================
# FETCH LAST PAGE
# ============================================================

def get_last_page():
    try:
        token = Path("token.txt").read_text().strip()

        r = requests.get(
            "https://api.djdownload.me/tracks?page=1",
            headers={
                "Authorization": f"Bearer {token}",
                "User-Agent": "Mozilla/5.0"
            },
            timeout=20
        )

        data = r.json()
        total = data.get("total", 0)
        limit = data.get("limit", 1)

        return math.ceil(total / limit)

    except Exception:
        return None


# ============================================================
# HEADER
# ============================================================

st.title("🎧 DJ AI Shortlist")

last_page = get_last_page()

if last_page:
    st.caption(f"📄 Latest DJDownload page: {last_page}")
else:
    st.caption("📄 Latest DJDownload page: unavailable")

st.caption("Example-based shortlisting using DJDownload previews")

st.divider()

# ============================================================
# FOLDER INPUT (cloud safe)
# ============================================================

examples_folder = st.text_input(
    "📁 Examples folder (MP3)",
    "examples",
)

output_folder = st.text_input(
    "📦 Shortlist output folder",
    "shortlist",
)

# ============================================================
# GENRES
# ============================================================

st.subheader("🎼 Genres")

AVAILABLE_GENRES = [
    "Afro House",
    "Melodic House",
    "Organic House",
    "Deep House",
    "Progressive House",
    "House",
    "Tech House",
    "Drum & Bass",
    "Techno",
]

selected_genres = []
cols = st.columns(3)

for i, genre in enumerate(AVAILABLE_GENRES):
    if cols[i % 3].checkbox(genre, value=(genre == "Afro House")):
        selected_genres.append(genre)

st.divider()

# ============================================================
# SIMILARITY
# ============================================================

threshold = st.slider(
    "🎯 Similarity threshold",
    min_value=0.20,
    max_value=0.90,
    value=0.70,
    step=0.05,
)

# ============================================================
# PAGE RANGE SLIDER (BACK!)
# ============================================================

st.subheader("📄 Page range to scan")

if last_page:
    start_page, end_page = st.slider(
        "Select page range",
        min_value=1,
        max_value=last_page,
        value=(1, min(100, last_page)),
        step=1,
    )

    st.info(f"Scanning pages {start_page} → {end_page}")

else:
    st.warning("Unable to fetch DJDownload page count")
    start_page = end_page = None

st.divider()

# ============================================================
# RUN
# ============================================================

if st.button("🚀 Build shortlist", use_container_width=True):

    ex_path = Path(examples_folder)
    out_path = Path(output_folder)

    if not ex_path.exists():
        st.error("Examples folder does not exist")
        st.stop()

    if not selected_genres:
        st.error("Select at least one genre")
        st.stop()

    if not start_page or not end_page:
        st.error("Invalid page range")
        st.stop()

    with st.spinner("Analyzing examples and scanning DJDownload…"):
        try:
            result = build_shortlist_from_djdownload(
                examples_folder=ex_path,
                output_folder=out_path,
                genres=selected_genres,
                selected_years=[],   # no longer used
                threshold=threshold,
                start_page=start_page,
                end_page=end_page,
            )

        except Exception as e:
            st.error("❌ Error during processing")
            st.exception(e)
            st.stop()

    st.success("✅ Shortlist completed")

    st.subheader("🎯 Result")
    st.write(f"Tracks kept: **{result['kept']}**")

    if result["tracks"]:
        st.json(result["tracks"])
    else:
        st.info("No tracks matched the current threshold.")




