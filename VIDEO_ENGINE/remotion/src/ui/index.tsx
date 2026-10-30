// UI building blocks for generated scenes (import from "../ui"): the pieces of a polished explainer card layout, so a scene spends its code on the idea, not on redrawing a glass card.
// Frame-driven (spring from useCurrentFrame), SVG + DOM only, no canvas / WebGL / backdrop-filter. Colours are 6-digit hex strings (#RRGGBB): a glow is `${hex}55`.
// Unlike the optional motion kit these are always available: they are low-level parts (a card, a chip, a bar, a drawing), never a finished scene.
import React from "react";
import { interpolate, spring, useCurrentFrame, useVideoConfig } from "remotion";
import { FONT } from "../fonts";

/** 0 -> 1 spring that starts at frame `at` of the enclosing Sequence. */
export const useEnter = (at = 0, damping = 18): number => {
  const frame = useCurrentFrame();
  const { fps } = useVideoConfig();
  return spring({ frame: frame - at, fps, config: { damping, stiffness: 110 } });
};

/** A glass card with a glowing coloured border that rises in at frame `enterAt`. Put the card's own content (IconChip / Illustration, title, caption, ProgressRow ...) inside. */
export const GlassPanel: React.FC<{
  children?: React.ReactNode; accent: string; width?: number | string; height?: number | string; padding?: number; radius?: number; enterAt?: number; style?: React.CSSProperties;
}> = ({ children, accent, width, height, padding = 32, radius = 28, enterAt = 0, style }) => {
  const p = useEnter(enterAt);
  return (
    <div data-ui="glass-panel" style={{
      position: "relative", boxSizing: "border-box", width, height, padding, borderRadius: radius,
      background: "linear-gradient(160deg, rgba(255,255,255,0.11), rgba(255,255,255,0.03))", border: `2px solid ${accent}`,
      boxShadow: `0 0 36px ${accent}55, inset 0 0 28px ${accent}22, 0 30px 80px rgba(0,0,0,0.45)`,
      opacity: p, transform: `translateY(${(1 - p) * 24}px) scale(${0.96 + 0.04 * p})`, ...style,
    }}>{children}</div>
  );
};

/** A rounded gradient chip with a glow that holds an icon (Phosphor `weight="duotone"` / lucide, white) or an Illustration. */
export const IconChip: React.FC<{ children?: React.ReactNode; accent: string; size?: number; enterAt?: number }> = ({ children, accent, size = 96, enterAt = 0 }) => {
  const p = useEnter(enterAt);
  return (
    <div data-ui="icon-chip" style={{
      width: size, height: size, borderRadius: size * 0.28, display: "flex", alignItems: "center", justifyContent: "center", flexShrink: 0,
      background: `linear-gradient(145deg, ${accent}, ${accent}99)`, boxShadow: `0 0 28px ${accent}88, inset 0 2px 0 rgba(255,255,255,0.35)`,
      opacity: p, transform: `scale(${0.7 + 0.3 * p})`,
    }}>{children}</div>
  );
};

/** A round check badge (a finished step). */
export const CheckBadge: React.FC<{ size?: number; accent?: string; enterAt?: number }> = ({ size = 40, accent = "#2DD4A0", enterAt = 0 }) => {
  const p = useEnter(enterAt, 12);
  return (
    <svg width={size} height={size} viewBox="0 0 40 40" style={{ flexShrink: 0, transform: `scale(${p})`, filter: `drop-shadow(0 0 8px ${accent}99)` }}>
      <circle cx="20" cy="20" r="19" fill={accent} />
      <path d="M11 20.5l6.5 6.5L29 14" fill="none" stroke="#fff" strokeWidth="4.2" strokeLinecap="round" strokeLinejoin="round" />
    </svg>
  );
};

/** A labelled progress bar that fills to `progress` (0 to 1) and shows a check badge when it is full. The fill is decorative: it prints no number. */
export const ProgressRow: React.FC<{ label: string; progress?: number; accent: string; enterAt?: number; width?: number | string; labelSize?: number }> = ({ label, progress = 1, accent, enterAt = 0, width = "100%", labelSize = 26 }) => {
  const p = useEnter(enterAt);
  const fill = useEnter(enterAt + 8, 24) * progress;
  return (
    <div data-ui="progress-row" style={{ display: "flex", alignItems: "center", gap: 16, width, opacity: p, transform: `translateX(${(1 - p) * -20}px)` }}>
      <div style={{ width: 40, height: 40, flexShrink: 0 }}>{progress >= 1 ? <CheckBadge enterAt={enterAt + 18} /> : null}</div>
      <div style={{ flex: 1, minWidth: 0 }}>
        <div style={{ fontFamily: FONT, fontWeight: 600, fontSize: labelSize, color: "#f1f5f9", marginBottom: 8, lineHeight: 1.2 }}>{label}</div>
        <div style={{ height: 14, borderRadius: 7, background: "rgba(255,255,255,0.14)", overflow: "hidden" }}>
          <div style={{ width: `${fill * 100}%`, height: "100%", borderRadius: 7, background: `linear-gradient(90deg, ${accent}, #34d399)`, boxShadow: `0 0 14px ${accent}99` }} />
        </div>
      </div>
    </div>
  );
};

