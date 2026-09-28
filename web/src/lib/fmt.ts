export const pct = (v: number | null | undefined) => (v == null ? "n/a" : Math.round(v * 100) + "%");
export const f2 = (v: number | null | undefined) => (v == null ? "n/a" : v.toFixed(2));
/** Sequential single-hue ramp (recall 0..1) on the dark surface: near-surface -> green. */
export function heat(v: number | null | undefined) {
  if (v == null) return { bg: "transparent", fg: "#71717a" };
  const t = Math.max(0, Math.min(1, v));
  const a = [26, 28, 31], b = [56, 178, 104];
  const c = a.map((x, i) => Math.round(x + (b[i] - x) * Math.pow(t, 1.15)));
  return { bg: `rgb(${c.join(",")})`, fg: t > 0.7 ? "#0a0a0b" : "#ededee" };
}
/** Clamp a [x0,y0,x1,y1] box in 0..1000 space to CSS percentages, or null if unusable. */
export function boxStyle(b: unknown) {
  if (!Array.isArray(b) || b.length !== 4 || b.some(x => typeof x !== "number")) return null;
  let [x0, y0, x1, y1] = (b as number[]).map(v => Math.max(0, Math.min(1000, v)));
  if (x1 < x0) [x0, x1] = [x1, x0];
  if (y1 < y0) [y0, y1] = [y1, y0];
  if (x1 - x0 < 4 || y1 - y0 < 4) return null;
  return `left:${x0 / 10}%;top:${y0 / 10}%;width:${(x1 - x0) / 10}%;height:${(y1 - y0) / 10}%`;
}
