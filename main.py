
import json
import os
import re
import sqlite3
import subprocess
import sys
import uuid
from datetime import datetime, timezone
from pathlib import Path
from threading import Lock

from dotenv import load_dotenv
from fastapi import BackgroundTasks, FastAPI, HTTPException
from fastapi.responses import FileResponse
from fastapi.staticfiles import StaticFiles
from groq import Groq
from pydantic import BaseModel, Field

load_dotenv()

BASE_DIR = Path(__file__).resolve().parent
DB_PATH = BASE_DIR / "youtube_agent.db"
HTML_PATH = BASE_DIR / "index.html"
AUDIO_DIR = BASE_DIR / "audio"
VOICE_MODEL = BASE_DIR / "voices" / "hi_IN-pratham-medium.onnx"
AUDIO_DIR.mkdir(parents=True, exist_ok=True)

API_KEY = os.getenv("GROQ_API_KEY")
MODEL = os.getenv("GROQ_MODEL", "openai/gpt-oss-20b")

if not API_KEY:
    raise RuntimeError("GROQ_API_KEY .env file mein set karo.")

client = Groq(api_key=API_KEY, timeout=120.0, max_retries=2)
app = FastAPI(title="YouTube AI Agent", version="1.1.0")
db_lock = Lock()


def now():
    return datetime.now(timezone.utc).isoformat()


def connect_db():
    connection = sqlite3.connect(DB_PATH, timeout=30)
    connection.row_factory = sqlite3.Row
    return connection


def init_db():
    with connect_db() as db:
        db.execute("""
            CREATE TABLE IF NOT EXISTS jobs (
                job_id TEXT PRIMARY KEY,
                status TEXT NOT NULL,
                prompt TEXT NOT NULL,
                video_type TEXT NOT NULL,
                language TEXT NOT NULL,
                duration_minutes INTEGER NOT NULL,
                style TEXT NOT NULL,
                result_json TEXT,
                error TEXT,
                created_at TEXT NOT NULL,
                updated_at TEXT NOT NULL
            )
        """)
        db.commit()


init_db()


class VideoRequest(BaseModel):
    prompt: str = Field(min_length=5, max_length=3000)
    video_type: str = Field(pattern="^(shorts|long)$")
    language: str = Field(default="Hindi", min_length=2, max_length=40)
    duration_minutes: int = Field(default=1, ge=1, le=20)
    style: str = Field(default="AI presenter/avatar", max_length=100)


def update_job(job_id, **fields):
    allowed = {
        "status", "result_json", "error", "updated_at"
    }
    if not fields or any(key not in allowed for key in fields):
        raise ValueError("Invalid database update fields")

    fields["updated_at"] = now()
    assignments = ", ".join(f"{key} = ?" for key in fields)
    values = list(fields.values()) + [job_id]

    with db_lock:
        with connect_db() as db:
            db.execute(
                f"UPDATE jobs SET {assignments} WHERE job_id = ?",
                values,
            )
            db.commit()


def get_job(job_id):
    with connect_db() as db:
        row = db.execute(
            "SELECT * FROM jobs WHERE job_id = ?", (job_id,)
        ).fetchone()
    return dict(row) if row else None


def parse_json(content):
    content = content.strip()
    content = re.sub(r"^```(?:json)?\s*", "", content)
    content = re.sub(r"\s*```$", "", content)
    try:
        return json.loads(content)
    except json.JSONDecodeError:
        start = content.find("{")
        end = content.rfind("}")
        if start >= 0 and end > start:
            return json.loads(content[start:end + 1])
        raise ValueError("Groq ne valid JSON return nahi kiya.")


