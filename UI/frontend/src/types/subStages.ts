import { StageState, StageStatus } from './pipeline';

export interface SubStageConfig {
  id: string;
  order: number;
  label: string;
  description: string;
  weight: number;
}

export interface SubStageState {
  id: string;
  order: number;
  label: string;
  description: string;
  status: StageStatus;
  percentage: number;
  currentActivity?: string;
}

export const CANONICAL_SUB_STAGES: Record<string, SubStageConfig[]> = {
  // 01. Audio Analysis (14 sub-stages from audio_analysis.py STAGES)
  analyzer: [
    { id: 'ana_file_valid', order: 1, label: 'Audio File Validation', description: 'Decodability check, stream presence & header integrity', weight: 0.07 },
    { id: 'ana_meta_extract', order: 2, label: 'Audio Metadata Extraction', description: 'Measured sample rate, channels, container & bitrate via ffprobe', weight: 0.07 },
    { id: 'ana_preprocess', order: 3, label: 'Audio Preprocessing', description: 'WAV format normalization and lead/trail silence trimming', weight: 0.07 },
    { id: 'ana_lang_detect', order: 4, label: 'Language & Speech Detection', description: 'Whisper language verification (Telugu / English)', weight: 0.07 },
    { id: 'ana_asr_transcribe', order: 5, label: 'Speech-to-Text (ASR)', description: 'Whisper acoustic tokenization & multilingual transcription', weight: 0.10 },
    { id: 'ana_tech_vocab', order: 6, label: 'Telugu + English Technical Vocabulary', description: 'Telugu + English technical vocabulary mapping', weight: 0.07 },
    { id: 'ana_conf_score', order: 7, label: 'Confidence-Based Correction', description: 'Acoustic word confidence scoring & low-confidence flagging', weight: 0.07 },
    { id: 'ana_llm_transcript', order: 8, label: 'Raw vs Corrected Transcript (LLM)', description: 'Deterministic LLM review & phonetic disambiguation', weight: 0.08 },
    { id: 'ana_word_align', order: 9, label: 'Word-Level Alignment', description: 'Timestamp boundary anchoring and gap analysis', weight: 0.08 },
    { id: 'ana_timestamp_integrity', order: 10, label: 'Word Timestamp Integrity', description: 'Sequential monotonic timestamp validation', weight: 0.08 },
    { id: 'ana_pause_rhythm', order: 11, label: 'Pause & Speech Rhythm Analysis', description: 'Silencedetect pause duration mapping and cadence extraction', weight: 0.07 },
    { id: 'ana_quality_check', order: 12, label: 'Audio Quality & Uncertainty Detection', description: 'RMS loudness, volume bounds and noise level evaluation', weight: 0.06 },
    { id: 'ana_final_valid', order: 13, label: 'Final Audio Analysis Validation', description: 'Schema verification and atomic write of audio_analysis.json', weight: 0.06 },
    { id: 'ana_cache_resume', order: 14, label: 'Caching & Resume', description: 'Idempotency fingerprint caching & state check', weight: 0.05 }
  ],

  // 03. Scene Segmentation (7 canonical sub-stages from scene_segmentation.py STAGES)
  segmentation: [
    { id: 'seg_reader', order: 1, label: 'Analysis Data Reader', description: 'Ingesting transcript tokens, word timings, and pause boundaries', weight: 0.15 },
    { id: 'seg_sentence_clause', order: 2, label: 'Sentence & Clause Detection', description: 'Extracting clause markers and natural sentence units', weight: 0.15 },
    { id: 'seg_semantic', order: 3, label: 'Semantic Understanding', description: 'Analyzing conceptual continuity and thematic idea shifts', weight: 0.15 },
    { id: 'seg_topic_change', order: 4, label: 'Topic & Idea Change Detection', description: 'Identifying rhetorical transitions and narrative shift points', weight: 0.15 },
    { id: 'seg_boundary_grouping', order: 5, label: 'Scene Boundary & Grouping', description: 'Grouping coherent word sequences into distinct visual scenes', weight: 0.15 },
    { id: 'seg_duration_timing', order: 6, label: 'Duration & Timing Assignment', description: 'Assigning start/end times and enforcing duration bounds', weight: 0.15 },
    { id: 'seg_validation_continuity', order: 7, label: 'Scene Validation & Continuity', description: 'Validating continuous coverage and scene contract integrity', weight: 0.10 }
  ],

  // 04. Visual Planning (8 sub-stages from visual_planning.py STAGES)
  planning: [
    { id: 'plan_semantic', order: 1, label: 'Semantic Understanding', description: 'Context and narrative tone extraction per scene', weight: 0.13 },
    { id: 'plan_scene_objective', order: 2, label: 'Scene Objective & Visual Concept', description: 'Primary visual metaphor and layout concept design', weight: 0.13 },
    { id: 'plan_element_breakdown', order: 3, label: 'Element Breakdown', description: 'Assigning typography anchors, graphics, and backgrounds', weight: 0.13 },
    { id: 'plan_relationships', order: 4, label: 'Relationships & Visual Hierarchy', description: 'Establishing visual flow and component dependencies', weight: 0.13 },
    { id: 'plan_mode_aware', order: 5, label: 'Mode-Aware Planning', description: 'Configuring layout for Motion-Only vs Image-Assisted mode', weight: 0.12 },
    { id: 'plan_audio_timing', order: 6, label: 'Audio Timing & Text', description: 'Synchronizing visual cues with spoken keyword timings', weight: 0.12 },
    { id: 'plan_style_continuity', order: 7, label: 'Style & Continuity', description: 'Enforcing consistent palette, styling & typography rhythm', weight: 0.12 },
    { id: 'plan_validation', order: 8, label: 'Validation & Confidence', description: 'Writing authoritative visual_planning.json and scene_plan.json', weight: 0.12 }
  ],

  // 05. Motion Planning (13 sub-stages from motion_planning.py STAGES)
  motion_plan: [
    { id: 'mp_reader', order: 1, label: 'Motion Plan Reader', description: 'Reading the Visual Plan and the scene timing', weight: 0.08 },
    { id: 'mp_element_resolver', order: 2, label: 'Element Resolver', description: 'Matching every element to something the library draws', weight: 0.08 },
    { id: 'mp_preset_lookup', order: 3, label: 'Preset Registry Lookup', description: 'Checking every preset against the real registry', weight: 0.08 },
    { id: 'mp_effect_reuse', order: 4, label: 'Effect Reuse Engine', description: 'Reusing existing presets without repeating them', weight: 0.08 },
    { id: 'mp_anim_builder', order: 5, label: 'Animation Builder', description: 'Building the action sequence of every scene', weight: 0.08 },
    { id: 'mp_engine_adapter', order: 6, label: 'Animation Engine Adapter', description: 'Checking the parameters the engine accepts', weight: 0.08 },
    { id: 'mp_composition_builder', order: 7, label: 'Composition & Transition Builder', description: 'Planning how the scenes enter and leave', weight: 0.08 },
    { id: 'mp_timing_sync', order: 8, label: 'Timing & Audio Sync', description: 'Fixing seconds and frames on the audio timeline', weight: 0.08 },
    { id: 'mp_layout_validator', order: 9, label: 'Layout Validator', description: 'Checking safe areas, overlaps and reading time', weight: 0.07 },
    { id: 'mp_code_validator', order: 10, label: 'Code & Plan Validator', description: 'Checking the plan against its contract', weight: 0.07 },
    { id: 'mp_test_runner', order: 11, label: 'Motion Test Runner', description: 'Running the motion library checks', weight: 0.07 },
    { id: 'mp_error_repair', order: 12, label: 'Error Repair Handler', description: 'Repairing only what is safe to repair', weight: 0.08 },
    { id: 'mp_remotion_adapter', order: 13, label: 'Remotion Output Adapter', description: 'Preparing the layers Remotion will build', weight: 0.07 }
  ],

  // 06. Motion Generation (13 sub-stages from motion_generation.py STAGES)
  motion_gen: [
    { id: 'mg_reader', order: 1, label: 'Plan Reader', description: 'Reading motion-plan.json', weight: 0.08 },
    { id: 'mg_element_resolver', order: 2, label: 'Element Resolver', description: 'Finding what draws every planned element', weight: 0.08 },
    { id: 'mg_preset', order: 3, label: 'Preset Registry', description: 'Checking every preset against the real registry', weight: 0.08 },
    { id: 'mg_effect_reuse', order: 4, label: 'Effect Reuse', description: 'Reusing existing effects, adding none', weight: 0.08 },
    { id: 'mg_anim_builder', order: 5, label: 'Animation Builder', description: 'Building one descriptor per layer', weight: 0.08 },
    { id: 'mg_engine_adapter', order: 6, label: 'Engine Adapter', description: 'Routing to frame-driven components', weight: 0.08 },
    { id: 'mg_composition_builder', order: 7, label: 'Composition Builder', description: 'Ordering scenes, layers and transitions', weight: 0.08 },
    { id: 'mg_audio_sync', order: 8, label: 'Audio Sync', description: 'Fixing seconds and frames on the audio timeline', weight: 0.08 },
    { id: 'mg_layout_val', order: 9, label: 'Layout Validation', description: 'Checking safe areas and overlaps', weight: 0.07 },
    { id: 'mg_code_val', order: 10, label: 'Code Validation', description: 'Checking the composition against the renderer', weight: 0.07 },
    { id: 'mg_motion_test', order: 11, label: 'Motion Testing', description: 'Running the motion checks and a repeat build', weight: 0.07 },
    { id: 'mg_error_repair', order: 12, label: 'Error Repair', description: 'Repairing only what is safe to repair', weight: 0.08 },
    { id: 'mg_remotion_adapter', order: 13, label: 'Remotion Adapter', description: 'Writing the composition for Remotion', weight: 0.07 }
  ],

  // 07. Motion Validation (12 sub-stages from motion_validation.py STAGES)
  motion_validation: [
    { id: 'mv_input_provenance', order: 1, label: 'Input Reader & Provenance', description: 'Reading the current artifacts and where they came from', weight: 0.09 },
    { id: 'mv_fingerprint', order: 2, label: 'Fingerprint & Freshness', description: 'Proving every input is current', weight: 0.09 },
    { id: 'mv_scene_mapping', order: 3, label: 'Scene Mapping & Coverage', description: 'One planned scene for every canonical scene', weight: 0.09 },
    { id: 'mv_timing_frame', order: 4, label: 'Timing & Frame Integrity', description: 'Seconds, frames, gaps and exits', weight: 0.09 },
    { id: 'mv_element_completeness', order: 5, label: 'Element Completeness & Drawn Support', description: 'Every required element really drawn', weight: 0.08 },
    { id: 'mv_anim_preset', order: 6, label: 'Animation & Preset Validity', description: 'Presets, properties and descriptors', weight: 0.08 },
    { id: 'mv_layout_collision', order: 7, label: 'Layout & Collision', description: 'Safe area, overlaps and z-order', weight: 0.08 },
    { id: 'mv_audio_text_sync', order: 8, label: 'Audio & Text Synchronization', description: 'Audio, text timing and emphasis words', weight: 0.08 },
    { id: 'mv_transition_readiness', order: 9, label: 'Transition & Continuity Readiness', description: 'Transitions the timeline can build', weight: 0.08 },
    { id: 'mv_buildability', order: 10, label: 'Composition Buildability & Determinism', description: 'Renderer contract, read-back, repeat build', weight: 0.08 },
    { id: 'mv_preview_val', order: 11, label: 'Preview Validation & Visual Evidence', description: 'Stills and what was reviewed by a person', weight: 0.08 },
    { id: 'mv_readiness_gate', order: 12, label: 'Findings, Report & Timeline Readiness Gate', description: 'One truthful decision', weight: 0.08 }
  ],

  // 08. Timeline Build (12 sub-stages from timeline_build.py STAGES)
  timeline: [
    { id: 'tl_request_lock', order: 1, label: 'Build Request & Lock', description: 'Acquiring run lock and verifying build eligibility', weight: 0.09 },
    { id: 'tl_discovery', order: 2, label: 'Input Artifact Discovery', description: 'Scanning motion and audio input contracts', weight: 0.09 },
    { id: 'tl_freshness_gate', order: 3, label: 'Source Freshness & Readiness Gate', description: 'Verifying upstream artifact hash integrity', weight: 0.09 },
    { id: 'tl_settings', order: 4, label: 'Project Settings Normalization', description: 'Normalizing resolution, aspect ratio, and 30 FPS timing', weight: 0.09 },
    { id: 'tl_scene_mapping', order: 5, label: 'Scene Mapping', description: 'Mapping visual scenes to timeline track layers', weight: 0.08 },
    { id: 'tl_frame_timing', order: 6, label: 'Frame Timing Normalization', description: 'Aligning frame boundaries to audio timestamps', weight: 0.08 },
    { id: 'tl_video_track', order: 7, label: 'Video / Composition Track Assembly', description: 'Sequencing video and graphic layers', weight: 0.08 },
    { id: 'tl_audio_track', order: 8, label: 'Audio & Narration Track Assembly', description: 'Multiplexing speech and background audio tracks', weight: 0.08 },
    { id: 'tl_transitions_gaps', order: 9, label: 'Transition & Gap Policy Application', description: 'Applying seamless scene transitions and gap fills', weight: 0.08 },
    { id: 'tl_assembly', order: 10, label: 'Timeline Assembly & Duration', description: 'Building the unified root Remotion timeline', weight: 0.08 },
    { id: 'tl_validation', order: 11, label: 'Structural / Post-Build Validation', description: 'Checking frame bounds and track synchronization', weight: 0.08 },
    { id: 'tl_publish', order: 12, label: 'Persist, Read Back & Publish', description: 'Writing authoritative timeline.json manifest', weight: 0.08 }
  ],

  // 09. Timeline Approval (4 sub-stages)
  approval: [
    { id: 'app_lineage', order: 1, label: 'Artifact Freshness & Lineage Check', description: 'Cryptographic hash check linking audio, scenes, and timeline', weight: 0.25 },
    { id: 'app_scene_coverage', order: 2, label: 'Scene & Track Coverage Review', description: 'Verifying 100% complete scene and narration coverage', weight: 0.25 },
    { id: 'app_gap_transition', order: 3, label: 'Audio-Video Gap & Transition Audit', description: 'Checking no black gaps or misaligned transitions', weight: 0.25 },
    { id: 'app_producer_gate', order: 4, label: 'Human Review & Signoff Gate', description: 'Enforcing producer review and recording approval token', weight: 0.25 }
  ],

  // 10. Render Video (5 sub-stages)
  render: [
    { id: 'rnd_env_setup', order: 1, label: 'Remotion Environment Setup', description: 'Allocating dedicated render port and headless browser instance', weight: 0.20 },
    { id: 'rnd_asset_preload', order: 2, label: 'Asset Preload & Font Caching', description: 'Preloading fonts, SVGs, and graphics in memory bundle', weight: 0.20 },
    { id: 'rnd_headless_frames', order: 3, label: 'Headless Frame Rendering (30 FPS)', description: 'Frame-by-frame 30 fps hardware-accelerated rendering', weight: 0.30 },
    { id: 'rnd_ffmpeg_mux', order: 4, label: 'Audio-Video Multiplexing (FFmpeg)', description: 'FFmpeg H.264 video + AAC 320kbps audio multiplexing', weight: 0.20 },
    { id: 'rnd_output_verify', order: 5, label: 'Output Integrity & Completeness Check', description: 'Verifying final MP4 file integrity and duration match', weight: 0.10 }
  ],

  // 11. Final QC (14 sub-stages from final_qc.py STAGES)
  qc: [
    { id: 'qc_init', order: 1, label: 'Run Initialization', description: 'Initializing QC run environment and parameters', weight: 0.07 },
    { id: 'qc_manifest', order: 2, label: 'Artifact & Manifest', description: 'Loading project manifest and input artifact hashes', weight: 0.07 },
    { id: 'qc_provenance', order: 3, label: 'Provenance & Approval', description: 'Verifying signed approval gate token and lineage', weight: 0.07 },
    { id: 'qc_integrity', order: 4, label: 'File Integrity', description: 'Checking MP4 container readability and byte size', weight: 0.07 },
    { id: 'qc_stream_meta', order: 5, label: 'Stream & Metadata', description: 'ffprobe video/audio codec, profile, and bitrate verification', weight: 0.07 },
    { id: 'qc_video_decode', order: 6, label: 'Video Decode', description: 'Testing complete H.264 stream decodability without dropped frames', weight: 0.07 },
    { id: 'qc_duration_frames', order: 7, label: 'Duration & Frames', description: 'Checking total frame count matches audio length within 0.05s', weight: 0.08 },
    { id: 'qc_audio_integrity', order: 8, label: 'Audio Integrity', description: 'Evaluating volume levels, clipping, and silence bounds', weight: 0.07 },
    { id: 'qc_av_sync', order: 9, label: 'A/V Sync', description: 'Lip-sync and audio-visual synchronization check', weight: 0.08 },
    { id: 'qc_frame_quality', order: 10, label: 'Frame Quality', description: 'Testing frame luma for black frames and static freezes', weight: 0.07 },
    { id: 'qc_scene_boundaries', order: 11, label: 'Scenes & Transitions', description: 'Verifying cut locations match scene boundaries', weight: 0.07 },
    { id: 'qc_reconciliation', order: 12, label: 'Upstream Reconciliation', description: 'Reconciling rendered frames with visual plan elements', weight: 0.07 },
    { id: 'qc_llm_review', order: 13, label: 'LLM Review', description: 'The Final QC LLM review decides about this exact file', weight: 0.08 },
    { id: 'qc_report_gate', order: 14, label: 'Report & Delivery Gate', description: 'Writing authoritative final_qc.json audit token', weight: 0.09 }
  ],

  // 12. Final Delivery (4 sub-stages)
  final: [
    { id: 'del_manifest', order: 1, label: 'Release Manifest Generation', description: 'Computing SHA-256 fingerprint of final video and artifacts', weight: 0.25 },
    { id: 'del_desktop', order: 2, label: 'Desktop Publication', description: 'Publishing final MP4 to Desktop/darkworld-renders workspace', weight: 0.35 },
    { id: 'del_archive', order: 3, label: 'Artifact Archiving & Provenance Pack', description: 'Compressing run logs, telemetry, and checkpoint state', weight: 0.20 },
    { id: 'del_complete', order: 4, label: 'Production Release Complete', description: 'Marking video project release ready for distribution', weight: 0.20 }
  ]
};

