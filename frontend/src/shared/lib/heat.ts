const LOW_RGB = [250, 204, 21] as const
const HIGH_RGB = [220, 38, 38] as const
const HIGH_RATE = 0.4

export function rateColor(rate: number): string {
  const t = Math.min(Math.max(rate / HIGH_RATE, 0), 1)
  const [r, g, b] = LOW_RGB.map((low, i) => Math.round(low + (HIGH_RGB[i] - low) * t))
  return `#${[r, g, b].map((channel) => channel.toString(16).padStart(2, '0')).join('')}`
}
