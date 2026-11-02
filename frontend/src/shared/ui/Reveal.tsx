import type { ReactNode } from 'react'

type RevealProps = {
  index?: number
  children: ReactNode
}

export function Reveal({ index = 0, children }: RevealProps) {
  const delay = Math.min(Math.max(index, 0), 8) * 40
  return (
    <div className="page-enter" style={{ animationDelay: `${delay}ms` }}>
      {children}
    </div>
  )
}
