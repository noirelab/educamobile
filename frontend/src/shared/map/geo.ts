export type LatLng = { latitude: number; longitude: number }

export const DEFAULT_CENTER: LatLng = { latitude: -25.43, longitude: -49.27 }
export const DEFAULT_ZOOM = 12

type Position = [number, number]

export function toLeaflet(p: LatLng): [number, number] {
  return [p.latitude, p.longitude]
}

export function geoJsonLineToLatLngs(line: { coordinates: Position[] }): [number, number][] {
  return line.coordinates.map(([lng, lat]) => [lat, lng])
}

export function multiPolygonToLatLngs(mp: { coordinates: Position[][][] }): [number, number][][][] {
  return mp.coordinates.map((polygon) =>
    polygon.map((ring) => ring.map(([lng, lat]) => [lat, lng] as [number, number])),
  )
}

export function latLngsToMultiPolygon(rings: [number, number][][][]): {
  type: 'MultiPolygon'
  coordinates: Position[][][]
} {
  return {
    type: 'MultiPolygon',
    coordinates: rings.map((polygon) =>
      polygon.map((ring) => {
        const points = ring.map(([lat, lng]) => [lng, lat] as Position)
        const first = points[0]
        const last = points[points.length - 1]
        if (first && last && (first[0] !== last[0] || first[1] !== last[1])) {
          points.push([first[0], first[1]])
        }
        return points
      }),
    ),
  }
}
