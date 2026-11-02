import { render, screen } from '@testing-library/react'
import { createRef } from 'react'
import { describe, expect, it } from 'vitest'
import { FloatingField } from './FloatingField'

describe('FloatingField', () => {
  it('renders the error with aria-invalid and aria-describedby', () => {
    render(<FloatingField label="E-mail" error="E-mail inválido" />)
    const input = screen.getByLabelText('E-mail')
    expect(input).toHaveAttribute('aria-invalid', 'true')
    const describedBy = input.getAttribute('aria-describedby')
    expect(describedBy).toBeTruthy()
    expect(document.getElementById(describedBy as string)).toHaveTextContent('E-mail inválido')
  })

  it('forwards ref to the input', () => {
    const ref = createRef<HTMLInputElement>()
    render(<FloatingField ref={ref} label="Nome" />)
    expect(ref.current).toBeInstanceOf(HTMLInputElement)
  })
})
