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
# 1) Dropbox client + paths (same secrets as previous app)
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
    except ApiError as e:
        # Most common: file doesn't exist yet OR wrong path/permission.
        # We treat "not found" as first run; everything else we warn about.
        st.warning(
            "No Dropbox TSV found (or download failed) — using local file (or creating a new one)."
        )
        # If you want more detail, temporarily uncomment:
        # st.warning(f"Dropbox download ApiError: {e}")
        return False
    except Exception as e:
        st.warning(f"Could not download TSV from Dropbox: {e}")
        return False

    with open(local_file, "wb") as f:
        f.write(res.content)
    return True


def upload_to_dropbox(local_file: str = LOCAL_TSV_PATH) -> bool:
    """Upload local TSV to Dropbox at REMOTE_TSV_PATH (overwrite)."""
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
            df = pd.DataFrame(columns=COLUMNS)
    else:
        df = pd.DataFrame(columns=COLUMNS)

    # Ensure correct columns/order
    for col in COLUMNS:
        if col not in df.columns:
            df[col] = pd.NA
    df = df[COLUMNS]
    return df


def save_tsv(df: pd.DataFrame, local_file: str = LOCAL_TSV_PATH) -> None:
    df = df.copy()[COLUMNS]
    df.to_csv(local_file, sep="\t", index=False, encoding="utf-8")


def append_submission(name: str, song1: str, song2: str) -> bool:
    """
    Mechanics:
    - download latest TSV from Dropbox (if exists)
    - append a new row
    - save locally as TSV
    - upload back to Dropbox (overwrite remote)
    """
    download_from_dropbox(LOCAL_TSV_PATH)  # best-effort

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
**Instructions:** Enter a name you want (can also be a fantasy name, submissions are anonymous) and **2 song names** approximately in this format:

`Title - Interpret`
"""
)

# Form avoids the session_state reset error, and `clear_on_submit=True` clears inputs automatically.
with st.form("song_form", clear_on_submit=True):
    name = st.text_input("Name", placeholder="e.g., Max")
    song1 = st.text_input("Song1", placeholder="e.g., Song Title - Artist")
    song2 = st.text_input("Song2", placeholder="e.g., Song Title - Artist")
    submitted = st.form_submit_button("Submit", type="primary")

if submitted:
    clean_name = (name or "").strip()
    clean_song1 = (song1 or "").strip()
    clean_song2 = (song2 or "").strip()

    if not clean_name or not clean_song1 or not clean_song2:
        st.error("Please fill in Name, Song1, and Song2.")
    else:
        # Light format hints (not strict)
        #if "-" not in clean_song1 or "-" not in clean_song2:
        #    st.warning("Tip: Expected format is roughly `Title - Interpret` (but submission will still be saved).")

        ok = append_submission(clean_name, clean_song1, clean_song2)
        if ok:
            st.success("Submitted! ✅")
        else:
            st.error("Saved locally, but upload to Dropbox failed. Check Dropbox secrets/path/permissions and try again.")


# Optional: show latest submissions
with st.expander("Show latest submissions"):
    download_from_dropbox(LOCAL_TSV_PATH)  # best-effort refresh
    df_preview = load_tsv(LOCAL_TSV_PATH)

    if df_preview.empty:
        st.write("No submissions yet.")
    else:
        # Hide Name in the display (but keep it stored in Dropbox)
        st.dataframe(df_preview[["Song1", "Song2"]].tail(20), use_container_width=True)

