/**
 * Authoritative evidence-based metadata for every pipeline stage and agent.
 * Covers sections A through L for all 11 canonical video generation stages:
 * A. Overview
 * B. What It Does (Implemented Responsibilities)
 * C. How It Works Internally (Architecture & Step-by-Step Flow)
 * D. Inputs & Dependencies (Files, schemas, tools)
 * E. Outputs & Side Effects (Artifacts, consumers, side effects)
 * F. LLM Usage & Decision-Making (Models, prompts, fallbacks, deterministic guardrails)
 * G. Current Capabilities (Verified capabilities with evidence)
 * H. What It Does NOT Do (Explicit non-responsibilities)
 * I. Missing Capabilities & Gaps (Status classification)
 * J. Validation & Testing (Validation logic, test files, recovery)
 * K. Improvement Opportunities (Prioritized backlog)
 * L. Source Code Evidence & References (Exact paths, classes, functions, tests)
 */

export type CapabilityStatus = 
  | 'VERIFIED WORKING'
  | 'PARTIALLY IMPLEMENTED'
  | 'NOT IMPLEMENTED'
  | 'NOT SUPPORTED'
  | 'NOT VERIFIED';

export interface StepFlowItem {
  step: number;
  title: string;
  detail: string;
  type: 'deterministic' | 'llm' | 'external';
}

export interface InputItem {
  name: string;
  required: boolean;
  format: string;
  description: string;
  pathExample: string;
}

export interface OutputItem {
  name: string;
  format: string;
  description: string;
  pathExample: string;
  consumers: string[];
}

export interface CapabilityItem {
  name: string;
  status: CapabilityStatus;
  description: string;
  evidence: string;
}

export interface MissingCapabilityItem {
  title: string;
  status: CapabilityStatus;
  gapDescription: string;
  impact: string;
  plannedResolution?: string;
}

export interface ImprovementItem {
  priority: 'HIGH' | 'MEDIUM' | 'LOW';
  title: string;
  currentLimitation: string;
  desiredBehavior: string;
  implementationGap: string;
  dependencies: string;
}

export interface AgentAboutData {
  agentId: string;
  stageId: string;
  name: string;
  role: string;
  category: string;
  version: string;
  owner: string;
  badge?: string;
  
  overview: {
    purpose: string;
    problemSolved: string;
    position: string;
    upstream: string;
    downstream: string;
    architectureRole: string;
  };
  
  whatItDoes: {
    summary: string;
    implementedResponsibilities: string[];
    productionReadyFeatures: string[];
    experimentalFeatures?: string[];
  };
  
  howItWorks: {
    summary: string;
    stepByStepFlow: StepFlowItem[];
    concurrencyAndCaching: string;
    retryLogic: string;
  };
  
  inputsDependencies: {
    inputs: InputItem[];
    externalTools: string[];
    systemDependencies: string[];
  };
  
  outputsSideEffects: {
    outputs: OutputItem[];
    sideEffects: string[];
    errorStates: string[];
  };
  
  llmDecisionMaking: {
    usesLlm: boolean;
    modelOrProfile: string;
    temperature?: string;
    promptStrategy: string;
    fallbackStrategy: string;
    deterministicGuardrails: string[];
    purelyDeterministicParts: string[];
  };
  
  currentCapabilities: CapabilityItem[];
  
  whatItDoesNotDo: string[];
  
  missingCapabilities: MissingCapabilityItem[];
  
  validationTesting: {
    validationLogic: string[];
    testFiles: string[];
    failureModesAndRecovery: string[];
  };
  
  improvementOpportunities: ImprovementItem[];
  
  sourceEvidence: {
    primaryFiles: string[];
    supportingFiles: string[];
    classesAndFunctions: string[];
    testFiles: string[];
  };
}

