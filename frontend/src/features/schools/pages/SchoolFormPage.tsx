import { zodResolver } from '@hookform/resolvers/zod'
import { Controller, useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { ApiError } from '@/shared/api/errors'
import type { components } from '@/shared/api/schema'
import { PointPicker } from '@/shared/map/PointPicker'
import { Button } from '@/shared/ui/button'
import { Field } from '@/shared/ui/Field'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { usePoleOptions, useSaveSchool, useSchool } from '../hooks'
import { schoolSchema, type SchoolFormValues } from '../schemas'

type EscolaLer = components['schemas']['EscolaLer']
type EscolaCriar = components['schemas']['EscolaCriar']
type Coordenadas = components['schemas']['Coordenadas']
type PoloLer = components['schemas']['PoloLer']

const INEP_CONFLICT = 'Código INEP já cadastrado ou polo inexistente'

const FORM_FIELDS = ['nome', 'codigo_inep', 'endereco', 'polo_id', 'localizacao'] as const
type FormField = (typeof FORM_FIELDS)[number]

function isFormField(field: string): field is FormField {
  return (FORM_FIELDS as readonly string[]).includes(field)
}

function toPayload(values: SchoolFormValues, localizacao: Coordenadas): EscolaCriar {
  return {
    nome: values.nome,
    codigo_inep: values.codigo_inep === '' ? null : values.codigo_inep,
    endereco: values.endereco === '' ? null : values.endereco,
    polo_id: values.polo_id === '' ? null : Number(values.polo_id),
    localizacao,
  }
}

type SchoolFormProps = { school?: EscolaLer; poles: PoloLer[] }

function SchoolForm({ school, poles }: SchoolFormProps) {
  const navigate = useNavigate()
  const save = useSaveSchool(school?.id)
  const {
    register,
    handleSubmit,
    setError,
    control,
    formState: { errors },
  } = useForm<SchoolFormValues>({
    resolver: zodResolver(schoolSchema),
    defaultValues: {
      nome: school?.nome ?? '',
      codigo_inep: school?.codigo_inep ?? '',
      endereco: school?.endereco ?? '',
      polo_id: school?.polo_id != null ? String(school.polo_id) : '',
      localizacao: school?.localizacao ?? null,
    },
  })

  function applyServerError(e: unknown) {
    if (!(e instanceof ApiError)) {
      notifyError(e)
      return
    }
    if (e.status === 409) {
      setError('codigo_inep', { message: INEP_CONFLICT })
      return
    }
    const fieldEntries = Object.entries(e.fieldErrors)
    for (const [field, message] of fieldEntries) {
      if (isFormField(field)) setError(field, { message })
    }
    if (fieldEntries.length > 0) return
    notifyError(e)
  }

  async function onSubmit(values: SchoolFormValues) {
    const localizacao = values.localizacao
    if (localizacao === null) return
    try {
      const saved = await save.mutateAsync(toPayload(values, localizacao))
      notifySuccess('Escola salva')
      navigate(`/schools/${saved.id}`)
    } catch (e) {
      applyServerError(e)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={school ? 'Editar escola' : 'Nova escola'}
        description="Dados cadastrais e localização da escola no mapa"
      />
      <Panel dense className="max-w-[720px] p-6 lg:p-6">
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="grid gap-x-4 sm:grid-cols-2">
          <div className="sm:col-span-2">
            <FloatingField label="Nome" error={errors.nome?.message} {...register('nome')} />
          </div>
          <FloatingField
            label="Código INEP"
            inputMode="numeric"
            error={errors.codigo_inep?.message}
            {...register('codigo_inep')}
          />
          <Field label="Polo" error={errors.polo_id?.message}>
            <select id="school-polo" {...register('polo_id')}>
              <option value="">Sem polo</option>
              {poles.map((pole) => (
                <option key={pole.id} value={String(pole.id)}>
                  {pole.nome}
                </option>
              ))}
            </select>
          </Field>
          <div className="sm:col-span-2">
            <FloatingField label="Endereço" error={errors.endereco?.message} {...register('endereco')} />
          </div>
          <section className="flex flex-col gap-2 sm:col-span-2">
            <h2 className="text-section font-semibold text-ink">Localização</h2>
            {errors.localizacao?.message && (
              <p role="alert" className="text-caption text-danger">
                {errors.localizacao.message}
              </p>
            )}
            <Controller
              control={control}
              name="localizacao"
              render={({ field }) => (
                <PointPicker value={field.value} onChange={field.onChange} required />
              )}
            />
          </section>
          <div className="flex justify-end gap-2 pt-6 sm:col-span-2">
            <Button variant="ghost" asChild>
              <Link to={school ? `/schools/${school.id}` : '/schools'}>Cancelar</Link>
            </Button>
            <Button type="submit" disabled={save.isPending}>
              Salvar
            </Button>
          </div>
        </form>
      </Panel>
    </div>
  )
}

function EditSchoolForm({ schoolId, poles }: { schoolId: number; poles: PoloLer[] }) {
  const query = useSchool(schoolId)

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) return <PageState status="error" error={query.error} />

  return <SchoolForm school={query.data} poles={poles} />
}

export function SchoolFormPage() {
  const { id } = useParams()
  const poles = usePoleOptions()

  if (poles.isPending) return <PageState status="loading" />
  if (poles.isError) {
    return <PageState status="error" error={poles.error} onRetry={() => void poles.refetch()} />
  }

  if (id === undefined) return <SchoolForm poles={poles.data} />

  return <EditSchoolForm schoolId={Number(id)} poles={poles.data} />
}
