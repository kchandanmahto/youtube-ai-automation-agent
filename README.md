# 🎬 YouTube AI Automation Agent

**An AI-powered YouTube content creation pipeline built with Python, FastAPI, Groq, SQLite, and Piper TTS.**

Generate YouTube video plans and create Hindi voiceovers locally using text-to-speech. This project is being developed in phases toward an automated video production workflow.

## 🚀 Current Features

- 🤖 **AI Script Generation:** Generate video titles, descriptions, hooks, scripts, and tags using Groq.
- 🎞️ **Scene Planning:** Create scene-by-scene visual instructions, narration, and on-screen text.
- ⏱️ **Duration Control:** Configure the target video duration and adjust scene timings.
- 🇮🇳 **Hindi Text-to-Speech:** Generate Hindi voiceovers locally using Piper TTS.
- 🎧 **Audio Output:** Save and play generated narration audio.
- 🌐 **Web Dashboard:** Use a simple HTML, CSS, and JavaScript interface.
- ⚡ **FastAPI Backend:** Manage video-generation jobs through REST API endpoints.
- 🗄️ **SQLite Database:** Store job status and generated video-plan data.

## 🛠️ Tech Stack

| Technology | Purpose |
|---|---|
| Python | Core application logic |
| FastAPI | Backend API |
| Groq API | AI script and scene generation |
| Piper TTS | Local text-to-speech |
| SQLite | Job and result storage |
| HTML, CSS, JavaScript | Web dashboard |
| Uvicorn | ASGI development server |

## 🏗️ Architecture

1. Enter a video topic in the dashboard.
2. Groq generates the script and scene plan.
3. Scene durations are adjusted to the selected target.
4. Piper converts the narration into Hindi audio.
5. The application saves the generated results for playback and download.

## 📋 Prerequisites

- Python 3.12 recommended
- A Groq API key
- Piper TTS and a compatible Hindi voice model
- Windows, macOS, or Linux with the required dependencies

## ⚙️ Installation

Clone the repository:

```bash
git clone https://github.com/YOUR_USERNAME/youtube-ai-automation-agent.git
cd youtube-ai-automation-agent
```

Create and activate a virtual environment:

```bash
python -m venv .venv
```

Windows:

```bash
.venv\Scripts\activate
```

Install dependencies:

```bash
python -m pip install -r requirements.txt
```

Create a `.env` file in the project root:

```env
GROQ_API_KEY=your_groq_api_key
GROQ_MODEL=openai/gpt-oss-20b
```

Use the model name supported by your Groq account. Keep API keys private.

Download a compatible Piper Hindi voice model and its matching configuration file. Configure the model path as required by your local setup.

Start the application:

```bash
python -m uvicorn main:app --reload
```

Open the dashboard:

`http://127.0.0.1:8000`

## 🔌 API Endpoints

| Method | Endpoint | Purpose |
|---|---|---|
| GET | `/` | Open the dashboard |
| GET | `/health` | Check application health |
| POST | `/api/jobs` | Create a video-plan job |
| GET | `/api/jobs` | List recent jobs |
| GET | `/api/jobs/{job_id}` | Check job status |
| GET | `/api/jobs/{job_id}/result` | Retrieve generated results |

## 🗺️ Development Roadmap

- [x] Phase 1: AI script and scene-plan generation
- [x] Phase 2: Local Hindi voice generation
- [ ] Phase 3: Realistic AI presenter and lip-sync video
- [ ] Phase 4: Automated video composition and subtitles
- [ ] Phase 5: Complete video export and quality checks
- [ ] Phase 6: YouTube upload automation

*Roadmap items are planned features and are not claimed as completed.*

## 🔐 Security

- Never commit `.env` files or API keys.
- Keep generated databases, private user data, and temporary files out of Git.
- Check the size and licensing of voice models before publishing them.
- Review generated content before uploading it publicly.

## 📌 Project Status

**In active development.** The current focus is AI script generation and Hindi voiceover automation. Presenter animation, full video rendering, and YouTube upload automation are future milestones.

## 📄 License

A license has not yet been selected. Add a suitable license before inviting reuse or contributions.

---

Built as a phased AI automation project with Python and open-source tools.

Built as a phased AI automation project with Python and open-source tools.

Built as a phased AI automation project with Python and open-source tools.
