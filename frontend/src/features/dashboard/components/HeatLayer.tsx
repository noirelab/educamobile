import '@/shared/map/leafletGlobal'
import L from 'leaflet'
import 'leaflet.heat'
import { useEffect } from 'react'
import { useMap } from 'react-leaflet'

type HeatLayerProps = {
  points: [number, number, number][]
}

const HEAT_GRADIENT = { 0: '#facc15', 1: '#dc2626' }

export function HeatLayer({ points }: HeatLayerProps) {
  const map = useMap()

  useEffect(() => {
    const weighted = points.map(([lat, lng, rate]): [number, number, number] => [lat, lng, Math.max(rate, 0.04)])
    const layer = L.heatLayer(weighted, { radius: 45, blur: 25, max: 0.4, minOpacity: 0.55, gradient: HEAT_GRADIENT })
    layer.addTo(map)
    return () => {
      layer.remove()
    }
  }, [map, points])

  return null
}
