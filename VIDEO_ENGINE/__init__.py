"""VIDEO_ENGINE - Canonical Video Generation Engine.

Consists of:
- pipeline: Canonical PipelineOrchestrator and execution adapters
- stages: 12-stage video generation modules (including frozen ASR and segmentation)
- config: Engine-level configuration and render settings
- remotion: Remotion motion graphics compositions and bundle assets (Batch 4)
- ffmpeg: Media probing, conversion, and muxing utilities (Batch 4)
"""
from SYSTEM.core.backend_alias import install

install()   # engine modules import through the `backend` alias: register it before any of them loads
