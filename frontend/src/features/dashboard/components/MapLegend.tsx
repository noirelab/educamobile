import { GlassPanel } from '@/shared/ui/GlassPanel'

export function MapLegend() {
  return (
    <GlassPanel strong className="absolute bottom-3 right-3 z-[1000] flex flex-col gap-1.5 rounded-[12px] p-2.5 text-caption text-ink">
      <div
        aria-hidden="true"
        className="h-2 w-[120px] rounded-full"
        style={{ background: 'linear-gradient(to right, #facc15, #dc2626)' }}
      />
      <div className="flex justify-between gap-4 text-ink-muted">
        <span>Baixa</span>
        <span>Alta</span>
      </div>
    </GlassPanel>
  )
}
