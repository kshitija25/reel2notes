import os
import re
import subprocess
from datetime import datetime
from pathlib import Path

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


def extract_audio(video_path: Path) -> Path:
    if video_path.suffix.lower() == ".wav":
        return video_path
    audio_path = video_path.with_suffix(".wav")
    cmd = f'ffmpeg -y -i "{video_path}" -ar 16000 -ac 1 -c:a pcm_s16le "{audio_path}"'
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


def write_note(url: str, raw: str, en: str, video_path: Path) -> Path:
    NOTES.mkdir(parents=True, exist_ok=True)

    now = datetime.now().strftime("%Y-%m-%d %H:%M")
    title = slugify(video_path.stem)
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
    url = input("Paste Instagram Reel URL: ").strip()

    video = download_reel(url)
    audio = extract_audio(video)

    raw_text, en_text = transcribe_both(audio, model_name=DEFAULT_MODEL, language=DEFAULT_LANG)

    note = write_note(url, raw_text, en_text, video)

    print("Saved note:", note)
    print("Downloaded video:", video)
