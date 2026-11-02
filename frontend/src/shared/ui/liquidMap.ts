const squircle = (t: number) => Math.pow(1 - Math.pow(1 - t, 4), 0.25)

function edgeInfo(i: number, j: number, width: number, height: number, radius: number) {
  const dx = Math.max(radius - i, 0, i - (width - 1 - radius))
  const dy = Math.max(radius - j, 0, j - (height - 1 - radius))
  if (dx > 0 && dy > 0) {
    return {
      distance: radius - Math.hypot(dx, dy),
      angle: Math.atan2(j < height / 2 ? -dy : dy, i < width / 2 ? -dx : dx),
    }
  }
  const edges = [i, width - 1 - i, j, height - 1 - j]
  const minEdge = Math.min(...edges)
  return { distance: minEdge, angle: [Math.PI, 0, -Math.PI / 2, Math.PI / 2][edges.indexOf(minEdge)] }
}

const LIGHT_ANGLE = (-60 * Math.PI) / 180

export function buildSpecularMap(width: number, height: number, radius: number, bezel: number): Uint8ClampedArray {
  const data = new Uint8ClampedArray(width * height * 4)
  const rim = Math.max(2, Math.min(bezel * 0.5, 10))
  for (let j = 0; j < height; j++) {
    for (let i = 0; i < width; i++) {
      const { distance, angle } = edgeInfo(i, j, width, height, radius)
      let alpha = 0
      if (distance >= 0 && distance < rim) {
        const facing = Math.cos(angle - LIGHT_ANGLE)
        const strength = Math.abs(facing) ** 1.5 * (facing > 0 ? 1 : 0.35)
        alpha = strength * (1 - distance / rim) ** 1.5
      }
      const k = (j * width + i) * 4
      data[k] = 255
      data[k + 1] = 255
      data[k + 2] = 255
      data[k + 3] = Math.round(alpha * 255)
    }
  }
  return data
}

export function buildDisplacementMap(width: number, height: number, radius: number, bezel: number): Uint8ClampedArray {
  const data = new Uint8ClampedArray(width * height * 4)
  for (let j = 0; j < height; j++) {
    for (let i = 0; i < width; i++) {
      const { distance, angle } = edgeInfo(i, j, width, height, radius)
      let magnitude = 0
      if (distance >= 0 && distance < bezel) {
        const t = distance / bezel
        const epsilon = 0.001
        magnitude = (squircle(Math.min(t + epsilon, 1)) - squircle(Math.max(t - epsilon, 0))) / (2 * epsilon) / 6
        magnitude = Math.min(magnitude, 1)
      }
      const k = (j * width + i) * 4
      data[k] = 128 - Math.cos(angle) * magnitude * 127
      data[k + 1] = 128 - Math.sin(angle) * magnitude * 127
      data[k + 2] = 128
      data[k + 3] = 255
    }
  }
  return data
}
