import os
import re
import shutil
import subprocess
from datetime import datetime
from pathlib import Path

import db

# --- Fix ffmpeg discovery on Windows (needed by Whisper internally) ---
# If ffmpeg isn't on PATH in this terminal, add the known WinGet location.
ffmpeg_exe = shutil.which("ffmpeg")
if not ffmpeg_exe:
    ffmpeg_bin = r"C:\Users\kshit\AppData\Local\Microsoft\WinGet\Packages\Gyan.FFmpeg_Microsoft.Winget.Source_8wekyb3d8bbwe\ffmpeg-8.0.1-full_build\bin"
    os.environ["PATH"] = os.environ.get("PATH", "") + os.pathsep + ffmpeg_bin
    ffmpeg_exe = shutil.which("ffmpeg")

if not ffmpeg_exe:
    raise RuntimeError(
        "ffmpeg not found. Open PowerShell and run `where.exe ffmpeg` to locate it, "
        "then update ffmpeg_bin in test_pipeline.py."
    )

import whisper

ROOT = Path(__file__).parent
DOWNLOADS = ROOT / "data" / "downloads"
NOTES = ROOT / "data" / "notes"

DEFAULT_MODEL = "medium"   # accuracy-first (slower on CPU)
DEFAULT_LANG = "hi"        # force Hindi to avoid Urdu mis-detect for your content


def run(cmd: str) -> str:
    p = subprocess.run(cmd, capture_output=True, text=True, shell=True)
    if p.returncode != 0:
        raise RuntimeError(
            f"Command failed ({p.returncode}): {cmd}\n\nSTDOUT:\n{p.stdout}\n\nSTDERR:\n{p.stderr}"
        )
    return p.stdout.strip()


def slugify(s: str) -> str:
    s = re.sub(r"[^\w\s-]", "", s, flags=re.UNICODE).strip().lower()
    s = re.sub(r"[-\s]+", "-", s)
    return s[:80] or "reel"


def download_reel(url: str) -> Path:
    DOWNLOADS.mkdir(parents=True, exist_ok=True)

    outtmpl = str(DOWNLOADS / "%(id)s.%(ext)s")
    cmd = f'yt-dlp -f "bv*+ba/b" -o "{outtmpl}" "{url}"'
    run(cmd)

    files = sorted(DOWNLOADS.glob("*"), key=lambda p: p.stat().st_mtime, reverse=True)
    if not files:
        raise RuntimeError("Download seems to have produced no files in data/downloads.")
    return files[0]


def extract_audio(downloaded_path: Path) -> Path:
    # If yt-dlp already downloaded audio as wav, just use it.
    if downloaded_path.suffix.lower() == ".wav":
        return downloaded_path

    audio_path = downloaded_path.with_suffix(".wav")
    cmd = f'ffmpeg -y -i "{downloaded_path}" -ar 16000 -ac 1 -c:a pcm_s16le "{audio_path}"'
    run(cmd)
    return audio_path


def transcribe_both(audio_path: Path, model_name: str = DEFAULT_MODEL, language: str = DEFAULT_LANG) -> tuple[str, str]:
    model = whisper.load_model(model_name)

    raw = model.transcribe(
        str(audio_path),
        task="transcribe",
        language=language,
    )["text"].strip()

    en = model.transcribe(
        str(audio_path),
        task="translate",
        language=language,
    )["text"].strip()

    return raw, en


def write_note(url: str, raw: str, en: str, downloaded_path: Path) -> Path:
    NOTES.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = slugify(downloaded_path.stem)
    md_path = NOTES / f"{title}.md"

    md = f"""# {title}

Source: {url}
Created: {now}

## English (quick review)
{en}

## Raw transcript (verify details)
{raw}
"""
    md_path.write_text(md, encoding="utf-8")
    return md_path


if __name__ == "__main__":
    db.init_db()

    url = input("Paste Instagram Reel URL: ").strip()

    downloaded = download_reel(url)
    audio = extract_audio(downloaded)

    reel_id = db.upsert_reel(
        url=url,
        downloaded_path=str(downloaded),
        audio_path=str(audio),
        model=DEFAULT_MODEL,
        language=DEFAULT_LANG,
    )

    raw_text, en_text = transcribe_both(audio, model_name=DEFAULT_MODEL, language=DEFAULT_LANG)
    db.save_transcripts(reel_id, raw_text, en_text)

    note = write_note(url, raw_text, en_text, downloaded)

    print("Saved note:", note)
    print("Downloaded media:", downloaded)
    print("Saved to DB reel_id:", reel_id)