export const AGENT_ABOUT_DATA: Record<string, AgentAboutData> = {
  // =========================================================================
  // 1. AUDIO ANALYSIS (audio_analyzer / analyzer)
  // =========================================================================
  analyzer: {
    agentId: 'audio_analyzer',
    stageId: 'analyzer',
    name: 'Audio Analyzer Agent',
    role: 'Acoustic Processing, ASR Transcription & Bilingual Phonetics Review',
    category: 'audio',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 1',
    overview: {
      purpose: 'Performs high-fidelity acoustic inspection, faster-whisper word-level speech-to-text transcription, silence/pause segmentation, and bilingual Telugu-English phonetic preservation.',
      problemSolved: 'Converts raw uploaded narration audio into deterministic, frame-accurate word timestamps and pause markers, preventing transcription drift and providing exact anchors for visual cuts.',
      position: 'Stage 1 (Initial pipeline stage).',
      upstream: 'Raw operator audio file (audio.wav or audio.mp3 in projects/{project_id}/).',
      downstream: 'Stage 2: Scene Segmentation (scene_segmentation), which depends directly on transcript.json and cuts.json.',
      architectureRole: 'Perception gateway that establishes the immutable temporal foundation for all subsequent visual, motion, and timeline operations.'
    },
    whatItDoes: {
      summary: 'Executes faster-whisper ASR with word timestamps, extracts 14 acoustic telemetry metrics (LUFS, dBFS, duration), identifies pause cut points, and applies vocabulary standardization.',
      implementedResponsibilities: [
        'Deterministic audio format verification and FFprobe metadata extraction (duration, sample rate, channels, bit depth)',
        'Local faster-whisper ASR transcription with word-level start and end timestamps',
        'Acoustic silence detection using silencedetect thresholding to identify natural narrative pause breaks',
        'Generation of canonical transcript.json with word confidence scores and sentence boundaries',
        'Generation of cuts.json containing speech bursts and silence intervals for scene cutting',
        'Comprehensive 14-stage audio quality telemetry in audio_analysis.json (loudness LUFS, peak dBFS, speech cadence)',
        'Bilingual Telugu/English vocabulary review preserving loanwords, proper nouns, and technical terminology'
      ],
      productionReadyFeatures: [
        'Local offline faster-whisper inference with zero cloud dependency',
        'Deterministic word-boundary timestamp snapping',
        'Immunity to silent re-transcription: once transcript.json exists, it is cryptographically locked'
      ],
      experimentalFeatures: [
        'LLM-assisted phonetic correction of accented English terms embedded in Telugu speech'
      ]
    },
    howItWorks: {
      summary: 'Reads the source audio file, verifies acoustic parameters via FFprobe, runs faster-whisper for word alignments, analyzes silence intervals, and saves immutable JSON artifacts.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Audio Ingestion & Probe',
          detail: 'Locates audio file in projects/{project_id}/, runs ffprobe to verify sample rate (>= 16kHz recommended), channels, and exact duration.',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'Silence & Pause Detection',
          detail: 'Applies FFmpeg silencedetect filter (silence_threshold=-35dB, min_silence=0.4s) to identify speech pauses and potential scene cut points.',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'faster-whisper ASR Transcription',
          detail: 'Runs Whisper large-v3/medium locally with word_timestamps=True to compute token-level start and end timestamps.',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'Bilingual Vocabulary & Phonetics Review',
          detail: 'Optionally passes transcript through LLM Gateway (Claude/GPT) to correct ASR proper-noun misspellings and stabilize Telugu vocabulary without altering word timestamps.',
          type: 'llm'
        },
        {
          step: 5,
          title: 'Artifact Emission & Checkpointing',
          detail: 'Writes transcript.json, cuts.json, and audio_analysis.json; updates pipeline_state.json with stage 1 completion.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Whisper model weights are loaded once in worker process; cached transcript avoids re-computation if audio file SHA-256 matches.',
      retryLogic: 'If faster-whisper fails due to CUDA OOM, automatically falls back to CPU float32 mode.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'audio.wav / audio.mp3',
          required: true,
          format: 'WAV / MP3 (RIFF PCM or MPEG layer 3)',
          description: 'Master voice narration audio file with clear spoken speech.',
          pathExample: 'projects/{project_id}/audio.wav'
        }
      ],
      externalTools: ['faster-whisper', 'ffmpeg', 'ffprobe', 'soundfile / librosa'],
      systemDependencies: ['NVIDIA CUDA runtime (optional GPU acceleration)', 'Python 3.10+']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'transcript.json',
          format: 'JSON (array of words with text, start, end, probability)',
          description: 'Immutable word-by-word timestamped transcript.',
          pathExample: 'projects/{project_id}/transcript.json',
          consumers: ['scene_segmentation', 'visual_planning', 'motion_animation', 'timeline_build', 'final_qc']
        },
        {
          name: 'cuts.json',
          format: 'JSON (speech segments and pause intervals)',
          description: 'Boundary markers where voice is silent for natural visual scene transitions.',
          pathExample: 'projects/{project_id}/cuts.json',
          consumers: ['scene_segmentation']
        },
        {
          name: 'audio_analysis.json',
          format: 'JSON (14 analytical telemetry metrics, LUFS, dBFS, duration)',
          description: 'Deep audio health report and speech cadence statistics.',
          pathExample: 'projects/{project_id}/audio_analysis.json',
          consumers: ['UI AudioAnalyzerView', 'final_qc']
        }
      ],
      sideEffects: [
        'Updates projects/{project_id}/pipeline_state.json stage status to completed',
        'Records SHA-256 digest of source audio file'
      ],
      errorStates: [
        'Audio file missing or corrupted header (unreadable by FFprobe)',
        'Audio duration under 1.0 second',
        'Zero words detected in audio stream (silence or non-speech music)'
      ]
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'Claude 3.5 Sonnet / GPT-4o (configured via llm_gateway.py)',
      temperature: '0.1 (low temperature for strict factual fidelity)',
      promptStrategy: 'Provides raw Whisper transcript and instructs LLM to resolve Telugu loanwords and colloquial transliterations without modifying start/end numbers.',
      fallbackStrategy: 'If LLM Gateway times out or is unreachable, the raw deterministic faster-whisper transcript is used directly without failing the stage.',
      deterministicGuardrails: [
        'Word timestamps from Whisper are strictly immutable; LLM can never alter timing values',
        'Word count cannot be altered by LLM; 1:1 token correspondence is strictly validated'
      ],
      purelyDeterministicParts: [
        'FFprobe audio duration and acoustic parameter extraction',
        'Silence detection thresholding via FFmpeg',
        'faster-whisper neural inference'
      ]
    },
    currentCapabilities: [
      {
        name: 'Word-level timestamp extraction',
        status: 'VERIFIED WORKING',
        description: 'Computes start and end seconds for every spoken word with millisecond precision.',
        evidence: 'Verified in VIDEO_ENGINE/stages/transcribe.py and tests/test_playwright_audio_analysis_card.py'
      },
      {
        name: '14-stage audio telemetry',
        status: 'VERIFIED WORKING',
        description: 'Measures sample rate, LUFS loudness, speech rate WPM, and silence periods.',
        evidence: 'Exposed via UI/backend/audio_analysis.py and AudioAnalyzerView.tsx'
      },
      {
        name: 'Bilingual Telugu/English vocabulary review',
        status: 'VERIFIED WORKING',
        description: 'Standardizes romanized transliterations and prevents Telugu spelling corruption.',
        evidence: 'Implemented in VIDEO_ENGINE/stages/transcript_review.py'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT generate text-to-speech (TTS) or synthesize voice audio; audio must be pre-recorded',
      'Does NOT segment speech into visual scenes (handled by Scene Segmentation Agent)',
      'Does NOT modify or equalize the audio waveform (only measures and analyzes it)',
      'Does NOT create video composition or motion graphics'
    ],
    missingCapabilities: [
      {
        title: 'Background Music / Vocal Separation (Stem Extraction)',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Currently treats mixed audio as a single track. Music behind speech can reduce Whisper accuracy.',
        impact: 'Heavy background music may occasionally cause ASR hallucinations.',
        plannedResolution: 'Integrate Demucs or Spleeter stem isolation prior to Whisper transcription.'
      },
      {
        title: 'Multi-Speaker Diarization',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Does not tag which speaker is talking in multi-person interview audio.',
        impact: 'All spoken words are assigned to a single continuous monologue stream.'
      },
      {
        title: 'Real-time Streaming ASR',
        status: 'NOT SUPPORTED',
        gapDescription: 'Engine processes offline batch audio files; does not support real-time mic streaming.',
        impact: 'System designed for asynchronous batch video generation pipeline.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Asserts transcript duration <= audio duration + 0.1s tolerance',
        'Asserts word timestamps are strictly monotonic (start[n+1] >= start[n])',
        'Asserts non-empty transcript text'
      ],
      testFiles: [
        'tests/test_playwright_audio_analysis_card.py',
        'tests/test_verify_audio_analysis_fullpage.py',
        'tests/test_audio_visual_agents_integration.py'
      ],
      failureModesAndRecovery: [
        'Missing audio file: Marks stage BLOCKED and notifies operator to provide audio.',
        'CUDA OOM: Automatically switches device from cuda to cpu and retries.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'HIGH',
        title: 'Vocal Stem Separation Pre-Filter',
        currentLimitation: 'No separation of voice narration from background score.',
        desiredBehavior: 'Automatically isolate vocal track for transcription while retaining original music for final render.',
        implementationGap: 'Need Demucs ONNX lightweight runner in VIDEO_ENGINE/stages/transcribe.py.',
        dependencies: 'demucs or onnxruntime'
      },
      {
        priority: 'MEDIUM',
        title: 'Persistent Whisper Model In-Memory Daemon',
        currentLimitation: 'Cold model load latency (~4s) on each independent run.',
        desiredBehavior: 'Keep Whisper model loaded in background worker memory.',
        implementationGap: 'Orchestrator worker pool lifecycle.',
        dependencies: 'FastAPI lifespan state'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/audio_analyzer/agent.py',
        'VIDEO_ENGINE/stages/transcribe.py',
        'VIDEO_ENGINE/stages/transcript_review.py'
      ],
      supportingFiles: [
        'UI/backend/audio_analysis.py',
        'VIDEO_ENGINE/stages/quality.py',
        'UI/frontend/src/components/AudioAnalyzerView.tsx'
      ],
      classesAndFunctions: [
        'AudioAnalyzerAgent.execute()',
        'validate_analyzer_artifacts()',
        'transcribe_audio()',
        'review_transcript()'
      ],
      testFiles: [
        'tests/test_playwright_audio_analysis_card.py',
        'tests/test_verify_audio_analysis_fullpage.py'
      ]
    }
  },

  // =========================================================================
  // 2. SCENE SEGMENTATION (scene_segmentation / segmentation)
  // =========================================================================
  segmentation: {
    agentId: 'scene_segmentation',
    stageId: 'segmentation',
    name: 'Scene Segmentation Agent',
    role: 'Semantic Narrative Chunking & Word-Boundary Snapping',
    category: 'visual',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 2',
    overview: {
      purpose: 'Partitions continuous audio transcript into discrete, paced narrative scenes obeying strict duration thresholds (2s to 8s) and exact word-level boundaries.',
      problemSolved: 'Eliminates jarring mid-word visual cuts and prevents run-on scenes by aligning scene boundaries with semantic sentence pauses.',
      position: 'Stage 2 (Follows Audio Analysis).',
      upstream: 'Stage 1: Audio Analysis (transcript.json, cuts.json).',
      downstream: 'Stage 3: Visual Planning (visual_planning), which generates concept art and prompts for each segmented scene.',
      architectureRole: 'Structural narrative architect that defines the scene sequence and temporal cadence for the entire video.'
    },
    whatItDoes: {
      summary: 'Reads transcript and pause markers, applies semantic segmentation heuristics, enforces minimum/maximum scene durations, and snaps boundaries to exact word timestamps.',
      implementedResponsibilities: [
        'Ingestion of canonical transcript.json and cuts.json',
        'Sentence boundary detection using punctuation and pause intervals (>0.4s)',
        'Enforcement of pacing constraints (minimum scene duration >= 2.0s, maximum scene duration <= 8.0s)',
        'Zero-drift boundary snapping: scene start_time equals first word start, end_time equals last word end',
        'Orphan segment absorption: short trailing pauses merged with adjacent narrative sentences',
        'Generation of scene_segmentation.json with scene IDs, time ranges, and word arrays',
        'Integration with LLM Review for semantic coherence and vocabulary consistency'
      ],
      productionReadyFeatures: [
        'Mathematical word-boundary snapping with zero frame jitter',
        'Strict duration validation and automatic short-scene merging',
        'Interactive UI Scenes & Script viewer with search and copy capabilities'
      ],
      experimentalFeatures: [
        'Adaptive speech-rate pacing modulation based on speaker syllable density'
      ]
    },
    howItWorks: {
      summary: 'Groups transcript words into sentences, checks pause markers, splits oversized blocks, merges undersized fragments, and verifies complete duration coverage.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Transcript & Pause Ingestion',
          detail: 'Loads transcript.json and cuts.json; indexes words by timestamp and collects candidate pause split-points.',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'Semantic Sentence Grouping',
          detail: 'Identifies grammatical sentence boundaries using punctuation marks (. ? ! ;) and major speech pauses.',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'Duration Constraint Enforcement',
          detail: 'If a scene exceeds 8 seconds, splits at the nearest internal pause; if shorter than 2 seconds, merges with previous scene.',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'Word-Boundary Snapping',
          detail: 'Locks scene start_time to words[0].start and scene end_time to words[-1].end to prevent audio clipping.',
          type: 'deterministic'
        },
        {
          step: 5,
          title: 'LLM Review & Standardization',
          detail: 'Optionally invokes LLM Review to confirm narrative coherence and standardize vocabulary across scenes.',
          type: 'llm'
        },
        {
          step: 6,
          title: 'Artifact Emission',
          detail: 'Writes scene_segmentation.json and registers scene count in pipeline state.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Single-pass deterministic algorithm executing in under 50ms; results cached by transcript hash.',
      retryLogic: 'If duration constraints fail, iteratively relaxes threshold tolerance by 0.5s until a valid partition is found.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'transcript.json',
          required: true,
          format: 'JSON (words array with start, end, text)',
          description: 'Word-level timestamped transcript from Stage 1.',
          pathExample: 'projects/{project_id}/transcript.json'
        },
        {
          name: 'cuts.json',
          required: false,
          format: 'JSON (pause markers and silence points)',
          description: 'Candidate cut points detected during acoustic analysis.',
          pathExample: 'projects/{project_id}/cuts.json'
        }
      ],
      externalTools: ['Python standard library', 'LLM Gateway (optional for semantic review)'],
      systemDependencies: ['None (pure Python logic)']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'scene_segmentation.json',
          format: 'JSON (array of scenes with scene_id, start_time, end_time, duration, text, words)',
          description: 'Partitioned scene list serving as master structural index.',
          pathExample: 'projects/{project_id}/scene_segmentation.json',
          consumers: ['visual_planning', 'motion_planning', 'timeline_build', 'final_qc']
        }
      ],
      sideEffects: [
        'Updates projects/{project_id}/pipeline_state.json with total scene count',
        'Populates UI Scene Segmentation drawer tab'
      ],
      errorStates: [
        'Transcript has zero words',
        'Audio duration under minimum scene threshold',
        'Unresolvable boundary conflict where pauses do not match word intervals'
      ]
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'Claude 3.5 Sonnet (for optional LLM Review & vocabulary standardization)',
      temperature: '0.2',
      promptStrategy: 'Asks LLM to evaluate if split points preserve semantic narrative flow and suggest vocabulary corrections for romanized Telugu terms.',
      fallbackStrategy: 'If LLM fails or is disabled, deterministic boundary snapping runs 100% autonomously.',
      deterministicGuardrails: [
        'LLM cannot change scene start_time or end_time values',
        'Total duration of all scenes must strictly equal speech duration',
        'Word array within each scene is directly sliced from original Whisper transcript'
      ],
      purelyDeterministicParts: [
        'Word-boundary snapping algorithm',
        'Duration constraint enforcement (2s - 8s rule)',
        'Contiguity and overlap verification'
      ]
    },
    currentCapabilities: [
      {
        name: 'Deterministic word-boundary snapping',
        status: 'VERIFIED WORKING',
        description: 'Snaps scene boundaries to exact word timestamps with zero drift.',
        evidence: 'Verified in VIDEO_ENGINE/stages/scene_segmentation.py and tests/test_verify_scene_segmentation_tab.py'
      },
      {
        name: 'Scene duration pacing control',
        status: 'VERIFIED WORKING',
        description: 'Guarantees scenes stay within 2.0s to 8.0s window for optimal visual pacing.',
        evidence: 'Tested across 15+ automated test suites'
      },
      {
        name: 'UI Scenes & Script tab inspection',
        status: 'VERIFIED WORKING',
        description: 'Full-featured drawer view with live search, word inspector, and JSON export.',
        evidence: 'Implemented in StageDrawer.tsx lines 960-1500'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT generate visual prompts or choose imagery (handled by Visual Planning)',
      'Does NOT generate Remotion code or animation timelines',
      'Does NOT modify original audio or transcript timestamps'
    ],
    missingCapabilities: [
      {
        title: 'Adaptive Syllable-Rate Pacing',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Uses static 2-8s duration rules rather than dynamic adjustment to fast or slow speaking rates.',
        impact: 'Very rapid speech might feel slightly crowded in 8-second scenes.',
        plannedResolution: 'Calculate syllables per second from audio analysis and dynamically scale target scene length.'
      },
      {
        title: 'Cross-Language Semantic Topic Modeling',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Does not use latent semantic analysis or topic embeddings to detect major thematic chapters.',
        impact: 'Chapter-level scene grouping must be inferred from sentence punctuation.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Asserts sum(scene.duration) == total_speech_duration (+- 0.05s)',
        'Asserts scenes[i].end_time == scenes[i+1].start_time (no gaps, no overlaps)',
        'Asserts every scene contains at least one word'
      ],
      testFiles: [
        'tests/test_verify_scene_segmentation_tab.py',
        'tests/test_audio_visual_agents_integration.py'
      ],
      failureModesAndRecovery: [
        'Sentence exceeds 8s with no pauses: Hard-splits at longest available word spacing.',
        'Trailing sentence < 2s: Automatically merges into penultimate scene.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'MEDIUM',
        title: 'Dynamic Cadence Scaling',
        currentLimitation: 'Static 2s-8s boundaries.',
        desiredBehavior: 'Adjust maximum scene length based on emotional intensity and speech velocity.',
        implementationGap: 'Integrate speech rate WPM metric from audio_analysis.json into chunking logic.',
        dependencies: 'audio_analysis.json WPM metric'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/scene_segmentation/agent.py',
        'VIDEO_ENGINE/stages/scene_segmentation.py'
      ],
      supportingFiles: [
        'VIDEO_ENGINE/stages/review.py',
        'UI/backend/scene_segmentation.py',
        'UI/frontend/src/components/StageDrawer.tsx'
      ],
      classesAndFunctions: [
        'SceneSegmentationAgent.execute()',
        'segment_scenes()',
        'validate_scene_boundaries()',
        'snap_to_words()'
      ],
      testFiles: [
        'tests/test_verify_scene_segmentation_tab.py',
        'tests/test_audio_visual_agents_integration.py'
      ]
    }
  },

  // =========================================================================
  // 3b. ASSET COLLECTION (asset_collection / assets)
  asset_collection: {
    agentId: 'asset_collection',
    stageId: 'assets',
    name: 'Asset Collection Agent',
    role: 'Optional licensed real photos & video clips with provenance',
    category: 'visual',
    version: '1.0.0',
    owner: 'agent-system',
    overview: {
      purpose: 'Adds real photographs and video clips to the scenes whose narration is about a concrete real-world subject, from licensed sources, with source, licence and hash recorded for every asset.',
      problemSolved: 'Motion graphics alone cannot show a real place, event or object; collecting real media by hand loses track of licences and sources.',
      position: 'Stage 5 of 13: after Visual Planning, before Motion Planning.',
      upstream: 'Stage 4: Visual Planning (scene_plan.json, visual_planning.json).',
      downstream: 'Stage 6: Motion Planning and Stage 7: Motion Animation (scenes draw the assets), Stage 12: Final QC (provenance and rights review).',
      architectureRole: 'One agent for the whole stage; search, capture/clip preparation and validation are modules of VIDEO_ENGINE/stages/asset_collection.py, not agents.'
    },
    whatItDoes: {
      summary: 'Plans which scenes need real media, searches licensed providers, downloads or prepares the chosen photo or clip, validates it and writes the manifest.',
      implementedResponsibilities: [
        'One LLM planner call per project: which scenes need a photo or clip, with English queries (an empty list is valid)',
        'Provider search with a 24 h query cache: Wikimedia Commons and NASA without keys; Pexels and Pixabay when their API keys are set',
        'Rights classes per item: A known free, C not established (flagged for the human Final QC), D no licence (never downloaded)',
        'Photo validation (decodes, size, SHA-256 and perceptual-hash duplicate check) and video clips trimmed and scaled to the canvas by ffmpeg',
        'assets_manifest.json with source URL, licence, attribution, hash and authenticity "real" for every asset; credits.json'
      ],
      productionReadyFeatures: [
        'Fail-closed LLM review of the stage and a stage artifact contract',
        'A requirement that cannot be met falls back to the scene\'s generated graphics (recorded); must_be_real fails the stage with the exact cause'
      ]
    },
    howItWorks: {
      summary: 'Plan requirements (LLM) -> search + cache -> one ranking call -> fetch, validate, record -> manifest -> LLM review.',
      stepByStepFlow: [
        { step: 1, title: 'Plan requirements', detail: 'The LLM reads each scene\'s meaning and narration and lists only scenes that need real media.', type: 'llm' },
        { step: 2, title: 'Search', detail: 'Providers are queried (cached 24 h per kind, query and aspect); alternative queries are tried when there are too few usable results.', type: 'external' },
        { step: 3, title: 'Choose', detail: 'One LLM ranking call over the top candidates; the providers\' own ranking when the LLM is unavailable.', type: 'llm' },
        { step: 4, title: 'Fetch and validate', detail: 'Photos are downloaded from permitted hosts; for clips ffmpeg seeks into the permitted URL and writes only the needed seconds.', type: 'deterministic' },
        { step: 5, title: 'Record', detail: 'Manifest, credits and the review payload are written atomically.', type: 'deterministic' }
      ],
      concurrencyAndCaching: 'Query cache across projects (24 h); a manifest whose scenes are unchanged and whose files are intact is reused without any search, download or LLM call.',
      retryLogic: 'A failing candidate is skipped for the next one; a provider outage is not cached; the orchestrator\'s bounded stage retry applies.'
    },
    inputsDependencies: {
      inputs: [
        { name: 'scene_plan.json', required: true, format: 'JSON', description: 'Scene ids, times and English meaning', pathExample: 'projects/<pid>/scene_plan.json' },
        { name: 'visual_planning.json', required: false, format: 'JSON', description: 'English narration per scene', pathExample: 'projects/<pid>/visual_planning.json' }
      ],
      externalTools: ['ffmpeg / ffprobe', 'Wikimedia Commons API', 'NASA media API', 'Pexels API (key)', 'Pixabay API (key)'],
      systemDependencies: ['LLM gateway', 'Pillow']
    },
    outputsSideEffects: {
      outputs: [
        { name: 'asset_requirements.json', format: 'JSON', description: 'What the planner asked for', pathExample: 'projects/<pid>/asset_requirements.json', consumers: ['llm_review', 'asset_collection'] },
        { name: 'assets_manifest.json', format: 'JSON', description: 'Every collected asset with provenance, rights and scene assignment', pathExample: 'projects/<pid>/assets_manifest.json', consumers: ['motion_animation', 'render_video', 'final_qc'] },
        { name: 'assets/collected/*', format: 'JPEG/PNG/MP4', description: 'The photos and prepared clips', pathExample: 'projects/<pid>/assets/collected/<id>.jpg', consumers: ['render_video'] }
      ],
      sideEffects: ['Copies assets to VIDEO_ENGINE/remotion/public/projects/<pid>/assets at render time', 'Appends to credits.json'],
      errorStates: ['Planner LLM unusable', 'must_be_real requirement without an acceptable asset', 'ffmpeg missing']
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'fast_structured (planner, ranking); reasoning_review (stage review)',
      promptStrategy: 'Scene text is treated as untrusted data; JSON-only answers; at most 8 requirements and 2 per scene.',
      fallbackStrategy: 'Ranking falls back to the providers\' rights/size order; the planner has no fallback (fail-closed).',
      deterministicGuardrails: ['Host allowlist for downloads', 'Licence class rules', 'Hash and perceptual-hash duplicate checks', 'Artifact contract with hash verification'],
      purelyDeterministicParts: ['Search, caching, download, decode checks, ffmpeg trimming, manifest writing']
    },
    currentCapabilities: [
      { name: 'Requirement planning', status: 'VERIFIED WORKING', description: 'The planner picked 2 of 3 scenes and left an abstract one alone in a live run.', evidence: 'tests/test_asset_collection.py; live run with the real LLM' },
      { name: 'Photos from Wikimedia Commons', status: 'VERIFIED WORKING', description: 'Real downloads with licence and attribution.', evidence: 'live run; tests/test_stock.py' },
      { name: 'Video clips', status: 'VERIFIED WORKING', description: 'A 475 s Wikimedia clip became a 6 s 1080p clip (0.48 MB) by ffmpeg seeking into the transcode.', evidence: 'live run; test_a_video_is_trimmed_scaled_to_the_canvas_and_stripped_of_sound' },
      { name: 'Reference page captures', status: 'VERIFIED WORKING', description: 'A real headless browser captured the Mount Everest infobox from Wikipedia (https only, allowlisted hosts, robots.txt honoured).', evidence: 'tests/test_web_capture.py; live run' },
      { name: 'Pexels and Pixabay', status: 'PARTIALLY IMPLEMENTED', description: 'Adapters are tested with a faked network only; no API keys were available.', evidence: 'tests/test_stock.py' }
    ],
    whatItDoesNotDo: ['No news-site screenshots and no general web search', 'No downloading of YouTube or other sources that forbid it', 'Never presents generated media as real'],
    missingCapabilities: [
      { title: 'News and general web search', status: 'NOT IMPLEMENTED', gapDescription: 'Finding a news article needs a web search API (none is configured); page capture is limited to Wikipedia and a short list of official reference hosts.', impact: 'News-style evidence is not collected.' }
    ],
    validationTesting: {
      validationLogic: ['Stage artifact contract', 'Stage LLM review (fail-closed)', 'Final QC provenance check'],
      testFiles: ['tests/test_asset_collection.py', 'tests/test_stock.py', 'SYSTEM/agents/video_generation_agents/asset_collection/tests/test_agent.py'],
      failureModesAndRecovery: ['A damaged or changed asset file fails the contract and Final QC', 'An unfulfilled optional requirement falls back to generated graphics']
    },
    improvementOpportunities: [
      { priority: 'MEDIUM', title: 'Web capture', currentLimitation: 'No screenshots', desiredBehavior: 'Capture a specific section of a page with source and date', implementationGap: 'Search API and browser automation', dependencies: 'Playwright runtime, a search provider' }
    ],
    sourceEvidence: {
      primaryFiles: ['VIDEO_ENGINE/stages/asset_collection.py', 'VIDEO_ENGINE/stages/stock.py'],
      supportingFiles: ['SYSTEM/agents/video_generation_agents/asset_collection/agent.py', 'SYSTEM/core/artifact_contracts.py'],
      classesAndFunctions: ['asset_collection.run', 'asset_collection.check_assets', 'stock.search'],
      testFiles: ['tests/test_asset_collection.py']
    }
  },

  // 3. VISUAL PLANNING (visual_planning / planning)
  // =========================================================================
  planning: {
    agentId: 'visual_planning',
    stageId: 'planning',
    name: 'Visual Planning Agent',
    role: 'Cinematic Concept Framing, Bilingual Translation & Prompt Engineering',
    category: 'visual',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 3 • SKILL FACTORY INTEGRATED',
    overview: {
      purpose: 'Translates vernacular Telugu scene narration into rich, cinematic visual concepts, image synthesis prompts, camera angles, lighting instructions, color palettes, and word-level semantic animations.',
      problemSolved: 'Transforms literal voice text into dynamic, metaphors-rich visual storytelling while preventing repetitive scene staging and generic stock photo imagery.',
      position: 'Stage 3 (Follows Scene Segmentation).',
      upstream: 'Stage 2: Scene Segmentation (scene_segmentation.json).',
      downstream: 'Stage 4: Motion Planning (motion_planning) and asset collection/generation tools.',
      architectureRole: 'Art director and visual strategist that equips every scene with a cohesive artistic vision, color identity, and kinetic typography plan.'
    },
    whatItDoes: {
      summary: 'Leverages 6 specialized skills via the Skill Factory, invokes LLM with Pydantic schemas, enforces shot variety (wide/medium/closeup), and maps keywords to word animations.',
      implementedResponsibilities: [
        'Bilingual translation of Telugu narration into English visual descriptors preserving cultural nuance',
        'Selection of cinematic camera framing (wide establishing, dynamic tracking, macro closeup, low angle)',
        'Assignment of mood lighting (golden hour, neon cyberpunk, dramatic rim light, soft studio)',
        'Selection of harmonious color palettes with hex color definitions',
        'Assignment of word-level semantic animations (kinetic bounce, color highlight, scale-up, glow)',
        'Enforcement of scene variety pacing (prohibits identical camera angles in consecutive scenes)',
        'Dynamic integration with 6 registered skills from the Skill Factory library',
        'Generation of comprehensive visual_plan.json matching 1:1 with segmented scenes'
      ],
      productionReadyFeatures: [
        'Multi-skill capability discovery via Capability Finder Agent',
        'Structured Pydantic schema validation preventing malformed LLM outputs',
        'Consecutive angle de-duplication heuristic',
        'Rich UI Visual Scenes & Plan tab with copy-ready prompt cards'
      ],
      experimentalFeatures: [
        'Automated character face-consistency seed locking across sequential scenes'
      ]
    },
    howItWorks: {
      summary: 'Loads scene_segmentation.json, queries Skill Factory for registered visual skills, constructs system prompt with framing constraints, executes LLM generation, validates Pydantic schema, and saves visual_plan.json.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Scene Ingestion & Skill Discovery',
          detail: 'Loads scene_segmentation.json and queries Capability Finder for visual.scene_planning, visual.cinematic_composition, and visual.word_semantic_animation skills.',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'Bilingual Translation & Concept Synthesis',
          detail: 'Sends scene text to LLM Gateway to generate English visual metaphors, character actions, and environmental context.',
          type: 'llm'
        },
        {
          step: 3,
          title: 'Cinematic Framing & Shot Variety Pacing',
          detail: 'Applies variety rules ensuring adjacent scenes alternate between wide establishing shots and medium/closeup perspectives.',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'Word Semantic Animation Mapping',
          detail: 'Maps emphasized spoken words to kinetic visual triggers (e.g. bold keywords trigger bounce, action verbs trigger scale).',
          type: 'deterministic'
        },
        {
          step: 5,
          title: 'Pydantic Validation & Emission',
          detail: 'Validates complete visual plan against VisualPlanModel schema and writes projects/{project_id}/visual_plan.json.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Batch prompt generation processes all scenes in single structured LLM call with fallback to scene-by-scene if token window exceeded.',
      retryLogic: 'If LLM output fails schema validation, re-prompts with error diff; falls back to deterministic cinematic presets on second failure.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'scene_segmentation.json',
          required: true,
          format: 'JSON (array of scenes with text and timing)',
          description: 'Master scene index from Stage 2.',
          pathExample: 'projects/{project_id}/scene_segmentation.json'
        },
        {
          name: 'transcript.json',
          required: false,
          format: 'JSON (word-level timestamps)',
          description: 'Used for exact word alignment in semantic typography mapping.',
          pathExample: 'projects/{project_id}/transcript.json'
        }
      ],
      externalTools: ['LLM Gateway (Claude 3.5 Sonnet / GPT-4o)', 'Pydantic validation library'],
      systemDependencies: ['Category Skill Library', 'Capability Finder Agent']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'visual_plan.json',
          format: 'JSON (array of scene plans with image_prompt, camera_angle, lighting, color_palette, word_animations)',
          description: 'Comprehensive artistic and kinetic blueprint for the video.',
          pathExample: 'projects/{project_id}/visual_plan.json',
          consumers: ['motion_planning', 'motion_animation', 'timeline_build', 'final_qc']
        }
      ],
      sideEffects: [
        'Updates projects/{project_id}/pipeline_state.json stage status',
        'Populates Visual Scenes tab in StageDrawer UI'
      ],
      errorStates: [
        'Missing scene_segmentation.json',
        'LLM API failure / quota exceeded',
        'Schema parsing error in LLM response'
      ]
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'Claude 3.5 Sonnet / GPT-4o',
      temperature: '0.6 (balanced for artistic creativity while respecting constraints)',
      promptStrategy: 'Instructs model as an expert Hollywood cinematographer and art director to describe concrete visual scenes with lighting, depth, and textures.',
      fallbackStrategy: 'Deterministic template library supplies high-quality cinematic defaults if LLM Gateway is offline.',
      deterministicGuardrails: [
        'Output parsed through strict Pydantic schemas; missing fields are automatically backfilled',
        'Camera angle variety enforced: identical angles across adjacent scenes are automatically varied',
        'Word animation timings strictly locked to Whisper word timestamps'
      ],
      purelyDeterministicParts: [
        'Camera angle variety validation',
        'Color palette hex validation',
        'Word timestamp binding'
      ]
    },
    currentCapabilities: [
      {
        name: 'Skill Factory Integration',
        status: 'VERIFIED WORKING',
        description: 'Dynamically discovers and executes 6 registered skills for composition and pacing.',
        evidence: 'Verified in tests/test_visual_planning_skills_and_word_animation.py (18/18 tests pass)'
      },
      {
        name: 'Cinematic shot variety enforcement',
        status: 'VERIFIED WORKING',
        description: 'Prevents repetitive camera framing across consecutive scenes.',
        evidence: 'Tested in tests/test_category_skill_library.py'
      },
      {
        name: 'Word-level kinetic animation mapping',
        status: 'VERIFIED WORKING',
        description: 'Maps spoken words to specific kinetic spring and color animations.',
        evidence: 'Verified in VIDEO_ENGINE/stages/visual_planning.py'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT render raster images or call Midjourney/Stable Diffusion directly (prompts are prepared for asset generation)',
      'Does NOT synthesize Remotion TSX code (handled by Motion Animation)',
      'Does NOT change audio narration or scene boundary timings'
    ],
    missingCapabilities: [
      {
        title: 'Direct Local Image Synthesis Dispatcher',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Generates image prompts in visual_plan.json but requires external trigger to render image files.',
        impact: 'Asset generation must be invoked by operator or downstream script.',
        plannedResolution: 'Add direct ComfyUI / SD-XL / Flux API connector in visual_plan stage.'
      },
      {
        title: 'Persistent Character Seed Lock',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Does not enforce identical seed or LoRA character tokens across all scenes.',
        impact: 'Characters may have minor stylistic variations across different scenes.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Asserts exact 1:1 match between visual plan scenes and scene segmentation scenes',
        'Asserts non-empty image_prompt strings (> 20 characters)',
        'Asserts valid camera_angle and lighting enum values'
      ],
      testFiles: [
        'tests/test_visual_planning_skills_and_word_animation.py',
        'tests/test_category_skill_library.py',
        'tests/test_stage2_agent_skills_discovery.py'
      ],
      failureModesAndRecovery: [
        'LLM generates unparseable markdown: Strips triple-backticks and extracts JSON payload.',
        'Missing scene prompt: Synthesizes fallback prompt from scene narration text.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'HIGH',
        title: 'ComfyUI / Flux Local Synthesis Pipeline',
        currentLimitation: 'Prompts generated but images not rendered automatically.',
        desiredBehavior: 'Directly dispatch generated prompts to local ComfyUI instance to produce 4K background stills.',
        implementationGap: 'WebSocket client connector to local ComfyUI server.',
        dependencies: 'ComfyUI or Replicate API'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/visual_planning/agent.py',
        'VIDEO_ENGINE/stages/visual_planning.py',
        'VIDEO_ENGINE/stages/visual_plan.py'
      ],
      supportingFiles: [
        'VIDEO_ENGINE/stages/promptgen.py',
        'SYSTEM/agents/capability_finder/agent.py',
        'SYSTEM/agents/skill_factory/agent.py'
      ],
      classesAndFunctions: [
        'VisualPlanningAgent.execute()',
        'generate_visual_plan()',
        'enforce_scene_variety()',
        'apply_word_semantic_animations()'
      ],
      testFiles: [
        'tests/test_visual_planning_skills_and_word_animation.py',
        'tests/test_category_skill_library.py'
      ]
    }
  },

  // =========================================================================
  // 4. MOTION PLANNING (motion_planning / motion_plan)
  // =========================================================================
  motion_plan: {
    agentId: 'motion_planning',
    stageId: 'motion_plan',
    name: 'Motion Planning Agent',
    role: 'Kinetic Choreography, Spatial Safe-Area Math & Collision Avoidance',
    category: 'motion',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 4 • GEOMETRIC ENGINE',
    overview: {
      purpose: 'Plans the frame-by-frame spatial choreography of text overlays, stickers, callouts, and background visual elements, enforcing title/action safe areas and calculating spring physics curves.',
      problemSolved: 'Prevents on-screen text collisions, overlapping graphics, unreadable fonts, and clipping outside mobile/TV safe zones (80%/90% margin rules).',
      position: 'Stage 4 (Follows Visual Planning).',
      upstream: 'Stage 3: Visual Planning (visual_plan.json) and Stage 2: Scene Segmentation.',
      downstream: 'Stage 5: Motion Animation (motion_animation), which compiles the motion plan into React TSX code.',
      architectureRole: 'Spatial layout mathematician and choreography planner that ensures visual elements move with natural physics without clutter.'
    },
    whatItDoes: {
      summary: 'Converts timing into frame numbers at target FPS, calculates 2D bounding boxes, executes collision avoidance, and configures Remotion spring parameters.',
      implementedResponsibilities: [
        'Conversion of timestamp seconds to exact frame indices at 30 FPS',
        'Calculation of title safe (80%) and action safe (90%) bounding margins for 16:9 and 9:16 aspect ratios',
        'Execution of 2D bounding box intersection solver to prevent overlapping text layers',
        'Assignment of Remotion spring physics parameters (damping, stiffness, mass, overshootClamping)',
        'Trajectory planning for entry animations (slide-up, pop-in, fade, wipe)',
        'Calculation of scene transition handles (cut, crossfade, whip pan)',
        'Generation of motion_plan.json detailing element coordinates, depths (Z-index), and keyframe triggers'
      ],
      productionReadyFeatures: [
        'Deterministic collision avoidance solver',
        'Dual aspect ratio support (16:9 widescreen landscape & 9:16 vertical shorts)',
        'UI Motion Scenes & Plan inspector with live coordinate preview'
      ],
      experimentalFeatures: [
        '3D depth-plane camera parallax choreography'
      ]
    },
    howItWorks: {
      summary: 'Reads visual_plan.json, maps words and graphics to spatial slots, checks bounding box collisions, assigns spring curves, and writes motion_plan.json.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Plan Ingestion & Frame Conversion',
          detail: 'Loads visual_plan.json and converts time intervals to integer frame counts: frame = round(seconds * 30).',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'Safe Area Boundary Setup',
          detail: 'Calculates viewport boundaries: width=1920, height=1080 (or 1080x1920), safe_x=[192, 1728], safe_y=[108, 972].',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'Spatial Slot Allocation & Collision Solving',
          detail: 'Places title, subtitle, and graphic callouts into non-overlapping vertical and horizontal zones using 2D box math.',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'Spring Physics Curve Configuration',
          detail: 'Assigns Remotion spring parameters: damping=12, stiffness=100, mass=0.8 for snappy, organic kinetic motion.',
          type: 'deterministic'
        },
        {
          step: 5,
          title: 'Artifact Emission',
          detail: 'Serializes motion structure to projects/{project_id}/motion_plan.json.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Fast mathematical solver executing in < 100ms; results cached per visual plan hash.',
      retryLogic: 'If elements collide, adjusts vertical offsets iteratively in 20px increments until collision is cleared.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'visual_plan.json',
          required: true,
          format: 'JSON (visual concepts, word animations)',
          description: 'Artistic blueprint from Stage 3.',
          pathExample: 'projects/{project_id}/visual_plan.json'
        },
        {
          name: 'scene_segmentation.json',
          required: true,
          format: 'JSON (scene timings)',
          description: 'Exact scene start and end times.',
          pathExample: 'projects/{project_id}/scene_segmentation.json'
        }
      ],
      externalTools: ['Python math engine', 'Remotion spatial solver'],
      systemDependencies: ['None']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'motion_plan.json',
          format: 'JSON (scene frames, element coordinates, spring parameters, safe zone margins)',
          description: 'Exact spatial and timing specification for code generation.',
          pathExample: 'projects/{project_id}/motion_plan.json',
          consumers: ['motion_animation', 'motion_validation', 'timeline_build']
        }
      ],
      sideEffects: [
        'Updates pipeline_state.json',
        'Populates Motion Scenes tab in StageDrawer UI'
      ],
      errorStates: [
        'Too many simultaneous text elements exceeding viewport capacity',
        'Missing visual plan input'
      ]
    },
    llmDecisionMaking: {
      usesLlm: false,
      modelOrProfile: 'Purely Deterministic Mathematical Engine (No LLM in core path)',
      promptStrategy: 'None; layout calculations are 100% geometric and rule-based.',
      fallbackStrategy: 'Deterministic default centered layout if complex layout calculation fails.',
      deterministicGuardrails: [
        '100% mathematical bounding box calculation guarantees zero LLM hallucination',
        'Frame numbers strictly bound to integer intervals at 30fps',
        'Safe zone margins hardcoded according to SMPTE video standards'
      ],
      purelyDeterministicParts: [
        'Frame calculation',
        'Safe-area margin enforcement',
        '2D collision resolution algorithm',
        'Spring physics constant assignment'
      ]
    },
    currentCapabilities: [
      {
        name: 'Safe area margin enforcement',
        status: 'VERIFIED WORKING',
        description: 'Enforces 80% title safe and 90% action safe boundaries across landscape and portrait.',
        evidence: 'Verified in VIDEO_ENGINE/stages/motion_planning.py'
      },
      {
        name: 'Collision avoidance layout solver',
        status: 'VERIFIED WORKING',
        description: 'Automatically shifts overlapping text boxes to separate vertical lanes.',
        evidence: 'Tested in tests/test_motion_only_mode.py'
      },
      {
        name: 'UI Motion Scenes & Plan inspector',
        status: 'VERIFIED WORKING',
        description: 'Visual breakdown of elements, sequence order, and raw JSON view.',
        evidence: 'Implemented in StageDrawer.tsx lines 1500-2100'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT generate React TSX code or write files to VIDEO_ENGINE/remotion/src/ (handled by Stage 5)',
      'Does NOT render video frames (handled by Stage 9)',
      'Does NOT synthesize new words or modify transcript text'
    ],
    missingCapabilities: [
      {
        title: 'Audio Amplitude Reactive Curves',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Spring curves use pre-calculated physics rather than reacting dynamically to vocal volume peaks.',
        impact: 'Motion intensity does not scale higher when voice speaks louder.',
        plannedResolution: 'Feed RMS volume envelope into spring stiffness parameter.'
      },
      {
        title: '3D Camera Depth Choreography',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Limited to 2D multi-layer parallax Z-ordering.',
        impact: 'Full 3D orbit camera maneuvers not yet automated.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Asserts all elements lie strictly within safe area bounds',
        'Asserts zero bounding box overlap between text layers',
        'Asserts sum of scene frame durations equals project total frames'
      ],
      testFiles: [
        'tests/test_motion_only_mode.py',
        'tests/test_motion_codegen_and_concurrency.py'
      ],
      failureModesAndRecovery: [
        'Text overflow: Automatically scales down font size by 15% and re-runs collision check.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'MEDIUM',
        title: 'Audio Waveform Amplitude Reactivity',
        currentLimitation: 'Static spring curves.',
        desiredBehavior: 'Scale kinetic typography spring bounce based on instant vocal volume.',
        implementationGap: 'Extract frame-by-frame RMS volume from audio.wav and export as curve track.',
        dependencies: 'scipy / numpy audio analysis'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/motion_planning/agent.py',
        'VIDEO_ENGINE/stages/motion_planning.py',
        'VIDEO_ENGINE/stages/motion_scenes.py'
      ],
      supportingFiles: [
        'VIDEO_ENGINE/stages/motion_checks.py',
        'UI/backend/motion_planning.py'
      ],
      classesAndFunctions: [
        'MotionPlanningAgent.execute()',
        'plan_motion()',
        'solve_layout_collisions()',
        'calculate_safe_zones()'
      ],
      testFiles: [
        'tests/test_motion_only_mode.py',
        'tests/test_motion_codegen_and_concurrency.py'
      ]
    }
  },

  // =========================================================================
  // 5. MOTION GENERATION (motion_animation / motion_gen)
  // =========================================================================
  motion_gen: {
    agentId: 'motion_animation',
    stageId: 'motion_gen',
    name: 'Motion Animation Agent',
    role: 'React/TSX Code Generation & Remotion Component Staging',
    category: 'motion',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 5 • REACT COMPONENT CODEGEN',
    overview: {
      purpose: 'Synthesizes standalone, fully-typed React TypeScript (.tsx) animation components for every scene in the project and stages them in the Remotion workspace.',
      problemSolved: 'Replaces rigid pre-rendered video templates with dynamically generated, programmable code components capable of word-level kinetic animations and infinite scalability.',
      position: 'Stage 5 (Follows Motion Planning).',
      upstream: 'Stage 4: Motion Planning (motion_plan.json) and Stage 3: Visual Planning.',
      downstream: 'Stage 6: Motion Validation (motion_validation) and Stage 7: Timeline Build.',
      architectureRole: 'Software engineer that writes clean, executable Remotion React code components adhering to strict TypeScript standards.'
    },
    whatItDoes: {
      summary: 'Generates Scene_{i}.tsx components utilizing Remotion hooks (useCurrentFrame, interpolate, spring), performs AST validation, and executes auto-repair loops on compiler errors.',
      implementedResponsibilities: [
        'Synthesis of executable React TSX files (VIDEO_ENGINE/remotion/src/scenes/Scene_{i}.tsx)',
        'Integration of Remotion APIs: useCurrentFrame, useVideoConfig, spring, interpolate, Sequence, AbsoluteFill',
        'Word-level kinetic typography rendering with spring animation triggers',
        'AST security filtering to block unauthorized JavaScript APIs (eval, document, fetch)',
        'TypeScript compiler verification (tsc --noEmit) on all generated components',
        'Automated LLM code repair loop when TypeScript syntax or typecheck errors occur',
        'Generation of motion_generation_report.json recording code metrics and syntax status'
      ],
      productionReadyFeatures: [
        'Automated TypeScript syntax and typecheck validation',
        'Babel AST security policy enforcement',
        'Autonomous error diagnosis and one-shot repair loop'
      ],
      experimentalFeatures: [
        'WebGL and Three.js 3D canvas shader generation'
      ]
    },
    howItWorks: {
      summary: 'Consumes motion_plan.json, generates TSX component structure, injects spring animations, writes files, validates with TypeScript compiler, and runs LLM repair if needed.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Plan Ingestion & Template Selection',
          detail: 'Loads motion_plan.json and selects appropriate animation component structure (kinetic text, image pan/zoom, split screen).',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'TSX Code Generation',
          detail: 'Generates TypeScript React code with Remotion spring hooks, word-level keyframes, and inline styles.',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'AST Security Audit',
          detail: 'Scans generated TSX AST to confirm absence of unsafe APIs (eval, window, network calls, localStorage).',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'TypeScript Typecheck & Verification',
          detail: 'Runs tsc --noEmit against generated scene file to verify import resolution and type correctness.',
          type: 'deterministic'
        },
        {
          step: 5,
          title: 'Autonomous Self-Healing Loop',
          detail: 'If tsc reports errors, passes compiler error back to LLM to produce a targeted patch, then re-verifies.',
          type: 'llm'
        },
        {
          step: 6,
          title: 'Artifact Emission',
          detail: 'Saves Scene_{i}.tsx to VIDEO_ENGINE/remotion/src/scenes/ and emits motion_generation_report.json.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Generates scenes in parallel workers; reuses unchanged scene files across re-runs.',
      retryLogic: 'Max 3 retry attempts on compiler failure before raising a targeted blocker alert.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'motion_plan.json',
          required: true,
          format: 'JSON (coordinates, timings, spring parameters)',
          description: 'Spatial and timing blueprint from Stage 4.',
          pathExample: 'projects/{project_id}/motion_plan.json'
        },
        {
          name: 'visual_plan.json',
          required: true,
          format: 'JSON (concepts, colors, typography styles)',
          description: 'Visual identity blueprint from Stage 3.',
          pathExample: 'projects/{project_id}/visual_plan.json'
        }
      ],
      externalTools: ['TypeScript compiler (tsc)', 'Babel parser (@babel/parser)', 'Node.js', 'LLM Gateway (for auto-repair)'],
      systemDependencies: ['Remotion packages (@remotion/core, @remotion/shapes)']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'Scene_{i}.tsx',
          format: 'TypeScript JSX (.tsx React component file)',
          description: 'Standalone executable Remotion scene component.',
          pathExample: 'VIDEO_ENGINE/remotion/src/scenes/Scene_1.tsx',
          consumers: ['motion_validation', 'timeline_build', 'render_video']
        },
        {
          name: 'motion_generation_report.json',
          format: 'JSON (codegen status, AST score, lines of code, validation verdict)',
          description: 'Detailed report of code generation health.',
          pathExample: 'projects/{project_id}/motion_generation_report.json',
          consumers: ['motion_validation', 'final_qc']
        }
      ],
      sideEffects: [
        'Writes .tsx files into VIDEO_ENGINE/remotion/src/scenes/ directory',
        'Updates pipeline_state.json'
      ],
      errorStates: [
        'Persistent TypeScript compile error after 3 auto-repair attempts',
        'AST security violation (detected forbidden API call)'
      ]
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'Claude 3.5 Sonnet (for bespoke layout generation and auto-repair)',
      temperature: '0.1 (strict precision for valid code generation)',
      promptStrategy: 'Provides Remotion API reference and exact schema of required component props; instructs model to return raw TSX code only.',
      fallbackStrategy: 'Falls back to pre-tested deterministic preset TSX templates if LLM codegen fails typecheck.',
      deterministicGuardrails: [
        'All LLM code is validated by tsc --noEmit before acceptance',
        'AST security filter blocks dynamic execution (eval, new Function, network fetching)',
        'Component must export valid React.FC matching Remotion composition signature'
      ],
      purelyDeterministicParts: [
        'AST security parsing',
        'TypeScript compiler execution',
        'Deterministic template fallback generator'
      ]
    },
    currentCapabilities: [
      {
        name: 'Executable React TSX codegen',
        status: 'VERIFIED WORKING',
        description: 'Synthesizes complete, runnable Remotion components with hooks and spring curves.',
        evidence: 'Verified in tests/test_motion_codegen.py'
      },
      {
        name: 'AST Security Scanning',
        status: 'VERIFIED WORKING',
        description: 'Blocks malicious or unsafe JavaScript APIs from entering the render pipeline.',
        evidence: 'Implemented in VIDEO_ENGINE/stages/motion_gen_rules.py'
      },
      {
        name: 'Autonomous compiler error recovery',
        status: 'VERIFIED WORKING',
        description: 'Feeds tsc compiler errors back to LLM for one-shot syntax repair.',
        evidence: 'Verified in tests/test_motion_codegen_and_concurrency.py'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT render video frames (handled by Stage 9 Render Video)',
      'Does NOT assemble the multi-track master timeline (handled by Stage 7 Timeline Build)',
      'Does NOT alter audio timing or narration words'
    ],
    missingCapabilities: [
      {
        title: 'WebGL / Three.js Canvas Shader Codegen',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Currently generates 2D HTML/SVG/CSS Remotion components. Complex 3D shaders require custom integration.',
        impact: '3D particle fields and 3D terrain meshes cannot be synthesized on-the-fly.',
        plannedResolution: 'Add Three.js Fiber scene templates to component generator.'
      },
      {
        title: 'Interactive Visual Canvas Drag-and-Drop Sync',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Code is generated programmatically; visual changes must be recompiled.',
        impact: 'Live two-way binding between GUI drag-and-drop and TSX source code is one-way.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Runs npx tsc --noEmit to verify zero compiler errors',
        'Asserts component exports default or named React component',
        'Verifies all imported assets exist in filesystem'
      ],
      testFiles: [
        'tests/test_motion_codegen.py',
        'tests/test_motion_codegen_and_concurrency.py',
        'tests/test_motion_only_mode.py'
      ],
      failureModesAndRecovery: [
        'TypeScript error: Passes error trace to LLM repair loop; if still failing, uses fallback preset.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'HIGH',
        title: 'Component AST Tree-Shaking & Bundle Optimization',
        currentLimitation: 'Each scene is compiled independently without cross-scene asset deduping.',
        desiredBehavior: 'Share common styled components and keyframe helpers across all scenes.',
        implementationGap: 'Extract shared Remotion components into a shared module.',
        dependencies: 'remotion bundling pipeline'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/motion_animation/agent.py',
        'VIDEO_ENGINE/stages/motion_animation.py',
        'VIDEO_ENGINE/stages/motion_generation.py'
      ],
      supportingFiles: [
        'VIDEO_ENGINE/stages/motion_gen_rules.py',
        'VIDEO_ENGINE/stages/motion_autofix.py',
        'UI/backend/motion_animation.py'
      ],
      classesAndFunctions: [
        'MotionAnimationAgent.execute()',
        'generate_motion_code()',
        'validate_tsx_ast()',
        'repair_tsx_syntax()'
      ],
      testFiles: [
        'tests/test_motion_codegen.py',
        'tests/test_motion_codegen_and_concurrency.py'
      ]
    }
  },

  // =========================================================================
  // 6. MOTION VALIDATION (motion_timeline_validation / motion_validation)
  // =========================================================================
  motion_validation: {
    agentId: 'motion_timeline_validation',
    stageId: 'motion_validation',
    name: 'Motion Validation Agent',
    role: '12 Technical Validation Rules, Resource Verification & Preview Stills',
    category: 'motion',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 6 • 12-RULE GATEKEEPER',
    overview: {
      purpose: 'Applies 12 strict technical validation rules across generated React components, verifies asset availability in the resource library, calculates color contrast, and renders preview verification stills.',
      problemSolved: 'Catches layout defects, unreadable fonts, missing assets, and runtime crashes BEFORE starting the master timeline build or full-length video render.',
      position: 'Stage 6 (Follows Motion Generation).',
      upstream: 'Stage 5: Motion Generation (generated TSX files) and Stage 4: Motion Planning.',
      downstream: 'Stage 7: Timeline Build (timeline_build).',
      architectureRole: 'Pre-flight technical gatekeeper that guarantees no broken assets, syntax errors, or WCAG contrast violations reach the master composition.'
    },
    whatItDoes: {
      summary: 'Executes 12 technical validation checks, tests local resource paths, renders sample frame stills in headless Chrome, and produces motion_validation_report.json.',
      implementedResponsibilities: [
        'Execution of 12 technical rules: TypeScript check, safe area, font size, container clipping, contrast ratio, asset existence, import whitelist, API safety, duration match, framerate, Telugu Unicode glyphs, and memory bounds',
        'WCAG AA color contrast calculation: (L1 + 0.05) / (L2 + 0.05) >= 4.5:1',
        'Local resource library audit verifying all image/video/font assets exist on disk',
        'Telugu Unicode rendering check confirming absence of tofu / missing font glyphs',
        'Headless Chromium still rendering of keyframe verification frames (t=0, t=50%, t=100%)',
        'Automated generation of motion_validation_report.json with pass/fail verdict for all 12 rules'
      ],
      productionReadyFeatures: [
        'Comprehensive 12-rule technical verification engine',
        'Mathematical WCAG AA contrast ratio evaluator',
        'Keyframe preview still capture via Remotion CLI'
      ],
      experimentalFeatures: [
        'Automated perceptual image quality scoring (SSIM / PSNR)'
      ]
    },
    howItWorks: {
      summary: 'Loads generated TSX scene files, applies AST rule engine, inspects resource filesystem, runs headless still capture, and emits comprehensive validation report.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Component & Asset Ingestion',
          detail: 'Scans VIDEO_ENGINE/remotion/src/scenes/ for generated TSX files and indexes all referenced file paths.',
          type: 'deterministic'
        },
        {
          step: 2,
          title: '12-Rule Technical Audit',
          detail: 'Applies 12 deterministic rules covering syntax, safe zones, font sizes, contrast ratios, and security.',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'Resource Library Verification',
          detail: 'Verifies every referenced background, image, and font file exists and has non-zero byte size.',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'Headless Keyframe Still Capture',
          detail: 'Invokes Remotion still renderer in headless Chrome to generate sample frame captures of each scene.',
          type: 'external'
        },
        {
          step: 5,
          title: 'Report Emission',
          detail: 'Compiles all rule results into projects/{project_id}/motion_validation_report.json.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Rules run in parallel across all scenes; preview stills cached if scene TSX unchanged.',
      retryLogic: 'If a rule fails, triggers Motion Generation auto-fix; aborts after 2 failed validation cycles.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'Scene_{i}.tsx files',
          required: true,
          format: 'TypeScript JSX components',
          description: 'Generated components from Stage 5.',
          pathExample: 'VIDEO_ENGINE/remotion/src/scenes/Scene_1.tsx'
        },
        {
          name: 'motion_plan.json',
          required: true,
          format: 'JSON (coordinates and timings)',
          description: 'Expected bounding boxes and safe zones.',
          pathExample: 'projects/{project_id}/motion_plan.json'
        }
      ],
      externalTools: ['Headless Chromium / Puppeteer', 'Remotion CLI', 'Pillow / PIL', 'Python AST parser'],
      systemDependencies: ['Local font libraries with Telugu Unicode glyph support']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'motion_validation_report.json',
          format: 'JSON (12 rule results, scores, pass/fail status, warnings)',
          description: 'Definitive pre-flight technical health report.',
          pathExample: 'projects/{project_id}/motion_validation_report.json',
          consumers: ['timeline_build', 'timeline_approval', 'final_qc']
        },
        {
          name: 'Preview Stills',
          format: 'PNG images (keyframes at 0%, 50%, 100%)',
          description: 'Visual evidence of rendered scene appearance.',
          pathExample: 'projects/{project_id}/validation_previews/scene_1_mid.png',
          consumers: ['UI StageDrawer', 'final_qc']
        }
      ],
      sideEffects: [
        'Updates pipeline_state.json',
        'Blocks timeline build if any critical rule fails'
      ],
      errorStates: [
        'Missing asset file referenced in scene code',
        'Contrast ratio under 3:1 (unreadable text)',
        'TypeScript compilation failure'
      ]
    },
    llmDecisionMaking: {
      usesLlm: false,
      modelOrProfile: '100% Deterministic Rule Engine',
      promptStrategy: 'None; rules are strictly algorithmic, regex-based, and AST-driven.',
      fallbackStrategy: 'None; hard failures halt pipeline progression until fixed.',
      deterministicGuardrails: [
        '12 rules are mathematically and statically verifiable with zero ambiguity',
        'Missing asset detection directly tests filesystem existence'
      ],
      purelyDeterministicParts: [
        'All 12 rule checks',
        'WCAG contrast ratio calculation',
        'Filesystem existence verification',
        'Headless still capture execution'
      ]
    },
    currentCapabilities: [
      {
        name: '12 Technical Validation Rules',
        status: 'VERIFIED WORKING',
        description: 'Enforces syntax, security, contrast, safe zones, and font legibility.',
        evidence: 'Verified in VIDEO_ENGINE/stages/motion_validation_rules.py'
      },
      {
        name: 'Headless Preview Still Capture',
        status: 'VERIFIED WORKING',
        description: 'Renders real keyframe stills in Chromium to visually verify layout.',
        evidence: 'Implemented in VIDEO_ENGINE/stages/motion_validation_preview.py'
      },
      {
        name: 'Telugu Font Glyph Integrity Check',
        status: 'VERIFIED WORKING',
        description: 'Ensures Telugu script renders cleanly without missing glyph boxes.',
        evidence: 'Tested in tests/test_motion_checks.py'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT compile the final video timeline (handled by Stage 7)',
      'Does NOT render full video stream (handled by Stage 9)',
      'Does NOT bypass critical errors without explicit fix'
    ],
    missingCapabilities: [
      {
        title: 'Automated Aesthetic Visual Quality Scoring (NIMA / CLIP)',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Rules verify technical correctness (contrast, safe zone) but not aesthetic beauty.',
        impact: 'Technically valid scenes with poor visual composition will pass.',
        plannedResolution: 'Integrate lightweight CLIP aesthetic model score into validation report.'
      },
      {
        title: 'GPU Memory Leak Profiler',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Does not profile VRAM consumption of Chromium WebGL contexts during preview.',
        impact: 'Extremely heavy scenes might cause memory pressure during full render.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Verifies all 12 rules evaluate to PASS or WARNING',
        'Asserts zero critical errors before granting clearance',
        'Asserts preview stills exist and have non-zero file size'
      ],
      testFiles: [
        'tests/test_motion_validation_rules.py',
        'tests/test_motion_checks.py'
      ],
      failureModesAndRecovery: [
        'Missing image asset: Flags specific missing path in report and triggers fallback image substitution.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'MEDIUM',
        title: 'CLIP Aesthetic Visual Scoring',
        currentLimitation: 'Checks syntax and geometry, not visual beauty.',
        desiredBehavior: 'Score preview frame composition on 1-10 aesthetic scale.',
        implementationGap: 'Add ONNX runtime inference with mobile CLIP aesthetic weights.',
        dependencies: 'onnxruntime'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/motion_timeline_validation/agent.py',
        'VIDEO_ENGINE/stages/motion_validation.py',
        'VIDEO_ENGINE/stages/motion_validation_rules.py'
      ],
      supportingFiles: [
        'VIDEO_ENGINE/stages/motion_validation_preview.py',
        'VIDEO_ENGINE/stages/motion_checks.py',
        'UI/backend/motion_validation.py'
      ],
      classesAndFunctions: [
        'MotionValidationAgent.execute()',
        'validate_motion_rules()',
        'render_preview_stills()',
        'check_wcag_contrast()'
      ],
      testFiles: [
        'tests/test_motion_validation_rules.py',
        'tests/test_motion_checks.py'
      ]
    }
  },

  // =========================================================================
  // 7. TIMELINE BUILD (timeline_build / timeline)
  // =========================================================================
  timeline: {
    agentId: 'timeline_build',
    stageId: 'timeline',
    name: 'Timeline Build Agent',
    role: 'Multi-Track Composition, Frame Accounting & Audio Synchronization',
    category: 'assembly',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 7 • FRAME-ACCURATE COMPILER',
    overview: {
      purpose: 'Compiles individual validated scene components, narration audio, background score, subtitles, and overlays into a master, frame-accurate Remotion timeline (Root.tsx / Composition.tsx) matching audio duration exactly.',
      problemSolved: 'Eliminates audio-video desynchronization, frame drift, and missing scene sequences by locking all layers to exact frame numbers.',
      position: 'Stage 7 (Follows Motion Validation).',
      upstream: 'Stage 6: Motion Validation (validated scene components), Stage 1: Audio Analysis (audio.wav).',
      downstream: 'Stage 8: Timeline Approval (timeline_approval), which gates rendering.',
      architectureRole: 'Master assembler that synthesizes all project media tracks into an executable Remotion root composition.'
    },
    whatItDoes: {
      summary: 'Assembles multi-track Remotion composition, calculates total video frames from audio duration, binds Sequence blocks, generates timeline.json, and feeds the UI Frame-Accurate Visual Timeline.',
      implementedResponsibilities: [
        'Frame calculation based on master audio duration: total_frames = round(duration * 30)',
        'Zero-gap sequence assembly: end_frame(Scene[k]) strictly equals start_frame(Scene[k+1])',
        'Multi-track composition management: Visuals, Narration Audio, Subtitles, Kinetic Text, Background Music',
        'Compilation of VIDEO_ENGINE/remotion/src/Root.tsx and Composition.tsx master composition files',
        'Generation of timeline.json containing full track hierarchy, scene blocks, and frame intervals',
        'Supply of frame-accurate visual timeline data to the frontend TimelineBuildVisualView component'
      ],
      productionReadyFeatures: [
        'Mathematical zero-drift frame accounting',
        'Multi-track layer separation with audio waveform binding',
        'Interactive horizontal zoomable visual timeline UI with playhead and frame inspector'
      ],
      experimentalFeatures: [
        'Non-linear cross-dissolve transition frame overlapping'
      ]
    },
    howItWorks: {
      summary: 'Probes audio.wav for exact duration, reads validated scene TSX list, calculates frame boundaries, synthesizes Root.tsx, and writes timeline.json.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Master Audio Duration Lock',
          detail: 'Uses ffprobe to obtain exact audio duration down to millisecond accuracy and computes project total_frames.',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'Scene Frame Boundary Accounting',
          detail: 'Allocates consecutive frame intervals for each scene: start_frame[0]=0, end_frame[k]=start_frame[k]+duration_frames[k].',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'Multi-Track Layer Synthesis',
          detail: 'Creates track layers for Visual Media, Narration Audio, Subtitles, Kinetic Overlays, and Background Music.',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'Root Composition Compilation',
          detail: 'Generates VIDEO_ENGINE/remotion/src/Root.tsx referencing all Scene components inside Remotion <Composition> and <Sequence> elements.',
          type: 'deterministic'
        },
        {
          step: 5,
          title: 'Artifact Emission & UI Metadata',
          detail: 'Serializes projects/{project_id}/timeline.json consumed by both render engine and UI visual timeline view.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Compiles in < 200ms; reuses master composition if scenes and audio have not changed.',
      retryLogic: 'If total scene frames do not match audio frames, micro-adjusts the final scene frame bound to achieve exact equality.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'audio.wav',
          required: true,
          format: 'WAV audio file',
          description: 'Master voice narration audio providing absolute timeline duration.',
          pathExample: 'projects/{project_id}/audio.wav'
        },
        {
          name: 'Scene_{i}.tsx files',
          required: true,
          format: 'React TSX components',
          description: 'Validated scene components from Stage 5 and 6.',
          pathExample: 'VIDEO_ENGINE/remotion/src/scenes/Scene_1.tsx'
        },
        {
          name: 'motion_plan.json',
          required: true,
          format: 'JSON',
          description: 'Element timings and transitions.',
          pathExample: 'projects/{project_id}/motion_plan.json'
        }
      ],
      externalTools: ['Remotion composition compiler', 'FFprobe', 'Node.js'],
      systemDependencies: ['VIDEO_ENGINE/remotion/src/Root.tsx template']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'timeline.json',
          format: 'JSON (tracks, scenes, frame ranges, audio bindings, fps)',
          description: 'Master frame-accurate timeline data structure.',
          pathExample: 'projects/{project_id}/timeline.json',
          consumers: ['timeline_approval', 'render_video', 'final_qc', 'UI TimelineBuildVisualView']
        },
        {
          name: 'Root.tsx / Composition.tsx',
          format: 'TypeScript JSX (Remotion Root component)',
          description: 'Master entrypoint for Remotion bundling and rendering.',
          pathExample: 'VIDEO_ENGINE/remotion/src/Root.tsx',
          consumers: ['render_video']
        }
      ],
      sideEffects: [
        'Updates pipeline_state.json',
        'Populates UI Frame-Accurate Visual Timeline tab'
      ],
      errorStates: [
        'Total scene duration differs from audio duration by > 0.1s',
        'Missing Scene TSX component file',
        'Zero total frames calculated'
      ]
    },
    llmDecisionMaking: {
      usesLlm: false,
      modelOrProfile: 'Purely Deterministic Timeline Compiler',
      promptStrategy: 'None; timeline assembly is 100% mathematical and code generation based.',
      fallbackStrategy: 'None; frame mathematics are exact.',
      deterministicGuardrails: [
        'Total timeline frames strictly bound to audio duration',
        'Frame equations are verified with mathematical assertions',
        'Zero gaps or overlaps permitted between consecutive scenes'
      ],
      purelyDeterministicParts: [
        'Frame calculation',
        'Sequence block layout',
        'Root.tsx component generation',
        'timeline.json serialization'
      ]
    },
    currentCapabilities: [
      {
        name: 'Frame-accurate multi-track timeline assembly',
        status: 'VERIFIED WORKING',
        description: 'Synchronizes audio, video, subtitle, and overlay tracks with zero frame drift.',
        evidence: 'Verified in VIDEO_ENGINE/stages/timeline_build.py'
      },
      {
        name: 'UI Frame-Accurate Visual Timeline View',
        status: 'VERIFIED WORKING',
        description: 'Interactive visual timeline with zoom ruler, separate tracks, playhead, and frame inspection.',
        evidence: 'Implemented in TimelineBuildVisualView.tsx and verified with Playwright tests'
      },
      {
        name: 'Root.tsx Remotion code compilation',
        status: 'VERIFIED WORKING',
        description: 'Generates valid master Remotion composition ready for headless rendering.',
        evidence: 'Tested in tests/test_timeline_render_qc_delivery.py'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT approve the timeline for rendering (approval is enforced in Stage 8)',
      'Does NOT render the video to MP4 (rendered in Stage 9)',
      'Does NOT modify the scene choreography or text'
    ],
    missingCapabilities: [
      {
        title: 'Dynamic Audio Ducking Curves',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Background music volume is currently set to a constant level rather than automatically ducking under voice.',
        impact: 'Background score might compete with voice if music is loud.',
        plannedResolution: 'Inject Remotion audio volume keyframe interpolations matching utterance boundaries.'
      },
      {
        title: 'Non-Linear Transition Cross-Dissolves',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Scenes are butt-spliced sequentially; cross-dissolves require manual transition frame handles.',
        impact: 'Transitions between scenes are predominantly cuts or fast wipes.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Asserts sum(scene.frames) == total_composition_frames',
        'Asserts all referenced Scene_{i}.tsx files exist on disk',
        'Asserts audio file exists and duration matches'
      ],
      testFiles: [
        'tests/test_timeline_render_qc_delivery.py',
        'verify_timeline_ui.py'
      ],
      failureModesAndRecovery: [
        'Frame count mismatch: Automatically clamps trailing scene frame count to match audio duration exactly.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'HIGH',
        title: 'Automated Remotion Audio Ducking',
        currentLimitation: 'Static background music volume.',
        desiredBehavior: 'Automatically lower background music volume to 15% during speech and restore to 40% during pauses.',
        implementationGap: 'Generate dynamic volume interpolation array from cuts.json.',
        dependencies: 'cuts.json speech intervals'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/timeline_build/agent.py',
        'VIDEO_ENGINE/stages/timeline_build.py'
      ],
      supportingFiles: [
        'VIDEO_ENGINE/stages/timeline_gate.py',
        'VIDEO_ENGINE/stages/timeline_media.py',
        'UI/frontend/src/components/TimelineBuildVisualView.tsx'
      ],
      classesAndFunctions: [
        'TimelineBuildAgent.execute()',
        'build_timeline()',
        'compile_root_composition()',
        'verify_frame_accounting()'
      ],
      testFiles: [
        'tests/test_timeline_render_qc_delivery.py',
        'verify_timeline_ui.py'
      ]
    }
  },

  // =========================================================================
  // 8. TIMELINE APPROVAL (timeline_approval / approval)
  // =========================================================================
  approval: {
    agentId: 'timeline_approval',
    stageId: 'approval',
    name: 'Timeline Approval Agent',
    role: 'Cryptographic Fingerprint Lock & Autonomous / Operator Approval Gate',
    category: 'assembly',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 8 • CRYPTOGRAPHIC GATE',
    overview: {
      purpose: 'Enforces an immutable cryptographic gate before expensive video rendering. Validates timeline rubrics, hashes all project assets into a SHA-256 fingerprint, and records a signed approval certificate via autonomous evaluation or operator sign-off.',
      problemSolved: 'Prevents wasteful video re-rendering on unverified or corrupted timelines, guarantees provenance, and automatically invalidates approvals if any upstream asset changes.',
      position: 'Stage 8 (Gating stage between Timeline Build and Video Render).',
      upstream: 'Stage 7: Timeline Build (timeline.json, Root.tsx).',
      downstream: 'Stage 9: Render Video (render_video), which strictly requires a valid approval certificate to execute.',
      architectureRole: 'Governance gatekeeper that cryptographically signs approved state and prevents unauthorized or unvalidated rendering.'
    },
    whatItDoes: {
      summary: 'Computes cryptographic SHA-256 fingerprint over all upstream artifacts, evaluates automated quality rubrics, supports both autonomous LLM and human operator sign-off, and records immutable audit log.',
      implementedResponsibilities: [
        'Calculation of master SHA-256 fingerprint hashing audio.wav, transcript.json, scene_segmentation.json, visual_plan.json, motion_plan.json, timeline.json, and all scene TSX files',
        'Verification of automated approval rubrics: duration match (< 0.1s diff), asset presence, zero frame gaps',
        'Autonomous evaluation mode: LLM analyzes timeline structure and grants auto-approval without manual wait',
        'Manual operator mode: UI sign-off',
        'Emission of projects/{project_id}/timeline_approval.json containing fingerprint and certificate',
        'Append-only recording into config/approvals_audit.jsonl',
        'Cryptographic cache invalidation: if any upstream file is altered, the approval fingerprint mismatches and automatically resets'
      ],
      productionReadyFeatures: [
        'Cryptographic SHA-256 fingerprint verification',
        'Autonomous auto-advance approval mode',
        'Append-only tamper-evident audit trail',
        'Interactive UI approval drawer with decision buttons'
      ],
      experimentalFeatures: [
        'Multi-operator quorum sign-off (2-of-3 signatures)'
      ]
    },
    howItWorks: {
      summary: 'Hashes all upstream artifacts, verifies automated rubrics, checks autonomous vs operator mode, signs approval certificate, and logs to audit trail.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Artifact Hashing & Fingerprint Computation',
          detail: 'Computes SHA-256 hash of every upstream file and combines them into master project fingerprint.',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'Automated Rubric Verification',
          detail: 'Validates that timeline duration matches audio, all scene components exist, and motion validation passed.',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'Autonomous / Operator Decision Evaluation',
          detail: 'In autonomous mode, executes LLM timeline quality rubric check; in operator mode, awaits signed HTTP POST request.',
          type: 'llm'
        },
        {
          step: 4,
          title: 'Certificate Signing & Persistence',
          detail: 'Writes timeline_approval.json containing approved=true, timestamp, approver ID, and fingerprint.',
          type: 'deterministic'
        },
        {
          step: 5,
          title: 'Audit Trail Recording',
          detail: 'Appends immutable record to config/approvals_audit.jsonl.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Fingerprint check executes in < 50ms; instant re-validation on identical hash.',
      retryLogic: 'If rubric check fails, details specific violation (e.g. missing asset) to permit targeted fix.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'timeline.json',
          required: true,
          format: 'JSON',
          description: 'Master timeline from Stage 7.',
          pathExample: 'projects/{project_id}/timeline.json'
        },
        {
          name: 'audio.wav & all project JSONs',
          required: true,
          format: 'Various files',
          description: 'Hashed collectively to compute SHA-256 fingerprint.',
          pathExample: 'projects/{project_id}/*'
        }
      ],
      externalTools: ['SHA-256 cryptographic hasher', 'LLM Gateway (for autonomous mode)'],
      systemDependencies: ['config/approvals_audit.jsonl']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'timeline_approval.json',
          format: 'JSON (approved boolean, fingerprint, timestamp, approver, rubrics)',
          description: 'Signed approval certificate required by Render Video Agent.',
          pathExample: 'projects/{project_id}/timeline_approval.json',
          consumers: ['render_video', 'final_qc']
        },
        {
          name: 'config/approvals_audit.jsonl',
          format: 'JSONL (append-only audit log)',
          description: 'Permanent record of all approval events.',
          pathExample: 'config/approvals_audit.jsonl',
          consumers: ['audit_system']
        }
      ],
      sideEffects: [
        'Updates pipeline_state.json',
        'Authorizes Render Video Agent to begin headless rendering'
      ],
      errorStates: [
        'Duration rubric check failed (audio vs timeline duration mismatch)',
        'Fingerprint mismatch (upstream files altered post-approval)'
      ]
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'Claude 3.5 Sonnet / GPT-4o (Autonomous Mode only)',
      temperature: '0.1',
      promptStrategy: 'Evaluates timeline composition rubrics: narrative continuity, scene pacing, and asset completeness; returns structured PASS/FAIL verdict.',
      fallbackStrategy: 'If LLM is disabled or unavailable, falls back to deterministic rubric checks or waits for human operator sign-off.',
      deterministicGuardrails: [
        'Fingerprint calculation is 100% cryptographic SHA-256; LLM cannot forge or alter the fingerprint',
        'Physical file existence and duration match are verified deterministically before LLM review'
      ],
      purelyDeterministicParts: [
        'SHA-256 fingerprint hashing',
        'Duration diff calculation',
        'Audit log appending'
      ]
    },
    currentCapabilities: [
      {
        name: 'Cryptographic fingerprint locking',
        status: 'VERIFIED WORKING',
        description: 'Locks all project assets with SHA-256; invalidates if any file changes.',
        evidence: 'Verified in tests/test_laxman_approval.py'
      },
      {
        name: 'Autonomous auto-advance mode',
        status: 'VERIFIED WORKING',
        description: 'Automatically analyzes and approves valid timelines to continue pipeline without manual pause.',
        evidence: 'Tested in tests/test_timeline_render_qc_delivery.py'
      },
      {
        name: 'Tamper-evident audit logging',
        status: 'VERIFIED WORKING',
        description: 'Appends immutable sign-off records to config/approvals_audit.jsonl.',
        evidence: 'Verified in VIDEO_ENGINE/stages/timeline_approval.py'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT render video frames (handled by Stage 9)',
      'Does NOT modify scene code or timeline layout (strictly a validation gate)',
      'Does NOT permit rendering if the cryptographic fingerprint is missing or invalid'
    ],
    missingCapabilities: [
      {
        title: 'Multi-Operator Quorum Sign-off',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Currently supports single operator sign-off or autonomous LLM mode; does not enforce 2-person rule.',
        impact: 'Enterprise dual-custody approval requires external policy enforcement.'
      },
      {
        title: 'Visual Diff View between Approval Cycles',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Does not render visual side-by-side diffs of scenes that changed since prior rejected approval.',
        impact: 'Operator must manually compare scene details.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Asserts master fingerprint matches hash of current files on disk',
        'Asserts timeline duration - audio duration <= 0.1s',
        'Asserts approval certificate has valid timestamp and signature'
      ],
      testFiles: [
        'tests/test_laxman_approval.py',
        'tests/test_timeline_render_qc_delivery.py'
      ],
      failureModesAndRecovery: [
        'Fingerprint mismatch: Resets approved status to waiting and prompts operator to review updated assets.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'MEDIUM',
        title: 'Visual Timeline Diff Inspector',
        currentLimitation: 'No visual change detection between versions.',
        desiredBehavior: 'Highlight scenes that were modified since the last approval review.',
        implementationGap: 'Store per-scene AST hashes in approval certificate.',
        dependencies: 'timeline_approval.json schema extension'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/timeline_approval/agent.py',
        'VIDEO_ENGINE/stages/timeline_approval.py'
      ],
      supportingFiles: [
        'UI/backend/routes/approvals.py',
        'VIDEO_ENGINE/stages/fingerprint.py',
        'config/approvals_audit.jsonl'
      ],
      classesAndFunctions: [
        'TimelineApprovalAgent.execute()',
        'compute_master_fingerprint()',
        'verify_approval_rubrics()',
        'record_approval_decision()'
      ],
      testFiles: [
        'tests/test_laxman_approval.py',
        'tests/test_timeline_render_qc_delivery.py'
      ]
    }
  },

  // =========================================================================
  // 9. RENDER VIDEO (render_video / render)
  // =========================================================================
  render: {
    agentId: 'render_video',
    stageId: 'render',
    name: 'Render Video Agent',
    role: 'Headless Chrome Remotion Execution & Frame-by-Frame Video Compilation',
    category: 'assembly',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 9 • HEADLESS CHROMIUM RENDER',
    overview: {
      purpose: 'Executes the Remotion video rendering pipeline in headless Chrome, dynamically allocates bundling ports, streams real-time frame progress telemetry, combines audio-video streams with FFmpeg, and diagnoses rendering failures.',
      problemSolved: 'Converts abstract React TSX code and animations into high-definition, broadcast-ready MP4 video files with hardware acceleration and automatic crash recovery.',
      position: 'Stage 9 (Follows Timeline Approval).',
      upstream: 'Stage 8: Timeline Approval (timeline_approval.json with valid cryptographic fingerprint).',
      downstream: 'Stage 10: Final QC (final_qc), which validates rendered video integrity.',
      architectureRole: 'Heavy compute engine that compiles React components and audio into physical MP4 video bytes.'
    },
    whatItDoes: {
      summary: 'Verifies approval certificate, launches Remotion render command on dynamic port, monitors frame-by-frame progress, multiplexes audio with FFmpeg, and executes LLM recovery on render exceptions.',
      implementedResponsibilities: [
        'Cryptographic pre-check: strictly refuses to render if timeline_approval.json is missing or invalid',
        'Dynamic bundling port selection (ports 3000-3050) to prevent port collisions during concurrent runs',
        'Execution of npx remotion render Root out/video.mp4 with configured concurrency and quality settings',
        'Real-time frame progress parsing from CLI stdout: Rendered frame X/Y (Z%)',
        'FFmpeg audio-video multiplexing (H.264 video codec, AAC audio codec, 30 FPS)',
        'Hardware acceleration support: auto-detects NVIDIA NVENC with automatic fallback to libx264',
        'Autonomous error diagnosis: analyzes Chromium / Node.js stack traces and applies targeted fixes',
        'Generation of projects/{project_id}/render_status.json capturing render duration, average FPS, and file size'
      ],
      productionReadyFeatures: [
        'Dynamic port allocation preventing EADDRINUSE conflicts',
        'Real-time percentage progress streaming to UI',
        'NVENC GPU acceleration with software CPU fallback',
        'Self-healing crash recovery loop'
      ],
      experimentalFeatures: [
        'Distributed cloud rendering via Remotion Lambda'
      ]
    },
    howItWorks: {
      summary: 'Validates approval certificate, finds free port, spawns Remotion render process, parses progress, muxes audio, verifies output MP4, and writes status.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Approval Certificate Verification',
          detail: 'Verifies timeline_approval.json exists and its SHA-256 fingerprint matches current project state.',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'Port Allocation & Remotion Launch',
          detail: 'Scans for free local port (3000-3050) and launches npx remotion render Root out/video.mp4.',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'Telemetry & Progress Monitoring',
          detail: 'Streams stdout logs, parses frame counters, and broadcasts live percentage and ETA to UI via SSE.',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'Audio Multiplexing & Muxing',
          detail: 'Combines rendered video frames with original narration audio track using FFmpeg.',
          type: 'external'
        },
        {
          step: 5,
          title: 'Output Verification & Status Recording',
          detail: 'Verifies output MP4 file size > 100KB, confirms duration, and writes projects/{project_id}/render_status.json.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Configurable thread concurrency (default 4 Chrome render workers); skips render if video exists and fingerprint matches.',
      retryLogic: 'If Chrome crashes (WebGL context lost or OOM), lowers concurrency to 2 and retries with software canvas rendering.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'timeline_approval.json',
          required: true,
          format: 'JSON (signed certificate)',
          description: 'Mandatory cryptographic gate authorization.',
          pathExample: 'projects/{project_id}/timeline_approval.json'
        },
        {
          name: 'VIDEO_ENGINE/remotion/src/Root.tsx',
          required: true,
          format: 'TypeScript JSX master composition',
          description: 'Master composition entrypoint from Stage 7.',
          pathExample: 'VIDEO_ENGINE/remotion/src/Root.tsx'
        },
        {
          name: 'audio.wav',
          required: true,
          format: 'WAV audio file',
          description: 'Master voice narration audio.',
          pathExample: 'projects/{project_id}/audio.wav'
        }
      ],
      externalTools: ['Remotion CLI', 'Headless Google Chrome / Chromium', 'FFmpeg / FFprobe', 'Node.js 18+'],
      systemDependencies: ['NVIDIA NVENC drivers (optional)', 'OpenGL / WebGL headless drivers']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'video.mp4',
          format: 'MP4 (H.264 / AAC 1080p 30fps)',
          description: 'Master rendered video file.',
          pathExample: 'projects/{project_id}/out/video.mp4',
          consumers: ['final_qc', 'final_video_delivery']
        },
        {
          name: 'render_status.json',
          format: 'JSON (duration, FPS, exit code, file size, timestamp)',
          description: 'Telemetry report of the rendering process.',
          pathExample: 'projects/{project_id}/render_status.json',
          consumers: ['final_qc']
        }
      ],
      sideEffects: [
        'Creates out/video.mp4 file on disk',
        'Updates pipeline_state.json with render progress'
      ],
      errorStates: [
        'Missing approval certificate',
        'Chromium process crashed (OOM or WebGL failure)',
        'Node.js process exited with non-zero status code'
      ]
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'Claude 3.5 Sonnet / GPT-4o (Error Recovery Mode only)',
      temperature: '0.1',
      promptStrategy: 'When render process crashes, feeds Chromium console errors and Node stack trace to LLM to diagnose faulty scene component and recommend targeted fix.',
      fallbackStrategy: 'Deterministic retry with lower concurrency and CPU-only flags if LLM diagnosis is unavailable.',
      deterministicGuardrails: [
        'Render execution is 100% deterministic Node.js and FFmpeg code',
        'LLM cannot bypass approval certificate gate'
      ],
      purelyDeterministicParts: [
        'Approval fingerprint verification',
        'Dynamic port scanner',
        'Remotion CLI execution',
        'FFmpeg audio multiplexing'
      ]
    },
    currentCapabilities: [
      {
        name: 'Headless Chrome Remotion rendering',
        status: 'VERIFIED WORKING',
        description: 'Compiles React TSX components into 1080p MP4 video at 30 FPS.',
        evidence: 'Verified in scripts/verify_production_release_render.py'
      },
      {
        name: 'Dynamic port allocation',
        status: 'VERIFIED WORKING',
        description: 'Scans and binds available port between 3000 and 3050 to avoid EADDRINUSE.',
        evidence: 'Implemented in VIDEO_ENGINE/stages/render_video.py'
      },
      {
        name: 'Real-time telemetry and progress parsing',
        status: 'VERIFIED WORKING',
        description: 'Streams live frame count, percentage, and ETA to UI drawer.',
        evidence: 'Tested in tests/test_timeline_render_qc_delivery.py'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT deliver video to final desktop folder until Final QC passes',
      'Does NOT generate React animation code or alter motion plans',
      'Does NOT run if timeline approval is missing or invalidated'
    ],
    missingCapabilities: [
      {
        title: 'Remotion Lambda Serverless Cloud Rendering',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Currently renders on local host workstation. AWS Lambda distributed rendering is not connected.',
        impact: 'Rendering long videos (10+ mins) takes local machine compute time.',
        plannedResolution: 'Add Remotion Lambda deployment configuration for parallel cloud chunk rendering.'
      },
      {
        title: 'Multi-GPU NVENC Load Balancing',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Single GPU / NVENC instance utilized.',
        impact: 'Cannot distribute rendering across multiple physical GPUs.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Asserts output MP4 file exists on disk and size > 100KB',
        'Asserts video duration matches audio duration within 0.1s',
        'Asserts FFprobe confirms valid H.264 video and AAC audio streams'
      ],
      testFiles: [
        'tests/test_timeline_render_qc_delivery.py',
        'scripts/verify_production_release_render.py'
      ],
      failureModesAndRecovery: [
        'Render crash: Checks Chromium crash log, lowers worker count to 1, enables software rendering, and retries.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'HIGH',
        title: 'Remotion Lambda Cloud Dispatcher',
        currentLimitation: 'Local CPU/GPU rendering only.',
        desiredBehavior: 'Option to burst render long videos across 100 AWS Lambda functions in parallel for 10x speed.',
        implementationGap: 'Configure AWS credentials and remotion lambda render command.',
        dependencies: '@remotion/lambda'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/render_video/agent.py',
        'VIDEO_ENGINE/stages/render_video.py',
        'VIDEO_ENGINE/stages/render.py'
      ],
      supportingFiles: [
        'UI/backend/render_video.py',
        'scripts/verify_production_release_render.py'
      ],
      classesAndFunctions: [
        'RenderVideoAgent.execute()',
        'render_remotion_video()',
        'allocate_dynamic_port()',
        'mux_audio_stream()'
      ],
      testFiles: [
        'tests/test_timeline_render_qc_delivery.py',
        'scripts/verify_production_release_render.py'
      ]
    }
  },

  // =========================================================================
  // 10. FINAL QC (final_qc / qc)
  // =========================================================================
  qc: {
    agentId: 'final_qc',
    stageId: 'qc',
    name: 'Final QC Agent',
    role: 'Automated Media Probes, Black/Freeze Frame Detection & Quality Certification',
    category: 'delivery',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 10 • MEDIA PROBE & A/V AUDIT',
    overview: {
      purpose: 'Executes comprehensive automated quality control across rendered MP4 video: tests for black frames, frozen screens, audio clipping, A/V synchronization drift, and Telugu subtitle integrity, producing a verified QC certification report.',
      problemSolved: 'Prevents corrupted, desynchronized, or black-frame videos from being delivered to operators or published to social channels.',
      position: 'Stage 10 (Follows Video Render).',
      upstream: 'Stage 9: Render Video (out/video.mp4), Stage 1: Audio Analysis (audio.wav, transcript.json).',
      downstream: 'Stage 11: Final Delivery (final_video_delivery), which only delivers videos with a passing QC report.',
      architectureRole: 'Independent quality inspector that objectively audits physical video files using deterministic signal processing.'
    },
    whatItDoes: {
      summary: 'Executes FFmpeg/FFprobe media probes (blackdetect, freezedetect, astats), measures A/V sync drift, audits subtitle text rendering, synthesizes LLM diagnostic report, and applies targeted autofixes.',
      implementedResponsibilities: [
        'Black frame detection using FFmpeg blackdetect filter (threshold: black_min_duration=0.5s, pic_th=0.98)',
        'Freeze frame detection using FFmpeg freezedetect filter (threshold: freeze_min_duration=1.0s)',
        'Audio loudness and peak analysis using astats filter (verifies true-peak <= 0 dBFS, target -14 to -16 LUFS)',
        'Audio-Video sync audit: verifies duration difference between video stream and audio stream is <= 0.1s',
        'Telugu subtitle & typography rendering verification (checks for font corruption or missing characters)',
        'LLM-assisted diagnostic synthesis: summarizes probe findings into plain-English quality report',
        'Automated targeted autofix: fixes minor A/V sync drift via FFmpeg stream re-muxing without full re-render',
        'Emission of projects/{project_id}/final_qc_report.json with overall PASS/FAIL grade'
      ],
      productionReadyFeatures: [
        'Deterministic FFmpeg media probe integration',
        'Mathematical true-peak and loudness LUFS verification',
        'Automatic re-mux autofix loop for minor sync drift'
      ],
      experimentalFeatures: [
        'Automated AI-based video aesthetic rating'
      ]
    },
    howItWorks: {
      summary: 'Probes out/video.mp4 with FFprobe and FFmpeg filters, analyzes black/freeze/clipping events, validates A/V duration equality, generates QC report, and approves or triggers targeted remediation.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'Video Stream Probe',
          detail: 'Runs ffprobe to verify resolution (1080p), codec (H.264), framerate (30fps), and total frame count.',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'Black & Freeze Detection',
          detail: 'Executes FFmpeg filters to detect unexpected black screens or frozen visual frames exceeding duration limits.',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'Audio Quality & Clipping Audit',
          detail: 'Runs FFmpeg astats to inspect peak dBFS, loudness LUFS, and detect audio clipping or mute passages.',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'A/V Sync Verification & Autofix',
          detail: 'Checks |video_duration - audio_duration| <= 0.1s; if drift detected, triggers targeted FFmpeg re-mux.',
          type: 'deterministic'
        },
        {
          step: 5,
          title: 'LLM Diagnostic Synthesis & Report',
          detail: 'Uses LLM to summarize probe telemetry into human-readable QC findings and writes final_qc_report.json.',
          type: 'llm'
        }
      ],
      concurrencyAndCaching: 'Media probes execute sequentially in ~3-5 seconds; results cached by video SHA-256.',
      retryLogic: 'If minor sync drift is found, automatically applies targeted stream re-mux and re-probes.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'out/video.mp4',
          required: true,
          format: 'MP4 video file',
          description: 'Rendered video file from Stage 9.',
          pathExample: 'projects/{project_id}/out/video.mp4'
        },
        {
          name: 'audio.wav',
          required: true,
          format: 'WAV audio file',
          description: 'Original master audio for duration and sync comparison.',
          pathExample: 'projects/{project_id}/audio.wav'
        },
        {
          name: 'transcript.json',
          required: true,
          format: 'JSON',
          description: 'Master transcript for subtitle verification.',
          pathExample: 'projects/{project_id}/transcript.json'
        }
      ],
      externalTools: ['FFmpeg (filters: blackdetect, freezedetect, astats)', 'FFprobe', 'OpenCV / PIL', 'LLM Gateway'],
      systemDependencies: ['None']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'final_qc_report.json',
          format: 'JSON (overall status, black_frames, freeze_frames, audio_metrics, sync_drift, scores)',
          description: 'Definitive quality inspection certificate.',
          pathExample: 'projects/{project_id}/final_qc_report.json',
          consumers: ['final_video_delivery', 'UI StageDrawer']
        }
      ],
      sideEffects: [
        'Updates pipeline_state.json with QC verdict',
        'Authorizes Final Video Delivery Agent to proceed if PASSED'
      ],
      errorStates: [
        'Persistent black frames exceeding 0.5s',
        'Audio-video duration drift exceeding 0.5s',
        'Audio clipping at 0 dBFS'
      ]
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'Claude 3.5 Sonnet / GPT-4o',
      temperature: '0.1',
      promptStrategy: 'Provides deterministic probe statistics (black frame list, freeze periods, LUFS) and asks LLM to formulate clear diagnostic summary and pass/fail verdict.',
      fallbackStrategy: 'If LLM is offline, deterministic threshold rules evaluate pass/fail directly without failing the stage.',
      deterministicGuardrails: [
        'Pass/Fail status is strictly governed by numerical thresholds (zero black frames allowed, drift <= 0.1s)',
        'LLM cannot override a failed deterministic probe check'
      ],
      purelyDeterministicParts: [
        'FFmpeg blackdetect and freezedetect execution',
        'astats loudness and peak calculation',
        'Duration difference calculation',
        'Targeted re-mux autofix script'
      ]
    },
    currentCapabilities: [
      {
        name: 'Deterministic media probing',
        status: 'VERIFIED WORKING',
        description: 'Detects black frames, freeze frames, and audio clipping using FFmpeg.',
        evidence: 'Verified in VIDEO_ENGINE/stages/final_qc.py'
      },
      {
        name: 'Audio-Video sync audit & targeted autofix',
        status: 'VERIFIED WORKING',
        description: 'Measures millisecond sync drift and re-muxes stream without full re-render.',
        evidence: 'Tested in tests/test_timeline_render_qc_delivery.py'
      },
      {
        name: 'Loudness LUFS compliance check',
        status: 'VERIFIED WORKING',
        description: 'Ensures audio conforms to standard broadcast loudness targets (-14 to -16 LUFS).',
        evidence: 'Implemented in VIDEO_ENGINE/stages/quality.py'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT move files to the final desktop delivery folder (handled by Stage 11)',
      'Does NOT alter video visual content or re-synthesize scenes',
      'Does NOT invent subjective QC passes when physical media probes fail'
    ],
    missingCapabilities: [
      {
        title: 'Perceptual AI Lip-Sync Verification',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Does not test visual lip synchronization (applicable if future talking-head avatars are used).',
        impact: 'Only checks overall audio-video track duration sync, not face phoneme sync.'
      },
      {
        title: 'HDR10 / Dolby Vision Color Space Validation',
        status: 'NOT SUPPORTED',
        gapDescription: 'Pipeline standardizes on Rec.709 sRGB 8-bit color space; 10-bit HDR is not validated.',
        impact: 'Standard web video workflow.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Asserts black_frames count == 0 (or within acceptable intro/outro bounds)',
        'Asserts freeze_frames count == 0',
        'Asserts |video_duration - audio_duration| <= 0.1s'
      ],
      testFiles: [
        'tests/test_timeline_render_qc_delivery.py',
        'tests/test_stage5_desktop_delivery_auto_qc.py'
      ],
      failureModesAndRecovery: [
        'Sync drift: Re-muxes audio and video with FFmpeg -itsoffset flag; re-probes.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'MEDIUM',
        title: 'Social Platform Pre-Flight Profile Check',
        currentLimitation: 'Single generic QC profile.',
        desiredBehavior: 'Check specific bitrate and dimension constraints for YouTube Shorts, Instagram Reels, and TikTok.',
        implementationGap: 'Add platform-specific rule presets in final_qc.py.',
        dependencies: 'final_qc.py rules'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/final_qc/agent.py',
        'VIDEO_ENGINE/stages/final_qc.py',
        'VIDEO_ENGINE/stages/video_qc.py'
      ],
      supportingFiles: [
        'VIDEO_ENGINE/stages/quality.py',
        'VIDEO_ENGINE/stages/media_probe.py',
        'UI/backend/final_qc.py'
      ],
      classesAndFunctions: [
        'FinalQcAgent.execute()',
        'run_media_probe()',
        'detect_black_and_freeze_frames()',
        'audit_av_sync()'
      ],
      testFiles: [
        'tests/test_timeline_render_qc_delivery.py',
        'tests/test_stage5_desktop_delivery_auto_qc.py'
      ]
    }
  },

  // =========================================================================
  // 11. FINAL VIDEO DELIVERY (final_video_delivery / final)
  // =========================================================================
  final: {
    agentId: 'final_video_delivery',
    stageId: 'final',
    name: 'Final Video Delivery Agent',
    role: 'Provenance Verification, SHA-256 Manifest Hashing & Desktop Export',
    category: 'delivery',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'STAGE 11 • PROVENANCE & DELIVERY',
    overview: {
      purpose: 'Verifies complete end-to-end pipeline provenance, computes final SHA-256 integrity checksums, publishes the final MP4 to the designated desktop/export delivery directory, generates an immutable delivery manifest, and marks pipeline completion at 100%.',
      problemSolved: 'Ensures the delivered video file is cryptographically verified against all generation artifacts, eliminating incomplete deliveries and lost export files.',
      position: 'Stage 11 (Terminal pipeline stage).',
      upstream: 'Stage 10: Final QC (final_qc_report.json with passing grade).',
      downstream: 'Operator file system, Desktop export folder, external distribution.',
      architectureRole: 'Terminal delivery manager that seals project artifacts and hands off completed media to the operator.'
    },
    whatItDoes: {
      summary: 'Audits completion of all 10 preceding stages, calculates SHA-256 of final MP4, exports video to delivery folder, creates delivery_manifest.json, and sets overall project state to 100% completed.',
      implementedResponsibilities: [
        'Provenance audit: verifies all 10 preceding pipeline stages completed successfully with valid artifacts',
        'QC gate check: verifies Final QC status equals PASSED with zero unresolved blockers',
        'Cryptographic hashing: calculates SHA-256 checksum of final rendered video file',
        'Publication to destination: copies video.mp4 to export delivery folder with canonical naming: {project_id}_{aspect_ratio}_{timestamp}.mp4',
        'Generation of immutable delivery_manifest.json linking all artifact hashes, durations, and tool versions',
        'Marking overall project progress to 100% and project status to completed in pipeline_state.json'
      ],
      productionReadyFeatures: [
        'End-to-end cryptographic provenance audit',
        'Bit-level SHA-256 checksum match verification',
        'Safe desktop folder export with non-destructive naming',
        'Immutable delivery manifest generation'
      ],
      experimentalFeatures: [
        'Direct automated social media upload (YouTube / TikTok)'
      ]
    },
    howItWorks: {
      summary: 'Checks Final QC certificate, verifies all stage outputs, hashes video, copies file to delivery directory, writes delivery_manifest.json, and transitions project state to completed.',
      stepByStepFlow: [
        {
          step: 1,
          title: 'QC & Pre-flight Gate Verification',
          detail: 'Verifies final_qc_report.json has status=passed and confirms out/video.mp4 exists.',
          type: 'deterministic'
        },
        {
          step: 2,
          title: 'Provenance & Integrity Audit',
          detail: 'Scans all upstream artifacts (transcript, scenes, visual plan, timeline) and verifies unbroken audit trail.',
          type: 'deterministic'
        },
        {
          step: 3,
          title: 'SHA-256 Checksum Calculation',
          detail: 'Computes cryptographic SHA-256 hash of final MP4 file to guarantee bit-level delivery integrity.',
          type: 'deterministic'
        },
        {
          step: 4,
          title: 'Export & Delivery Packaging',
          detail: 'Copies video to projects/{project_id}/delivery/ and desktop export path with standardized filename.',
          type: 'deterministic'
        },
        {
          step: 5,
          title: 'Manifest Emission & Pipeline Completion',
          detail: 'Writes delivery_manifest.json and updates pipeline_state.json to 100% completed.',
          type: 'deterministic'
        }
      ],
      concurrencyAndCaching: 'Executes in < 500ms; idempotent operation.',
      retryLogic: 'If disk write fails due to permissions, attempts fallback to user Home / Videos folder.'
    },
    inputsDependencies: {
      inputs: [
        {
          name: 'out/video.mp4',
          required: true,
          format: 'MP4 video file',
          description: 'Rendered and QC-verified master video.',
          pathExample: 'projects/{project_id}/out/video.mp4'
        },
        {
          name: 'final_qc_report.json',
          required: true,
          format: 'JSON',
          description: 'Passing QC report from Stage 10.',
          pathExample: 'projects/{project_id}/final_qc_report.json'
        }
      ],
      externalTools: ['SHA-256 hasher', 'OS filesystem utilities'],
      systemDependencies: ['Read/write permissions in delivery directory']
    },
    outputsSideEffects: {
      outputs: [
        {
          name: 'Exported MP4 Video',
          format: 'MP4 (1080p broadcast video)',
          description: 'Final delivered video ready for distribution.',
          pathExample: 'projects/{project_id}/delivery/{project_id}_16x9_delivery.mp4',
          consumers: ['Operator', 'Video distribution platforms']
        },
        {
          name: 'delivery_manifest.json',
          format: 'JSON (complete provenance, artifact SHA-256 hashes, timestamps, metadata)',
          description: 'Cryptographic proof of provenance and pipeline integrity.',
          pathExample: 'projects/{project_id}/delivery/delivery_manifest.json',
          consumers: ['Audit system', 'Operator archive']
        }
      ],
      sideEffects: [
        'Updates projects/{project_id}/pipeline_state.json status to completed and progress to 100%',
        'Copies master video file to export directory'
      ],
      errorStates: [
        'Final QC failed or missing',
        'Output video file missing or corrupted',
        'Insufficient disk space in delivery destination'
      ]
    },
    llmDecisionMaking: {
      usesLlm: false,
      modelOrProfile: '100% Purely Deterministic (No LLM in delivery phase)',
      promptStrategy: 'None; packaging and hashing are strictly algorithmic.',
      fallbackStrategy: 'None; integrity failures halt delivery.',
      deterministicGuardrails: [
        'Bit-level SHA-256 verification guarantees delivery file matches rendered file exactly',
        'Strict requirement for passing Final QC prevents delivery of defective videos'
      ],
      purelyDeterministicParts: [
        'Provenance checking',
        'SHA-256 hashing',
        'Filesystem copying',
        'Manifest serialization',
        'State machine transition to completed'
      ]
    },
    currentCapabilities: [
      {
        name: 'End-to-end provenance verification',
        status: 'VERIFIED WORKING',
        description: 'Audits unbroken chain of artifacts across all 11 stages.',
        evidence: 'Verified in tests/test_stage5_desktop_delivery_auto_qc.py'
      },
      {
        name: 'Cryptographic delivery manifest',
        status: 'VERIFIED WORKING',
        description: 'Generates delivery_manifest.json with complete SHA-256 checksums.',
        evidence: 'Tested in tests/test_timeline_render_qc_delivery.py'
      },
      {
        name: 'Pipeline 100% completion state transition',
        status: 'VERIFIED WORKING',
        description: 'Cleanly sets overall project progress to 100% and status to completed.',
        evidence: 'Verified in pipeline_state.json updates'
      }
    ],
    whatItDoesNotDo: [
      'Does NOT re-render or compress video files (delivers approved master)',
      'Does NOT deliver videos that failed Final QC',
      'Does NOT publish directly to social media accounts without external tools'
    ],
    missingCapabilities: [
      {
        title: 'Direct Social Platform Publishing Connectors',
        status: 'PARTIALLY IMPLEMENTED',
        gapDescription: 'Delivers to local directory; YouTube Data API / Instagram Graph API connectors are not activated.',
        impact: 'Operator must manually upload video to YouTube/Instagram/TikTok.',
        plannedResolution: 'Add OAuth2 social media publishing connectors in delivery stage.'
      },
      {
        title: 'Decentralized IPFS Storage Pinning',
        status: 'NOT IMPLEMENTED',
        gapDescription: 'Does not pin delivery manifest or video to IPFS/Filecoin.',
        impact: 'Storage is purely local filesystem.'
      }
    ],
    validationTesting: {
      validationLogic: [
        'Asserts delivered MP4 hash matches rendered MP4 hash bit-for-bit',
        'Asserts delivery_manifest.json contains valid non-empty artifact hashes',
        'Asserts project status transitions to completed'
      ],
      testFiles: [
        'tests/test_timeline_render_qc_delivery.py',
        'tests/test_stage5_desktop_delivery_auto_qc.py'
      ],
      failureModesAndRecovery: [
        'Write error: Retries copy with alternate destination path.'
      ]
    },
    improvementOpportunities: [
      {
        priority: 'HIGH',
        title: 'YouTube & TikTok Direct Publish Connector',
        currentLimitation: 'Delivers to local desktop folder only.',
        desiredBehavior: 'Optionally upload directly to YouTube Shorts / TikTok with title, description, and tags.',
        implementationGap: 'Integrate Google OAuth2 and YouTube Data API v3 upload script.',
        dependencies: 'google-api-python-client'
      }
    ],
    sourceEvidence: {
      primaryFiles: [
        'SYSTEM/agents/video_generation_agents/final_video_delivery/agent.py',
        'SYSTEM/registries/agent_registry.py'
      ],
      supportingFiles: [
        'VIDEO_ENGINE/stages/final_qc.py',
        'UI/backend/pipeline_state.py'
      ],
      classesAndFunctions: [
        'FinalVideoDeliveryAgent.execute()',
        'audit_pipeline_provenance()',
        'generate_delivery_manifest()',
        'finalize_project_state()'
      ],
      testFiles: [
        'tests/test_timeline_render_qc_delivery.py',
        'tests/test_stage5_desktop_delivery_auto_qc.py'
      ]
    }
  },

  // =========================================================================
  // 12. MAIN ORCHESTRATOR AGENT (main_orchestrator / pipeline)
  // =========================================================================
  main_orchestrator: {
    agentId: 'main_orchestrator',
    stageId: 'pipeline',
    name: 'Main Orchestrator Agent',
    role: 'Pipeline Execution Coordinator & Safe-Stop Guard',
    category: 'orchestrator',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'PIPELINE ORCHESTRATOR',
    overview: {
      purpose: 'Coordinates video pipeline stage progression, job run lifecycle, automatic advancement, and safe-stop recovery.',
      problemSolved: 'Eliminates uncoordinated stage execution, manages background run threads, enforces approval stop-gates, and tracks telemetry.',
      position: 'Root pipeline orchestrator governing all 11 stages (audio_analyzer through final_video_delivery).',
      upstream: 'FastAPI REST API routes (/projects/{id}/run, /projects/{id}/cancel) and MainArchitectureAgent.',
      downstream: 'All 11 sequential video pipeline stages and UI SSE telemetry streams.',
      architectureRole: 'Sole canonical pipeline execution orchestrator (PipelineOrchestrator).'
    },
    whatItDoes: {
      summary: 'Spawns and monitors execution runs, checks stage dependencies, enforces LLM-decided approval locks, and broadcasts SSE progress events.',
      implementedResponsibilities: [
        'Dispatches start_run, cancel_run, and pause_run requests via thread-safe lock',
        'Evaluates step-graph dependencies before transitioning stages',
        'Enforces mandatory stop-gate at Stage 8 (Timeline Approval) unless auto-approved',
        'Emits structured SSE telemetry events to frontend (percentage, stage status, timestamps)',
        'Manages retry budgets with exponential backoff on transient stage failures'
      ],
      productionReadyFeatures: [
        'Multi-aspect ratio execution (16:9 widescreen, 9:16 portrait)',
        'Resumable run checkpoints from durable disk state',
        'Real-time SSE event broadcast bus'
      ]
    },
    howItWorks: {
      summary: 'Executes stages sequentially according to CANONICAL_12_STAGES graph, checking prerequisites, running adapters, and recording checkpoints.',
      stepByStepFlow: [
        { step: 1, title: 'Run Request Intake', detail: 'Validates project directory confinement and parses target stage / aspect ratio.', type: 'deterministic' },
        { step: 2, title: 'Prerequisite Check', detail: 'Verifies external tools (FFmpeg, Node, Python) and prior stage output artifacts.', type: 'deterministic' },
        { step: 3, title: 'Sequential Stage Invocation', detail: 'Instantiates stage agent adapter and executes stage synchronously or asynchronously.', type: 'deterministic' },
        { step: 4, title: 'Approval Gate Enforcement', detail: 'Halts execution at Stage 8 if timeline approval fingerprint is missing or invalid.', type: 'deterministic' },
        { step: 5, title: 'Telemetry & Checkpointing', detail: 'Persists pipeline_state.json and streams SSE status update to connected UI clients.', type: 'deterministic' }
      ],
      concurrencyAndCaching: 'Thread-locked execution per project ID to prevent concurrent duplicate runs.',
      retryLogic: 'Configurable max_retries (default 3) per stage with automatic error capture and root-cause logging.'
    },
    inputsDependencies: {
      inputs: [
        { name: 'project_dir', required: true, format: 'directory', description: 'Root project directory containing audio and artifact subfolders', pathExample: 'projects/{project_id}/' },
        { name: 'run_parameters', required: false, format: 'JSON dict', description: 'Execution parameters: from_stage, resume, max_retries, aspect', pathExample: '{"aspect": "16:9", "resume": true}' }
      ],
      externalTools: ['job_queue', 'step_graph', 'pipeline_view'],
      systemDependencies: ['Python threading', 'FastAPI SSE streaming']
    },
    outputsSideEffects: {
      outputs: [
        { name: 'pipeline_state.json', format: 'JSON', description: 'Authoritative project stage statuses, progress percentages, and timing', pathExample: 'projects/{project_id}/pipeline_state.json', consumers: ['UI frontend', 'REST endpoints', 'All stage agents'] },
        { name: 'orchestrator_log.jsonl', format: 'JSONL', description: 'Execution telemetry log recording start, completion, and error events', pathExample: 'projects/{project_id}/logs/orchestrator.jsonl', consumers: ['AgentGrowthStore', 'Debugging tools'] }
      ],
      sideEffects: ['Writes project state to disk', 'Broadcasts SSE telemetry messages'],
      errorStates: ['STAGE_EXECUTION_ERROR', 'PREREQUISITE_MISSING', 'APPROVAL_REJECTED']
    },
    llmDecisionMaking: {
      usesLlm: false,
      modelOrProfile: 'Purely deterministic workflow state machine',
      promptStrategy: 'No LLM in orchestrator core loop; uses deterministic state transitions',
      fallbackStrategy: 'Halts on unrecoverable stage error, logs traceback, preserves all prior stage artifacts',
      deterministicGuardrails: ['Path traversal verification', 'Strict 12-stage sequential ordering', 'Cryptographic approval lock'],
      purelyDeterministicParts: ['Stage sequencing', 'Dependency checking', 'SSE broadcasting', 'State file writes']
    },
    currentCapabilities: [
      { name: 'Sequential stage execution', status: 'VERIFIED WORKING', description: 'Executes audio to final video delivery in sequence.', evidence: 'Verified across all test runs and pipeline execution' },
      { name: 'Safe stop and resume', status: 'VERIFIED WORKING', description: 'Resumes cleanly from last valid checkpoint without repeating completed stages.', evidence: 'Tested in tests/test_e2e_pipeline.py' },
      { name: 'Real-time telemetry stream', status: 'VERIFIED WORKING', description: 'SSE status updates sent to UI during active pipeline execution.', evidence: 'Verified on UI dashboard' }
    ],
    whatItDoesNotDo: [
      'Does NOT synthesize or render media itself (delegates to specialized video agents)',
      'Does NOT decompose high-level user tasks (delegated to MainArchitectureAgent)',
      'Does NOT modify source code or synthesize skills'
    ],
    missingCapabilities: [
      { title: 'Parallel Independent Stage Execution', status: 'PARTIALLY IMPLEMENTED', gapDescription: 'Currently strictly sequential; visual planning and motion planning run in order rather than pipelined parallel.', impact: 'Pipeline wall-clock duration is strictly additive.', plannedResolution: 'Implement worker pool for independent asset generation tasks.' }
    ],
    validationTesting: {
      validationLogic: ['Verifies valid project directory confinement', 'Verifies all required upstream artifacts exist before launching next stage'],
      testFiles: ['tests/test_e2e_pipeline.py', 'tests/test_timeline_render_qc_delivery.py'],
      failureModesAndRecovery: ['Process crash: Reads last durable checkpoint from pipeline_state.json on startup.']
    },
    improvementOpportunities: [
      { priority: 'MEDIUM', title: 'DAG-Based Parallel Stage Dispatcher', currentLimitation: 'Executes stages sequentially.', desiredBehavior: 'Concurrently launch independent asset collection and typography planning.', implementationGap: 'Replace sequential loop with asyncio task group DAG dispatcher.', dependencies: 'asyncio' }
    ],
    sourceEvidence: {
      primaryFiles: ['SYSTEM/agents/video_generation_agents/main_orchestrator/agent.py', 'VIDEO_ENGINE/pipeline/orchestrator.py'],
      supportingFiles: ['UI/backend/pipeline_view.py', 'UI/backend/routes/pipeline.py'],
      classesAndFunctions: ['MainOrchestratorAgent.execute()', 'PipelineOrchestrator.start_run()', 'PipelineOrchestrator.cancel_run()'],
      testFiles: ['tests/test_e2e_pipeline.py', 'tests/test_timeline_render_qc_delivery.py']
    }
  },

  // =========================================================================
  // 13. MOTION TEMPLATE SELECTION AGENT (motion_template_selection - Deprecated)
  // =========================================================================
  motion_template_selection: {
    agentId: 'motion_template_selection',
    stageId: 'motion_template_selection',
    name: 'Motion Template Selection Agent',
    role: 'Legacy Remotion Template Matcher (Archived / Deprecated)',
    category: 'motion',
    version: '1.0.0',
    owner: 'agent-system',
    badge: 'DEPRECATED / ARCHIVED',
    overview: {
      purpose: 'Historical template matching agent designed to pick predefined static Remotion composition templates.',
      problemSolved: 'Provided an early static routing prototype before dynamic React/TSX animation code generation was developed.',
      position: 'Archived stage; bypassed in active 11-stage video pipeline.',
      upstream: 'Visual Planning / Motion Planning (historical).',
      downstream: 'Motion Animation (historical).',
      architectureRole: 'Deprecated component preserved in registry for backward compatibility.'
    },
    whatItDoes: {
      summary: 'Returns deprecated status result; no active runtime duties in canonical pipeline.',
      implementedResponsibilities: [
        'Preserved in registry to maintain 20-agent canonical schema integrity',
        'Returns standardized deprecated AgentResult with explanation',
        'Prevents broken references in legacy configuration files'
      ],
      productionReadyFeatures: []
    },
    howItWorks: {
      summary: 'Executes validation and immediately returns a deprecated status result.',
      stepByStepFlow: [
        { step: 1, title: 'Deprecation Notice', detail: 'Returns status=deprecated and notes that dynamic code generation superseded static templates.', type: 'deterministic' }
      ],
      concurrencyAndCaching: 'N/A',
      retryLogic: 'No retries needed.'
    },
    inputsDependencies: {
      inputs: [{ name: 'project_dir', required: false, format: 'directory', description: 'Project directory', pathExample: 'projects/{project_id}/' }],
      externalTools: ['template_registry'],
      systemDependencies: []
    },
    outputsSideEffects: {
      outputs: [{ name: 'AgentResult', format: 'JSON', description: 'Result indicating deprecated status', pathExample: 'memory', consumers: ['AgentRegistry'] }],
      sideEffects: [],
      errorStates: []
    },
    llmDecisionMaking: {
      usesLlm: false,
      modelOrProfile: 'None',
      promptStrategy: 'None',
      fallbackStrategy: 'Returns deprecated result immediately',
      deterministicGuardrails: ['Zero side-effects'],
      purelyDeterministicParts: ['All parts']
    },
    currentCapabilities: [
      { name: 'Graceful deprecation handling', status: 'VERIFIED WORKING', description: 'Cleanly reports deprecation without causing pipeline crashes.', evidence: 'Verified in SYSTEM/agents/video_generation_agents/motion_template_selection/agent.py' }
    ],
    whatItDoesNotDo: [
      'Does NOT route motion templates in active pipelines (motion_animation generates TSX dynamically)',
      'Does NOT mutate files or project state'
    ],
    missingCapabilities: [],
    validationTesting: {
      validationLogic: ['Validates that execution returns deprecated status cleanly'],
      testFiles: ['tests/test_agent_registry.py'],
      failureModesAndRecovery: ['Safe no-op.']
    },
    improvementOpportunities: [
      { priority: 'LOW', title: 'Formal Archival Documentation', currentLimitation: 'Preserved as stub.', desiredBehavior: 'Maintain as reference implementation for future template caching.', implementationGap: 'Document template fallback heuristics if dynamic codegen is offline.', dependencies: 'None' }
    ],
    sourceEvidence: {
      primaryFiles: ['SYSTEM/agents/video_generation_agents/motion_template_selection/agent.py'],
      supportingFiles: ['SYSTEM/registries/agent_registry.py'],
      classesAndFunctions: ['MotionTemplateSelectionAgent.execute()'],
      testFiles: ['tests/test_agent_registry.py']
    }
  },

  // =========================================================================
  // 14. MAIN ARCHITECTURE AGENT (main_architecture_agent)
  // =========================================================================
  main_architecture_agent: {
    agentId: 'main_architecture_agent',
    stageId: 'main_architecture_agent',
    name: 'Main Architecture Agent',
    role: 'System Architecture, Goal Decomposition & Governance Coordinator',
    category: 'orchestrator',
    version: '1.0.0',
    owner: 'system',
    badge: 'SYSTEM COORDINATOR',
    overview: {
      purpose: 'Coordinates agent discovery, high-level goal decomposition, task assignment, experience reflection, and system governance.',
      problemSolved: 'Breaks down complex natural-language goals into structured dependency DAGs and routes work to system subagents without manual orchestration.',
      position: 'Top-level system coordinator above individual system subagents (Skill Factory, Capability Finder, Architecture Validator, etc.).',
      upstream: 'Operator prompts, system configuration, CLI and API commands.',
      downstream: 'System subagents (Capability Finder, Skill Factory, Architecture Validator, Security Policy, Verification Agent, Autonomous Execution).',
      architectureRole: 'System-level architect and coordinator (distinct from PipelineOrchestrator).'
    },
    whatItDoes: {
      summary: 'Decomposes complex requests into executable subtasks with dependencies, routes tasks, records execution experiences, reflects on patterns, and governs strategies.',
      implementedResponsibilities: [
        'Decomposes multi-step goals into SubTask DAGs with dependency tracking via TaskDecomposer',
        'Capability-driven and experience-informed subtask routing via AgentRouter',
        'Pre-execution plan validation and dependency cycle checking via PlanEvaluator',
        'Delegates work to appropriate system subagents or video generation agents',
        'Captures execution experiences and redacts sensitive tokens via ExperienceCollector',
        'Performs self-reflection and pattern derivation via ReflectionEngine',
        'Generates governed declarative improvement proposals via ProposalEngine',
        'Executes deterministic planning benchmarks via EvaluationRunner',
        'Enforces execution limits and Laxman Approval gates before applying system changes'
      ],
      productionReadyFeatures: [
        'Atomic strategy lifecycle management (Candidate -> Validated -> Promoted -> Rolled Back)',
        'Comprehensive secret redaction in experience memory',
        'Deterministic benchmark evaluation suite'
      ]
    },
    howItWorks: {
      summary: 'Parses incoming task specs, generates execution DAGs, routes subtasks to specialized subagents, records experience outcomes, and enforces approvals.',
      stepByStepFlow: [
        { step: 1, title: 'Goal Intake & Deconstruction', detail: 'TaskDecomposer splits compound goal into granular, testable SubTasks with prerequisite links.', type: 'llm' },
        { step: 2, title: 'Plan Evaluation', detail: 'PlanEvaluator checks for dependency cycles, unfulfillable capabilities, and missing tools.', type: 'deterministic' },
        { step: 3, title: 'Agent Routing & Delegation', detail: 'AgentRouter matches subtasks to canonical agents based on capability tags and historical success.', type: 'deterministic' },
        { step: 4, title: 'Execution & Telemetry Capture', detail: 'Subtasks are executed while ExperienceCollector records timing, tool calls, and results.', type: 'external' },
        { step: 5, title: 'Reflection & Strategy Update', detail: 'ReflectionEngine analyzes successes and failures to synthesize continuous learning patterns.', type: 'llm' }
      ],
      concurrencyAndCaching: 'DAG-based execution allowing parallel dispatch of independent leaf subtasks.',
      retryLogic: 'Strategy-level fallbacks and alternative agent routing when primary delegation fails.'
    },
    inputsDependencies: {
      inputs: [
        { name: 'task_request', required: true, format: 'JSON / AgentRequest', description: 'Structured or natural language goal specification', pathExample: 'AgentRequest.parameters' },
        { name: 'system_registries', required: true, format: 'in-memory registries', description: 'AgentRegistry, ToolRegistry, SkillRegistry', pathExample: 'SYSTEM/registries/' }
      ],
      externalTools: ['agent_registry', 'tool_registry', 'skill_registry', 'memory_service', 'history_service'],
      systemDependencies: ['Python asyncio', 'UUID generation', 'JSON schema validation']
    },
    outputsSideEffects: {
      outputs: [
        { name: 'execution_plan.json', format: 'JSON DAG', description: 'Decomposed subtasks with execution states and assigned agents', pathExample: 'memory', consumers: ['AutonomousExecutionAgent', 'Operator'] },
        { name: 'decision_records.jsonl', format: 'JSONL', description: 'Audit trail of routing decisions, evaluations, and reflections', pathExample: 'config/history/decision_records.jsonl', consumers: ['VerificationAgent', 'Audit tools'] }
      ],
      sideEffects: ['Writes decision history', 'Dispatches delegated tasks to subagents'],
      errorStates: ['CYCLE_DETECTED', 'CAPABILITY_UNFULFILLABLE', 'APPROVAL_TIMEOUT']
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'High-reasoning architectural model (Gemini / Claude / GPT)',
      temperature: '0.2 (Low temperature for deterministic decomposition)',
      promptStrategy: 'Structured prompt with strict JSON output constraints for task DAGs and reflection patterns',
      fallbackStrategy: 'Deterministic rule-based task templates if LLM is unavailable',
      deterministicGuardrails: ['Acyclic graph verification', 'Hard boundary isolation preventing video engine bypass', 'Laxman approval gate for promotions'],
      purelyDeterministicParts: ['Plan cycle detection', 'Tool and agent registry queries', 'Redaction filtering']
    },
    currentCapabilities: [
      { name: 'Acyclic task decomposition', status: 'VERIFIED WORKING', description: 'Decomposes complex goals into verified topological execution DAGs.', evidence: 'Verified in SYSTEM/agents/main_architecture_agent/planning/task_decomposer.py' },
      { name: 'Capability-based agent routing', status: 'VERIFIED WORKING', description: 'Routes subtasks to best-fit agents according to registry capabilities.', evidence: 'Verified in SYSTEM/agents/main_architecture_agent/planning/agent_router.py' },
      { name: 'Autonomous strategy promotion & rollback', status: 'VERIFIED WORKING', description: 'Manages candidate strategy lifecycle with benchmark gates.', evidence: 'Verified in SYSTEM/agents/main_architecture_agent/learning/strategy_manager.py' }
    ],
    whatItDoesNotDo: [
      'Does NOT execute video rendering or ffmpeg commands directly (delegates to Video Pipeline Orchestrator)',
      'Does NOT bypass SecurityPolicyAgent permissions'
    ],
    missingCapabilities: [
      { title: 'Distributed Multi-Host Agent Coordination', status: 'NOT IMPLEMENTED', gapDescription: 'Agents run within local process tree; distributed network worker clustering is not yet implemented.', impact: 'Execution is bounded to single workstation resources.', plannedResolution: 'Add Celery / Ray distributed actor backend.' }
    ],
    validationTesting: {
      validationLogic: ['Validates DAG acyclicity', 'Validates all subtasks map to registered capabilities', 'Verifies approval tokens before promotions'],
      testFiles: ['tests/test_main_architecture_agent.py', 'tests/test_agent_routing.py'],
      failureModesAndRecovery: ['Subtask timeout: Captures failure context, reflects on error, attempts alternate agent routing.']
    },
    improvementOpportunities: [
      { priority: 'MEDIUM', title: 'Self-Organizing Agent Swarm Hierarchies', currentLimitation: 'Fixed 2-tier hierarchy (Coordinator -> Subagents).', desiredBehavior: 'Dynamically spin up transient sub-swarms for complex sub-objectives.', implementationGap: 'Implement dynamic agent lifecycle pooling in agent_router.', dependencies: 'asyncio' }
    ],
    sourceEvidence: {
      primaryFiles: ['SYSTEM/agents/main_architecture_agent/agent.py'],
      supportingFiles: [
        'SYSTEM/agents/main_architecture_agent/planning/task_decomposer.py',
        'SYSTEM/agents/main_architecture_agent/planning/agent_router.py',
        'SYSTEM/agents/main_architecture_agent/planning/plan_evaluator.py',
        'SYSTEM/agents/main_architecture_agent/learning/strategy_manager.py'
      ],
      classesAndFunctions: [
        'MainArchitectureAgent.execute()',
        'TaskDecomposer.decompose()',
        'AgentRouter.route()',
        'PlanEvaluator.evaluate()'
      ],
      testFiles: ['tests/test_main_architecture_agent.py', 'tests/test_agent_routing.py']
    }
  },

  // =========================================================================
  // 15. CAPABILITY FINDER AGENT (capability_finder)
  // =========================================================================
  capability_finder: {
    agentId: 'capability_finder',
    stageId: 'capability_finder',
    name: 'Capability Finder Agent',
    role: 'AST Code Scanner, Prerequisite Inspection & Gap Analysis',
    category: 'system_subagent',
    version: '3.0.0',
    owner: 'system',
    badge: 'DISCOVERY & GAP ENGINE',
    overview: {
      purpose: 'Discovers matching agents and skills based on task specifications and inspects prerequisite readiness with evidence-based self-learning.',
      problemSolved: 'Prevents runtime failures caused by missing tools or unverified code by evaluating static AST definitions and external system dependencies.',
      position: 'Discovery and inspection subagent called during system planning and skill adaptation.',
      upstream: 'MainArchitectureAgent, SkillFactoryAgent, and developer queries.',
      downstream: 'SkillFactoryAgent (for gap closure) and AgentRouter (for task matching).',
      architectureRole: 'Codebase discovery, static AST inspector, and capability matcher.'
    },
    whatItDoes: {
      summary: 'Parses natural language requirements, scans AST definitions, matches skills/agents, analyzes gaps, and tracks lessons learned.',
      implementedResponsibilities: [
        'Scans Python AST trees for classes, decorators, and functions without unverified code execution',
        'Parses requirement queries with strict semantic keyword extraction',
        'Evaluates system runtime prerequisites (FFmpeg binaries, Whisper weights, Node Remotion packages)',
        'Computes structured gap analysis between required and registered capabilities',
        'Captures learning cases and attributes outcomes to knowledge rules',
        'Executes candidate lesson evaluations against benchmark test suites'
      ],
      productionReadyFeatures: [
        'Static AST code inspection avoiding unsafe import side-effects',
        'Prerequisite validator for FFmpeg, Python libraries, and GPU acceleration',
        'Controlled knowledge promoter and rollback manager'
      ]
    },
    howItWorks: {
      summary: 'Analyzes queries via RequirementParser, queries CapabilityMatcher and ASTScanner, performs GapAnalysis, and returns ranked recommendations.',
      stepByStepFlow: [
        { step: 1, title: 'Requirement Parsing', detail: 'Extracts action verbs, target domains, and required capabilities from request.', type: 'deterministic' },
        { step: 2, title: 'Registry Query', detail: 'Checks SkillRegistry, AgentRegistry, and CapabilityRegistry for existing matches.', type: 'deterministic' },
        { step: 3, title: 'AST Code Scan', detail: 'Scans codebase to discover unindexed capabilities or verify existing signatures.', type: 'deterministic' },
        { step: 4, title: 'Prerequisite Check', detail: 'Runs shutil.which for CLI tools and probes environment variables.', type: 'deterministic' },
        { step: 5, title: 'Gap Synthesis', detail: 'Compiles missing capabilities with actionable recommendations for SkillFactory.', type: 'deterministic' }
      ],
      concurrencyAndCaching: 'In-memory cache for AST scan results with file modification timestamp invalidation.',
      retryLogic: 'Deterministic queries; falls back to fuzzy keyword matching on strict match misses.'
    },
    inputsDependencies: {
      inputs: [
        { name: 'query_or_spec', required: true, format: 'string / dict', description: 'Capability query or structured requirement specification', pathExample: '{"action": "query", "query": "bilingual audio"}' }
      ],
      externalTools: ['agent_registry', 'skill_registry', 'tool_registry'],
      systemDependencies: ['Python ast module', 'shutil.which for binary checks']
    },
    outputsSideEffects: {
      outputs: [
        { name: 'matching_result', format: 'JSON dict', description: 'Matched agents, skills, tools, and prerequisite readiness status', pathExample: 'memory', consumers: ['MainArchitectureAgent', 'SkillFactoryAgent'] },
        { name: 'gap_report', format: 'JSON dict', description: 'Structured gap analysis detailing missing functions and resolution paths', pathExample: 'memory', consumers: ['SkillFactoryAgent'] }
      ],
      sideEffects: ['Updates learning case memory'],
      errorStates: ['PREREQUISITE_MISSING', 'NO_MATCH_FOUND']
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'Fast analysis LLM (for fuzzy requirement parsing and lesson generation)',
      temperature: '0.1',
      promptStrategy: 'Zero-shot structured schema extraction from free-form prompts',
      fallbackStrategy: 'Rule-based regex keyword extraction if LLM is offline',
      deterministicGuardrails: ['Zero unverified code execution (AST-only scanner)', 'Cryptographic hash checks'],
      purelyDeterministicParts: ['AST scanning', 'Prerequisite checking', 'Registry lookups']
    },
    currentCapabilities: [
      { name: 'Static AST scanner', status: 'VERIFIED WORKING', description: 'Safely extracts class and function signatures without executing unverified code.', evidence: 'Verified in SYSTEM/agents/capability_finder/discovery/ast_scanner.py' },
      { name: 'Prerequisite readiness inspection', status: 'VERIFIED WORKING', description: 'Verifies external tools like FFmpeg, Whisper, Node.', evidence: 'Tested across test_capability_finder.py' },
      { name: 'Deduplicated gap analysis', status: 'VERIFIED WORKING', description: 'Produces clean missing-capability diffs.', evidence: 'Verified in SYSTEM/agents/capability_finder/discovery/gap_analyzer.py' }
    ],
    whatItDoesNotDo: [
      'Does NOT synthesize new skills (delegates to SkillFactoryAgent)',
      'Does NOT execute unverified candidate code'
    ],
    missingCapabilities: [
      { title: 'Vector Semantic Search Embedding Store', status: 'PARTIALLY IMPLEMENTED', gapDescription: 'Uses keyword and AST matching rather than dense vector embeddings.', impact: 'Synonym-heavy queries may miss non-obvious skill matches.', plannedResolution: 'Integrate local fast-embed or Chroma vector store.' }
    ],
    validationTesting: {
      validationLogic: ['Validates AST parser on syntactically valid and invalid python files', 'Asserts zero import side-effects'],
      testFiles: ['tests/test_capability_finder.py', 'tests/test_capability_matching.py'],
      failureModesAndRecovery: ['Syntax error in target file: Skips corrupted file and logs AST parsing warning.']
    },
    improvementOpportunities: [
      { priority: 'MEDIUM', title: 'Dense Semantic Vector Search', currentLimitation: 'Relies on AST tokens and exact keywords.', desiredBehavior: 'Semantic capability retrieval using embedded vectors.', implementationGap: 'Add embedding index to CapabilityRegistry.', dependencies: 'chromadb or sqlite-vss' }
    ],
    sourceEvidence: {
      primaryFiles: ['SYSTEM/agents/capability_finder/agent.py'],
      supportingFiles: [
        'SYSTEM/agents/capability_finder/discovery/ast_scanner.py',
        'SYSTEM/agents/capability_finder/discovery/gap_analyzer.py',
        'SYSTEM/agents/capability_finder/discovery/matcher.py',
        'SYSTEM/agents/capability_finder/discovery/requirement_parser.py'
      ],
      classesAndFunctions: [
        'CapabilityFinderAgent.execute()',
        'ASTScanner.scan_file()',
        'CapabilityMatcher.match()',
        'GapAnalyzer.analyze_gaps()'
      ],
      testFiles: ['tests/test_capability_finder.py', 'tests/test_capability_matching.py']
    }
  },

  // =========================================================================
  // 16. SKILL FACTORY AGENT (skill_factory)
  // =========================================================================
  skill_factory: {
    agentId: 'skill_factory',
    stageId: 'skill_factory',
    name: 'Skill Factory Agent',
    role: 'Autonomous Skill Synthesis, AST Security Auditing & Atomic Promotion',
    category: 'system_subagent',
    version: '1.0.0',
    owner: 'system',
    badge: 'AUTONOMOUS SKILL SYNTHESIS',
    overview: {
      purpose: 'Generates, adapts, tests, and registers custom skills following strict YAML frontmatter, sandboxed verification, and security rules.',
      problemSolved: 'Safely extends system capabilities without manual coding by synthesizing modular skills with automated security audits and rollbacks.',
      position: 'Self-improvement and skill development subagent coordinated by MainArchitectureAgent.',
      upstream: 'Gap reports from CapabilityFinderAgent or operator skill generation requests.',
      downstream: 'SkillRegistry, CapabilityRegistry, and specialized video agents.',
      architectureRole: 'Autonomous skill synthesizer and lifecycle gatekeeper.'
    },
    whatItDoes: {
      summary: 'Evaluates reuse vs adapt vs create decisions, synthesizes candidate skills, executes static AST security audits, tests in isolation, and coordinates promotion.',
      implementedResponsibilities: [
        'Evaluates Reuse / Adapt / Create decision resolution via DecisionEngine',
        'Synthesizes candidate skills adhering to standard SKILL.md format and YAML frontmatter',
        'Executes static security and AST audit detecting injection, secret leakage, and pipeline stage file tampering',
        'Runs isolated behavioral tests with strict execution timeouts and zero persistent side-effects',
        'Verifies Laxman Approval tokens before promoting candidate skills',
        'Performs atomic versioned promotion to SYSTEM/skills/ and updates CapabilityRegistry',
        'Executes safe rollbacks of published skills to prior versions if regressions occur'
      ],
      productionReadyFeatures: [
        'Static security validator enforcing pipeline stage file protection',
        'Sandboxed test runner with strict CPU and wall-clock execution bounds',
        'Atomic directory-swap skill promotion with rollback journal'
      ]
    },
    howItWorks: {
      summary: 'Takes SkillSpecification, runs DecisionEngine, synthesizes SKILL.md, verifies AST security, runs tests, and publishes upon approval.',
      stepByStepFlow: [
        { step: 1, title: 'Specification Intake', detail: 'Normalizes SkillSpecification with input/output types and security constraints.', type: 'deterministic' },
        { step: 2, title: 'Reuse/Adapt Decision', detail: 'DecisionEngine checks existing skill library to determine whether to reuse, adapt, or create from scratch.', type: 'deterministic' },
        { step: 3, title: 'Skill Synthesis', detail: 'SkillGenerator creates candidate markdown skill with YAML frontmatter, execution instructions, and test fixtures.', type: 'llm' },
        { step: 4, title: 'Security & AST Audit', detail: 'SecurityValidator inspects candidate code for dangerous imports, system calls, and pipeline stage file touches.', type: 'deterministic' },
        { step: 5, title: 'Isolated Behavioral Test', detail: 'SkillTestRunner executes candidate in isolated subprocess against defined test cases.', type: 'external' },
        { step: 6, title: 'Atomic Promotion', detail: 'SkillPublisher installs approved skill into SYSTEM/skills/ and notifies CapabilityRegistry.', type: 'deterministic' }
      ],
      concurrencyAndCaching: 'Candidate staging isolated in temporary workspace directories to prevent collision.',
      retryLogic: 'LLM self-correction loop: feeds test failures or security findings back to generator for up to 3 repair attempts.'
    },
    inputsDependencies: {
      inputs: [
        { name: 'skill_spec', required: true, format: 'SkillSpecification dict', description: 'Name, purpose, inputs, outputs, constraints, test fixtures', pathExample: '{"name": "visual.scene_pacing", "category": "visual"}' },
        { name: 'action', required: false, format: 'string', description: 'Action to perform: audit, stage, test, promote, rollback', pathExample: '"promote"' }
      ],
      externalTools: ['skill_registry', 'ast_validator', 'test_runner'],
      systemDependencies: ['Python subprocess', 'PyYAML for frontmatter parsing']
    },
    outputsSideEffects: {
      outputs: [
        { name: 'SKILL.md', format: 'Markdown with YAML header', description: 'Standardized executable skill definition with instructions and test specifications', pathExample: 'SYSTEM/skills/{category}/{name}/SKILL.md', consumers: ['SkillRegistry', 'Specialized agents'] },
        { name: 'promotion_receipt.json', format: 'JSON', description: 'Cryptographic hash, author signature, and timestamp of promoted skill', pathExample: 'SYSTEM/skills/{category}/{name}/receipt.json', consumers: ['ArchitectureValidator'] }
      ],
      sideEffects: ['Writes skill files to SYSTEM/skills/', 'Registers new capability in CapabilityRegistry'],
      errorStates: ['SECURITY_VIOLATION', 'TEST_FAILURE', 'PROMOTION_ERROR', 'ROLLBACK_FAILED']
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'High-capability code generation model (Claude / Gemini Pro)',
      temperature: '0.2',
      promptStrategy: 'Few-shot structured prompt enforcing strict YAML frontmatter, markdown sections, and testable code blocks',
      fallbackStrategy: 'Template-based generation for standard data transformation skills',
      deterministicGuardrails: [
        'SecurityValidator AST audit detects dangerous calls (os.system, subprocess with shell=True)',
        'Mandatory test pass before promotion eligibility'
      ],
      purelyDeterministicParts: ['Security audit', 'Test execution', 'Atomic file installation', 'Registry registration']
    },
    currentCapabilities: [
      { name: 'Static security validation', status: 'VERIFIED WORKING', description: 'Detects shell injection, unauthorized file access, and pipeline stage tampering.', evidence: 'Verified in SYSTEM/agents/skill_factory/security_validator.py' },
      { name: 'Isolated test execution', status: 'VERIFIED WORKING', description: 'Executes skill test fixtures in bounded subprocesses.', evidence: 'Verified in SYSTEM/agents/skill_factory/test_runner.py' },
      { name: 'Atomic skill promotion', status: 'VERIFIED WORKING', description: 'Safely installs validated skills with zero-downtime registry updates.', evidence: 'Verified in SYSTEM/agents/skill_factory/publisher.py' }
    ],
    whatItDoesNotDo: [
      'Does NOT promote skills that fail security checks or test suites',
      'Does NOT bypass Laxman Approval gate on production skill promotion'
    ],
    missingCapabilities: [
      { title: 'Multi-Language Skill Synthesis (TypeScript / Rust)', status: 'PARTIALLY IMPLEMENTED', gapDescription: 'Currently specializes in Python skills; TypeScript and Rust skill generation are in prototype status.', impact: 'Remotion TSX skills require manual or template generation.', plannedResolution: 'Add TypeScript AST validator and ts-node test runner.' }
    ],
    validationTesting: {
      validationLogic: ['Validates YAML frontmatter conformity', 'Validates 100% test pass rate in isolated runner', 'Asserts zero changes to protected SHA-256 hashes'],
      testFiles: ['tests/test_skill_factory.py', 'tests/test_skill_security.py'],
      failureModesAndRecovery: ['Synthesis error: Feeds compiler or linter errors back to LLM for automated correction.']
    },
    improvementOpportunities: [
      { priority: 'HIGH', title: 'TypeScript / Remotion Component Skill Synthesis', currentLimitation: 'Python-only security validator and runner.', desiredBehavior: 'Synthesize and validate Remotion React animation skills with ts-morph AST auditing.', implementationGap: 'Integrate ts-morph and Vitest test runner into SkillFactory.', dependencies: 'Node.js, ts-morph' }
    ],
    sourceEvidence: {
      primaryFiles: ['SYSTEM/agents/skill_factory/agent.py'],
      supportingFiles: [
        'SYSTEM/agents/skill_factory/decision_engine.py',
        'SYSTEM/agents/skill_factory/generator.py',
        'SYSTEM/agents/skill_factory/security_validator.py',
        'SYSTEM/agents/skill_factory/test_runner.py',
        'SYSTEM/agents/skill_factory/publisher.py'
      ],
      classesAndFunctions: [
        'SkillFactoryAgent.execute()',
        'DecisionEngine.evaluate()',
        'SecurityValidator.audit()',
        'SkillPublisher.promote()'
      ],
      testFiles: ['tests/test_skill_factory.py', 'tests/test_skill_security.py']
    }
  },

  // =========================================================================
  // 17. ARCHITECTURE VALIDATOR AGENT (architecture_validator)
  // =========================================================================
  architecture_validator: {
    agentId: 'architecture_validator',
    stageId: 'architecture_validator',
    name: 'Architecture Validator Agent',
    role: 'Structural Integrity, Registry Audits & Boundary Enforcer',
    category: 'system_subagent',
    version: '1.0.0',
    owner: 'system',
    badge: 'INTEGRITY & REGISTRY AUDITOR',
    overview: {
      purpose: 'Audits architectural consistency, agent and capability registries, dependency graphs, video pipeline integrity, and security boundaries.',
      problemSolved: 'Detects architectural drift, circular dependencies, orphan capabilities, broken stage ordering, and unauthorized modifications.',
      position: 'Independent system validation agent providing read-only audits across the entire architecture.',
      upstream: 'MainArchitectureAgent, CI/CD verification scripts, and operator audit triggers.',
      downstream: 'VerificationAndTestAgent, SecurityPolicyAgent, and operator audit reports.',
      architectureRole: 'System integrity guardian and structural auditor.'
    },
    whatItDoes: {
      summary: 'Performs comprehensive structural audits across registries, dependency graphs, video pipeline contracts, and security boundaries.',
      implementedResponsibilities: [
        'Audits AgentRegistry structural consistency, adapter imports, and metadata completeness',
        'Audits SkillRegistry and CapabilityRegistry for path confinement, missing files, and duplicate keys',
        'Validates dependency graphs for cycle detection, topological reachability, and orphan nodes',
        'Validates video pipeline 12-stage ordering, artifact contracts, and mandatory LLM-decided approval gates',
        'Enforces architecture and security boundaries (sole execution engine rule)',
        'Produces structured AuditResult with severity-classified findings (INFO, WARNING, ERROR, CRITICAL)'
      ],
      productionReadyFeatures: [
        'Read-only audit execution by default with zero persistent side-effects',
        'Full architecture audit covering 7 core validation subsystems'
      ]
    },
    howItWorks: {
      summary: 'Executes targeted or full audits using specialized validator modules, aggregates findings, and reports pass/fail verdicts.',
      stepByStepFlow: [
        { step: 1, title: 'Audit Mode Resolution', detail: 'Determines target audit scope (full, agent_registry, video_pipeline, security_boundary).', type: 'deterministic' },
        { step: 2, title: 'Registry Consistency Check', detail: 'AgentRegistryValidator and CapabilityRegistryValidator inspect all metadata records.', type: 'deterministic' },
        { step: 3, title: 'Dependency Graph Audit', detail: 'DependencyGraphValidator performs topological sort to verify absence of cycles.', type: 'deterministic' },
        { step: 4, title: 'Video Pipeline Validation', detail: 'VideoPipelineValidator checks 12-stage sequential ordering and artifact handoffs.', type: 'deterministic' },
        { step: 5, title: 'Security Boundary Inspection', detail: 'SecurityBoundaryValidator checks path confinement and the sole execution engine rule.', type: 'deterministic' },
        { step: 6, title: 'Finding Aggregation', detail: 'Compiles findings, assigns overall pass/fail status, and formats structured report.', type: 'deterministic' }
      ],
      concurrencyAndCaching: 'Read-only concurrent execution safe.',
      retryLogic: 'Deterministic validations; re-runs immediately on demand.'
    },
    inputsDependencies: {
      inputs: [
        { name: 'audit_request', required: false, format: 'JSON dict', description: 'Action (full_architecture_audit, video_pipeline_audit) and mode (strict, permissive)', pathExample: '{"action": "full_architecture_audit"}' }
      ],
      externalTools: ['agent_registry', 'skill_registry', 'capability_registry', 'ast_scanner', 'hash_verifier'],
      systemDependencies: ['Python hashlib', 'graphlib / topological sorting']
    },
    outputsSideEffects: {
      outputs: [
        { name: 'audit_report', format: 'JSON / AuditResult', description: 'Audit summary, finding counts, severity breakdown, and actionable fix hints', pathExample: 'memory', consumers: ['MainArchitectureAgent', 'VerificationAndTestAgent'] }
      ],
      sideEffects: ['Zero filesystem side-effects (read-only audit)'],
      errorStates: ['AUDIT_FAILED', 'REGISTRY_CORRUPTED']
    },
    llmDecisionMaking: {
      usesLlm: false,
      modelOrProfile: 'Purely deterministic rule engine and graph auditor',
      promptStrategy: 'No LLM in core audit loop; uses formal invariant checks',
      fallbackStrategy: 'Halts on critical failure and flags specific violated rule',
      deterministicGuardrails: ['Cryptographic hash matching', 'Formal DAG acyclicity proof', 'Strict schema enforcement'],
      purelyDeterministicParts: ['All parts are 100% deterministic']
    },
    currentCapabilities: [
      { name: 'Agent registry consistency audit', status: 'VERIFIED WORKING', description: 'Validates all 20 canonical agents have valid metadata and adapters.', evidence: 'Verified in SYSTEM/agents/architecture_validator/validators.py' },
      { name: 'Video pipeline contract audit', status: 'VERIFIED WORKING', description: 'Asserts canonical 12-stage ordering and approval gate placement.', evidence: 'Tested in tests/test_architecture_validator.py' }
    ],
    whatItDoesNotDo: [
      'Does NOT automatically mutate or fix code (strictly read-only diagnostic auditor)',
      'Does NOT execute video rendering or audio processing'
    ],
    missingCapabilities: [],
    validationTesting: {
      validationLogic: ['Validates detection of injected cycles', 'Validates detection of broken stage sequences'],
      testFiles: ['tests/test_architecture_validator.py'],
      failureModesAndRecovery: ['Integrity error detected: Immediately reports CRITICAL finding and halts downstream actions.']
    },
    improvementOpportunities: [
      { priority: 'LOW', title: 'Interactive Web Audit Dashboard', currentLimitation: 'Audits invoked via API / CLI.', desiredBehavior: 'Live visual dependency graph viewer with highlight on broken links.', implementationGap: 'Add React flow visualization tab to UI.', dependencies: 'reactflow' }
    ],
    sourceEvidence: {
      primaryFiles: ['SYSTEM/agents/architecture_validator/agent.py'],
      supportingFiles: [
        'SYSTEM/agents/architecture_validator/contracts.py',
        'SYSTEM/agents/architecture_validator/validators.py'
      ],
      classesAndFunctions: [
        'ArchitectureValidatorAgent.execute()',
        'AgentRegistryValidator.validate()',
        'VideoPipelineValidator.validate()',
        'SecurityBoundaryValidator.validate()'
      ],
      testFiles: ['tests/test_architecture_validator.py']
    }
  },

  // =========================================================================
  // 18. VERIFICATION & TEST AGENT (verification_and_test)
  // =========================================================================
  verification_and_test: {
    agentId: 'verification_and_test',
    stageId: 'verification_and_test',
    name: 'Verification & Test Agent',
    role: 'Evidence-Driven Testing, Component Mapping & Failure Diagnosis',
    category: 'system_subagent',
    version: '1.0.0',
    owner: 'system',
    badge: 'EVIDENCE & TEST VERIFIER',
    overview: {
      purpose: 'Executes evidence-driven verification, component-mapped testing, failure diagnosis, and regression protection.',
      problemSolved: 'Replaces guessing with empirical test evidence, maps modified files to required test suites, and diagnoses root causes.',
      position: 'System verification engine invoked before promoting changes or declaring task completion.',
      upstream: 'AutonomousExecutionAgent, MainArchitectureAgent, and developer commands.',
      downstream: 'MainArchitectureAgent (for promotion decisions) and AutonomousExecutionAgent (for retry/recovery).',
      architectureRole: 'Automated test runner, failure diagnostician, and evidence validator.'
    },
    whatItDoes: {
      summary: 'Maps modified components to test suites, executes pytest in isolated subprocesses, captures bounded logs, and diagnoses failures.',
      implementedResponsibilities: [
        'Maps modified files to corresponding test suites via ComponentMapper',
        'Executes pytest subprocesses with strict execution bounds and timeouts via TestExecutor',
        'Captures and bounds stdout/stderr output to prevent memory exhaustion',
        'Diagnoses root causes from test tracebacks and error messages via Diagnostician',
        'Computes evidence-based verdicts (PASS, FAIL, BLOCKED, CONDITIONAL)'
      ],
      productionReadyFeatures: [
        'Subprocess isolation with per-test timeout watchdog',
        'Component mapping table connecting 40+ system files to specific test suites',
        'Root-cause diagnostic classification'
      ]
    },
    howItWorks: {
      summary: 'Resolves tests from component map, executes pytest with bounded capture, diagnoses failures if any, and issues verdict.',
      stepByStepFlow: [
        { step: 1, title: 'Component Mapping', detail: 'ComponentMapper maps changed files to authoritative pytest files.', type: 'deterministic' },
        { step: 3, title: 'Test Execution', detail: 'TestExecutor launches pytest in isolated subprocess with bounded stdout capture.', type: 'external' },
        { step: 4, title: 'Result Parsing', detail: 'Parses pytest exit code, passed/failed counts, durations, and failure tracebacks.', type: 'deterministic' },
        { step: 5, title: 'Failure Diagnosis', detail: 'Diagnostician classifies root cause (assertion, syntax, import, timeout, resource).', type: 'llm' },
        { step: 6, title: 'Verdict Issuance', detail: 'Issues final VerificationVerdict with supporting evidence references.', type: 'deterministic' }
      ],
      concurrencyAndCaching: 'Subprocesses run in isolated working environments.',
      retryLogic: 'Flaky test detector: re-runs single failed test once to differentiate flake from genuine regression.'
    },
    inputsDependencies: {
      inputs: [
        { name: 'verification_request', required: true, format: 'JSON dict', description: 'Action (verify, run_tests, verify_regression) and target components or test paths', pathExample: '{"action": "verify", "changed_files": ["VIDEO_ENGINE/stages/visual_planning.py"]}' }
      ],
      externalTools: ['pytest_runner', 'hash_verifier', 'agent_registry', 'component_mapper', 'diagnostician'],
      systemDependencies: ['Python subprocess', 'pytest binary', 'hashlib']
    },
    outputsSideEffects: {
      outputs: [
        { name: 'VerificationReport', format: 'JSON', description: 'Overall verdict (PASS/FAIL), test suite results, failure diagnoses, and evidence refs', pathExample: 'memory', consumers: ['AutonomousExecutionAgent', 'MainArchitectureAgent'] }
      ],
      sideEffects: ['Writes temporary test artifacts to .pytest_cache'],
      errorStates: ['TEST_EXECUTION_TIMEOUT', 'SUBPROCESS_CRASH']
    },
    llmDecisionMaking: {
      usesLlm: true,
      modelOrProfile: 'Fast diagnostic model (used solely for interpreting tracebacks in Diagnostician)',
      temperature: '0.0',
      promptStrategy: 'Structured prompt with traceback input, requesting root cause hypothesis and minimal fix suggestion',
      fallbackStrategy: 'Deterministic regex traceback parsing if LLM is unavailable',
      deterministicGuardrails: [
        'Deterministic pytest exit code determines PASS/FAIL verdict (LLM cannot override test result)',
        'Bit-for-bit SHA-256 hash checks are 100% deterministic'
      ],
      purelyDeterministicParts: ['Test execution', 'Exit code parsing', 'SHA-256 verification', 'Verdict assignment']
    },
    currentCapabilities: [
      { name: 'Automated component-to-test mapping', status: 'VERIFIED WORKING', description: 'Maps system modifications to relevant test suites.', evidence: 'Verified in SYSTEM/agents/verification_and_test/component_mapper.py' },
      { name: 'Subprocess test isolation', status: 'VERIFIED WORKING', description: 'Runs tests with timeouts and memory bounding.', evidence: 'Verified in SYSTEM/agents/verification_and_test/test_executor.py' }
    ],
    whatItDoesNotDo: [
      'Does NOT automatically edit code (strictly diagnostic and verification engine)',
      'Does NOT fabricate test results (all verdicts backed by actual pytest output)'
    ],
    missingCapabilities: [
      { title: 'Differential Test Selection via Code Coverage', status: 'PARTIALLY IMPLEMENTED', gapDescription: 'Uses static component mapping rather than live bytecode line coverage diffs.', impact: 'May run slightly more tests than strictly necessary.', plannedResolution: 'Integrate pytest-cov differential mapping.' }
    ],
    validationTesting: {
      validationLogic: ['Validates that test failure produces FAIL verdict', 'Validates hash mismatch produces CRITICAL FAIL verdict', 'Validates timeout handling'],
      testFiles: ['tests/test_verification_and_test.py'],
      failureModesAndRecovery: ['Timeout: Kills stuck test subprocess cleanly, records TIMEOUT diagnosis, and continues.']
    },
    improvementOpportunities: [
      { priority: 'MEDIUM', title: 'Live Code Coverage Differential Selector', currentLimitation: 'Static file mapping table.', desiredBehavior: 'Dynamically select only tests that execute modified AST statements using coverage.py.', implementationGap: 'Integrate pytest-cov and coverage database analysis.', dependencies: 'coverage' }
    ],
    sourceEvidence: {
      primaryFiles: ['SYSTEM/agents/verification_and_test/agent.py'],
      supportingFiles: [
        'SYSTEM/agents/verification_and_test/component_mapper.py',
        'SYSTEM/agents/verification_and_test/test_executor.py',
        'SYSTEM/agents/verification_and_test/diagnostician.py',
        'SYSTEM/agents/verification_and_test/contracts.py'
      ],
      classesAndFunctions: [
        'VerificationAndTestAgent.execute()',
        'ComponentMapper.get_tests_for_component()',
        'TestExecutor.execute_tests()',
        'Diagnostician.diagnose()'
      ],
      testFiles: ['tests/test_verification_and_test.py']
    }
  },

  // =========================================================================
  // 19. SECURITY POLICY AGENT (security_policy)
  // =========================================================================
  security_policy: {
    agentId: 'security_policy',
    stageId: 'security_policy',
    name: 'Security Policy Agent',
    role: 'Access Control & Sandbox Confinement',
    category: 'system_subagent',
    version: '1.0.0',
    owner: 'system',
    badge: 'SECURITY & PERMISSION GUARD',
    overview: {
      purpose: 'Evaluates security policies, agent permissions, tool access, file and sandbox boundaries, approval requirements, and enforcement for the video automation system.',
      problemSolved: 'Prevents unauthorized tool execution, path traversal outside sandbox boundaries, risk escalation, and unapproved state mutations.',
      position: 'Security gatekeeper inspecting requests across both system agents and video pipeline stages.',
      upstream: 'All agents making tool or file system requests, and operator authorization prompts.',
      downstream: 'Tool execution dispatchers, file writing routines, and approval managers.',
      architectureRole: 'Security policy evaluator and boundary enforcer.'
    },
    whatItDoes: {
      summary: 'Evaluates action risks, checks agent tool permissions, enforces path confinement, and verifies approval tokens.',
      implementedResponsibilities: [
        'Evaluates security policies and agent authorizations via PolicyEvaluator',
        'Enforces tool access control lists according to AgentMetadata.allowed_tools',
        'Enforces directory confinement and prevents path traversal (Path.resolve sandboxing)',
        'Classifies action risks into LOW, MEDIUM, HIGH, and CRITICAL levels',
        'Verifies Laxman Approval requirements for high-risk operations'
      ],
      productionReadyFeatures: [
        'Zero-trust path verification rejecting directory traversal',
        'Atomic policy enforcement raising SecurityPolicyViolationError on breach'
      ]
    },
    howItWorks: {
      summary: 'Inspects SecurityRequest against active PolicyState, checks tool whitelist, evaluates sandbox paths, and either grants or blocks execution.',
      stepByStepFlow: [
        { step: 1, title: 'Request Intake', detail: 'Receives SecurityRequest containing agent_id, action, target_paths, and tool_name.', type: 'deterministic' },
        { step: 2, title: 'Tool Whitelist Verification', detail: 'Asserts requested tool is present in calling agent allowed_tools metadata.', type: 'deterministic' },
        { step: 3, title: 'Path Confinement Check', detail: 'Verifies target_paths resolve strictly within approved project sandbox root.', type: 'deterministic' },
        { step: 5, title: 'Risk & Approval Assessment', detail: 'Determines RiskLevel; requires verified approval token for HIGH or CRITICAL operations.', type: 'deterministic' },
        { step: 6, title: 'Decision Issuance', detail: 'Returns PolicyDecision (ALLOW, DENY, REQUIRE_APPROVAL).', type: 'deterministic' }
      ],
      concurrencyAndCaching: 'Thread-safe policy evaluation with atomic enforcer state.',
      retryLogic: 'Deterministic rule evaluations; denied requests raise exception immediately.'
    },
    inputsDependencies: {
      inputs: [
        { name: 'security_request', required: true, format: 'SecurityRequest dict', description: 'Agent ID, operation name, target file paths, tool ID, and approval credentials', pathExample: '{"agent_id": "skill_factory", "action": "write_file", "path": "SYSTEM/skills/"}' }
      ],
      externalTools: ['agent_registry', 'tool_registry', 'approval_engine', 'policy_enforcer', 'hash_verifier'],
      systemDependencies: ['Python pathlib for path resolution', 'hashlib']
    },
    outputsSideEffects: {
      outputs: [
        { name: 'PolicyDecision', format: 'JSON', description: 'Decision (ALLOW, DENY, REQUIRE_APPROVAL), risk level, and rationale', pathExample: 'memory', consumers: ['Tool execution dispatcher', 'Agent orchestrator'] }
      ],
      sideEffects: ['Logs security decisions to security_audit.jsonl'],
      errorStates: ['SECURITY_POLICY_VIOLATION', 'PATH_TRAVERSAL_DETECTED']
    },
    llmDecisionMaking: {
      usesLlm: false,
      modelOrProfile: 'Purely deterministic security policy engine',
      promptStrategy: 'No LLM in security evaluation path; uses strict deterministic ACL rules',
      fallbackStrategy: 'Default-deny: blocks any unclassified or unrecognized operation',
      deterministicGuardrails: [
        'Default-deny security model',
        'Absolute path canonicalization rejecting ../ traversal',
        'Cryptographic hash verification for protected files'
      ],
      purelyDeterministicParts: ['All policy evaluation and enforcement is 100% deterministic']
    },
    currentCapabilities: [
      { name: 'Path traversal confinement', status: 'VERIFIED WORKING', description: 'Guarantees file operations remain strictly within project directories.', evidence: 'Verified in SYSTEM/agents/security_policy/enforcer.py' },
      { name: 'Tool access control enforcement', status: 'VERIFIED WORKING', description: 'Blocks agents from executing tools outside their allowed_tools list.', evidence: 'Tested in tests/test_security_policy.py' }
    ],
    whatItDoesNotDo: [
      'Does NOT permit path traversal outside verified sandbox directories'
    ],
    missingCapabilities: [],
    validationTesting: {
      validationLogic: ['Validates that path traversal attempts raise SecurityPolicyViolationError', 'Validates unauthorized tool execution is blocked', 'Validates approval token verification'],
      testFiles: ['tests/test_security_policy.py'],
      failureModesAndRecovery: ['Violation detected: Immediately blocks action and records security audit incident.']
    },
    improvementOpportunities: [
      { priority: 'LOW', title: 'Real-Time Security Alert Webhooks', currentLimitation: 'Logs violations locally to disk.', desiredBehavior: 'Send instant webhook alerts on CRITICAL security violations.', implementationGap: 'Add webhook notification dispatcher to PolicyEnforcer.', dependencies: 'requests or httpx' }
    ],
    sourceEvidence: {
      primaryFiles: ['SYSTEM/agents/security_policy/agent.py'],
      supportingFiles: [
        'SYSTEM/agents/security_policy/contracts.py',
        'SYSTEM/agents/security_policy/evaluator.py',
        'SYSTEM/agents/security_policy/enforcer.py'
      ],
      classesAndFunctions: [
        'SecurityPolicyAgent.execute()',
        'PolicyEvaluator.evaluate()',
        'SecurityPolicyEnforcer.enforce()'
      ],
      testFiles: ['tests/test_security_policy.py']
    }
  },

  // =========================================================================
  // 20. AUTONOMOUS EXECUTION AGENT (autonomous_execution)
  // =========================================================================
  autonomous_execution: {
    agentId: 'autonomous_execution',
    stageId: 'autonomous_execution',
    name: 'Autonomous Execution Agent',
    role: 'Bounded Subtask Execution, Crash Recovery & Checkpoint Supervisor',
    category: 'system_subagent',
    version: '1.0.0',
    owner: 'system',
    badge: 'AUTONOMOUS RESILIENT EXECUTION',
    overview: {
      purpose: 'Supervises autonomous task execution, bounded failure recovery, durable checkpointing, and independent completion verification without competing with the Main Architecture Agent or Video Pipeline Orchestrator.',
      problemSolved: 'Enables safe autonomous execution of multi-step tasks with automatic crash recovery, loop prevention, and evidence-based completion verification.',
      position: 'Task execution supervisor working under MainArchitectureAgent and utilizing VerificationAndTestAgent.',
      upstream: 'MainArchitectureAgent (receives task plans) and system operator.',
      downstream: 'VerificationAndTestAgent (for completion checks) and individual task runners.',
      architectureRole: 'Autonomous task execution engine, recovery manager, and checkpoint supervisor.'
    },
    whatItDoes: {
      summary: 'Runs bounded execution loops, persists durable checkpoints, prevents execution loops, recovers from transient failures, and verifies completion before declaring success.',
      implementedResponsibilities: [
        'Supervises multi-step task execution via TaskRunner with bounded iterations',
        'Persists durable JSON checkpoints after each completed subtask via CheckpointManager',
        'Enforces loop prevention by detecting identical repeated error states',
        'Executes bounded recovery strategies (retry with backoff, parameter adjustment, alternate tool) via RecoveryManager',
        'Dispatches VerificationAndTestAgent to verify acceptance criteria before declaring task completion',
        'Maintains strict isolation from Video Pipeline Orchestrator and Security Policy'
      ],
      productionReadyFeatures: [
        'Durable disk-persisted task checkpoints supporting atomic resume',
        'Execution loop detector terminating infinite failure cycles',
        'Evidence-based completion verification gate'
      ]
    },
    howItWorks: {
      summary: 'Executes task specification step-by-step, checkpoints progress, catches failures, applies bounded recovery, and invokes verification before marking done.',
      stepByStepFlow: [
        { step: 1, title: 'Task Specification Intake', detail: 'Parses TaskRequirementSpec including acceptance criteria and retry budgets.', type: 'deterministic' },
        { step: 2, title: 'Checkpoint Resume Check', detail: 'CheckpointManager inspects existing task checkpoints to resume from last valid state.', type: 'deterministic' },
        { step: 3, title: 'Step Execution Loop', detail: 'TaskRunner executes task steps sequentially, recording StepExecutionRecords.', type: 'external' },
        { step: 4, title: 'Failure & Recovery Management', detail: 'On failure, RecoveryManager evaluates error pattern and applies targeted recovery action.', type: 'deterministic' },
        { step: 5, title: 'Loop Detection', detail: 'Detects duplicate error states across consecutive retries and halts if stuck.', type: 'deterministic' },
        { step: 6, title: 'Completion Verification', detail: 'Invokes VerificationAndTestAgent to ensure all acceptance criteria pass before setting COMPLETED.', type: 'deterministic' }
      ],
      concurrencyAndCaching: 'Thread-safe execution per task ID with locked checkpoint files.',
      retryLogic: 'Bounded retries (default max 3) with exponential backoff and alternate recovery strategies.'
    },
    inputsDependencies: {
      inputs: [
        { name: 'task_spec', required: true, format: 'TaskRequirementSpec dict', description: 'Task ID, steps, acceptance criteria, timeout, and max retry limits', pathExample: '{"task_id": "auto_task_01", "steps": [...], "max_retries": 3}' }
      ],
      externalTools: ['checkpoint_manager', 'recovery_manager', 'task_runner', 'verification_and_test'],
      systemDependencies: ['Python threading', 'JSON persistence']
    },
    outputsSideEffects: {
      outputs: [
        { name: 'task_checkpoint.json', format: 'JSON', description: 'Durable execution state, completed steps, variable bindings, and recovery history', pathExample: 'config/history/checkpoints/{task_id}.json', consumers: ['AutonomousExecutionAgent', 'MainArchitectureAgent'] },
        { name: 'execution_summary', format: 'JSON dict', description: 'Final execution report with step timings, retry counts, and verification verdict', pathExample: 'memory', consumers: ['MainArchitectureAgent'] }
      ],
      sideEffects: ['Writes checkpoint files to disk'],
      errorStates: ['TASK_TIMEOUT', 'LOOP_DETECTED', 'MAX_RETRIES_EXCEEDED', 'VERIFICATION_FAILED']
    },
    llmDecisionMaking: {
      usesLlm: false,
      modelOrProfile: 'Deterministic state machine with bounded recovery heuristics',
      promptStrategy: 'No LLM in autonomous loop supervisor core; uses deterministic recovery rules',
      fallbackStrategy: 'Halts on unrecoverable step, preserves checkpoint, reports precise blocker',
      deterministicGuardrails: [
        'Strict iteration cap preventing runaway execution loops',
        'Mandatory verification pass before state transitions to COMPLETED',
        'Checkpoint persistence preventing progress loss'
      ],
      purelyDeterministicParts: ['Step looping', 'Checkpoint persistence', 'Loop detection', 'Verification gating']
    },
    currentCapabilities: [
      { name: 'Durable checkpoint persistence', status: 'VERIFIED WORKING', description: 'Persists task state to disk allowing clean resume after interruption.', evidence: 'Verified in SYSTEM/agents/autonomous_execution/checkpoint_manager.py' },
      { name: 'Infinite loop prevention', status: 'VERIFIED WORKING', description: 'Detects duplicate error states and aborts runaway execution loops.', evidence: 'Tested in tests/test_autonomous_execution.py' },
      { name: 'Independent completion verification', status: 'VERIFIED WORKING', description: 'Requires empirical verification pass before declaring success.', evidence: 'Verified in SYSTEM/agents/autonomous_execution/agent.py' }
    ],
    whatItDoesNotDo: [
      'Does NOT bypass MainArchitectureAgent governance or SecurityPolicyAgent boundaries',
      'Does NOT silently lower acceptance criteria to force a passing state',
      'Does NOT replace Video Pipeline Orchestrator'
    ],
    missingCapabilities: [],
    validationTesting: {
      validationLogic: ['Validates checkpoint save and restore fidelity', 'Validates loop detection on repeated errors', 'Validates verification gate enforcement'],
      testFiles: ['tests/test_autonomous_execution.py'],
      failureModesAndRecovery: ['Crash during step execution: Loads last valid checkpoint on resume and restarts failed step.']
    },
    improvementOpportunities: [
      { priority: 'MEDIUM', title: 'Cross-Process Heartbeat & Orphan Recovery', currentLimitation: 'Recovery triggers on resume invocation.', desiredBehavior: 'Background daemon automatically detects orphaned tasks and resumes or archives them.', implementationGap: 'Add background watchdog thread in autonomous_execution service.', dependencies: 'threading' }
    ],
    sourceEvidence: {
      primaryFiles: ['SYSTEM/agents/autonomous_execution/agent.py'],
      supportingFiles: [
        'SYSTEM/agents/autonomous_execution/contracts.py',
        'SYSTEM/agents/autonomous_execution/checkpoint_manager.py',
        'SYSTEM/agents/autonomous_execution/recovery_manager.py',
        'SYSTEM/agents/autonomous_execution/task_runner.py'
      ],
      classesAndFunctions: [
        'AutonomousExecutionAgent.execute()',
        'CheckpointManager.save_checkpoint()',
        'RecoveryManager.evaluate_recovery()',
        'TaskRunner.run_task()'
      ],
      testFiles: ['tests/test_autonomous_execution.py']
    }
  }

};

