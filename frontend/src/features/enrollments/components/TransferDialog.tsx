import { zodResolver } from '@hookform/resolvers/zod'
import { ArrowRightLeft } from 'lucide-react'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { useClassesInScope } from '@/features/classes/hooks'
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
import { useTransfer } from '../hooks'
import { transferSchema, type TransferFormValues } from '../schemas'

type MatriculaLer = components['schemas']['MatriculaLer']

type TransferDialogProps = { matricula: MatriculaLer }

function defaultValues(): TransferFormValues {
  return { turma_destino_id: '', data: todayLocal() }
}

export function TransferDialog({ matricula }: TransferDialogProps) {
  const [open, setOpen] = useState(false)
  const [serverError, setServerError] = useState<string | null>(null)
  const classes = useClassesInScope()
  const transferir = useTransfer()
  const {
    register,
    handleSubmit,
    reset,
    formState: { errors },
  } = useForm<TransferFormValues>({ resolver: zodResolver(transferSchema), defaultValues: defaultValues() })

  const destinations = (classes.data ?? []).filter((turma) => turma.id !== matricula.turma_id)

  function handleOpenChange(next: boolean) {
    if (next) {
      reset(defaultValues())
      setServerError(null)
    }
    setOpen(next)
  }

  async function onSubmit(values: TransferFormValues) {
    setServerError(null)
    try {
      await transferir.mutateAsync({
        estudante_id: matricula.estudante_id,
        turma_destino_id: Number(values.turma_destino_id),
        data: values.data,
      })
      notifySuccess('Transferência registrada')
      setOpen(false)
    } catch (e) {
      setServerError(enrollmentErrorMessage(e))
    }
  }

  return (
    <Dialog open={open} onOpenChange={handleOpenChange}>
      <DialogTrigger asChild>
        <Button variant="secondary" size="sm">
          <ArrowRightLeft aria-hidden="true" />
          Transferir
        </Button>
      </DialogTrigger>
      <DialogContent>
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <DialogHeader>
            <DialogTitle>Transferir estudante</DialogTitle>
            <DialogDescription>A matrícula atual será marcada como transferida.</DialogDescription>
          </DialogHeader>
          <Field label="Turma de destino" error={errors.turma_destino_id?.message}>
            <select {...register('turma_destino_id')}>
              <option value="">Selecione a turma</option>
              {destinations.map((turma) => (
                <option key={turma.id} value={String(turma.id)}>
                  {turma.nome}
                </option>
              ))}
            </select>
          </Field>
          <Field label="Data" error={errors.data?.message}>
            <input type="date" {...register('data')} />
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
            <Button type="submit" disabled={transferir.isPending}>
              Salvar
            </Button>
          </DialogFooter>
        </form>
      </DialogContent>
    </Dialog>
  )
}
