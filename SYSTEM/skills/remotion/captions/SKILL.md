---
name: remotion-captions
description: Transcribing, displaying and animating captions
version: 4.0.537
---

> **Project overrides (Dark World pipeline).** Source: official `remotion-dev/skills` v4.0.537 (no LICENSE file in that repo; part of the Remotion project, whose license is at remotion.dev/license), copied unchanged except this block.
> - Transcription is Stage 2 (local faster-whisper, frozen) — do not use `transcribe-captions.md` or install whisper.cpp. Captions come from the project's word timings (`useSceneData().words` → `Caption[]` with `startMs`/`endMs`).
> - Use `@remotion/captions` (`createTikTokStyleCaptions`, `Caption`) for display; Telugu captions use `FONT` from `../fonts` (Noto Sans Telugu).

All captions must be processed in JSON. The captions must use the [`Caption`](https://www.remotion.dev/docs/captions/caption.md) type which is the following:

```ts
import type { Caption } from "@remotion/captions";
```

This is the definition:

```ts
type Caption = {
  text: string;
  startMs: number;
  endMs: number;
  timestampMs: number | null;
  confidence: number | null;
  pageBreakAfter?: boolean;
};
```

## Generating captions

To transcribe video and audio files to generate captions, load the [transcribe-captions.md](transcribe-captions.md) file for more instructions.

## Displaying captions

To display captions in your video, load the [display-captions.md](display-captions.md) file for more instructions.

## Importing captions

To import captions from a .srt file, load the [import-srt-captions.md](import-srt-captions.md) file for more instructions.

## Post-creation

After you're done, load this skill: Remotion Best Practices

If not alreay done, open the Remotion Studio, unless instructed otherwise.
