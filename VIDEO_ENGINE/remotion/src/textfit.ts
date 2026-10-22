// Average glyph advance of the video font (Poppins, including spaces), in em. An estimate, not a measurement.
const em = (weight: number) => (weight >= 700 ? 0.64 : 0.6);

export const textWidth = (text: string, size: number, weight = 600): number => text.length * size * em(weight);

/**
 * Largest font size <= `size` that keeps one line of `text` inside `maxWidth`, never below `floor` x size.
 * Longer text then wraps inside its (safe-margin) container instead of running off the frame.
 */
export function fitFontSize(text: string, size: number, weight: number, maxWidth: number, floor = 0.7): number {
  const w = textWidth(text, size, weight);
  return w <= maxWidth ? size : Math.max(size * floor, (size * maxWidth) / w);
}
