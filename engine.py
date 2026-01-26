# engine.py
import shutil
import tempfile
from pathlib import Path
import requests

import librosa
import numpy as np

# ============================================================
# CONFIG
# ============================================================

DJDOWNLOAD_API = "https://api.djdownload.me"

CACHE_ROOT = Path.home() / ".dj_ai_cache"
CACHE_ROOT.mkdir(parents=True, exist_ok=True)

SUPPORTED_EXT = (".mp3", ".wav", ".aiff")

HEADERS_BASE = {
    "User-Agent": "Mozilla/5.0",
    "Referer": "https://djdownload.me/",
}

# ============================================================
# AUTH
# ============================================================

def load_token() -> str:
    token_file = Path(__file__).parent / "token.txt"
    if not token_file.exists():
        raise RuntimeError("token.txt not found")
    return token_file.read_text().strip()


def api_headers():
    return {
        **HEADERS_BASE,
        "Authorization": f"Bearer {load_token()}",
    }

# ============================================================
# ARTIST EXTRACTION (WORKING + CLEAN)
# ============================================================

def extract_artist_from_track(track: dict) -> str:
    artists = track.get("artists")

    if isinstance(artists, list):
        names = [a["name"] for a in artists if isinstance(a, dict) and "name" in a]
        if names:
            return ", ".join(names)

    return ""

# ============================================================
# AUDIO ANALYSIS (SMART)
# ============================================================

def analyze_track(audio_path: Path) -> dict | None:
    try:
        y, sr = librosa.load(audio_path, mono=True, duration=90)

        # BPM
        tempo, _ = librosa.beat.beat_track(y=y, sr=sr)

        # Rhythm strength
        onset_env = librosa.onset.onset_strength(y=y, sr=sr)
        rhythm = float(np.mean(onset_env))

        # Key
        chroma = librosa.feature.chroma_stft(y=y, sr=sr)
        key_idx = int(np.argmax(chroma.mean(axis=1)))

        KEYS = ["C","C#","D","D#","E","F","F#","G","G#","A","A#","B"]

        # Brightness
        centroid = librosa.feature.spectral_centroid(y=y, sr=sr)
        brightness = float(np.mean(centroid))

        # Bass energy (20–150Hz)
        stft = np.abs(librosa.stft(y))
        freqs = librosa.fft_frequencies(sr=sr)

        bass_mask = (freqs >= 20) & (freqs <= 150)
        bass_energy = float(np.mean(stft[bass_mask]))

        return {
            "bpm": float(tempo),
            "rhythm": rhythm,
            "key": KEYS[key_idx],
            "brightness": brightness,
            "bass": bass_energy,
        }

    except Exception as e:
        print(f"[WARN] Track skipped: {audio_path.name} → {e}")
        return None

# ============================================================
# EXAMPLE PROFILE
# ============================================================

def analyze_examples_folder(folder: Path) -> dict:
    features = []

    for file in folder.iterdir():
        if file.suffix.lower() in SUPPORTED_EXT:
            f = analyze_track(file)
            if f:
                features.append(f)

    if not features:
        raise RuntimeError("No valid example tracks found")

    return {
        "bpm": float(np.mean([f["bpm"] for f in features])),
        "rhythm": float(np.mean([f["rhythm"] for f in features])),
        "brightness": float(np.mean([f["brightness"] for f in features])),
        "bass": float(np.mean([f["bass"] for f in features])),
        "key": max(
            set([f["key"] for f in features]),
            key=[f["key"] for f in features].count
        ),
        "count": len(features),
    }

# ============================================================
# DJDOWNLOAD API
# ============================================================

def fetch_tracks(page: int) -> list[dict]:
    url = f"{DJDOWNLOAD_API}/tracks?page={page}"
    r = requests.get(url, headers=api_headers(), timeout=30)
    r.raise_for_status()
    return r.json().get("tracks", [])

# ============================================================
# STREAM MP3 PREVIEW
# ============================================================

