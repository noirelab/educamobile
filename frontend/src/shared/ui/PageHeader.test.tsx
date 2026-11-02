import { render, screen } from '@testing-library/react'
import { describe, expect, it } from 'vitest'
import { PageHeader } from './PageHeader'

describe('PageHeader', () => {
  it('renders the h1 title, description, actions and filter row', () => {
    render(
      <PageHeader title="Painel" description="Infrequência da rede" actions={<button>Novo polo</button>}>
        <span>Filtro de período</span>
      </PageHeader>,
    )
    expect(screen.getByRole('heading', { level: 1, name: 'Painel' })).toBeInTheDocument()
    expect(screen.getByText('Infrequência da rede')).toBeInTheDocument()
    expect(screen.getByRole('button', { name: 'Novo polo' })).toBeInTheDocument()
    expect(screen.getByText('Filtro de período')).toBeInTheDocument()
  })

  it('omits the description paragraph when none is given', () => {
    const { container } = render(<PageHeader title="Escolas" />)
    expect(container.querySelector('p')).toBeNull()
  })
})
