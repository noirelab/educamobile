import { render, screen } from '@testing-library/react'
import { Users } from 'lucide-react'
import { describe, expect, it } from 'vitest'
import { KpiCard } from './KpiCard'

describe('KpiCard', () => {
  it('renders the label and the value', () => {
    render(<KpiCard label="Faltas" value="9" />)
    expect(screen.getByText('Faltas')).toBeInTheDocument()
    expect(screen.getByText('9')).toBeInTheDocument()
  })

  it('keeps the display font size class with a tone class', () => {
    render(<KpiCard label="Faltas" value="9" tone="danger" />)
    expect(screen.getByText('9').className).toContain('text-display')
  })

  it('exposes the tone as data-tone', () => {
    const { container } = render(<KpiCard label="Infrequência" value="41%" tone="danger" />)
    expect(container.querySelector('[data-tone="danger"]')).not.toBeNull()
  })

  it('renders the icon when given', () => {
    const { container } = render(<KpiCard label="Alunos" value="120" icon={Users} />)
    expect(container.querySelector('svg')).not.toBeNull()
  })

  it('hides the value and marks the card busy while loading', () => {
    render(<KpiCard label="Faltas" value="9" loading />)
    expect(screen.queryByText('9')).toBeNull()
    expect(screen.getByText('Faltas').closest('[aria-busy="true"]')).not.toBeNull()
  })
})
