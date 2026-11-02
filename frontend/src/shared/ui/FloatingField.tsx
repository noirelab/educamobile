import { forwardRef, useId, type InputHTMLAttributes, type ReactNode } from 'react'
import { AlertCircle } from 'lucide-react'
import { cn } from '@/shared/lib/utils'

type FloatingFieldProps = Omit<InputHTMLAttributes<HTMLInputElement>, 'placeholder'> & {
  label: string
  error?: string
  trailing?: ReactNode
}

export const FloatingField = forwardRef<HTMLInputElement, FloatingFieldProps>(function FloatingField(
  { label, error, id, className, trailing, ...props },
  ref,
) {
  const generatedId = useId()
  const inputId = id ?? generatedId
  const errorId = `${inputId}-error`

  return (
    <div className="relative my-3.5">
      <input
        ref={ref}
        id={inputId}
        placeholder=" "
        aria-invalid={error ? 'true' : undefined}
        aria-describedby={error ? errorId : undefined}
        className={cn(
          'peer h-[52px] w-full rounded-[14px] border border-line bg-glass-strong px-3.5 pb-1.5 pt-5 font-sans text-body text-ink outline-none transition-[border-color,box-shadow] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] focus:border-accent focus:shadow-[0_0_0_4px_rgba(15,118,110,0.18)]',
          trailing && 'pr-14',
          error && 'border-danger',
          className,
        )}
        {...props}
      />
      <label
        htmlFor={inputId}
        className="pointer-events-none absolute left-3.5 top-[17px] origin-left text-body text-ink-muted transition-[transform,font-size,color] duration-200 ease-[cubic-bezier(0.22,1,0.36,1)] peer-focus:-translate-y-2.5 peer-focus:text-[12px] peer-focus:font-medium peer-focus:text-accent peer-[:not(:placeholder-shown)]:-translate-y-2.5 peer-[:not(:placeholder-shown)]:text-[12px] peer-[:not(:placeholder-shown)]:font-medium peer-[:not(:placeholder-shown)]:text-accent"
      >
        {label}
      </label>
      {trailing && <div className="absolute right-1 top-1">{trailing}</div>}
      {error && (
        <p id={errorId} className="mt-1.5 flex items-center gap-1.5 text-caption text-danger">
          <AlertCircle size={16} strokeWidth={1.75} aria-hidden="true" />
          {error}
        </p>
      )}
    </div>
  )
})
