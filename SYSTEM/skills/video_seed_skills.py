"""The video project's 21 seed skills (Remotion motion, audio, QC, layout) as Skill Registry seed definitions.

Video-owned. The Agent System's skill registry never imports this module: the video project provides these seeds through the
integration interface (SYSTEM/core/integrations.py, capability 'skill_seeds'; see VIDEO_ENGINE/agent_system_integration.py).
Each seed is (skill_id, name, domain, summary, path under SYSTEM/skills, capabilities, tags, compatible agents).
"""
from __future__ import annotations


def video_seed_skills() -> list[tuple]:
    return [
        (
            "motion.kinetic_typography",
            "Kinetic Typography Specialist",
            "motion",
            "Principles and constraints for Telugu narration kinetic typography layout, timing, and readability.",
            "motion/kinetic_typography/SKILL.md",
            ["typography-layout", "rhythm-matching", "readability-optimization"],
            ["typography", "motion", "telugu", "timing"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.remotion_spring_curves",
            "Remotion Spring Physics & Curve Math",
            "motion",
            "Standard spring curves, damping coefficients, and interpolation mechanics for smooth Remotion animations.",
            "motion/remotion_spring_curves/SKILL.md",
            ["spring-physics", "interpolation-math", "frame-clamping"],
            ["remotion", "spring", "physics", "interpolation"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.design_kit",
            "Professional Design Kit (palette, glass, gradients, depth)",
            "motion",
            "Premium look: dark gradient background from @radix-ui/colors (slateDark/violetDark/cyanDark), glass cards (translucent gradient, 1px light border, soft shadow), gradient text, "
            "soft glow via drop-shadow, generous spacing, one accent pair per video, fontFamily FONT from ../fonts. Vary it: one hero element per scene, no identical card grids, mood from the subject, numbered markers only for real sequences. No canvas/WebGL/feTurbulence (slow on CPU).",
            "motion/design_kit/SKILL.md",
            ["palette", "glassmorphism", "gradients", "depth"],
            ["design", "palette", "glass", "professional"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.charts_nivo_echarts",
            "Charts & Gauges (Nivo / ECharts SVG)",
            "motion",
            "Charts: @nivo/bar|line|pie|radar|funnel|waffle|sankey|treemap|heatmap|chord with FIXED width/height (never Responsive*), animate={false}, theme text colours light, gradient fills via defs; "
            "values = target * spring/interpolate(frame). Gauges: echarts/core + GaugeChart + SVGRenderer, init(null,null,{renderer:'svg',ssr:true,width,height}), animation:false, renderToSVGString() in dangerouslySetInnerHTML.",
            "motion/charts_nivo_echarts/SKILL.md",
            ["bar-chart", "line-chart", "gauge", "sankey", "treemap"],
            ["charts", "nivo", "echarts", "data"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.icons_logos",
            "Icons, Logos & Flags",
            "motion",
            "Icons: @phosphor-icons/react (weight=\"duotone\" or \"bold\", size, colour from the palette) or lucide-react; brand logos: simple-icons (import { siGithub } ... <path d={siGithub.path}/>, no OpenAI logo exists); "
            "flags: flag-icons SVG files. Put icons in glass chips with a soft glow; animate scale/opacity with spring(frame). Never load icons over the network.",
            "motion/icons_logos/SKILL.md",
            ["icons", "logos", "flags"],
            ["icons", "phosphor", "simple-icons", "flags"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.svg_morph_paths",
            "SVG Morphing & Path Drawing",
            "motion",
            "Shape morph: flubber interpolate(fromPath, toPath, { maxSegmentLength: 8 })(t) with t = interpolate(frame,...); draw-on lines: @remotion/paths evolvePath(progress, path) for strokeDasharray/offset; "
            "gradient strokes via <linearGradient>. Deterministic: derive everything from the frame.",
            "motion/svg_morph_paths/SKILL.md",
            ["morphing", "path-draw"],
            ["svg", "flubber", "paths", "animation"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.lottie_overlays",
            "Lottie Animated Illustrations",
            "motion",
            "@remotion/lottie <Lottie animationData={data} /> with the animation JSON imported statically (import data from \"./x.json\"; never fetch); frame-driven by Remotion. "
            "Only free/licensed files; keep them small (under ~300 KB) and SVG-based.",
            "motion/lottie_overlays/SKILL.md",
            ["lottie"],
            ["lottie", "illustration", "animation"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.diagrams_layout",
            "Diagrams, Networks & Maps (precomputed layout)",
            "motion",
            "Flowcharts: @dagrejs/dagre computes node positions, draw with SVG. Networks: d3-force run N ticks synchronously (simulation.tick(300)) then draw; trees/treemaps: d3-hierarchy. "
            "Maps: d3-geo + topojson-client + world-atlas projected to SVG paths, glow/gradient styling, reveal with frame-driven opacity/stroke. No live simulations, no tiles.",
            "motion/diagrams_layout/SKILL.md",
            ["flowchart", "network", "map"],
            ["diagram", "d3-force", "dagre", "map"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.captions_subtitles",
            "Captions & Word-Synced Emphasis",
            "motion",
            "English captions: @remotion/captions createTikTokStyleCaptions({ captions: [{text,startMs,endMs,timestampMs:null,confidence:null}], combineTokensWithinMilliseconds }) -> pages with tokens {text,fromMs,toMs}; "
            "active token by (frame/fps)*1000. Spoken-word times: useSceneData().words (seconds, Telugu: timing only, never print) with useAbsFrame() from ../sceneContext. Telugu subtitles are the separate meta.subtitles layer.",
            "motion/captions_subtitles/SKILL.md",
            ["captions", "word-sync"],
            ["captions", "subtitles", "emphasis"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.infographic_layouts",
            "Infographic Layouts (timeline, comparison, progress, table, lower third, callout)",
            "motion",
            "Explainer layouts from SVG/DOM + spring: timeline (evolvePath line, staggered nodes), A-vs-B comparison (VS badge, bars), progress ring/bar with counting number, table rows revealing in turn, lower third (accent bar slides in), "
            "callout (leader line + label), before/after (clipPath inset wipe), split screen, title card. Max 3 to 4 items, the key number biggest, d3-scale for lengths.",
            "motion/infographic_layouts/SKILL.md",
            ["timeline", "comparison", "progress", "table", "lower-third"],
            ["infographic", "layout", "explainer"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.transitions_scene_effects",
            "In-Scene Transitions (DOM-only) and Scene Hand-off",
            "motion",
            "Scene-to-scene transitions belong to the pipeline; a scene needs a clean entrance (10 frames) and exit (8 to 12 frames). Inside a scene use TransitionSeries with ONLY fade/slide/wipe/flip/iris/clock-wipe from @remotion/transitions/<name>. "
            "FORBIDDEN (WebGL, audit rejects): @remotion/light-leaks, blurSlide, crossZoom, dreamyZoom, filmBurn, linearBlur and similar; fake a light leak with a frame-driven radial gradient.",
            "motion/transitions_scene_effects/SKILL.md",
            ["transitions"],
            ["transitions", "dom-only"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.particles_ambient_effects",
            "Particles & Ambient Effects (seeded, CPU-friendly)",
            "motion",
            "Ambient particles/glows: positions from random(\"p\"+i) (remotion) and noise2D (@remotion/noise) plus the frame, never Math.random/timers; at most ~60 SVG circles (1 to 4px, opacity 0.15 to 0.6), no per-particle blur, no canvas; "
            "behind the content, under 40% opacity.",
            "motion/particles_ambient_effects/SKILL.md",
            ["particles", "ambient"],
            ["particles", "noise", "ambient"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.audio_visualizer",
            "Audio Visualizer (real, from the narration)",
            "motion",
            "Real audio bars: const { audio } = useSceneData() (../sceneData); audioData = useAudioData(staticFile(audio)); bars = visualizeAudio({ audioData, frame: useAbsFrame(), fps, numberOfSamples: 32 }) (power of two, values 0..1: boost with pow(v,0.5)); "
            "mirrored gradient bars with a minimum height, behind or under the headline, never over text.",
            "motion/audio_visualizer/SKILL.md",
            ["audio-visualization"],
            ["audio", "visualizer", "waveform"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.hud_technical_overlays",
            "HUD & Technical Overlays",
            "motion",
            "2D SVG HUD: corner brackets drawn with evolvePath, scan line translateY=(frame*6)%height, blueprint grid at 5 to 8% white, tick ring rotating with the frame, monospace readouts (fontStack(\"mono\") from ../fonts), target crosshair with spring. "
            "30 to 60% opacity, no WebGL, no perspective.",
            "motion/hud_technical_overlays/SKILL.md",
            ["hud", "overlay"],
            ["hud", "technical", "scan"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.backgrounds_reveals_camera",
            "Animated Backgrounds, Reveals & Camera Moves",
            "motion",
            "Moving gradient (angle = 120 + frame*0.3) with 2 to 3 big radial blobs driven by noise2D; clipPath reveals (inset / circle / polygon) from interpolate(frame); slow push-in scale 1 to 1.06; 2D parallax layers (no perspective); "
            "glitch only 6 to 10 frames. No full-frame blur filters.",
            "motion/backgrounds_reveals_camera/SKILL.md",
            ["background", "reveal", "camera"],
            ["background", "reveal", "camera", "parallax"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.math_code_visuals",
            "Math Formulas & Code Visuals",
            "motion",
            "Formulas: katex.renderToString(expr, { displayMode: true, throwOnError: false }) in dangerouslySetInnerHTML (stylesheet loaded globally, never import CSS in a scene). "
            "Code: prism-react-renderer <Highlight theme={themes.vsDark} code language=\"tsx\"> in a glass terminal card, fontStack(\"mono\"), typewriter = code.slice(0, floor(frame*1.5)), max ~12 lines.",
            "motion/math_code_visuals/SKILL.md",
            ["math", "code"],
            ["math", "katex", "code", "terminal"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.maps_regions",
            "Regional Maps (US states, countries, nation outlines)",
            "motion",
            "TopoJSON maps: us-atlas/states-10m.json (ids = 2-digit FIPS strings) with feature(us, us.objects.states), geoAlbersUsa().fitSize, geoPath; world-atlas/countries-110m.json (numeric ISO ids as strings). Dim glass fill, thin borders, "
            "accent gradient + glow on highlighted regions revealed by frame, label chip at pathOf.centroid. No tiles, no WebGL.",
            "motion/maps_regions/SKILL.md",
            ["us-map", "regional-map"],
            ["map", "us-atlas", "regions"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "motion.real_media",
            "Real Photos & Video Clips in Scenes",
            "motion",
            "How to place a collected real photo or clip (an element with a real_media object) in a scene: <Img>/<OffthreadVideo muted> with staticFile(real_media.file), hero scrim or framed card, slow frame-driven push-in, "
            "mandatory real_media.credit chip, honest framing (never recolour, never imply it is generated).",
            "motion/real_media/SKILL.md",
            ["real-media-placement", "credit-chips", "honest-framing"],
            ["real-media", "photo", "video-clip", "credit"],
            ["motion_planning", "motion_animation"],
        ),
        (
            "validation.layout_safe_zones",
            "Layout Safe Zones & Collision Guard",
            "validation",
            "Deterministic boundary checks and safe zone enforcement for 9:16 and 16:9 Remotion compositions.",
            "validation/layout_safe_zones/SKILL.md",
            ["safe-zone-validation", "collision-detection", "bounding-box-audit"],
            ["validation", "safe-zone", "bounds", "collision"],
            ["motion_planning", "motion_timeline_validation"],
        ),
        (
            "audio.bilingual_preservation",
            "Bilingual Telugu Script & Orthography Preservation",
            "audio",
            "Principles for maintaining native Telugu vocabulary in Telugu script while retaining technical terms in English.",
            "audio/bilingual_preservation/SKILL.md",
            ["telugu-orthography", "script-routing", "technical-term-detection"],
            ["audio", "telugu", "transcription", "phonetics"],
            ["audio_analyzer", "visual_planning"],
        ),
        (
            "media_probe",
            "Media Probe & Quality Verification",
            "qc",
            "Performs deterministic video probing, codec verification, audio track analysis, and frame integrity checks using ffprobe.",
            "media/media_probe/SKILL.md",
            ["media-probing", "audio-stream-verification", "resolution-audit", "freeze-frame-detection"],
            ["media", "probe", "qc", "ffmpeg"],
            ["final_qc", "render_video", "video_generator", "architecture_validator"],
        ),
    ]