def stream_track(stream_url: str) -> Path:
    tmp = tempfile.NamedTemporaryFile(
        suffix=".mp3",
        delete=False,
        dir=CACHE_ROOT
    )

    with requests.get(stream_url, headers=api_headers(), stream=True) as r:
        r.raise_for_status()
        for chunk in r.iter_content(chunk_size=8192):
            if chunk:
                tmp.write(chunk)

    tmp.close()
    return Path(tmp.name)

# ============================================================
# GENRE WEIGHTS (BALANCED)
# ============================================================

GENRE_WEIGHTS = {
    "Afro House":        dict(bpm=0.20, rhythm=0.35, bass=0.25, brightness=0.10, key=0.10),
    "Progressive House":dict(bpm=0.20, rhythm=0.20, bass=0.10, brightness=0.30, key=0.20),
    "Melodic House":    dict(bpm=0.20, rhythm=0.20, bass=0.10, brightness=0.30, key=0.20),
    "Tech House":       dict(bpm=0.30, rhythm=0.35, bass=0.20, brightness=0.05, key=0.10),
    "Drum & Bass":      dict(bpm=0.40, rhythm=0.30, bass=0.20, brightness=0.05, key=0.05),
    "Techno":           dict(bpm=0.30, rhythm=0.40, bass=0.20, brightness=0.05, key=0.05),
}

DEFAULT_WEIGHTS = dict(
    bpm=0.25,
    rhythm=0.30,
    bass=0.20,
    brightness=0.15,
    key=0.10
)

# ============================================================
# SIMILARITY (GENRE AWARE)
# ============================================================

def similarity_score(example: dict, candidate: dict, genre: str) -> float:

    w = GENRE_WEIGHTS.get(genre, DEFAULT_WEIGHTS)

    bpm_score = max(0.0, 1 - abs(example["bpm"] - candidate["bpm"]) / 30)
    rhythm_score = max(0.0, 1 - abs(example["rhythm"] - candidate["rhythm"]) / 1.2)
    brightness_score = max(0.0, 1 - abs(example["brightness"] - candidate["brightness"]) / 2500)
    bass_score = max(
        0.0,
        1 - abs(example["bass"] - candidate["bass"]) / (example["bass"] + 1e-6)
    )
    key_score = 1.0 if example["key"] == candidate["key"] else 0.0

    return (
        w["bpm"] * bpm_score +
        w["rhythm"] * rhythm_score +
        w["bass"] * bass_score +
        w["brightness"] * brightness_score +
        w["key"] * key_score
    )

# ============================================================
# MAIN CONTROLLER
# ============================================================

def build_shortlist_from_djdownload(
    examples_folder: Path,
    output_folder: Path,
    genres: list[str],
    selected_years: list[str],
    threshold: float,
    start_page: int,
    end_page: int,
):

    example_profile = analyze_examples_folder(examples_folder)
    print(f"✅ Example profile built from {example_profile['count']} tracks")

    kept = []

    for page in range(start_page, end_page + 1):
        print(f"📄 Scanning page {page}")

        tracks = fetch_tracks(page)

        for track in tracks:

            genre = track.get("genre")

            if genres and genre not in genres:
                continue

            # ================= YEAR FILTER =================

            release_date = track.get("release_date")

            if release_date:
                year = release_date.split("-")[0]

                if "Older" not in selected_years and year not in selected_years:
                    continue

            # =================================================

            if "url" not in track or "title" not in track:
                continue

            audio_path = stream_track(track["url"])
            features = analyze_track(audio_path)

            if not features:
                audio_path.unlink(missing_ok=True)
                continue

            score = similarity_score(example_profile, features, genre)

            if score >= threshold:

                genre_dir = output_folder / genre.replace(" ", "_")
                genre_dir.mkdir(parents=True, exist_ok=True)

                artist = extract_artist_from_track(track)
                title = track["title"].strip()

                filename = f"{artist} - {title}.mp3" if artist else f"{title}.mp3"
                filename = filename.replace("/", "_")

                shutil.move(audio_path, genre_dir / filename)

                kept.append({
                    "artist": artist,
                    "title": title,
                    "genre": genre,
                    "score": round(score, 3),
                })

                print(f"✅ MATCH: {artist} - {title} ({score:.2f})")

            else:
                audio_path.unlink(missing_ok=True)

    return {
        "kept": len(kept),
        "tracks": kept,
    }

