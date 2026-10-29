export interface ArtDirection {
  name: string;
  background: string;   // CSS background of the whole scene (a solid or a gradient)
  text: string;
  accent: string;
  muted: string;
}

/** Looks a video can have, so that not every video is dark navy. A scene picks ONE and keeps it for all its shots. */
export const ART_DIRECTIONS = {
  midnight: { name: "Midnight", background: "linear-gradient(160deg, #0b1020 0%, #1b2447 100%)", text: "#f8fafc", accent: "#38bdf8", muted: "#94a3b8" },
  paper: { name: "Paper", background: "linear-gradient(160deg, #faf6ee 0%, #efe6d3 100%)", text: "#1f2937", accent: "#b45309", muted: "#6b7280" },
  signal: { name: "Signal", background: "linear-gradient(160deg, #111111 0%, #2a0f0f 100%)", text: "#fafafa", accent: "#ef4444", muted: "#a3a3a3" },
  forest: { name: "Forest", background: "linear-gradient(160deg, #06251c 0%, #0f3d2e 100%)", text: "#ecfdf5", accent: "#34d399", muted: "#86a79a" },
  sunrise: { name: "Sunrise", background: "linear-gradient(160deg, #fff1e6 0%, #ffd9c2 100%)", text: "#3b1d12", accent: "#e8590c", muted: "#8a6a5a" },
} satisfies Record<string, ArtDirection>;

export type ArtDirectionKey = keyof typeof ART_DIRECTIONS;
