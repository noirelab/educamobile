export type PasswordScore = 0 | 1 | 2 | 3 | 4

export function passwordScore(v: string): PasswordScore {
  if (v.length < 10) return 0
  let score = 1
  if (/[a-z]/.test(v) && /[A-Z]/.test(v)) score++
  if (/\d/.test(v)) score++
  if (/[^A-Za-z0-9]/.test(v)) score++
  return score as PasswordScore
}
