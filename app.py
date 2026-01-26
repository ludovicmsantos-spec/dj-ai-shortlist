# app.py (cloud-ready)

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
# UPLOAD EXAMPLES
# ============================================================

st.subheader("📁 Upload example tracks")

uploaded_files = st.file_uploader(
    "Upload MP3/WAV examples",
    type=["mp3", "wav"],
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

st.subheader("📅 Years to scan")

col1, col2, col3 = st.columns(3)

scan_2026 = col1.checkbox("2026", value=True)
scan_2025 = col2.checkbox("2025", value=True)
scan_2024 = col3.checkbox("2024", value=False)

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
# PAGE RANGE AUTO
# ============================================================

page_ranges = []

if scan_2026:
    page_ranges.append((1, 80))

if scan_2025:
    page_ranges.append((100, 1600))

if scan_2024 and last_page:
    page_ranges.append((2000, last_page))

if page_ranges:
    start_page = min(r[0] for r in page_ranges)
    end_page = max(r[1] for r in page_ranges)
else:
    start_page = None
    end_page = None

st.subheader("📄 Auto page range")

if start_page and end_page:
    st.info(f"Scanning pages {start_page} → {end_page}")
else:
    st.warning("No years selected")

st.divider()

# ============================================================
# RUN
# ============================================================

if st.button("🚀 Build shortlist", use_container_width=True):

    if not uploaded_files:
        st.error("Upload at least one example track")
        st.stop()

    if not selected_genres:
        st.error("Select at least one genre")
        st.stop()

    if not start_page or not end_page:
        st.error("Select at least one year")
        st.stop()

    # Create temp folders
    examples_dir = Path(tempfile.mkdtemp())
    output_dir = Path(tempfile.mkdtemp())

    # Save uploaded examples
    for file in uploaded_files:
        dest = examples_dir / file.name
        with open(dest, "wb") as f:
            f.write(file.read())

    with st.spinner("Analyzing examples and scanning DJDownload…"):

        try:
            result = build_shortlist_from_djdownload(
                examples_folder=examples_dir,
                output_folder=output_dir,
                genres=selected_genres,
                selected_years=[],
                threshold=threshold,
                start_page=start_page,
                end_page=end_page,
            )

        except Exception as e:
            st.error("❌ Error during processing")
            st.exception(e)
            shutil.rmtree(examples_dir, ignore_errors=True)
            shutil.rmtree(output_dir, ignore_errors=True)
            st.stop()

    st.success("✅ Shortlist completed")

    st.subheader("🎯 Result")
    st.write(f"Tracks kept: **{result['kept']}**")

    if result["tracks"]:
        st.json(result["tracks"])
    else:
        st.info("No tracks matched the current threshold.")

    # ============================================================
    # ZIP OUTPUT
    # ============================================================

    zip_path = output_dir.parent / "shortlist.zip"

    with zipfile.ZipFile(zip_path, "w", zipfile.ZIP_DEFLATED) as zipf:
        for file in output_dir.rglob("*"):
            if file.is_file():
                zipf.write(file, arcname=file.relative_to(output_dir))

    with open(zip_path, "rb") as f:
        st.download_button(
            "📥 Download shortlist (ZIP)",
            data=f,
            file_name="dj_ai_shortlist.zip",
            mime="application/zip"
        )



