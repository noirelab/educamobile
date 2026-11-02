import type { Layer } from 'leaflet'

declare module 'leaflet' {
  export interface HeatLayerOptions {
    minOpacity?: number
    maxZoom?: number
    max?: number
    radius?: number
    blur?: number
    gradient?: Record<number, string>
  }

  export function heatLayer(latlngs: [number, number, number][], options?: HeatLayerOptions): Layer
}
