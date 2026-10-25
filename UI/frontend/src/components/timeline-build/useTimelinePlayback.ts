import { useState, useEffect, useRef, useMemo, useCallback } from 'react';

export function useTimelinePlayback(fps: number, totalFrames: number, totalDurationSeconds: number) {
  const [currentFrame, setCurrentFrame] = useState<number>(0);
  const [isPlaying, setIsPlaying] = useState<boolean>(false);
  const [zoomLevel, setZoomLevel] = useState<number>(1);
  const [copiedArtifact, setCopiedArtifact] = useState<string | null>(null);

  const audioRef = useRef<HTMLAudioElement | null>(null);
  const timelineScrollRef = useRef<HTMLDivElement | null>(null);
  const animationFrameRef = useRef<number | null>(null);

  // Playback Control Loop
  useEffect(() => {
    if (!isPlaying) {
      if (audioRef.current && !audioRef.current.paused) {
        audioRef.current.pause();
      }
      if (animationFrameRef.current) {
        cancelAnimationFrame(animationFrameRef.current);
      }
      return;
    }

    if (audioRef.current) {
      const expectedAudioTime = currentFrame / fps;
      if (Math.abs(audioRef.current.currentTime - expectedAudioTime) > 0.15) {
        audioRef.current.currentTime = expectedAudioTime;
      }
      audioRef.current.play().catch(() => {});
    }

    let lastTime = performance.now();
    const frameDuration = 1000 / fps;

    const tick = (now: number) => {
      const delta = now - lastTime;
      if (delta >= frameDuration) {
        setCurrentFrame((prev) => {
          if (prev >= totalFrames - 1) {
            setIsPlaying(false);
            return 0;
          }
          return prev + 1;
        });
        lastTime = now - (delta % frameDuration);
      }
      animationFrameRef.current = requestAnimationFrame(tick);
    };

    animationFrameRef.current = requestAnimationFrame(tick);

    return () => {
      if (animationFrameRef.current) cancelAnimationFrame(animationFrameRef.current);
    };
  }, [isPlaying, fps, totalFrames, currentFrame]);

  // Keyboard navigation shortcuts
  useEffect(() => {
    const handleKeyDown = (e: KeyboardEvent) => {
      if (e.target instanceof HTMLInputElement || e.target instanceof HTMLTextAreaElement) return;

      if (e.code === 'Space') {
        e.preventDefault();
        setIsPlaying((p) => !p);
      } else if (e.code === 'ArrowLeft' || e.key.toLowerCase() === 'j') {
        e.preventDefault();
        setIsPlaying(false);
        setCurrentFrame((prev) => Math.max(0, prev - (e.shiftKey ? 15 : 1)));
      } else if (e.code === 'ArrowRight' || e.key.toLowerCase() === 'l') {
        e.preventDefault();
        setIsPlaying(false);
        setCurrentFrame((prev) => Math.min(totalFrames - 1, prev + (e.shiftKey ? 15 : 1)));
      } else if (e.code === 'Home') {
        e.preventDefault();
        setCurrentFrame(0);
      } else if (e.code === 'End') {
        e.preventDefault();
        setCurrentFrame(totalFrames - 1);
      }
    };

    window.addEventListener('keydown', handleKeyDown);
    return () => window.removeEventListener('keydown', handleKeyDown);
  }, [totalFrames]);

  // Zoom Pixel Width Computation
  const timelinePixelWidth = useMemo(() => {
    const baseWidth = 1100;
    return Math.max(baseWidth, baseWidth * zoomLevel);
  }, [zoomLevel]);

  const frameToPx = useCallback((frame: number) => {
    if (totalFrames <= 0) return 0;
    return (frame / totalFrames) * timelinePixelWidth;
  }, [totalFrames, timelinePixelWidth]);

  // Dynamic Ruler Interval
  const rulerTicks = useMemo(() => {
    const pxPerSec = timelinePixelWidth / Math.max(1, totalDurationSeconds);
    let stepSec = 5;
    if (pxPerSec > 220) stepSec = 0.5;
    else if (pxPerSec > 110) stepSec = 1;
    else if (pxPerSec > 55) stepSec = 2;
    else stepSec = 5;

    const ticks: { sec: number; frame: number; leftPx: number }[] = [];
    for (let s = 0; s <= totalDurationSeconds + 0.1; s += stepSec) {
      const frame = Math.round(s * fps);
      ticks.push({ sec: Number(s.toFixed(2)), frame, leftPx: frameToPx(frame) });
    }
    return ticks;
  }, [timelinePixelWidth, totalDurationSeconds, fps, frameToPx]);

  // Scrubbing on Timeline
  const handleTimelineClick = (e: React.MouseEvent<HTMLDivElement>) => {
    const rect = e.currentTarget.getBoundingClientRect();
    const clickX = e.clientX - rect.left;
    const progress = Math.max(0, Math.min(1, clickX / rect.width));
    const targetFrame = Math.round(progress * (totalFrames - 1));
    setCurrentFrame(targetFrame);
    if (audioRef.current) {
      audioRef.current.currentTime = targetFrame / fps;
    }
  };

  const handleCopyJson = (content: any, label: string) => {
    navigator.clipboard.writeText(JSON.stringify(content, null, 2));
    setCopiedArtifact(label);
    setTimeout(() => setCopiedArtifact(null), 2500);
  };

  return {
    currentFrame,
    setCurrentFrame,
    isPlaying,
    setIsPlaying,
    zoomLevel,
    setZoomLevel,
    audioRef,
    timelineScrollRef,
    timelinePixelWidth,
    frameToPx,
    rulerTicks,
    handleTimelineClick,
    handleCopyJson,
    copiedArtifact
  };
}
