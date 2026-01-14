import os
import streamlit as st
import dropbox
import pandas as pd
from dropbox.exceptions import ApiError


# -----------------------------------------------------------------------------
# 0) Page config (must be the first Streamlit call)
# -----------------------------------------------------------------------------
st.set_page_config(
    page_title="Song Submission",
    layout="centered",
)


# -----------------------------------------------------------------------------
# 1) Dropbox client + paths
# -----------------------------------------------------------------------------
dbx = dropbox.Dropbox(
    app_key=st.secrets["DROPBOX_APP_KEY"],
    app_secret=st.secrets["DROPBOX_APP_SECRET"],
    oauth2_refresh_token=st.secrets["DROPBOX_REFRESH_TOKEN"],
)

LOCAL_TSV_PATH = "song_submissions.tsv"
REMOTE_TSV_PATH = st.secrets["DROPBOX_PATH"]  # e.g. "/song_submissions.tsv"

COLUMNS = ["Name", "Song1", "Song2"]


# -----------------------------------------------------------------------------
# 2) Dropbox helpers (TSV)
# -----------------------------------------------------------------------------
def download_from_dropbox(local_file: str = LOCAL_TSV_PATH) -> bool:
    """Download TSV from Dropbox to local file. Returns True if successful."""
    try:
        _md, res = dbx.files_download(REMOTE_TSV_PATH)
    except ApiError:
        # File not found yet -> treat as first run
        return False
    except Exception as e:
        st.warning(f"Could not download TSV from Dropbox: {e}")
        return False

    with open(local_file, "wb") as f:
        f.write(res.content)
    return True


def upload_to_dropbox(local_file: str = LOCAL_TSV_PATH) -> bool:
    """Upload local TSV to Dropbox at REMOTE_TSV_PATH."""
    try:
        with open(local_file, "rb") as f:
            dbx.files_upload(
                f.read(),
                REMOTE_TSV_PATH,
                mode=dropbox.files.WriteMode("overwrite"),
            )
        return True
    except Exception as e:
        st.warning(f"Could not upload TSV to Dropbox: {e}")
        return False


# -----------------------------------------------------------------------------
# 3) Local TSV helpers
# -----------------------------------------------------------------------------
def load_tsv(local_file: str = LOCAL_TSV_PATH) -> pd.DataFrame:
    """Load local TSV if it exists, otherwise return an empty dataframe with correct columns."""
    if os.path.exists(local_file):
        try:
            df = pd.read_csv(local_file, sep="\t", dtype=str)
        except Exception:
            # If file exists but is malformed, fall back to empty
            df = pd.DataFrame(columns=COLUMNS)
    else:
        df = pd.DataFrame(columns=COLUMNS)

    # Ensure correct columns/order
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[COLUMNS].astype(str)
    return df


def save_tsv(df: pd.DataFrame, local_file: str = LOCAL_TSV_PATH) -> None:
    df = df.copy()
    df = df[COLUMNS]
    df.to_csv(local_file, sep="\t", index=False, encoding="utf-8")


def append_submission(name: str, song1: str, song2: str) -> bool:
    """
    Mechanics:
    - download latest TSV from Dropbox (if exists)
    - append a new row
    - save locally as TSV
    - upload back to Dropbox (overwrite remote)
    """
    # Always try to fetch latest before appending (basic safeguard for multiple users)
    downloaded = download_from_dropbox(LOCAL_TSV_PATH)
    if downloaded:
        st.info("Loaded latest TSV from Dropbox.")
    else:
        # Not fatal; it may be first run, or transient failure
        st.warning("No Dropbox TSV found (or download failed) — using local file (or creating a new one).")

    df = load_tsv(LOCAL_TSV_PATH)

    new_row = pd.DataFrame([{"Name": name, "Song1": song1, "Song2": song2}])
    df = pd.concat([df, new_row], ignore_index=True)

    save_tsv(df, LOCAL_TSV_PATH)
    return upload_to_dropbox(LOCAL_TSV_PATH)


# -----------------------------------------------------------------------------
# 4) UI (single landing page)
# -----------------------------------------------------------------------------
st.title("Song Submission")

st.markdown(
    """
**Instructions:** Enter a name you want and **2 song names** approximately in this format:

`Title - Interpret`

Fill out:

- **Name**
- **Song1**
- **Song2**
"""
)

# Initialize defaults
st.session_state.setdefault("name", "")
st.session_state.setdefault("song1", "")
st.session_state.setdefault("song2", "")

name = st.text_input("Name", key="name", placeholder="e.g., Max")
song1 = st.text_input("Song1", key="song1", placeholder="e.g., Song Title - Artist")
song2 = st.text_input("Song2", key="song2", placeholder="e.g., Song Title - Artist")

# Gentle format hints (not strict)
format_warnings = []
if song1.strip() and "-" not in song1:
    format_warnings.append("Song1 doesn’t contain a '-' (expected: Title - Interpret).")
if song2.strip() and "-" not in song2:
    format_warnings.append("Song2 doesn’t contain a '-' (expected: Title - Interpret).")
if format_warnings:
    st.warning(" ".join(format_warnings))

submit = st.button("Submit", type="primary")

if submit:
    clean_name = name.strip()
    clean_song1 = song1.strip()
    clean_song2 = song2.strip()

    if not clean_name or not clean_song1 or not clean_song2:
        st.error("Please fill in Name, Song1, and Song2.")
    else:
        ok = append_submission(clean_name, clean_song1, clean_song2)
        if ok:
            st.success("Submitted! ✅")

            # Clear fields after successful submission
            st.session_state["name"] = ""
            st.session_state["song1"] = ""
            st.session_state["song2"] = ""
        else:
            st.error("Saved locally, but upload to Dropbox failed. Please try again.")

# Optional: show last submissions (kept on the same page)
with st.expander("Show latest submissions"):
    # Try to show the freshest possible view
    download_from_dropbox(LOCAL_TSV_PATH)
    df_preview = load_tsv(LOCAL_TSV_PATH)
    if df_preview.empty:
        st.write("No submissions yet.")
    else:
        st.dataframe(df_preview.tail(20), use_container_width=True)
