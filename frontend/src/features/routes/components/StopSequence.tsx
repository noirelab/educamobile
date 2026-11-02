import {
  closestCenter,
  DndContext,
  KeyboardSensor,
  PointerSensor,
  useSensor,
  useSensors,
  type DragEndEvent,
} from '@dnd-kit/core'
import {
  SortableContext,
  sortableKeyboardCoordinates,
  useSortable,
  verticalListSortingStrategy,
} from '@dnd-kit/sortable'
import { CSS } from '@dnd-kit/utilities'
import { GripVertical, X } from 'lucide-react'
import { moveStop, removeStop } from '../sequence'

type StopSequenceProps = {
  ids: number[]
  names: Map<number, string>
  readOnly: boolean
  onChange: (ids: number[]) => void
}

type SortableRowProps = {
  id: number
  position: number
  name: string
  readOnly: boolean
  onRemove: (id: number) => void
}

function SortableRow({ id, position, name, readOnly, onRemove }: SortableRowProps) {
  const { attributes, listeners, setNodeRef, setActivatorNodeRef, transform, transition, isDragging } = useSortable({
    id,
    disabled: readOnly,
  })

  return (
    <li
      ref={setNodeRef}
      style={{ transform: CSS.Transform.toString(transform), transition }}
      className={`flex min-h-[52px] items-center gap-3 px-1 py-2 ${isDragging ? 'relative z-10 opacity-80' : ''}`}
    >
      {!readOnly && (
        <button
          type="button"
          ref={setActivatorNodeRef}
          aria-label={`Arrastar ${name}`}
          className="focus-ring flex h-11 w-9 shrink-0 cursor-grab touch-none items-center justify-center rounded-[10px] text-ink-muted hover:bg-[rgba(15,30,51,0.06)] active:cursor-grabbing"
          {...attributes}
          {...listeners}
        >
          <GripVertical size={18} strokeWidth={1.75} aria-hidden="true" />
        </button>
      )}
      <span className="flex h-6 w-6 shrink-0 items-center justify-center rounded-full bg-accent-soft text-label font-semibold text-accent tabular-nums">
        {position}
      </span>
      <span className="min-w-0 flex-1 truncate text-body font-semibold text-ink">{name}</span>
      {!readOnly && (
        <button
          type="button"
          aria-label={`Remover ${name}`}
          onClick={() => onRemove(id)}
          className="focus-ring flex h-11 w-11 shrink-0 items-center justify-center rounded-[12px] text-ink-muted hover:bg-[rgba(15,30,51,0.06)] hover:text-ink"
        >
          <X size={18} strokeWidth={1.75} aria-hidden="true" />
        </button>
      )}
    </li>
  )
}

export function StopSequence({ ids, names, readOnly, onChange }: StopSequenceProps) {
  const sensors = useSensors(
    useSensor(PointerSensor, { activationConstraint: { distance: 4 } }),
    useSensor(KeyboardSensor, { coordinateGetter: sortableKeyboardCoordinates }),
  )

  function handleDragEnd(event: DragEndEvent) {
    const { active, over } = event
    if (!over || active.id === over.id) return
    const from = ids.indexOf(Number(active.id))
    const to = ids.indexOf(Number(over.id))
    if (from < 0 || to < 0) return
    onChange(moveStop(ids, from, to))
  }

  function labelFor(id: number): string {
    return names.get(id) ?? `Parada ${id}`
  }

  return (
    <DndContext sensors={sensors} collisionDetection={closestCenter} onDragEnd={handleDragEnd}>
      <SortableContext items={ids} strategy={verticalListSortingStrategy} disabled={readOnly}>
        <ol aria-label="Sequência de paradas" className="flex flex-col divide-y divide-line">
          {ids.map((id, index) => (
            <SortableRow
              key={id}
              id={id}
              position={index + 1}
              name={labelFor(id)}
              readOnly={readOnly}
              onRemove={(stopId) => onChange(removeStop(ids, stopId))}
            />
          ))}
        </ol>
      </SortableContext>
    </DndContext>
  )
}
