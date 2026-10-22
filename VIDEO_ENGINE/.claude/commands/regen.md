Regenerate ONE image prompt for project $ARGUMENTS (format: `<project id> <prompt number>`). TEXT ONLY, English, no images.

1. Run `.venv\Scripts\python.exe -m backend.prompt_review context <id> <n>` and read the JSON. It holds the approved scene (meaning, concept, mood,
   English narration, keywords), the prompt's role / ratio, its current text and the other prompts of the same scene.
2. Write ONE new prompt for that slot: English only, one clear subject, setting, light, camera angle, mood. No text, numbers, logos, watermarks or real
   people names inside the image. Do NOT repeat the style suffix (code appends it). Icon/object prompts: a flat simple subject. It must differ from
   the current text (the user asked for a new one) and follow the scene context; do not touch any other prompt.
3. Save it: `.venv\Scripts\python.exe -m backend.prompt_review set <id> <n> "<new prompt text>"`.
4. Reply in Telugu, 2 lines max: the new prompt and "UI లో Approve Prompt నొక్కండి".
Never edit prompts_map.json by hand, never view images.
