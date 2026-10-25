---
name: batch-video-automation
description: Schedule and execute batch video generation jobs, queue multiple audio files for automated multi-stage rendering, manage pipeline concurrency, and run overnight production batches.
---

# Batch Video Processing & Overnight Automation

Use this skill when processing a directory of multiple audio recordings into finished videos sequentially, scheduling overnight production runs, or managing background task concurrency.

## 1. Batch Audio Ingestion Workflow

To convert a directory of Telugu audio files into individual video projects:

```python
import os
import requests

BACKEND_URL = "http://127.0.0.1:8000"

def batch_ingest(audio_dir: str, aspect: str = "16:9", auto_start: bool = True):
    audio_files = [f for f in os.listdir(audio_dir) if f.lower().endswith(('.wav', '.mp3', '.m4a'))]
    print(f"[Batch] Discovered {len(audio_files)} audio files in {audio_dir}")

    for idx, filename in enumerate(audio_files, 1):
        file_path = os.path.join(audio_dir, filename)
        project_title = os.path.splitext(filename)[0].replace("_", " ").title()
        
        print(f"\n[Batch {idx}/{len(audio_files)}] Creating project for: {project_title}")
        with open(file_path, "rb") as af:
            files = {"audio_file": af}
            data = {
                "title": project_title,
                "aspect": aspect,
                "reusable_templates": "false",
                "media": '{"stock_ratio":0.5,"icon_ratio":0.3,"typography_ratio":0.2}'
            }
            res = requests.post(f"{BACKEND_URL}/api/projects/audio", files=files, data=data)
            project_id = res.json().get("id") or res.json().get("name")
            print(f"[Batch] Project created: {project_id}")

        if auto_start and project_id:
            # Trigger full pipeline run with autopilot enabled
            requests.post(f"{BACKEND_URL}/api/pipeline/start/{project_id}?auto_pilot=true")
            print(f"[Batch] Pipeline run initiated for {project_id}")
```

---

## 2. Queue Management & GPU/CPU Throttling

Video rendering (Remotion with Chromium headless and FFmpeg encode) requires significant CPU/GPU memory:
1. **Never run more than 1 Remotion render simultaneously** on consumer hardware (1 GPU / 16-32GB RAM).
2. **Sequential Queue**:
   - Wait until Project $N$ transitions to `completed` or `failed` before triggering the render stage of Project $N+1$.
   - Monitor status via `GET /api/projects/{projectId}/status`.

---

## 3. Scheduled / Cron Execution

To run an overnight batch job on Windows without manual intervention:

```powershell
# PowerShell background script to monitor folder and process newly dropped audio files
$AudioFolder = "e:\movies\Audio-to-video-main\incoming_audio"
Get-ChildItem -Path $AudioFolder -Filter *.wav | ForEach-Object {
    Write-Host "Processing $($_.Name)..."
    .venv\Scripts\python.exe scripts\run_pipeline_cli.py --audio $_.FullName --aspect 16:9
}
```
