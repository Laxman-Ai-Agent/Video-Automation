import gsap from "gsap";

/**
 * GSAP for render-critical animation, driven by the Remotion frame: a PAUSED timeline over a plain object of numbers, sought to an exact time, then read.
 * The result depends only on (init, build, seconds): no wall clock, no requestAnimationFrame, no DOM. GSAP only writes the numbers of this object; React
 * turns them into attributes, so no element property has two owners. Use it for a coordinated multi-part choreography; simple fades stay interpolate().
 */
export function sampleTimeline<T extends Record<string, number>>(init: T, build: (tl: gsap.core.Timeline, target: T) => void, seconds: number): T {
  const target = { ...init };
  const tl = gsap.timeline({ paused: true, defaults: { overwrite: false } });
  build(tl, target);
  tl.seek(Math.max(0, seconds), false); // false: no callbacks/events while seeking
  tl.kill();
  return Object.fromEntries(Object.keys(init).map((k) => [k, target[k]])) as T; // only the numbers: GSAP also attaches its own cache (_gsap) to the target
}