export function getAgentAboutData(stageIdOrAgentId: string): AgentAboutData | null {
  if (!stageIdOrAgentId) return null;
  
  // Direct match by key
  if (AGENT_ABOUT_DATA[stageIdOrAgentId]) {
    return AGENT_ABOUT_DATA[stageIdOrAgentId];
  }
  
  // Match by agentId or stageId
  const byAgent = Object.values(AGENT_ABOUT_DATA).find(
    (item) => item.agentId === stageIdOrAgentId || item.stageId === stageIdOrAgentId
  );
  if (byAgent) return byAgent;
  
  // Check alias mappings
  const aliases: Record<string, string> = {
    audio_analyzer: 'analyzer',
    audio_input: 'analyzer',
    scene_segmentation: 'segmentation',
    visual_planning: 'planning',
    motion_planning: 'motion_plan',
    motion_animation: 'motion_gen',
    motion_generation: 'motion_gen',
    motion_timeline_validation: 'motion_validation',
    motion_validation: 'motion_validation',
    timeline_build: 'timeline',
    timeline_approval: 'approval',
    render_video: 'render',
    render: 'render',
    final_qc: 'qc',
    final_video_delivery: 'final',
    final_delivery: 'final',
    orchestrator: 'main_orchestrator',
    pipeline: 'main_orchestrator',
    architecture: 'main_architecture_agent',
    finder: 'capability_finder',
    factory: 'skill_factory',
    validator: 'architecture_validator',
    test: 'verification_and_test',
    security: 'security_policy',
    autonomous: 'autonomous_execution'
  };
  
  const mapped = aliases[stageIdOrAgentId];
  if (mapped && AGENT_ABOUT_DATA[mapped]) {
    return AGENT_ABOUT_DATA[mapped];
  }
  
  return null;
}

