/** Determinism check of the GSAP adapter (run: npx tsx scripts/gsap_determinism.ts). Prints one JSON line {ok, checks}; exit code 1 when a check fails. */
import { sampleTimeline } from "../src/gsapTimeline";
import { checkmarkTimeline } from "../src/components/checkmarkTimeline";

const fps = 30, dur = 1.2;
const at = (frame: number) => checkmarkTimeline(frame / fps, dur);
const checks: Record<string, boolean> = {};
const forward = Array.from({ length: 37 }, (_, f) => at(f));
const backward = Array.from({ length: 37 }, (_, i) => at(36 - i)).reverse();
checks.same_frame_same_values_in_any_order = JSON.stringify(forward) === JSON.stringify(backward);
checks.repeat_is_identical = JSON.stringify(at(20)) === JSON.stringify(at(20));
checks.starts_at_rest = at(0).pop === 0 && at(0).draw === 0 && at(0).fade === 1;
checks.ends_complete = at(36).draw === 1 && at(36).fade === 0 && Math.abs(at(36).pop - 1) < 1e-9;
checks.values_bounded = forward.every((v) => v.draw >= 0 && v.draw <= 1 && v.fade >= 0 && v.fade <= 1 && v.pop >= 0 && v.pop < 1.5);
checks.draw_never_goes_backwards = forward.every((v, i) => i === 0 || v.draw >= forward[i - 1].draw - 1e-12);
checks.negative_time_is_the_start = at(-5).draw === 0;
checks.generic_adapter = sampleTimeline({ x: 0 }, (tl, o) => tl.to(o, { x: 10, duration: 1, ease: "none" }), 0.5).x === 5;
const ok = Object.values(checks).every(Boolean);
console.log(JSON.stringify({ ok, checks }));
process.exit(ok ? 0 : 1);
