import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import type { components } from '@/shared/api/schema'
import { todayLocal } from '@/shared/lib/format'
import { Button } from '@/shared/ui/button'
import {
  Dialog,
  DialogContent,
  DialogDescription,
  DialogFooter,
  DialogHeader,
  DialogTitle,
  DialogTrigger,
} from '@/shared/ui/dialog'
import { Field } from '@/shared/ui/Field'
import { notifySuccess } from '@/shared/ui/toast'
import { enrollmentErrorMessage } from '../labels'
import { useCloseEnrollment } from '../hooks'
import { closeEnrollmentSchema, type CloseEnrollmentFormValues } from '../schemas'

type MatriculaLer = components['schemas']['MatriculaLer']

type CloseEnrollmentDialogProps = { matricula: MatriculaLer }

function defaultValues(): CloseEnrollmentFormValues {
  return { data_fim: todayLocal() }
}

export function CloseEnrollmentDialog({ matricula }: CloseEnrollmentDialogProps) {
  const [open, setOpen] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const close = useCloseEnrollment()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<CloseEnrollmentFormValues>({
    resolver: zodResolver(closeEnrollmentSchema),
    defaultValues: defaultValues(),
  })

  function handleOpenChange(next: boolean) {
    if (next) {
      reset(defaultValues())
      setServerError(null)
    }
    setOpen(next)
  }

  async function onSubmit(values: CloseEnrollmentFormValues) {
    setServerError(null)
    try {
      await close.mutateAsync({ id: matricula.id, body: { data_fim: values.data_fim } })
      notifySuccess('Matrícula encerrada')
      setOpen(false)
    } catch (e) {
      setServerError(enrollmentErrorMessage(e))
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="danger-outline" size="sm">
          Encerrar
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Encerrar matrícula</DialogTitle>
            <DialogDescription>O estudante deixa a turma na data informada.</DialogDescription>
          </DialogHeader>
          <Field label="Data de encerramento" error={errors.data_fim?.message}>
            <input type="date" {...register('data_fim')} />
          </Field>
          {serverError && (
            <p role="alert" className="text-body text-danger">
              {serverError}
            </p>
          )}
          <DialogFooter>
            <Button type="button" variant="secondary" onClick={() => handleOpenChange(false)}>
              Cancelar
            </Button>
            <Button type="submit" disabled={close.isPending}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