/** Straight connector lines with two glowing nodes each, drawn from their start to their end from frame `enterAt`. `lines` are [x1, y1, x2, y2] in px of a `width` x `height` area. */
export const FlowLines: React.FC<{ width: number; height: number; lines: [number, number, number, number][]; color: string; enterAt?: number }> = ({ width, height, lines, color, enterAt = 0 }) => {
  const frame = useCurrentFrame();
  const draw = interpolate(frame - enterAt, [0, 24], [0, 1], { extrapolateLeft: "clamp", extrapolateRight: "clamp" });
  return (
    <svg data-ui="flow-lines" width={width} height={height} viewBox={`0 0 ${width} ${height}`} style={{ position: "absolute", left: 0, top: 0, pointerEvents: "none" }}>
      {lines.map(([x1, y1, x2, y2], i) => (
        <g key={i}>
          <line x1={x1} y1={y1} x2={x1 + (x2 - x1) * draw} y2={y1 + (y2 - y1) * draw} stroke={color} strokeWidth={4} strokeLinecap="round" opacity={0.85} style={{ filter: `drop-shadow(0 0 6px ${color})` }} />
          {[0.35, 0.7].map((t) => (draw >= t ? <circle key={t} cx={x1 + (x2 - x1) * t} cy={y1 + (y2 - y1) * t} r={8} fill="#fff" stroke={color} strokeWidth={4} /> : null))}
        </g>
      ))}
    </svg>
  );
};

/** A headline in the display font; the words listed in `accentWords` (compared without punctuation, case ignored) are drawn in `accent`. */
export const Headline: React.FC<{ text: string; accent: string; accentWords?: string[]; size?: number; enterAt?: number; align?: "left" | "center" }> = ({ text, accent, accentWords = [], size = 112, enterAt = 0, align = "center" }) => {
  const p = useEnter(enterAt);
  const hot = new Set(accentWords.map((w) => w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "")));
  return (
    <div data-ui="headline" style={{ fontFamily: FONT, fontWeight: 800, fontSize: size, lineHeight: 1.1, textAlign: align, color: "#f8fafc", textShadow: "0 6px 28px rgba(0,0,0,0.55)", opacity: p, transform: `translateY(${(1 - p) * 30}px)` }}>
      {text.split(" ").map((w, i) => (
        <span key={i} style={{ color: hot.has(w.toLowerCase().replace(/[^\p{L}\p{N}]/gu, "")) ? accent : undefined }}>{i ? " " : ""}{w}</span>
      ))}
    </div>
  );
};

/** The scene backdrop of the reference look: deep gradient, a slow-drifting star field and a dark horizon at the bottom. Put it first inside the scene's AbsoluteFill. */
export const StarField: React.FC<{ from?: string; to?: string; count?: number; seed?: number }> = ({ from = "#0b2a3a", to = "#050b18", count = 70, seed = 7 }) => {
  const frame = useCurrentFrame();
  const { width, height } = useVideoConfig();
  const rnd = (n: number) => { const x = Math.sin(n * 127.1 + seed * 311.7) * 43758.5453; return x - Math.floor(x); };
  return (
    <div data-ui="star-field" style={{ position: "absolute", inset: 0, background: `radial-gradient(ellipse at 50% 38%, ${from} 0%, ${to} 75%)`, overflow: "hidden" }}>
      <svg width={width} height={height} style={{ position: "absolute", inset: 0 }}>
        {Array.from({ length: count }, (_, i) => {
          const tw = 0.35 + 0.65 * (0.5 + 0.5 * Math.sin(frame / 20 + rnd(i) * 6.28));
          return <circle key={i} cx={rnd(i + 11) * width} cy={((rnd(i + 23) * height - frame * (0.1 + rnd(i + 5) * 0.25)) % height + height) % height} r={1 + rnd(i + 3) * 2.6} fill="#cfe9ff" opacity={tw * 0.6} />;
        })}
        <ellipse cx={width / 2} cy={height * 1.12} rx={width * 0.75} ry={height * 0.2} fill="#06101f" opacity={0.85} />
      </svg>
    </div>
  );
};

