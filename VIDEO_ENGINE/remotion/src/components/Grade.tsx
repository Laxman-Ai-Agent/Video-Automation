import { GRADES } from "../theme";

// Optional LUT-like color grade: a soft-light gradient over the whole frame (cheap, unlike a full-frame filter).
// meta.grade = warm | cool | teal-orange; nothing is rendered when it is missing.
export const Grade: React.FC<{ grade?: string }> = ({ grade }) => {
  const g = grade ? GRADES[grade] : undefined;
  if (!g) return null;
  return <div style={{ position: "absolute", inset: 0, pointerEvents: "none", mixBlendMode: "soft-light",
    background: `linear-gradient(180deg, ${g[0]}, ${g[1]})` }} />;
};