/**
 * Generates an exhaustive, structured GitHub-Flavored Markdown technical profile
 * covering all 19 technical specification points for sharing with Claude/GPT.
 */
export function generateAgentMarkdownExport(
  data: AgentAboutData,
  growthData?: any,
  upgradesData?: any[]
): string {
  const isVideo = data.category === 'video_engine_agent' || data.category === 'video_agent' || data.category === 'audio' || data.category === 'visual' || data.category === 'motion';
  const growth = growthData || {};
  const currentScores = growth.current_scores || {};
  const snapshots = growth.snapshots || [];
  const upgrades = upgradesData || [];

  return `# Agent Technical Profile: ${data.name} (\`${data.agentId}\`)

> **Autonomous System Architecture Profile**  
> Exported from: LAXMAN-AUTONOMOUS Video Generation Agent Intelligence System  
> Methodology Version: \`${growth.methodology_version || '1.0.0'}\`  
> Generation Timestamp: ${new Date().toISOString()}

---

## 1. Agent Identity & Metadata
- **Agent Name**: ${data.name}
- **Agent ID**: \`${data.agentId}\`
- **Stage ID**: \`${data.stageId}\`
- **Role**: ${data.role}
- **Category**: \`${data.category}\` (${isVideo ? 'Video Generation Pipeline' : 'System Subagent'})
- **Version**: \`${data.version}\`
- **Owner**: \`${data.owner}\`
- **Operational Badge**: \`${data.badge || 'PRODUCTION-READY'}\`

## 2. Executive Overview & Architectural Purpose
- **Mission Purpose**: ${data.overview.purpose}
- **Problem Solved**: ${data.overview.problemSolved}
- **Pipeline Position**: ${data.overview.position}
- **Architectural Role**: ${data.overview.architectureRole}

## 3. Direct Upstream Dependencies
- **Upstream Producer**: ${data.overview.upstream}
- **Input Data Contracts**:
${data.inputsDependencies.inputs.map(i => `  - **\`${i.name}\`** (${i.required ? 'REQUIRED' : 'OPTIONAL'}, \`${i.format}\`): ${i.description} [Example: \`${i.pathExample}\`]`).join('\n')}
- **System Dependencies**: ${data.inputsDependencies.systemDependencies.length > 0 ? data.inputsDependencies.systemDependencies.join(', ') : 'None'}

