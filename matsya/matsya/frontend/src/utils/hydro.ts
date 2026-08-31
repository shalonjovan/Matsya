export function fillOpacityForStage(stage: number, crest: number): number {
  if (stage <= crest) return 0.2
  const head = stage - crest
  return Math.min(0.8, 0.3 + head*0.2)
}
export function colorForStage(stage: number, crest: number): string {
  const op = fillOpacityForStage(stage, crest)
  if (stage <= crest) return `rgba(59,130,246,${op})` // blue light
  if (stage - crest < 1) return `rgba(37,99,235,${op})`
  return `rgba(30,64,175,${op})` // dark
}
export function drainColor(target: string): string {
  if (target.startsWith("wb:")) return "#3b82f6"
  if (target.startsWith("river:")) return "#0ea5e9"
  if (target==="sea") return "#06b6d4"
  return "#94a3b8"
}
