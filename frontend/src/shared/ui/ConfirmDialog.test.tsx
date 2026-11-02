import { cleanup, render, screen, waitFor } from '@testing-library/react'
import userEvent from '@testing-library/user-event'
import { afterEach, describe, expect, it, vi } from 'vitest'
import { ApiError } from '@/shared/api/errors'
import { ConfirmDialog } from './ConfirmDialog'

function setup(onConfirm: () => Promise<void>) {
  render(
    <ConfirmDialog
      trigger={<button>Abrir</button>}
      title="Excluir polo"
      description="Confirma a exclusao?"
      confirmLabel="Excluir"
      onConfirm={onConfirm}
    />,
  )
}

describe('ConfirmDialog', () => {
  afterEach(() => {
    cleanup()
    document.body.style.pointerEvents = ''
  })

  it('shows the error and stays open when confirm rejects', async () => {
    const user = userEvent.setup()
    setup(vi.fn().mockRejectedValue(new ApiError(409, 'Polo em uso')))
    await user.click(screen.getByRole('button', { name: 'Abrir' }))
    await user.click(screen.getByRole('button', { name: 'Excluir' }))
    expect(await screen.findByRole('alert')).toHaveTextContent('Polo em uso')
    expect(screen.getByRole('dialog')).toBeInTheDocument()
  })

  it('closes when confirm resolves', async () => {
    const user = userEvent.setup()
    setup(vi.fn().mockResolvedValue(undefined))
    await user.click(screen.getByRole('button', { name: 'Abrir' }))
    await user.click(screen.getByRole('button', { name: 'Excluir' }))
    await waitFor(() => expect(screen.queryByRole('dialog')).not.toBeInTheDocument())
  })
})