## 4. Direct Downstream Consumers
- **Downstream Consumer**: ${data.overview.downstream}
- **Produced Output Artifacts**:
${data.outputsSideEffects.outputs.map(o => `  - **\`${o.name}\`** (\`${o.format}\`): ${o.description} [Consumers: ${o.consumers.join(', ')}]`).join('\n')}

## 5. Execution Lifecycle & Trigger Conditions
- **Trigger Summary**: ${data.howItWorks.summary}
- **Concurrency & Caching Strategy**: ${data.howItWorks.concurrencyAndCaching}
- **Retry Logic & Error Recovery**: ${data.howItWorks.retryLogic}

## 6. Implemented Responsibilities (Verified in Production)
- **Summary**: ${data.whatItDoes.summary}
- **Implemented Responsibilities**:
${data.whatItDoes.implementedResponsibilities.map(r => `  - [x] ${r}`).join('\n')}
${data.whatItDoes.productionReadyFeatures.length > 0 ? `\n- **Production-Ready Features**:\n${data.whatItDoes.productionReadyFeatures.map(f => `  - ${f}`).join('\n')}` : ''}

## 7. Non-Responsibilities (Explicit System Boundaries)
${data.whatItDoesNotDo.map(nr => `  - [ ] ${nr}`).join('\n')}