/** A glowing orb with a slowly turning orbit ring and tick marks (the badge on top of the centre card); put a white icon inside. */
export const RingBadge: React.FC<{ children?: React.ReactNode; accent: string; ring?: string; size?: number; enterAt?: number }> = ({ children, accent, ring = "#2DD4BF", size = 130, enterAt = 0 }) => {
  const p = useEnter(enterAt);
  const frame = useCurrentFrame();
  const R = size / 2;
  return (
    <div data-ui="ring-badge" style={{ position: "relative", width: size, height: size, opacity: p, transform: `scale(${0.7 + 0.3 * p})`, flexShrink: 0 }}>
      <svg width={size} height={size} viewBox={`0 0 ${size} ${size}`} style={{ position: "absolute", inset: 0, transform: `rotate(${frame * 0.6}deg)` }}>
        <circle cx={R} cy={R} r={R - 3} fill="none" stroke={ring} strokeWidth={3} opacity={0.9} />
        {Array.from({ length: 12 }, (_, i) => { const a = (i / 12) * Math.PI * 2; return <line key={i} x1={R + Math.cos(a) * (R - 3)} y1={R + Math.sin(a) * (R - 3)} x2={R + Math.cos(a) * (R + 6)} y2={R + Math.sin(a) * (R + 6)} stroke={ring} strokeWidth={3} strokeLinecap="round" />; })}
      </svg>
      <div style={{ position: "absolute", inset: size * 0.14, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", background: `radial-gradient(circle at 35% 30%, #fff3d6, ${accent} 55%, ${accent}cc)`, boxShadow: `0 0 40px ${accent}aa, inset 0 -6px 14px rgba(0,0,0,0.18)` }}>{children}</div>
    </div>
  );
};

const Star: React.FC<{ size: number; color: string; on: boolean; enterAt: number }> = ({ size, color, on, enterAt }) => {
  const p = useEnter(enterAt, 10);
  return <svg width={size} height={size} viewBox="-12 -12 24 24" style={{ transform: `scale(${p})` }}><path d="M0-10l2.9 6.3 6.9.8-5.1 4.7 1.4 6.8L0 5.2l-6.1 3.4 1.4-6.8-5.1-4.7 6.9-.8z" fill={on ? color : "none"} stroke={color} strokeWidth={1.6} strokeLinejoin="round" /></svg>;
};

/** Five stars, the first `rating` of them filled; they pop in one by one. */
export const RatingStars: React.FC<{ rating?: number; size?: number; color?: string; enterAt?: number }> = ({ rating = 5, size = 34, color = "#FFC25A", enterAt = 0 }) => (
  <div data-ui="rating-stars" style={{ display: "flex", gap: size * 0.12 }}>
    {[0, 1, 2, 3, 4].map((i) => <Star key={i} size={size} color={color} on={i < rating} enterAt={enterAt + i * 3} />)}
  </div>
);

const MiniBar: React.FC<{ x: number; bw: number; h: number; height: number; accent: string; enterAt: number; op: number }> = ({ x, bw, h, height, accent, enterAt, op }) => {
  const p = useEnter(enterAt, 20);
  return <rect x={x} y={height - h * p} width={bw} height={h * p} rx={3} fill={accent} opacity={op} style={{ filter: `drop-shadow(0 0 5px ${accent}99)` }} />;
};

/** A small bar chart that rises bar by bar (a card's footer picture). `values` are 0..1. */
export const MiniBars: React.FC<{ values?: number[]; accent: string; width?: number; height?: number; enterAt?: number }> = ({ values = [0.2, 0.35, 0.3, 0.5, 0.45, 0.7, 0.85], accent, width = 300, height = 90, enterAt = 0 }) => {
  const gap = 8;
  const bw = (width - gap * (values.length - 1)) / values.length;
  return (
    <svg data-ui="mini-bars" width={width} height={height} viewBox={`0 0 ${width} ${height}`}>
      {values.map((v, i) => <MiniBar key={i} x={i * (bw + gap)} bw={bw} h={height * v} height={height} accent={accent} enterAt={enterAt + i * 3} op={0.5 + 0.5 * (i / values.length)} />)}
    </svg>
  );
};

/** A round glowing action badge holding a thumbs-up (approval / result). */
export const ThumbsBadge: React.FC<{ accent?: string; size?: number; enterAt?: number }> = ({ accent = "#14B8A6", size = 120, enterAt = 0 }) => {
  const p = useEnter(enterAt, 12);
  return (
    <div data-ui="thumbs-badge" style={{ width: size, height: size, borderRadius: "50%", display: "flex", alignItems: "center", justifyContent: "center", transform: `scale(${0.6 + 0.4 * p})`, opacity: p,
      background: `radial-gradient(circle at 35% 30%, ${accent}, ${accent}aa)`, border: "4px solid #7ff3e3", boxShadow: `0 0 44px ${accent}99, 0 0 0 14px ${accent}22` }}>
      <svg width={size * 0.5} height={size * 0.5} viewBox="0 0 24 24"><path d="M2 10h4v11H2zM8 10l4-8c1.7 0 3 1.3 3 3v3h5.4c1.4 0 2.4 1.3 2.1 2.6l-1.6 8A2.2 2.2 0 0 1 18.8 21H8z" fill="#fff" /></svg>
    </div>
  );
};

export type IllustrationName = "document-search" | "profile-card" | "growth-chart";

/** Two-colour illustrations (not line icons) for a card's hero picture: a document with a magnifier, a profile card with stars, a bar chart with a growth arrow. */
export const Illustration: React.FC<{ name: IllustrationName; size?: number; enterAt?: number }> = ({ name, size = 150, enterAt = 0 }) => {
  const p = useEnter(enterAt);
  const wrap = (body: React.ReactNode) => (
    <svg data-ui={`illustration-${name}`} width={size} height={size} viewBox="0 0 120 120" style={{ opacity: p, transform: `scale(${0.8 + 0.2 * p})`, filter: "drop-shadow(0 8px 18px rgba(0,0,0,0.4))" }}>
      <defs>
        <linearGradient id="ui-blue" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#5BB8FF" /><stop offset="1" stopColor="#2F6BE8" /></linearGradient>
        <linearGradient id="ui-amber" x1="0" y1="0" x2="1" y2="1"><stop offset="0" stopColor="#FFC25A" /><stop offset="1" stopColor="#F2812E" /></linearGradient>
      </defs>
      {body}
    </svg>
  );
  if (name === "document-search") {
    return wrap(<>
      <rect x="14" y="10" width="68" height="88" rx="10" fill="url(#ui-blue)" />
      <rect x="24" y="22" width="30" height="7" rx="3.5" fill="#fff" />
      {[40, 52, 64].map((y) => <rect key={y} x="24" y={y} width="48" height="5" rx="2.5" fill="#fff" opacity="0.7" />)}
      <circle cx="74" cy="72" r="22" fill="#cfe9ff" fillOpacity="0.35" stroke="#fff" strokeWidth="7" />
      <circle cx="74" cy="72" r="22" fill="none" stroke="#2F6BE8" strokeWidth="3" />
      <path d="M90 89l17 17" stroke="#fff" strokeWidth="9" strokeLinecap="round" />
      <path d="M90 89l17 17" stroke="#2F6BE8" strokeWidth="4" strokeLinecap="round" />
    </>);
  }
  if (name === "profile-card") {
    return wrap(<>
      <rect x="8" y="16" width="104" height="84" rx="12" fill="url(#ui-amber)" />
      <circle cx="40" cy="40" r="12" fill="#fff" opacity="0.95" />
      <path d="M20 70c2-11 10-17 20-17s18 6 20 17z" fill="#fff" opacity="0.95" />
      <rect x="64" y="32" width="38" height="6" rx="3" fill="#fff" opacity="0.9" />
      <rect x="64" y="44" width="28" height="6" rx="3" fill="#fff" opacity="0.7" />
      <rect x="20" y="84" width="80" height="6" rx="3" fill="#fff" opacity="0.55" />
    </>);
  }
  return wrap(<>
    {[[14, 70], [38, 54], [62, 40], [86, 24]].map(([x, y], i) => <rect key={i} x={x} y={y} width="18" height={104 - y} rx="4" fill="url(#ui-amber)" opacity={0.55 + i * 0.15} />)}
    <path d="M10 62C40 60 62 44 98 14" fill="none" stroke="#FFC25A" strokeWidth="6" strokeLinecap="round" />
    <path d="M80 12h22v22" fill="none" stroke="#FFC25A" strokeWidth="6" strokeLinecap="round" strokeLinejoin="round" />
  </>);
};
