---
name: pipeline-remote-alerts
description: Configure and send remote notifications and webhook alerts (Telegram, Discord, Slack, Local Webhooks) for video pipeline lifecycle events, long render completions, and timeline approval gates.
---

# Pipeline Remote Alerts & Webhook Gateway

Use this skill when integrating remote alerts for long-running video production tasks (Whisper transcription, Remotion render, QC verification), sending rendered video previews to chat apps, or notifying users when human approval is required.

## 1. Supported Notification Channels

### A. Telegram Bot Gateway
Send text messages and video files directly to a user or channel chat:

```python
import os
import requests

def send_telegram_alert(message: str, video_path: str = None):
    token = os.getenv("TELEGRAM_BOT_TOKEN")
    chat_id = os.getenv("TELEGRAM_CHAT_ID")
    if not token or not chat_id:
        print("[Alert] TELEGRAM_BOT_TOKEN or TELEGRAM_CHAT_ID not configured; skipping.")
        return

    # 1. Send text message
    text_url = f"https://api.telegram.org/bot{token}/sendMessage"
    requests.post(text_url, json={"chat_id": chat_id, "text": message, "parse_mode": "Markdown"})

    # 2. Optionally send rendered MP4 video
    if video_path and os.path.exists(video_path):
        video_url = f"https://api.telegram.org/bot{token}/sendVideo"
        with open(video_path, "rb") as vf:
            requests.post(video_url, data={"chat_id": chat_id, "caption": "🎬 Final Render Complete"}, files={"video": vf})
```

### B. Discord Webhook Gateway
Send rich embeds with status colors to a Discord server channel:

```python
import os
import requests

def send_discord_alert(title: str, description: str, color_hex: int = 0x1890FF):
    webhook_url = os.getenv("DISCORD_WEBHOOK_URL")
    if not webhook_url:
        return

    payload = {
        "embeds": [{
            "title": title,
            "description": description,
            "color": color_hex,
            "footer": {"text": "Telugu Audio-to-Video Engine"}
        }]
    }
    requests.post(webhook_url, json=payload)
```

---

## 2. Recommended Alert Triggers

Integrate alerts at critical milestones in `VIDEO_ENGINE/pipeline/orchestrator.py` or FastAPI event subscribers:

1. **Pipeline Run Started**:
   - Event: Audio uploaded and project pipeline initialized.
   - Severity: Info (`color: 0x38BDF8`).
2. **Timeline Approval Needed (Stage 09)**:
   - Event: Visual and Motion planning finished; human decision required before rendering.
   - Severity: Warning / Action Required (`color: 0xF59E0B`).
   - Action: Include link to web UI (`http://localhost:5173/?projectId={id}&stage=approval`).
3. **Render Completed (Stage 10/12)**:
   - Event: Final MP4 file rendered and QC verified.
   - Severity: Success (`color: 0x10B981`).
   - Action: Attach video preview or local file path.
4. **Pipeline Error / Blocked**:
   - Event: Unrecoverable failure in STT, segmentation, or render.
   - Severity: Error (`color: 0xEF4444`).
   - Action: Include failing stage ID and error message.

---

## 3. Security & Credentials Rule
- **Never commit bot tokens or webhook URLs into Git**.
- Store credentials in `.env` (which is in `.gitignore`):
  ```env
  TELEGRAM_BOT_TOKEN="your_token_here"
  TELEGRAM_CHAT_ID="your_chat_id"
  DISCORD_WEBHOOK_URL="https://discord.com/api/webhooks/..."
  ```
