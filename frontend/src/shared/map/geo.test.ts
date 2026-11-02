import { describe, expect, it } from 'vitest'
import {
  geoJsonLineToLatLngs,
  latLngsToMultiPolygon,
  multiPolygonToLatLngs,
  toLeaflet,
} from './geo'

describe('geo', () => {
  it('converts a LatLng to leaflet [lat, lng]', () => {
    expect(toLeaflet({ latitude: -25.43, longitude: -49.27 })).toEqual([-25.43, -49.27])
  })

  it('converts a GeoJSON line [lng, lat] to leaflet [lat, lng]', () => {
    expect(geoJsonLineToLatLngs({ coordinates: [[-49.27, -25.43]] })).toEqual([[-25.43, -49.27]])
  })

  it('closes each ring when building a MultiPolygon in [lng, lat] order', () => {
    const result = latLngsToMultiPolygon([
      [
        [
          [-25.4, -49.2],
          [-25.5, -49.2],
          [-25.5, -49.3],
        ],
      ],
    ])
    expect(result.type).toBe('MultiPolygon')
    const ring = result.coordinates[0][0]
    expect(ring[0]).toEqual([-49.2, -25.4])
    expect(ring[ring.length - 1]).toEqual(ring[0])
  })

  it('round trips multiPolygonToLatLngs and latLngsToMultiPolygon', () => {
    const geo: [number, number][][][] = [
      [
        [
          [-49.2, -25.4],
          [-49.2, -25.5],
          [-49.3, -25.5],
          [-49.2, -25.4],
        ],
      ],
    ]
    const leaflet = multiPolygonToLatLngs({ coordinates: geo })
    expect(leaflet[0][0][0]).toEqual([-25.4, -49.2])
    expect(latLngsToMultiPolygon(leaflet).coordinates).toEqual(geo)
  })
})
