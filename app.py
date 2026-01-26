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
# FAST YEAR BOUNDARY DETECTOR (CACHED)
# ============================================================

@st.cache_data
def detect_year_boundaries(last_page):

    token = Path("token.txt").read_text().strip()

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0"
    }

    # smart jumps (super fast)
    probe_pages = [
        1, 50, 100, 200, 400, 800,
        1200, 1600, 2000, 2500, last_page
    ]

    year_map = {}

    for page in probe_pages:

        r = requests.get(
            f"https://api.djdownload.me/tracks?page={page}",
            headers=headers,
            timeout=15
        )

        tracks = r.json().get("tracks", [])

        if not tracks:
            continue

        release = tracks[0].get("release") or tracks[0].get("release_date")

        if not release:
            continue

        year = release.split("-")[0]

        if year not in year_map:
            year_map[year] = page

    return year_map


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
# INPUT PATHS
# ============================================================

examples_folder = st.text_input(
    "📁 Examples folder (MP3)",
    "/Users/ludo_cisco/Desktop/examples_song",
)

output_folder = st.text_input(
    "📦 Shortlist output folder",
    "/Users/ludo_cisco/Desktop/shortlist",
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
# YEARS
# ============================================================

st.subheader("📅 Release years")

AVAILABLE_YEARS = ["2026", "2025", "2024", "Older"]

selected_years = []
cols = st.columns(4)

for i, year in enumerate(AVAILABLE_YEARS):
    if cols[i].checkbox(year, value=(year in ["2026", "2025"])):
        selected_years.append(year)

st.caption(
    f"Selected years: {', '.join(selected_years) if selected_years else 'None'}"
)

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

st.divider()

# ============================================================
# AUTO PAGE RANGE FROM REAL DATA
# ============================================================

st.subheader("📄 Page range to scan")

if last_page:
    year_boundaries = detect_year_boundaries(last_page)
else:
    year_boundaries = {}

auto_start = None
auto_end = None

for year in selected_years:

    if year == "Older":
        # everything older than the oldest detected year
        if year_boundaries:
            oldest_page = max(year_boundaries.values())
            auto_start = oldest_page if auto_start is None else min(auto_start, oldest_page)
            auto_end = last_page if auto_end is None else max(auto_end, last_page)

    elif year in year_boundaries:
        p = year_boundaries[year]

        auto_start = p if auto_start is None else min(auto_start, p)
        auto_end = p if auto_end is None else max(auto_end, p)

# fallback if nothing selected
if auto_start is None:
    auto_start = 1

if auto_end is None:
    auto_end = last_page if last_page else 1

# ============================================================
# SLIDER (AUTO-SET BUT MANUAL TUNABLE)
# ============================================================

start_page, end_page = st.slider(
    "Select page range",
    min_value=1,
    max_value=last_page if last_page else 1,
    value=(int(auto_start), int(auto_end)),
)

st.caption(f"Scanning pages {start_page} → {end_page}")

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

    if not selected_years:
        st.error("Select at least one year")
        st.stop()

    if end_page < start_page:
        st.error("End page must be >= start page")
        st.stop()

    with st.spinner("Analyzing examples and scanning DJDownload…"):
        try:
            result = build_shortlist_from_djdownload(
                examples_folder=ex_path,
                output_folder=out_path,
                genres=selected_genres,
                selected_years=selected_years,
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

