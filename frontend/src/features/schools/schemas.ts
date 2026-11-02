import { z } from 'zod'

const pointSchema = z.object({
  latitude: z.number(),
  longitude: z.number(),
})

export type SchoolFormValues = {
  nome: string
  codigo_inep: string
  endereco: string
  polo_id: string
  localizacao: z.infer<typeof pointSchema> | null
}

export const schoolSchema: z.ZodType<SchoolFormValues, SchoolFormValues> = z.object({
  nome: z.string().trim().min(1, 'Informe o nome'),
  codigo_inep: z
    .string()
    .trim()
    .refine((value) => value === '' || /^\d{8}$/.test(value), 'O código INEP tem 8 dígitos'),
  endereco: z.string().trim(),
  polo_id: z.string(),
  localizacao: pointSchema.nullable().refine((value) => value !== null, 'Marque a localização no mapa'),
})