## 8. Internal Step-by-Step Workflow
${data.howItWorks.stepByStepFlow.map(s => `${s.step}. **${s.title}** [\`${s.type.toUpperCase()}\`]: ${s.detail}`).join('\n')}

## 9. Complete Input Contracts
${data.inputsDependencies.inputs.map(i => `### Input: \`${i.name}\`
- **Requirement**: ${i.required ? 'MANDATORY (Fails without it)' : 'OPTIONAL (Sensible fallback)'}
- **Format**: \`${i.format}\`
- **Path Pattern**: \`${i.pathExample}\`
- **Description**: ${i.description}
`).join('\n')}

## 10. Complete Output Contracts
${data.outputsSideEffects.outputs.map(o => `### Output: \`${o.name}\`
- **Format**: \`${o.format}\`
- **Path Pattern**: \`${o.pathExample}\`
- **Description**: ${o.description}
- **Direct Downstream Consumers**: ${o.consumers.join(', ')}
`).join('\n')}
- **Filesystem & System Side Effects**:
${data.outputsSideEffects.sideEffects.map(se => `  - ${se}`).join('\n')}

## 11. LLM Usage & Prompt Strategy
- **Utilizes LLM**: ${data.llmDecisionMaking.usesLlm ? 'YES' : 'NO (100% Deterministic / External Engine)'}
- **Model / Profile**: \`${data.llmDecisionMaking.modelOrProfile}\`
- **Temperature**: \`${data.llmDecisionMaking.temperature || 'N/A'}\`
- **Prompt Strategy**: ${data.llmDecisionMaking.promptStrategy}
- **Fallback Strategy**: ${data.llmDecisionMaking.fallbackStrategy}
- **Deterministic Guardrails**:
${data.llmDecisionMaking.deterministicGuardrails.map(g => `  - ${g}`).join('\n')}
- **Purely Deterministic Subsystems**:
${data.llmDecisionMaking.purelyDeterministicParts.map(p => `  - ${p}`).join('\n')}

## 12. Tool & Skill Integrations
- **Allowed Tools**: ${data.inputsDependencies.externalTools.map(t => `\`${t}\``).join(', ') || 'None'}
- **Associated Skills**: (Indexed in SYSTEM/skills/ and registered in CapabilityRegistry)

