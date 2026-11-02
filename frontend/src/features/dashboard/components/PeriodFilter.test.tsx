import { describe, expect, it } from 'vitest'
import { fireEvent, screen } from '@testing-library/react'
import { useLocation } from 'react-router-dom'
import { renderWithRoutes } from '@/test/renderWithRoutes'
import { daysAgoLocal, todayLocal } from '@/shared/lib/format'
import { PeriodFilter } from './PeriodFilter'

function LocationProbe() {
  const location = useLocation()
  return <output data-testid="search">{location.search}</output>
}

function renderFilter(path = '/dashboard') {
  return renderWithRoutes(path, [
    {
      path: '/dashboard',
      element: (
        <>
          <PeriodFilter />
          <LocationProbe />
        </>
      ),
    },
  ])
}

describe('PeriodFilter', () => {
  it('starts from the default 30-day period when the URL has no dates', () => {
    renderFilter()

    expect(screen.getByLabelText('De')).toHaveValue(daysAgoLocal(30))
    expect(screen.getByLabelText('Até')).toHaveValue(todayLocal())
  })

  it('caps both inputs at today', () => {
    renderFilter()

    expect(screen.getByLabelText('De')).toHaveAttribute('max', todayLocal())
    expect(screen.getByLabelText('Até')).toHaveAttribute('max', todayLocal())
  })

  it('blocks an end date after today and does not commit it', () => {
    renderFilter()
    const tomorrow = daysAgoLocal(-1)

    fireEvent.change(screen.getByLabelText('Até'), { target: { value: tomorrow } })

    expect(screen.getByRole('alert')).toHaveTextContent('A data não pode ser futura')
    expect(screen.getByTestId('search').textContent).toBe('')
  })

  it('shows an error when the start date is after the end date and does not commit it', () => {
    renderFilter()

    fireEvent.change(screen.getByLabelText('De'), { target: { value: todayLocal() } })
    fireEvent.change(screen.getByLabelText('Até'), { target: { value: daysAgoLocal(10) } })

    expect(screen.getByRole('alert')).toHaveTextContent('A data inicial não pode ser posterior à final')
    expect(screen.getByTestId('search').textContent).not.toContain(`data_fim=${daysAgoLocal(10)}`)
  })

  it('writes a valid period into the URL', () => {
    renderFilter()
    const start = daysAgoLocal(7)

    fireEvent.change(screen.getByLabelText('De'), { target: { value: start } })

    expect(screen.queryByRole('alert')).not.toBeInTheDocument()
    expect(screen.getByTestId('search').textContent).toContain(`data_inicio=${start}`)
  })
})
