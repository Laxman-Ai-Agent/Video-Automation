# Asset Collection Agent

- **Agent ID:** `asset_collection`
- **Stage ID:** `assets` (Stage 5, between Visual Planning and Motion Planning)
- **Primary Class:** `AssetCollectionAgent` (alias `AssetCollectionAdapter`)

## Purpose
Motion-Only stays the identity of the pipeline. This agent only ADDS real evidence (photographs, video clips) to the scenes whose narration is about a concrete real-world subject, from licensed sources, with full provenance. Most scenes need nothing and the stage then completes with zero requirements.

## Capabilities
- `asset-requirement-planning`
- `licensed-source-search`
- `clip-preparation`
- `rights-and-provenance-tracking`
- `duplicate-detection`

## Bound Tools
- `stock_providers` (`VIDEO_ENGINE/stages/stock.py`: NASA, Wikimedia Commons, Pexels, Pixabay)
- `ffmpeg` (clip trim + scale to the canvas)
- `llm_gateway` (requirement planning and ranking)
- `asset_manifest` (`assets_manifest.json`)

## Reference page captures
A requirement of kind `page` is a screenshot of one infobox or table of a Wikipedia (or other allowlisted official) page, made by `VIDEO_ENGINE/stages/web_capture.py` with Playwright's Chromium: https only, host allowlist re-checked on every redirect hop, robots.txt honoured, no login or CAPTCHA handling, always rights class C. News search is not part of the agent (it needs a search API).

## Artifacts
`asset_requirements.json`, `assets_manifest.json`, `credits.json`, `assets/collected/*`. The logic lives in `VIDEO_ENGINE/stages/asset_collection.py`.

## Architecture Notes
One agent for the whole stage: it is one sequential pipeline over shared state, so extra agents would only add hand-offs. Rights classes: A (known free) is used; C (not established) is collected but flagged for the human Final QC; D (no licence) is never downloaded. An asset is never presented as something it is not: `authenticity` is `real`.
