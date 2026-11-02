import { zodResolver } from '@hookform/resolvers/zod'
import { useState } from 'react'
import { useForm } from 'react-hook-form'
import { Link, useNavigate, useParams } from 'react-router-dom'
import { AreaEditor } from '@/features/poles/components/AreaEditor'
import { ApiError } from '@/shared/api/errors'
import type { components } from '@/shared/api/schema'
import { BaseMap } from '@/shared/map/BaseMap'
import type { LatLng } from '@/shared/map/geo'
import { Button } from '@/shared/ui/button'
import { FloatingField } from '@/shared/ui/FloatingField'
import { PageHeader } from '@/shared/ui/PageHeader'
import { Panel } from '@/shared/ui/Panel'
import { PageState } from '@/shared/ui/PageState'
import { notifyError, notifySuccess } from '@/shared/ui/toast'
import { usePole, useSavePole } from '../hooks'
import { poleSchema, type PoleFormValues } from '../schemas'

type PoleLer = components['schemas']['PoloLer']
type MultiPolygon = components['schemas']['MultiPolygonGeoJSON']

const GEOMETRY_ERROR = /geometr|área|area/i

function firstPoint(area: MultiPolygon | null): LatLng | undefined {
  const point = area?.coordinates[0]?.[0]?.[0]
  return point ? { latitude: point[1], longitude: point[0] } : undefined
}

type PoleFormProps = { pole?: PoleLer }

function PoleForm({ pole }: PoleFormProps) {
  const navigate = useNavigate()
  const save = useSavePole(pole?.id)
  const [area, setArea] = useState<MultiPolygon | null>(pole?.area ?? null)
  const [geometryError, setGeometryError] = useState<string | null>(null)
  const {
    register,
    handleSubmit,
    setError,
    formState: { errors },
  } = useForm<PoleFormValues>({
    resolver: zodResolver(poleSchema),
    defaultValues: { nome: pole?.nome ?? '' },
  })

  function handleAreaChange(next: MultiPolygon | null) {
    setArea(next)
    setGeometryError(null)
  }

  function applyServerError(e: unknown) {
    if (!(e instanceof ApiError)) {
      notifyError(e)
      return
    }
    const fieldEntries = Object.entries(e.fieldErrors)
    for (const [field, message] of fieldEntries) {
      if (field === 'nome') setError('nome', { message })
      else setGeometryError(message)
    }
    if (fieldEntries.length > 0) return
    if (e.status === 422 && GEOMETRY_ERROR.test(e.detail)) {
      setGeometryError(e.detail)
      return
    }
    notifyError(e)
  }

  async function onSubmit(values: PoleFormValues) {
    setGeometryError(null)
    try {
      const saved = await save.mutateAsync({ nome: values.nome, area })
      notifySuccess('Polo salvo')
      navigate(`/poles/${saved.id}`)
    } catch (e) {
      applyServerError(e)
    }
  }

  return (
    <div className="flex flex-col gap-6">
      <PageHeader
        title={pole ? 'Editar polo' : 'Novo polo'}
        description="Nome e área de atendimento do polo no mapa"
      />
      <Panel dense className="max-w-[720px] p-6 lg:p-6">
        <form onSubmit={handleSubmit(onSubmit)} noValidate className="flex flex-col gap-4">
          <FloatingField label="Nome" error={errors.nome?.message} {...register('nome')} />
          <section className="flex flex-col gap-2">
            <h2 className="text-section font-semibold text-ink">Área do polo</h2>
            {geometryError && (
              <p role="alert" className="text-caption text-danger">
                {geometryError}
              </p>
            )}
            <BaseMap center={firstPoint(pole?.area ?? area)} className="h-[280px]">
              <AreaEditor value={area} onChange={handleAreaChange} />
            </BaseMap>
          </section>
          <div className="flex justify-end gap-2 pt-2">
            <Button variant="ghost" asChild>
              <Link to={pole ? `/poles/${pole.id}` : '/poles'}>Cancelar</Link>
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

function EditPoleForm({ poleId }: { poleId: number }) {
  const query = usePole(poleId)

  if (query.isPending) return <PageState status="loading" />
  if (query.isError) return <PageState status="error" error={query.error} />

  return <PoleForm pole={query.data} />
}

export function PoleFormPage() {
  const { id } = useParams()

  if (id === undefined) return <PoleForm />

  return <EditPoleForm poleId={Number(id)} />
}