def fit_scene_durations(scenes, target_seconds):
    """Adjust scene durations so their integer total equals target_seconds."""
    if not isinstance(scenes, list) or not scenes:
        raise ValueError("AI ne koi valid scene generate nahi kiya.")

    weights = []
    for scene in scenes:
        try:
            weight = max(1, int(scene.get("duration_seconds", 1)))
        except (TypeError, ValueError):
            weight = 1
        weights.append(weight)

    count = len(scenes)
    if target_seconds < count:
        scenes = scenes[:target_seconds]
        weights = weights[:target_seconds]
        count = len(scenes)

    total_weight = sum(weights)
    exact = [target_seconds * weight / total_weight for weight in weights]
    durations = [max(1, int(value)) for value in exact]

    # Correct rounding while keeping every scene at least 1 second.
    while sum(durations) > target_seconds:
        candidates = [i for i, value in enumerate(durations) if value > 1]
        if not candidates:
            break
        index = max(candidates, key=lambda i: durations[i] - exact[i])
        durations[index] -= 1

    while sum(durations) < target_seconds:
        index = max(
            range(count),
            key=lambda i: exact[i] - durations[i],
        )
        durations[index] += 1

    for index, scene in enumerate(scenes):
        scene["scene_number"] = index + 1
        scene["duration_seconds"] = durations[index]

    return scenes


def generate_hindi_audio(job_id, script):
    """
    Generate a local Hindi WAV using the installed Piper CLI.
    Returns (audio_filename, error_message). A TTS problem does not discard
    the successfully generated video plan.
    """
    if not VOICE_MODEL.exists():
        return None, (
            f"Hindi Piper model nahi mila: {VOICE_MODEL}. "
            "Model ko voices/hi_IN-pratham-medium.onnx naam se rakho."
        )

    audio_filename = f"{job_id}.wav"
    audio_path = AUDIO_DIR / audio_filename

    try:
        completed = subprocess.run(
            [
                sys.executable, "-m", "piper",
                "-m", str(VOICE_MODEL),
                "-f", str(audio_path),
                "--", script,
            ],
            capture_output=True,
            text=True,
            timeout=900,
            check=False,
        )
        if completed.returncode != 0:
            details = (completed.stderr or completed.stdout or "Unknown Piper error").strip()
            return None, f"Piper voice generation failed: {details[-1200:]}"
        if not audio_path.exists() or audio_path.stat().st_size == 0:
            return None, "Piper ne audio file generate nahi ki."
        return audio_filename, None
    except subprocess.TimeoutExpired:
        return None, "Hindi voice generation 15 minutes se zyada chali aur timeout ho gaya."
    except Exception as exc:
        return None, f"Voice generation error: {exc}"


def generate_plan(job_id, request_data):
    try:
        update_job(job_id, status="processing", error=None)

        duration_seconds = request_data["duration_minutes"] * 60
        video_type = request_data["video_type"]

        system_prompt = f"""
You are a professional YouTube video planner.

Return ONLY valid JSON. Do not use Markdown fences.

Use exactly this structure:
{{
  "title": "Video title",
  "description": "YouTube description",
  "audience": "Target audience",
  "hook": "Opening hook",
  "script": "Complete spoken narration",
  "scenes": [
    {{
      "scene_number": 1,
      "duration_seconds": 10,
      "visual": "Visual instructions",
      "narration": "Exact narration for this scene",
      "on_screen_text": "Short readable text"
    }}
  ],
  "thumbnail_prompt": "Thumbnail image prompt",
  "tags": ["tag1", "tag2"]
}}

Requirements:
- Write all spoken content in {request_data['language']}.
- Video format: {video_type}.
- Total target duration: {duration_seconds} seconds.
- Generate enough scenes to cover the whole video, usually 5-10 seconds per scene.
- Scene durations should add up to {duration_seconds} seconds.
- Keep each scene's narration aligned with its visual.
- The combined scene narration should match the complete script closely.
- Avoid repeating the same narration across scenes.
- Do not invent statistics, sources, results or factual claims.
- Make the first few seconds engaging and the ending useful.
- Style: {request_data['style']}.
- Tags must be an array of short strings.
"""

        user_prompt = f"""
Create a YouTube video plan for this idea:

{request_data['prompt']}

Format: {video_type}
Language: {request_data['language']}
Duration: {request_data['duration_minutes']} minute(s)
Visual style: {request_data['style']}

The result will later be used by an automated voice, avatar,
subtitle and video-rendering pipeline.
"""

        response = client.chat.completions.create(
            model=MODEL,
            messages=[
                {"role": "system", "content": system_prompt},
                {"role": "user", "content": user_prompt},
            ],
            temperature=0.4,
            max_completion_tokens=8000,
        )

        content = response.choices[0].message.content or ""
        result = parse_json(content)

        required = [
            "title", "description", "audience", "hook",
            "script", "scenes", "thumbnail_prompt", "tags",
        ]
        missing = [
            key for key in required
            if key not in result or result[key] is None
        ]
        if missing:
            raise ValueError("AI response mein fields missing hain: " +
                             ", ".join(missing))

        for field in ["title", "description", "script", "hook"]:
            if not isinstance(result[field], str) or not result[field].strip():
                raise ValueError(f"Invalid or empty field: {field}")

        result["scenes"] = fit_scene_durations(
            result["scenes"], duration_seconds
        )

        result["total_duration_seconds"] = sum(
            scene["duration_seconds"] for scene in result["scenes"]
        )
        result["model"] = MODEL

        # Generate local Hindi narration after the plan is ready.
        audio_filename, audio_error = generate_hindi_audio(job_id, result["script"])
        if audio_filename:
            result["audio_url"] = f"/api/jobs/{job_id}/audio"
            result["audio_filename"] = audio_filename
            result["audio_generation_status"] = "completed"
        else:
            result["audio_generation_status"] = "failed"
            result["audio_generation_error"] = audio_error

        update_job(
            job_id,
            status="completed",
            result_json=json.dumps(result, ensure_ascii=False),
            error=None,
        )

    except Exception as exc:
        # Keep details in the API response for local development/debugging.
        update_job(job_id, status="failed", error=str(exc))


