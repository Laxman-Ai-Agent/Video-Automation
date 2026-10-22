# JSON Schemas (contracts between steps)

Validate every file with pydantic (Python) or zod (Remotion). Reject and fix invalid JSON; never guess.
All times are seconds (float). Frame = round(at * fps). All text fields are English except `transcript`.

## transcript.json (Whisper output, Telugu)
```json
{"language":"te","duration":312.4,
 "segments":[{"id":0,"start":0.0,"end":4.8,"text":"...",
   "words":[{"w":"...","start":0.0,"end":0.4}]}]}
```

## cuts.json (code-made candidate cut points)
```json
{"cuts":[{"t":7.2,"reason":"sentence_end","silence":0.5}]}
```
Cuts snap to word end times. Claude chooses/merges them by meaning.

## scene_plan.json (Claude, Phase 1)
```json
{"style":{"suffix":"cinematic documentary, warm teal-orange, film grain, no text",
          "palette":["#0B1D26","#F2A541","#2A9D8F"]},
 "scenes":[{
  "id":1,"start":0.0,"end":7.2,
  "meaning":"Introduces the Krishna river and why it matters",
  "concept":"Aerial river over farmland, map shows its path",
  "mood":"calm, majestic",
  "mode":"image-composite",
  "keywords":[{"text":"Krishna River","at":1.2},{"text":"1,400 km","at":3.1}]
 }]}
```
`mode`: image-composite | graph | typography | map | stock-video | mixed.

## prompts_map.json (system only; user never reads)
```json
{"prompts":[{"n":1,"scene":1,"slot":"s01_main","role":"main",
  "ratio":"16:9","required":true,"bg":"full",
  "text":"Aerial view of a wide river ..."}]}
```
`role`: main | supporting | icon | object | background. `bg`: full | removable.
`n` = number printed in prompts.txt and expected file name (`01.png`).

## prompts.txt (user reads)
Numbered plain prompts, blank line between. Style suffix + ratio appended to each.
Icon/object prompts end with "isolated on plain white background".

## match_report.json (code, Phase 2)
```json
{"matches":[{"n":1,"file":"IMG_2381.png","method":"filename|clip",
  "score":0.31,"margin":0.08,"status":"ok|review|missing"}],
 "unused":["extra.png"],"duplicates":[["a.png","b.png"]],
 "warnings":[{"file":"07.png","type":"low_res|bad_ratio|blurry"}]}
```
Rules: filename `NN.ext` wins. Else CLIP cosine + Hungarian (scipy linear_sum_assignment).
`review` when score < 0.22 or margin to next best < 0.03. Thresholds in `backend/config.py`.

## composition.json (Claude Phase 1, filled by code Phase 2)
```json
{"meta":{"fps":30,"width":1920,"height":1080,"audio":"audio.mp3",
         "duration":312.4,"subtitles":false,
         "palette":["#0B1D26","#2A9D8F","#F2A541"],"grade":"teal-orange"},
 "scenes":[{
  "id":1,"start":0.0,"end":7.2,"pattern":"hero_map_icon",
  "camera":{"move":"push-in","from":1.0,"to":1.15,"focus":[0.6,0.4]},
  "layers":[ ...layer objects... ],
  "transition_out":{"type":"zoom-through","dur":0.6}}]}
```

## Layer objects (all have `z`, optional `enter`, `exit`)
`enter`/`exit`: `{"at":2.0,"anim":"fade|slide-left|slide-up|pop|wipe|draw","dur":0.5}`
```json
{"type":"image","slot":"s01_main","file":null,"z":0,"anim":"ken-burns","parallax":0.2}
{"type":"image","slot":"s01_map","file":null,"z":1,"pos":"right-third","enter":{"at":3.5,"anim":"slide-left"}}
{"type":"icon","lucide":"droplet","z":2,"pos":[200,150],"enter":{"at":2.0,"anim":"pop"}}
{"type":"effect","name":"sparkle|burst|glow|checkmark|particles","at":3.1,"pos":[960,540]}
{"type":"text","style":"big-highlight|caption|label|lower-third","text":"1,400 km","at":3.1}
{"type":"counter","from":0,"to":1400,"unit":"km","at":3.1,"dur":2.0}
{"type":"chart","kind":"bar|line|pie","data":[{"label":"A","value":12}],"at":4.0}
{"type":"map","region":"india","highlight":["AP","TG"],"route":[[x,y]],"at":2.0}
{"type":"callout","kind":"arrow|circle|underline|box","target":[x,y],"at":3.2}
{"type":"shape","kind":"line|rect|circle","from":[x,y],"to":[x,y],"at":1.0}
{"type":"stock-video","file":"stock/clouds.mp4","opacity":0.3,"z":0}
{"type":"background","kind":"gradient","colors":["#0B1D26","#2A9D8F"]}
```
`slot` links to prompts_map; code replaces `file:null` with the matched path.
`pos` presets: full, left-third, right-third, center, top-left, bottom-right, or [x,y] px.
Camera `move`: push-in | pull-out | pan-left | pan-right | zoom-to-focus | static.
Transitions: fade, slide, wipe, flip, clock-wipe (from @remotion/transitions);
custom: zoom-through, light-leak, blur, particle, mask-shape, match-move.

## STATUS.json (see STATUS.md)
```json
{"updated":"ISO time","milestones":[{"id":"M0","name":"...","status":"todo|doing|done",
 "tasks":[{"name":"...","done":false}]}]}
```

## review.json, crops.json (review workflow; project folder)
```json
{"gates":{"analysis":{"fp":"<hash of scene_plan.json>","at":"2026-10-09T10:00:00"}},
 "prompts":{"s02_0":{"base":"generated text","edited_text":"user text","history":[{"text":"...","at":"...","by":"edit|regenerated|plan"}],
  "approved_hash":"<hash of the approved text>","regen_requested":"..."}}}
{"s01_0":{"9:16":{"x":0.78,"y":0.0,"zoom":1.5,"file":"image.jpg","at":"..."}}}
```
An approval counts only while its fingerprint matches the files. A crop counts only for the image it was made for. composition layers get
`crop:[x,y]` (object-position) and `zoom` (>1, scale around the same point) from the saved crop; the original picture is never changed.
