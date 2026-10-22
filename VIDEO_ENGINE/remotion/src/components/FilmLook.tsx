import { random, useCurrentFrame } from "remotion";

// Vignette + subtle seeded grain; grain re-seeds every 2 frames for a film flicker.
export const FilmLook: React.FC = () => {
  const frame = useCurrentFrame();
  const seed = Math.floor(random(Math.floor(frame / 2)) * 1000);
  return (
    <>
      <div style={{
        position: "absolute", inset: 0, pointerEvents: "none",
        background: "radial-gradient(ellipse at center, rgba(0,0,0,0) 55%, rgba(0,0,0,0.55) 100%)",
      }} />
      <svg style={{ position: "absolute", inset: 0, width: "100%", height: "100%",
        mixBlendMode: "overlay", opacity: 0.18, pointerEvents: "none" }}>
        <filter id="grain">
          <feTurbulence type="fractalNoise" baseFrequency="0.8" numOctaves="2" seed={seed} stitchTiles="stitch" />
          <feColorMatrix type="saturate" values="0" />
        </filter>
        <rect width="100%" height="100%" filter="url(#grain)" />
      </svg>
    </>
  );
};