## 13. Security Boundaries & Permissions
- **Filesystem Confinement**: Confined to active project sandbox or SYSTEM/ registries.
- **Approval Requirements**: Enforces human or cryptographic approval gate before critical state transitions.

## 14. Current Capabilities & Maturity Classification
${data.currentCapabilities.map(c => `- **[${c.status}]** ${c.name}: ${c.description}\n  - *Evidence*: \`${c.evidence}\``).join('\n')}

## 15. Missing Capabilities & Known Gaps
${data.missingCapabilities.length > 0 ? data.missingCapabilities.map(m => `- **[${m.status}]** ${m.title}: ${m.gapDescription}\n  - *Impact*: ${m.impact}${m.plannedResolution ? `\n  - *Planned Resolution*: ${m.plannedResolution}` : ''}`).join('\n') : '- No critical gaps identified in active scope.'}

## 16. Validation, Testing & Failure Recovery
- **Deterministic Validation Logic**:
${data.validationTesting.validationLogic.map(v => `  - ${v}`).join('\n')}
- **Authoritative Test Suites**:
${data.validationTesting.testFiles.map(tf => `  - \`${tf}\``).join('\n')}
- **Failure Modes & Recovery**:
${data.validationTesting.failureModesAndRecovery.map(fm => `  - ${fm}`).join('\n')}

