import { render, screen } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { describe, expect, it, vi } from 'vitest'
import { PointPicker } from './PointPicker'

vi.mock('react-leaflet', () => ({
  MapContainer: ({ children }: { children: React.ReactNode }) => <div>{children}</div>,
  TileLayer: () => null,
  Marker: () => null,
  useMapEvents: () => null,
}))

describe('PointPicker', () => {
  it('shows range errors for out-of-range coordinates', async () => {
    const onChange = vi.fn()
    render(<PointPicker value={null} onChange={onChange} />)
    await userEvent.type(screen.getByLabelText('Latitude'), '95')
    await userEvent.type(screen.getByLabelText('Longitude'), '-200')
    expect(screen.getByText('Latitude entre -90 e 90')).toBeInTheDocument()
    expect(screen.getByText('Longitude entre -180 e 180')).toBeInTheDocument()
    expect(onChange).not.toHaveBeenCalled()
  })

  it('emits the point when both coordinates are valid and clears with Limpar', async () => {
    const onChange = vi.fn()
    render(<PointPicker value={null} onChange={onChange} />)
    await userEvent.type(screen.getByLabelText('Latitude'), '-25.43')
    await userEvent.type(screen.getByLabelText('Longitude'), '-49.27')
    expect(onChange).toHaveBeenLastCalledWith({ latitude: -25.43, longitude: -49.27 })
    await userEvent.click(screen.getByRole('button', { name: 'Limpar' }))
    expect(onChange).toHaveBeenLastCalledWith(null)
  })

  it('hides Limpar when required', () => {
    render(<PointPicker value={null} onChange={() => {}} required />)
    expect(screen.queryByRole('button', { name: 'Limpar' })).not.toBeInTheDocument()
  })
})
