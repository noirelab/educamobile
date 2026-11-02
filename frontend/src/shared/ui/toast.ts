import { createElement, type CSSProperties } from 'react'
import { Toaster as SonnerToaster, toast } from 'sonner'
import { errorMessage } from '@/shared/api/errors'

const toasterStyle = {
  '--normal-bg': 'rgba(255, 255, 255, 0.62)',
  '--normal-border': 'rgba(255, 255, 255, 0.6)',
  '--normal-text': 'var(--ink)',
  '--border-radius': '14px',
  '--width': '360px',
} as CSSProperties

export function Toaster() {
  return createElement(SonnerToaster, {
    position: 'bottom-right',
    style: toasterStyle,
    toastOptions: {
      className: 'glass-strong font-sans text-[14px] text-ink',
    },
  })
}

export function notifySuccess(msg: string) {
  toast.success(msg)
}

export function notifyError(e: unknown) {
  toast.error(errorMessage(e))
}
