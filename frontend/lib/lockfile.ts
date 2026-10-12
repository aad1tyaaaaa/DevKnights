// Same rules as extension/src/utils/workspace.ts and the backend's Lockfile model.

export const MAX_LOCKFILE_BYTES = 10 * 1024 * 1024

export interface ParsedLockfile {
  data: Record<string, unknown> & { lockfileVersion: number; name?: string }
  packageCount: number
}

/** Parses and structurally validates package-lock.json text. Throws an Error with a user-facing message. */
export function parseLockfile(text: string): ParsedLockfile {
  let data: unknown
  try {
    data = JSON.parse(text)
  } catch {
    throw new Error('This file is not valid JSON.')
  }
  if (typeof data !== 'object' || data === null || Array.isArray(data)) {
    throw new Error('A package-lock.json must contain a JSON object.')
  }
  const lock = data as ParsedLockfile['data']
  if (![1, 2, 3].includes(lock.lockfileVersion)) {
    throw new Error(`Unsupported lockfileVersion: ${String(lock.lockfileVersion)}. Expected 1, 2 or 3.`)
  }
  const section = lock.lockfileVersion === 1 ? 'dependencies' : 'packages'
  const value = lock[section]
  if (typeof value !== 'object' || value === null || Array.isArray(value)) {
    throw new Error(`lockfileVersion ${lock.lockfileVersion} requires a "${section}" object.`)
  }
  // v2/v3: the "" key is the project itself, not a dependency.
  const packageCount = Object.keys(value).filter((k) => k !== '').length
  return { data: lock, packageCount }
}
