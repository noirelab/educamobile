import { cloneElement, isValidElement, useId, type ReactElement, type ReactNode } from 'react'
import { AlertCircle, ChevronDown } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

type FieldProps = {
  label: string
  error?: string
  children: ReactNode
}

type ControlProps = {
  id?: string
  className?: string
  'aria-invalid'?: boolean | 'true' | 'false'
  'aria-describedby'?: string
}

const controlClass =
  'absolute inset-x-0 bottom-0 h-[32px] w-full appearance-none border-0 bg-transparent px-3.5 pb-1.5 font-sans text-body text-ink outline-none disabled:opacity-50'

export function Field({ label, error, children }: FieldProps) {
  const generatedId = useId()
  const control = isValidElement<ControlProps>(children) ? (children as ReactElement<ControlProps>) : null
  const inputId = control?.props.id ?? generatedId
  const errorId = `${inputId}-error`
  const isSelect = control?.type === 'select'

  return (
    <div className="my-3.5">
      <div
        className={cn(
          'relative h-[52px] rounded-[14px] border border-line bg-glass-strong transition-[border-color,box-shadow] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] focus-within:border-accent focus-within:shadow-[0_0_0_4px_rgba(15,118,110,0.18)] [&:focus-within>label]:text-accent',
          error && 'border-danger',
        )}
      >
        <label
          htmlFor={inputId}
          className="pointer-events-none absolute left-3.5 top-[7px] text-[12px] font-medium leading-4 text-ink-muted transition-colors duration-200"
        >
          {label}
        </label>
        {control
          ? cloneElement(control, {
              id: inputId,
              className: cn(controlClass, isSelect && 'pr-9', control.props.className),
              'aria-invalid': error ? true : control.props['aria-invalid'],
              'aria-describedby': error ? errorId : control.props['aria-describedby'],
            })
          : children}
        {isSelect && (
          <ChevronDown
            size={16}
            strokeWidth={1.75}
            aria-hidden="true"
            className="pointer-events-none absolute bottom-2 right-3.5 text-ink-muted"
          />
        )}
      </div>
      {error && (
        <p id={errorId} className="mt-1.5 flex items-center gap-1.5 text-caption text-danger">
          <AlertCircle size={16} strokeWidth={1.75} aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  )
}