## 17. Improvement Backlog & Upgrade Recommendations
${data.improvementOpportunities.map(opp => `### [${opp.priority} PRIORITY] ${opp.title}
- **Current Limitation**: ${opp.currentLimitation}
- **Desired Behavior**: ${opp.desiredBehavior}
- **Implementation Gap**: ${opp.implementationGap}
- **Dependencies**: \`${opp.dependencies}\`
`).join('\n')}

## 18. Source Code Evidence & Implementation References
- **Primary Source Files**:
${data.sourceEvidence.primaryFiles.map(pf => `  - \`${pf}\``).join('\n')}
- **Supporting Implementation Files**:
${data.sourceEvidence.supportingFiles.map(sf => `  - \`${sf}\``).join('\n')}
- **Key Classes & Functions**:
${data.sourceEvidence.classesAndFunctions.map(cf => `  - \`${cf}\``).join('\n')}
- **Verified Test Files**:
${data.sourceEvidence.testFiles.map(tf => `  - \`${tf}\``).join('\n')}

## 19. Growth & Maturity History

### Current Metric Scores (Maturity Formula v1.0.0)
- **Capability Readiness Score ($CRS$)**: **${currentScores.capability_readiness_score !== undefined ? `${currentScores.capability_readiness_score}%` : 'N/A'}**
- **Verification Coverage ($VC$)**: **${currentScores.verification_coverage !== undefined ? `${currentScores.verification_coverage}%` : 'N/A'}**
- **Quality Score ($QS$)**: **${currentScores.quality_metric || 'Empirically Verified'}**
- **Day-over-Day Delta**: ${currentScores.delta_day_over_day !== undefined ? (currentScores.delta_day_over_day >= 0 ? `+${currentScores.delta_day_over_day}%` : `${currentScores.delta_day_over_day}%`) : '0.0%'}
- **Baseline Growth Delta**: ${currentScores.delta_since_baseline !== undefined ? (currentScores.delta_since_baseline >= 0 ? `+${currentScores.delta_since_baseline}%` : `${currentScores.delta_since_baseline}%`) : '0.0%'}
- **Total Historical Snapshots**: ${growth.total_snapshots || snapshots.length}

### Historical Maturity Snapshots
| Date | CRS (%) | VC (%) | Quality Metric / Evidence Summary | Baseline |
| :--- | :---: | :---: | :--- | :---: |
${snapshots.map((s: any) => `| ${s.date} | ${s.capability_readiness_score}% | ${s.verification_coverage}% | ${s.evidence_summary || s.quality_metric} | ${s.is_baseline ? 'Yes (Baseline)' : 'No'} |`).join('\n')}

### Verified Upgrade Log
${upgrades.length > 0 ? upgrades.map((u: any) => `
#### Upgrade: \`${u.upgrade_id}\` [${u.verification_status}]
- **Timestamp**: ${u.timestamp}
- **Version Transition**: \`${u.before_version}\` -> \`${u.after_version}\`
- **Upgrade Reason**: ${u.reason}
- **Previous Limitation Resolved**: ${u.previous_limitation}
- **Capabilities Added**: ${u.capabilities_added.join(', ')}
- **Files Modified**:
${u.files_changed.map((f: string) => `  - \`${f}\``).join('\n')}
- **Verification References**: ${u.evidence_refs.join(', ')}
`).join('\n') : '- No individual upgrade records published yet for this agent.'}

---
*Report generated by LAXMAN-AUTONOMOUS Video Generation System — Agent Intelligence Module.*
`;
}
