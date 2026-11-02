import L from 'leaflet'
import { useEffect, useRef } from 'react'
import { useMap } from 'react-leaflet'
import { toLeaflet, type LatLng } from './geo'

type FitBoundsProps = {
  points: LatLng[]
  padding?: number
  maxZoom?: number
}

export function FitBounds({ points, padding = 40, maxZoom = 16 }: FitBoundsProps) {
  const map = useMap()
  const fitted = useRef(false)

  useEffect(() => {
    if (fitted.current || points.length === 0) return
    fitted.current = true
    const bounds = L.latLngBounds(points.map(toLeaflet))
    map.fitBounds(bounds, { padding: [padding, padding], maxZoom })
  }, [map, points, padding, maxZoom])

  return null
}
