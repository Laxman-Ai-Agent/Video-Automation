import { sampleTimeline } from "../gsapTimeline";

/** The checkmark effect as one GSAP timeline: the disc pops in (overshoot), the tick draws, then everything fades. `seconds` since the effect started, `dur` its length. */
export const checkmarkTimeline = (seconds: number, dur: number) =>
  sampleTimeline({ pop: 0, draw: 0, fade: 1 }, (tl, o) => {
    tl.fromTo(o, { pop: 0 }, { pop: 1, duration: 0.25 * dur, ease: "back.out(2)" }, 0)
      .fromTo(o, { draw: 0 }, { draw: 1, duration: 0.6 * dur, ease: "power2.out" }, 0)
      .fromTo(o, { fade: 1 }, { fade: 0, duration: 0.2 * dur, ease: "none" }, 0.8 * dur);
  }, seconds);
