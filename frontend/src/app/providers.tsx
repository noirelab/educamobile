import { useState, type ReactNode } from 'react'
import { QueryClientProvider } from '@tanstack/react-query'
import { AuroraBackground } from '@/shared/ui/AuroraBackground'
import { LiquidFilter } from '@/shared/ui/LiquidFilter'
import { Toaster } from '@/shared/ui/toast'
import { createQueryClient } from './queryClient'

export function Providers({ children }: { children: ReactNode }) {
  const [queryClient] = useState(createQueryClient)

  return (
    <QueryClientProvider client={queryClient}>
      <AuroraBackground />
      <LiquidFilter />
      <Toaster />
      {children}
    </QueryClientProvider>
  )
}
