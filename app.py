import streamlit as st
from pathlib import Path
import requests
import math
import tempfile
import zipfile
import shutil

from engine import build_shortlist_from_djdownload

# ============================================================
# PAGE CONFIG
# ============================================================

st.set_page_config(
    page_title="DJ AI Shortlist",
    layout="centered",
)

# ============================================================
# SESSION STATE
# ============================================================

if "stop_requested" not in st.session_state:
    st.session_state.stop_requested = False

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
# FAST YEAR BOUNDARY DETECTOR
# ============================================================

@st.cache_data
def detect_year_boundaries(last_page):

    token = Path("token.txt").read_text().strip()

    headers = {
        "Authorization": f"Bearer {token}",
        "User-Agent": "Mozilla/5.0"
    }

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
# UPLOAD EXAMPLES
# ============================================================

st.subheader("📁 Upload example MP3 tracks")

uploaded_files = st.file_uploader(
    "Upload MP3 examples",
    type=["mp3"],
    accept_multiple_files=True
)

st.divider()

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
    0.20,
    0.90,
    0.70,
    0.05
)

st.divider()

# ============================================================
# AUTO PAGE RANGE
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
        if year_boundaries:
            oldest_page = max(year_boundaries.values())
            auto_start = oldest_page if auto_start is None else min(auto_start, oldest_page)
            auto_end = last_page if auto_end is None else max(auto_end, last_page)

    elif year in year_boundaries:
        p = year_boundaries[year]
        auto_start = p if auto_start is None else min(auto_start, p)
        auto_end = p if auto_end is None else max(auto_end, p)

if auto_start is None:
    auto_start = 1

if auto_end is None:
    auto_end = last_page if last_page else 1

# ============================================================
# SLIDER
# ============================================================

start_page, end_page = st.slider(
    "Select page range",
    1,
    last_page if last_page else 1,
    (int(auto_start), int(auto_end)),
    step=1
)

st.caption(f"Scanning pages {start_page} → {end_page}")

st.divider()

# ============================================================
# STOP BUTTON
# ============================================================

if st.button("🛑 Stop scanning"):
    st.session_state.stop_requested = True

# ============================================================
# PROGRESS UI
# ============================================================

progress_bar = st.progress(0)
status_text = st.empty()
kept_text = st.empty()

def progress_callback(current_page, total_pages, kept_count):
    progress = current_page / total_pages
    progress_bar.progress(progress)

    status_text.info(f"📄 Page {current_page} / {total_pages}")
    kept_text.success(f"🎧 Tracks kept: {kept_count}")

# ============================================================
# RUN
# ============================================================

if st.button("🚀 Build shortlist", use_container_width=True):

    st.session_state.stop_requested = False

    if not uploaded_files:
        st.error("Upload at least one MP3 example")
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

    temp_examples = Path(tempfile.mkdtemp())
    temp_output = Path(tempfile.mkdtemp())

    for f in uploaded_files:
        with open(temp_examples / f.name, "wb") as out:
            out.write(f.read())

    with st.spinner("Analyzing examples and scanning DJDownload…"):

        try:
            result = build_shortlist_from_djdownload(
                examples_folder=temp_examples,
                output_folder=temp_output,
                genres=selected_genres,
                selected_years=selected_years,
                threshold=threshold,
                start_page=start_page,
                end_page=end_page,
                progress_callback=progress_callback,
                stop_flag=lambda: st.session_state.stop_requested
            )

        except Exception as e:
            st.error("❌ Error during processing")
            st.exception(e)
            st.stop()

    st.success("✅ Shortlist completed")
    st.write(f"Tracks kept: **{result['kept']}**")

    # ============================================================
    # ZIP DOWNLOAD
    # ============================================================

    zip_path = Path(tempfile.gettempdir()) / "shortlist.zip"

    with zipfile.ZipFile(zip_path, "w") as zipf:
        for file in temp_output.rglob("*"):
            if file.is_file():
                zipf.write(file, arcname=file.name)

    with open(zip_path, "rb") as f:
        st.download_button(
            "📥 Download shortlist (ZIP)",
            f,
            "shortlist.zip",
            mime="application/zip",
            use_container_width=True
        )

    shutil.rmtree(temp_examples, ignore_errors=True)
    shutil.rmtree(temp_output, ignore_errors=True)








