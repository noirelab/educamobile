import { BASE_SCALE, useLiquidEntries } from './useLiquidGlass'

export function LiquidFilter() {
  const entries = useLiquidEntries()
  return (
    <svg width="0" height="0" aria-hidden="true" style={{ position: 'absolute', pointerEvents: 'none' }}>
      {entries.map((entry) => (
        <filter
          key={entry.id}
          id={entry.id}
          x="0"
          y="0"
          width={entry.width}
          height={entry.height}
          filterUnits="userSpaceOnUse"
          colorInterpolationFilters="sRGB"
        >
          <feImage href={entry.displacement} x="0" y="0" width={entry.width} height={entry.height} preserveAspectRatio="none" result="map" />
          <feDisplacementMap
            id={`${entry.id}-d`}
            in="SourceGraphic"
            in2="map"
            scale={BASE_SCALE}
            xChannelSelector="R"
            yChannelSelector="G"
            result="refracted"
          />
          <feImage href={entry.specular} x="0" y="0" width={entry.width} height={entry.height} preserveAspectRatio="none" result="spec" />
          <feComponentTransfer in="spec" result="specSoft">
            <feFuncA type="linear" slope="0.6" />
          </feComponentTransfer>
          <feBlend in="specSoft" in2="refracted" mode="screen" />
        </filter>
      ))}
    </svg>
  )
}
