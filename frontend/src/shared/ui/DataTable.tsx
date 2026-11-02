import type { ReactNode } from 'react'
import { Link } from 'react-router-dom'
import { useMediaQuery } from '@/shared/hooks/useMediaQuery'
import { cn } from '@/shared/lib/utils'

type Column<T> = {
  key: string
  header: string
  cell: (row: T) => ReactNode
}

type DataTableProps<T> = {
  columns: Column<T>[]
  rows: T[]
  rowHref?: (row: T) => string
  footer?: ReactNode
  embedded?: boolean
}

export function DataTable<T>({ columns, rows, rowHref, footer, embedded = false }: DataTableProps<T>) {
  const isCompact = useMediaQuery('(max-width: 767px)')
  const surface = embedded ? undefined : 'glass glass-dense'

  if (isCompact) {
    return (
      <div className={cn(surface, "overflow-hidden")}>
        <ul role="list" className="divide-y divide-line">
          {rows.map((row, index) => {
            const content = (
              <dl className="grid gap-2 px-4 py-3.5">
                {columns.map((column) => (
                  <div key={column.key} className="flex justify-between gap-3 text-body">
                    <dt className="text-label text-ink-muted">{column.header}</dt>
                    <dd className="text-right font-medium tabular-nums text-ink">{column.cell(row)}</dd>
                  </div>
                ))}
              </dl>
            )
            return (
              <li key={index} className={cn(rowHref && 'transition-colors duration-250 hover:bg-[rgba(15,118,110,0.06)]')}>
                {rowHref ? (
                  <Link to={rowHref(row)} className="block">
                    {content}
                  </Link>
                ) : (
                  content
                )}
              </li>
            )
          })}
        </ul>
        {footer}
      </div>
    )
  }

  return (
    <div className={cn(surface, "overflow-x-auto")}>
      <table className="w-full border-collapse text-body">
        <thead>
          <tr className="border-b border-line text-left">
            {columns.map((column) => (
              <th key={column.key} scope="col" className="px-4 py-3 text-label font-medium text-ink-muted">
                {column.header}
              </th>
            ))}
          </tr>
        </thead>
        <tbody>
          {rows.map((row, index) => (
            <tr
              key={index}
              className="border-b border-line transition-colors duration-250 last:border-0 hover:bg-[rgba(15,118,110,0.06)]"
            >
              {columns.map((column, colIndex) => (
                <td
                  key={column.key}
                  className={cn('px-4 py-[15px] align-middle tabular-nums text-ink', rowHref && colIndex === 0 && 'font-semibold')}
                >
                  {rowHref && colIndex === 0 ? (
                    <Link to={rowHref(row)} className="block text-ink">
                      {column.cell(row)}
                    </Link>
                  ) : (
                    column.cell(row)
                  )}
                </td>
              ))}
            </tr>
          ))}
        </tbody>
      </table>
      {footer}
    </div>
  )
}
