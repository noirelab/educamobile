import { zodResolver } from '@hookform/resolvers/zod'
import { UserPlus } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useClassesInScope } from '@/features/classes/hooks'
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
import { useCreateEnrollment } from '../hooks'
import { enrollSchema, type EnrollFormValues } from '../schemas'

type EnrollDialogProps = { studentId: number }

function defaultValues(): EnrollFormValues {
  return { turma_id: '', data_inicio: todayLocal() }
}

export function EnrollDialog({ studentId }: EnrollDialogProps) {
  const [open, setOpen] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const classes = useClassesInScope()
  const create = useCreateEnrollment()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<EnrollFormValues>({ resolver: zodResolver(enrollSchema), defaultValues: defaultValues() })

  function handleOpenChange(next: boolean) {
    if (next) {
      reset(defaultValues())
      setServerError(null)
    }
    setOpen(next)
  }

  async function onSubmit(values: EnrollFormValues) {
    setServerError(null)
    try {
      await create.mutateAsync({
        estudante_id: studentId,
        turma_id: Number(values.turma_id),
        data_inicio: values.data_inicio,
      })
      notifySuccess('Matrícula registrada')
      setOpen(false)
    } catch (e) {
      setServerError(enrollmentErrorMessage(e))
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button>
          <UserPlus aria-hidden="true" />
          Matricular
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Matricular estudante</DialogTitle>
            <DialogDescription>Escolha a turma e a data em que o estudante começa.</DialogDescription>
          </DialogHeader>
          <Field label="Turma" error={errors.turma_id?.message}>
            <select {...register('turma_id')}>
              <option value="">Selecione a turma</option>
              {(classes.data ?? []).map((turma) => (
                <option key={turma.id} value={String(turma.id)}>
                  {turma.nome}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Data de início" error={errors.data_inicio?.message}>
            <input type="date" {...register('data_inicio')} />
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
            <Button type="submit" disabled={create.isPending}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