/**
 * Computes individual sub-stage states for a pipeline stage in real time based on authoritative stage state.
 * Never fabricates progress percentages when data is not available.
 */
export function computeSubStagesState(
  stageId: string, 
  stageState?: StageState
): SubStageState[] {
  const configs = CANONICAL_SUB_STAGES[stageId] || [];
  if (configs.length === 0) return [];

  const stageStatus = stageState?.status || 'waiting';
  const hasExplicitPct = stageState?.percentage !== null && stageState?.percentage !== undefined;
  const stagePct = hasExplicitPct 
    ? stageState!.percentage! 
    : (stageStatus === 'completed' ? 100 : 0);

  const N = configs.length;
  const stepSize = 100 / N;

  // Identify matching active sub-stage index from activity or explicit failing sub-stage
  const curActivity = (stageState?.currentActivity || '').toLowerCase();
  const failingSub = (stageState?.failingSubStage || '').toLowerCase();
  const errorText = (stageState?.errors?.[0] || '').toLowerCase();

  const matchedIdx = configs.findIndex(c => {
    const cLabel = c.label.toLowerCase();
    const cId = c.id.toLowerCase();
    if (failingSub && (failingSub.includes(cId) || failingSub.includes(cLabel))) return true;
    if (errorText && (errorText.includes(cId) || errorText.includes(cLabel))) return true;
    if (curActivity && (curActivity.includes(cId) || curActivity.includes(cLabel))) return true;
    return false;
  });

  const estimatedIdx = hasExplicitPct 
    ? Math.min(N - 1, Math.floor((stagePct / 100) * N)) 
    : 0;
  const activeIdx = matchedIdx !== -1 ? matchedIdx : estimatedIdx;

  return configs.map((cfg, idx) => {
    let subStatus: StageStatus = 'waiting';
    let subPct = 0;
    let activity = cfg.description;

    if (stageStatus === 'completed') {
      subStatus = 'completed';
      subPct = 100;
    } else if (stageStatus === 'waiting' || stageStatus === 'queued' || stageStatus === 'idle') {
      subStatus = 'waiting';
      subPct = 0;
    } else if (stageStatus === 'failed') {
      if (idx < activeIdx) {
        subStatus = 'completed';
        subPct = 100;
      } else if (idx === activeIdx) {
        subStatus = 'failed';
        subPct = hasExplicitPct ? Math.max(0, Math.min(100, Math.round(((stagePct - (activeIdx * stepSize)) / stepSize) * 100))) : 0;
        activity = stageState?.errors?.[0] || `Sub-stage failed: ${cfg.label}`;
      } else {
        subStatus = 'waiting';
        subPct = 0;
      }
    } else if (stageStatus === 'retrying' || stageStatus === 'recovering') {
      if (idx < activeIdx) {
        subStatus = 'completed';
        subPct = 100;
      } else if (idx === activeIdx) {
        subStatus = 'retrying';
        subPct = hasExplicitPct ? Math.max(0, Math.min(100, Math.round(((stagePct - (activeIdx * stepSize)) / stepSize) * 100))) : 0;
        activity = stageState?.retryReason || (stageState?.attempt ? `Retrying (attempt ${stageState.attempt}${stageState.maxAttempts ? `/${stageState.maxAttempts}` : ''})...` : 'Retrying sub-stage...');
      } else {
        subStatus = 'waiting';
        subPct = 0;
      }
    } else if (stageStatus === 'blocked') {
      if (idx < activeIdx) {
        subStatus = 'completed';
        subPct = 100;
      } else if (idx === activeIdx) {
        subStatus = 'blocked';
        subPct = 0;
        activity = stageState?.blockers?.[0] || 'Blocked awaiting prerequisites or approval';
      } else {
        subStatus = 'waiting';
        subPct = 0;
      }
    } else if (stageStatus === 'cancelled') {
      if (idx < activeIdx) {
        subStatus = 'completed';
        subPct = 100;
      } else if (idx === activeIdx) {
        subStatus = 'cancelled';
        subPct = 0;
        activity = 'Execution cancelled by user or supervisor';
      } else {
        subStatus = 'waiting';
        subPct = 0;
      }
    } else if (stageStatus === 'running') {
      const stepStart = activeIdx * stepSize;
      if (idx < activeIdx) {
        subStatus = 'completed';
        subPct = 100;
      } else if (idx === activeIdx) {
        subStatus = 'running';
        if (hasExplicitPct) {
          const rawInternal = Math.round(((stagePct - stepStart) / stepSize) * 100);
          subPct = Math.min(100, Math.max(0, rawInternal));
        } else {
          subPct = 0;
        }
        if (stageState?.currentActivity) {
          activity = stageState.currentActivity;
        }
      } else {
        subStatus = 'waiting';
        subPct = 0;
      }
    }

    return {
      id: cfg.id,
      order: cfg.order,
      label: cfg.label,
      description: activity,
      status: subStatus,
      percentage: subPct,
      currentActivity: (subStatus === 'running' || subStatus === 'retrying' || subStatus === 'failed') ? activity : undefined
    };
  });
}
