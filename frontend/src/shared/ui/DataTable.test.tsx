import { render, screen } from '@testing-library/react'
import { afterEach, beforeEach, describe, expect, it, vi } from 'vitest'
import { DataTable } from './DataTable'

type Row = { id: number; nome: string }

const columns = [{ key: 'nome', header: 'Nome', cell: (row: Row) => row.nome }]
const rows: Row[] = [{ id: 1, nome: 'Escola A' }]

describe('DataTable', () => {
  const original = window.matchMedia

  beforeEach(() => {
    window.matchMedia = vi.fn().mockImplementation((query: string) => ({
      matches: query === '(max-width: 767px)',
      media: query,
      onchange: null,
      addListener: vi.fn(),
      removeListener: vi.fn(),
      addEventListener: vi.fn(),
      removeEventListener: vi.fn(),
      dispatchEvent: vi.fn(),
    })) as unknown as typeof window.matchMedia
  })

  afterEach(() => {
    window.matchMedia = original
  })

  it('renders cards as a list below 768px', () => {
    render(<DataTable columns={columns} rows={rows} />)
    expect(screen.getByRole('list')).toBeInTheDocument()
  })
})
