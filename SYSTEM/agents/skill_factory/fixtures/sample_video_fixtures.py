"""Deterministic Test Fixtures for Video Skill Domain Benchmarks.

Provides realistic, production-aligned fixtures from the video generation pipeline for:
1. Telugu/English bilingual transcripts with timestamp monotonicity.
2. Semantic visual scene plans with element hierarchies.
3. Remotion custom TSX motion code with spring physics and zero prohibited presets.
4. Telugu Unicode typography and subtitle placement configurations.
5. FFmpeg stream probing and audio-video duration sync audits.
"""
from __future__ import annotations

# 1. Realistic Bilingual Transcript Fixture
SAMPLE_BILINGUAL_TRANSCRIPT = {
    "segments": [
        {
            "id": 0,
            "start": 0.0,
            "end": 2.4,
            "text": "ఈ ప్రాజెక్ట్ లో Artificial Intelligence మరియు Machine Learning కీలకం.",
            "words": [
                {"word": "ఈ", "start": 0.0, "end": 0.3},
                {"word": "ప్రాజెక్ట్", "start": 0.3, "end": 0.8},
                {"word": "లో", "start": 0.8, "end": 1.0},
                {"word": "Artificial", "start": 1.0, "end": 1.5},
                {"word": "Intelligence", "start": 1.5, "end": 2.0},
                {"word": "మరియు", "start": 2.0, "end": 2.2},
                {"word": "Machine", "start": 2.2, "end": 2.3},
                {"word": "Learning", "start": 2.3, "end": 2.4},
            ]
        },
        {
            "id": 1,
            "start": 2.45,
            "end": 5.1,
            "text": "డేటా ప్రాసెసింగ్ కోసం Pipeline Architecture ను ఉపయోగించాము.",
            "words": [
                {"word": "డేటా", "start": 2.45, "end": 2.9},
                {"word": "ప్రాసెసింగ్", "start": 2.9, "end": 3.5},
                {"word": "కోసం", "start": 3.5, "end": 3.8},
                {"word": "Pipeline", "start": 3.8, "end": 4.3},
                {"word": "Architecture", "start": 4.3, "end": 4.8},
                {"word": "ను", "start": 4.8, "end": 4.9},
                {"word": "ఉపయోగించాము", "start": 4.9, "end": 5.1},
            ]
        }
    ]
}

# 2. Semantic Visual Scene Plan Fixture
SAMPLE_VISUAL_PLAN = {
    "scenes": {
        "scene_01": {
            "scene_id": "scene_01",
            "concept": "AI Neural Network Activation",
            "visual_concept": "Glowing neural node topology activating with pulses.",
            "scene_objective": "Convey high-tech algorithmic sophistication.",
            "elements": [
                {"name": "bg_particles", "type": "vector_particles", "z_index": 0, "role": "ambient"},
                {"name": "neural_nodes", "type": "svg_graph", "z_index": 1, "role": "structure"},
                {"name": "headline_text", "type": "kinetic_typography", "z_index": 2, "role": "primary_focus"},
                {"name": "caption_layer", "type": "caption_badge", "z_index": 3, "role": "subtitle"},
            ],
            "layout_mode": "split_metric",
            "aspect_ratio": "9:16",
        },
        "scene_02": {
            "scene_id": "scene_02",
            "concept": "Data Stream Pipeline",
            "visual_concept": "Horizontal energy pulse moving along pipeline rails.",
            "scene_objective": "Demonstrate seamless end-to-end data throughput.",
            "elements": [
                {"name": "pipeline_rail", "type": "svg_path", "z_index": 1, "role": "track"},
                {"name": "throughput_counter", "type": "metric_counter", "z_index": 2, "role": "primary_focus"},
            ],
            "layout_mode": "centered_headline",
            "aspect_ratio": "9:16",
        }
    }
}

# 3. Clean Remotion Motion TSX Code Fixture (No Prohibited Presets)
SAMPLE_REMOTION_MOTION_CODE = """
import React from 'react';
import { AbsoluteFill, useCurrentFrame, useVideoConfig, spring, interpolate } from 'remotion';

export const Scene01Motion: React.FC = () => {
    const frame = useCurrentFrame();
    const { fps, width, height } = useVideoConfig();

    const entranceSpring = spring({
        frame,
        fps,
        config: { damping: 14, mass: 0.8, stiffness: 90 }
    });

    const opacity = interpolate(frame, [0, 15], [0, 1], { extrapolateRight: 'clamp' });
    const translateY = interpolate(entranceSpring, [0, 1], [60, 0]);

    return (
        <AbsoluteFill style={{ backgroundColor: '#0a0d14', justifyContent: 'center', alignItems: 'center' }}>
            <div style={{
                opacity,
                transform: `translateY(${translateY}px)`,
                color: '#00f2fe',
                fontFamily: 'Noto Sans Telugu, sans-serif',
                fontSize: 64,
                fontWeight: 700,
                textAlign: 'center',
                maxWidth: width * 0.8,
            }}>
                AI &amp; Machine Learning
            </div>
        </AbsoluteFill>
    );
};
"""

# 4. Telugu Typography Caption Specification Fixture
SAMPLE_TELUGU_CAPTION_SPEC = {
    "text": "ఈ ప్రాజెక్ట్ లో Artificial Intelligence\nమరియు Machine Learning కీలకం.",
    "font_family": "Noto Sans Telugu, sans-serif",
    "aspect_ratio": "9:16",
    "position_y_pct": 0.82,
    "max_words_per_line": 6,
}

# 5. FFmpeg Render and Stream Audit Fixture
SAMPLE_FFMPEG_AUDIT_DATA = {
    "video_stream": {
        "codec_name": "h264",
        "width": 1080,
        "height": 1920,
        "r_frame_rate": "30/1",
        "duration": 5.12,
        "pix_fmt": "yuv420p",
    },
    "audio_stream": {
        "codec_name": "aac",
        "sample_rate": 44100,
        "channels": 2,
        "duration": 5.10,
    },
    "freeze_frames": [],
    "black_frames": [],
}
