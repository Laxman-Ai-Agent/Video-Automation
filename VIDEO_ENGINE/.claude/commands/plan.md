Plan the video for project $ARGUMENTS (default `demo`). Phase 1: TEXT ONLY, no images, JSON only.
Do not ask questions unless the audio meaning is unclear.

1. Translate (Telugu stays for reference; English carries the SAME timestamps):
   `.venv\Scripts\python.exe -m backend.translate_io projects/$ARGUMENTS prepare`, read `translate_input.txt`,
   write `translation.json` {"segments":[{"id":0,"en":"..."}]} (clean English, fix obvious ASR slips, keep ids),
   then `... backend.translate_io projects/$ARGUMENTS merge` and `... backend.plan_input projects/$ARGUMENTS`.
   Do not block on minor Telugu transcription errors.
2. Read ONLY `projects/$ARGUMENTS/plan_input.txt`, `docs/schemas.md` (scene_plan, prompts_map),
   and `VIDEO_ENGINE/remotion/src/patterns/images.json` (pattern -> number of image slots).
   Patterns (see docs/components.md): hero_only hero_text hero_icon hero_map_icon split_two triple_stack
   grid_four collage_five stat_counter chart_focus map_route timeline quote_type object_float
   stock_overlay before_after.
3. Split into scenes BY MEANING. Boundaries must be 0, the audio duration, or a cut from plan_input.txt
   (merge small candidates, never invent times). Typical scene 3-15 s, never < 2 s or > 20 s.
4. Write `scene_plan.json` (schema = backend/models.py ScenePlan, extra keys are rejected):
   - style: ONE `suffix` (e.g. "cinematic documentary, warm teal-orange, film grain, no text") + palette [bg, accent, ...]
   - per scene: id, start, end, meaning, concept, mood, mode, pattern, keywords [{text, at}], params, optional transition
   - `mood`: short free text, but include one of calm majestic tense energetic hopeful sad playful dramatic (the transition table), e.g. "energetic, busy".
     A mood with none of these words is not judged for transition fit.
   - `transition`: one of fade slide wipe flip clock-wipe zoom-through light-leak blur mask-shape match-move particle.
     Never equal to the previous scene's. Omit it to let code pick by mood. Last scene has none.
   - `params` fill only what the pattern needs: text (+mark word), text2, icon (lucide kebab name), number+unit,
     data+kind (bar|line|pie), region+highlight (country names)+route [[lon,lat]]+labels, approximate.
   - Max 1-2 text elements per scene; some scenes with none. Text is English, short, key words/numbers/names only.
   - Numbers/data must be stated in the audio (digits appear in transcript). Else set params.approximate=true.
   - keywords[0].at times the main text/counter; use [t=..] anchors from plan_input.txt.
5. Write `prompts_map.json`: one entry per image slot. Slot name `s{scene:02}_{k}` where k = 0..n-1 is the image
   index of that pattern (0 = main). Number prompts n=1..N in scene order. Fields: n, scene, slot, role
   (main|supporting|icon|object|background), ratio (16:9 main/background, 4:3 or 16:9 supporting, 1:1 icon/object),
   required, bg (full|removable), text.
   - Prompts: ENGLISH only. Subject, setting, light, camera angle, mood; one clear subject. No text, numbers,
     logos, watermarks, real people names inside the image. Do NOT repeat the style suffix (code appends it).
   - Icon/object prompts: flat simple subject; code adds "isolated on plain white background".
   - Not every scene needs images; total prompts <= 1.5 x scenes. A pattern shows at most its images.json count.
6. Build and check (fix and rerun until clean):
   `cd remotion && npx tsx scripts/build_composition.ts ../projects/$ARGUMENTS && cd ..`
   `.venv\Scripts\python.exe -m backend.validate projects/$ARGUMENTS`
   `.venv\Scripts\python.exe -m backend.plan_checks projects/$ARGUMENTS`
   `.venv\Scripts\python.exe -m backend.prompts_writer projects/$ARGUMENTS`
7. Reply in Telugu, 10 lines max: scene count, image count, modes used, warnings, then a short scene list
   (id, time, one-line meaning) for the user to approve. After approval say: "prompts.txt is ready; generate
   images and upload".
Never write animation code, never view images, never invent cut times or data.