@app.get("/")
def dashboard():
    if not HTML_PATH.exists():
        raise HTTPException(status_code=500, detail="index.html nahi mila.")
    return FileResponse(HTML_PATH)


@app.get("/health")
def health():
    return {"status": "ok", "model": MODEL, "database": str(DB_PATH.name)}


@app.post("/api/jobs", status_code=202)
def create_job(data: VideoRequest, background_tasks: BackgroundTasks):
    job_id = str(uuid.uuid4())
    timestamp = now()

    with db_lock:
        with connect_db() as db:
            db.execute(
                """
                INSERT INTO jobs (
                    job_id, status, prompt, video_type, language,
                    duration_minutes, style, created_at, updated_at
                ) VALUES (?, ?, ?, ?, ?, ?, ?, ?, ?)
                """,
                (
                    job_id, "queued", data.prompt, data.video_type,
                    data.language, data.duration_minutes, data.style,
                    timestamp, timestamp,
                ),
            )
            db.commit()

    background_tasks.add_task(
        generate_plan, job_id, data.model_dump()
    )

    return {
        "job_id": job_id,
        "status": "queued",
        "status_url": f"/api/jobs/{job_id}",
        "result_url": f"/api/jobs/{job_id}/result",
    }


@app.get("/api/jobs")
def list_jobs():
    with connect_db() as db:
        rows = db.execute(
            """
            SELECT job_id, status, prompt, video_type, language,
                   duration_minutes, created_at, updated_at, error
            FROM jobs ORDER BY created_at DESC LIMIT 50
            """
        ).fetchall()
    return {"jobs": [dict(row) for row in rows]}


@app.get("/api/jobs/{job_id}")
def job_status(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    return {
        "job_id": job["job_id"],
        "status": job["status"],
        "created_at": job["created_at"],
        "updated_at": job["updated_at"],
        "error": job["error"],
    }


@app.get("/api/jobs/{job_id}/audio")
def job_audio(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    audio_path = AUDIO_DIR / f"{job_id}.wav"
    if not audio_path.exists():
        raise HTTPException(
            status_code=404,
            detail="Is job ke liye audio file available nahi hai. Job result mein audio_generation_error check karo."
        )

    return FileResponse(
        audio_path,
        media_type="audio/wav",
        filename=f"youtube-narration-{job_id[:8]}.wav",
    )


@app.get("/api/jobs/{job_id}/result")
def job_result(job_id: str):
    job = get_job(job_id)
    if not job:
        raise HTTPException(status_code=404, detail="Job not found")

    if job["status"] != "completed":
        return {
            "job_id": job_id,
            "status": job["status"],
            "error": job["error"],
        }

    return {
        "job_id": job_id,
        "status": "completed",
        "result": json.loads(job["result_json"]),
    }
