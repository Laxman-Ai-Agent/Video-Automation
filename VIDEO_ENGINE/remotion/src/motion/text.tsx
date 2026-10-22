import type { CSSProperties, ReactNode } from "react";
import { useVideoConfig } from "remotion";
import { FONT, fontStack } from "../fonts";
import { resourceFontStack } from "../library/resources";
import { useAbsFrame, useScene } from "../sceneContext";
import type { LayerT } from "../schema";
import { SAFE, SCRIM, useLayout, usePalette } from "../theme";
import type { Run } from "./phrase";
import { textRoom } from "./core";
import { type TextFrame, type TextParams, textFrame } from "./textFrame";

const SPAN: CSSProperties = { display: "inline-block", whiteSpace: "pre" };

/** The look of one run of a phrase (font, size, colour ...): only what the run sets, so a word without a run is drawn exactly as before. */
function runCss(r: Run | undefined, size: number): CSSProperties {
  if (!r) return {};
  const o: CSSProperties = {};
  if (r.font && r.font !== "sans") o.fontFamily = fontStack(r.font);
  if (r.scale && r.scale !== 1) o.fontSize = size * r.scale;
  if (r.weight) o.fontWeight = r.weight;
  if (r.italic) o.fontStyle = "italic";
  if (r.color) o.color = r.color;
  if (r.upper) o.textTransform = "uppercase";
  if (r.track) o.letterSpacing = `${r.track}em`;
  return o;
}

function Words({ f, accent }: { f: TextFrame; accent: string }): ReactNode {
  let ci = 0;
  return f.lines.map((l, li) => (
    <div key={li} style={{ ...l.style, whiteSpace: "nowrap" }}>
      {l.words.map((w, wi) => {
        const deco = w.emphDeco === "underline"
          ? <span aria-hidden style={{ position: "absolute", left: 0, bottom: "-0.06em", height: "0.07em", width: `${w.e * 100}%`, background: accent, borderRadius: 4 }} />
          : w.emphDeco === "stroke"
            ? <span aria-hidden style={{ position: "absolute", inset: "0.08em -0.12em", background: accent, transformOrigin: "left", transform: `scaleX(${w.e})`, zIndex: -1, borderRadius: "0.12em" }} />
            : null;
        return (
          <span key={wi} style={{ ...SPAN, position: "relative", isolation: "isolate", marginRight: wi < l.words.length - 1 ? "0.28em" : 0, ...runCss(w.run, f.size), ...w.style, ...w.emph }}>
            {w.chars ? w.chars.map((c, i) => <span key={i} style={{ ...SPAN, ...c.style }} data-i={ci++}>{c.text}</span>) : w.text}
            {deco}
          </span>
        );
      })}
    </div>
  ));
}

