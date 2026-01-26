import streamlit as st
from pathlib import Path
import requests
import math
import tempfile
import zipfile
import shutil
from datetime import datetime

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
# FILE UPLOAD
# ============================================================

st.subheader("📁 Upload example tracks (MP3)")

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

st.subheader("📅 Years to include")

col1, col2, col3 = st.columns(3)

scan_2026 = col1.checkbox("2026", value=True)
scan_2025 = col2.checkbox("2025", value=True)
scan_2024 = col3.checkbox("2024", value=False)

selected_years = []

if scan_2026:
    selected_years.append(2026)
if scan_2025:
    selected_years.append(2025)
if scan_2024:
    selected_years.append(2024)

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

# ============================================================
# PAGE RANGE
# ============================================================

st.subheader("📄 Page range to scan")

if last_page:
    start_page, end_page = st.slider(
        "Select page range",
        1,
        last_page,
        (1, min(100, last_page)),
        step=1
    )

    st.info(f"Scanning pages {start_page} → {end_page}")
else:
    start_page = end_page = None
    st.warning("Page count unavailable")

st.divider()

# ============================================================
# RUN
# ============================================================

if st.button("🚀 Build shortlist", use_container_width=True):

    if not uploaded_files:
        st.error("Upload at least one MP3 example")
        st.stop()

    if not selected_genres:
        st.error("Select at least one genre")
        st.stop()

    if not selected_years:
        st.error("Select at least one year")
        st.stop()

    if not start_page or not end_page:
        st.error("Invalid page range")
        st.stop()

    temp_examples = Path(tempfile.mkdtemp())
    temp_output = Path(tempfile.mkdtemp())

    for f in uploaded_files:
        with open(temp_examples / f.name, "wb") as out:
            out.write(f.read())

    with st.spinner("Scanning DJDownload…"):
        try:
            result = build_shortlist_from_djdownload(
                examples_folder=temp_examples,
                output_folder=temp_output,
                genres=selected_genres,
                selected_years=selected_years,
                threshold=threshold,
                start_page=start_page,
                end_page=end_page,
            )
        except Exception as e:
            st.error("Processing error")
            st.exception(e)
            st.stop()

    st.success("✅ Shortlist completed")
    st.write(f"Tracks kept: **{result['kept']}**")

    # ZIP OUTPUT
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