/** The text of one frame as React: every word of the script is always in the DOM and in order (presets only change how it is revealed). */
export function MotionTextView({ f, a, extra }: { f: TextFrame; a: TextParams; extra?: CSSProperties }) {
  const color = a.color ?? "#ffffff";
  const base: CSSProperties = { fontFamily: a.fontId ? resourceFontStack(a.fontId, FONT, a.fontSha) : fontStack(a.font), fontSize: f.size, fontWeight: a.weight ?? 800, lineHeight: 1.12, color, textShadow: a.flat ? "none" : "0 6px 30px rgba(0,0,0,0.55)", display: "inline-block", position: "relative" };
  const fullText = a.text;
  if (f.hidden) return null;
  const kind = f.deco.kind;
  const inner = <Words f={f} accent={a.accent} />;
  const sweepStyle: CSSProperties = kind === "sweep"
    ? { backgroundImage: `linear-gradient(100deg, ${color} 0%, ${color} ${f.deco.sweep * 130 - 25}%, #fff ${f.deco.sweep * 130 - 12}%, ${color} ${f.deco.sweep * 130}%, ${color} 100%)`, WebkitBackgroundClip: "text", backgroundClip: "text", WebkitTextFillColor: f.deco.sweep > 0 && f.deco.sweep < 1 ? "transparent" : undefined, textShadow: "none" } as CSSProperties
    : {};
  if (kind === "split") {
    const off = (1 - f.blockP) * f.size * 3;
    return (
      <div aria-label={fullText} style={{ ...base, ...extra, ...f.block }}>
        <div aria-hidden style={{ clipPath: f.blockP >= 1 ? "none" : "inset(0 0 50% 0)", transform: f.blockP >= 1 ? undefined : `translateX(${-off}px)` }}>{inner}</div>
        {f.blockP < 1 && <div aria-hidden style={{ position: "absolute", inset: 0, clipPath: "inset(50% 0 0 0)", transform: `translateX(${off}px)` }}>{inner}</div>}
      </div>
    );
  }
  return (
    <div aria-label={fullText} style={{ ...base, ...extra, ...f.block, ...sweepStyle }}>
      {kind === "layered" && <div aria-hidden style={{ position: "absolute", left: 0, top: 0, color: a.accent, opacity: 0.28 * f.blockP, transform: `translate(${(0.06 + (1 - f.blockP) * 0.2) * f.size}px, ${0.07 * f.size}px)`, textShadow: "none", filter: "blur(1.5px)" }}>{inner}</div>}
      <div style={{ position: "relative" }}>{inner}</div>
      {kind === "underline" && <div aria-hidden style={{ position: "absolute", left: 0, bottom: "-0.1em", height: "0.07em", width: `${f.deco.u * 100}%`, background: a.accent, borderRadius: 4 }} />}
      {kind === "caret" && f.deco.caret.on && <span aria-hidden style={{ position: "absolute", right: "-0.22em", bottom: "0.1em", width: "0.07em", height: "0.8em", background: a.accent }} />}
    </div>
  );
}

const STYLES = ["headline", "caption", "label", "quote", "lower-third"] as const;
/** Layer `motion_text`: the same boxes and safe margins as the classic text, any preset of the library. */
export const MotionTextLayer: React.FC<{ layer: LayerT }> = ({ layer }) => {
  const l = layer as LayerT & Partial<Omit<TextParams, "fps" | "size" | "maxWidth" | "exit">> & { exitPreset?: string; style?: string; pos?: [number, number]; center?: boolean; size?: number };
  const abs = useAbsFrame();
  const { fps, width } = useVideoConfig();
  const lay = useLayout();
  const { hasImage } = useScene();
  const { accent } = usePalette();
  const style = (STYLES as readonly string[]).includes(l.style ?? "") ? (l.style as (typeof STYLES)[number]) : "headline";
  const boxW = textRoom(width * (1 - 2 * SAFE) * (style === "headline" || style === "quote" || lay.portrait ? 1 : 0.7), width, SAFE, l.pos, l.center);
  const size = l.size ?? (style === "headline" || style === "quote" ? lay.type.display : lay.type.body);
  const at = l.at ?? l.enter?.at ?? 0;
  // the layer's own `exit` is the classic {at, anim, dur} object of the schema: the exit PRESET of the library is `exitPreset`
  const a: TextParams = { ...l, exit: l.exitPreset, text: l.text ?? "", at, size, maxWidth: boxW, accent: l.accent ?? accent, fps, weight: style === "headline" ? 800 : 600, until: l.until };
  const f = textFrame(a, abs);
  const place: CSSProperties = l.pos
    ? { left: l.pos[0], top: l.pos[1], transform: l.center ? "translateX(-50%)" : undefined }
    : style === "headline" ? { left: 0, right: 0, top: "38%", textAlign: "center" }
    : style === "quote" ? { left: `${SAFE * 100}%`, top: "30%", textAlign: "left" }
    : style === "caption" ? { left: 0, right: 0, bottom: lay.captionBottom, textAlign: "center" }
    : style === "label" ? { left: "6%", top: lay.labelTop } : { left: "6%", bottom: lay.lowerThirdBottom };
  const band: CSSProperties = hasImage ? { background: `rgba(0,0,0,${SCRIM})`, padding: "10px 28px", borderRadius: 14 } : {};
  return (
    <div style={{ position: "absolute", ...place, textAlign: (place.textAlign as CSSProperties["textAlign"]) ?? "left" }}>
      <MotionTextView f={f} a={a} extra={band} />
    </div>
  );
};
