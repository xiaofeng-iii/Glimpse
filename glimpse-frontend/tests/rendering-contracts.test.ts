import { readdirSync, readFileSync } from 'node:fs'
import { join, resolve } from 'node:path'
import { describe, expect, it } from 'vitest'

const sourceRoot = resolve(process.cwd(), 'src')

const collectVueFiles = (directory: string): string[] => readdirSync(directory, { withFileTypes: true })
  .flatMap((entry) => {
    const path = join(directory, entry.name)
    if (entry.isDirectory()) return collectVueFiles(path)
    return entry.isFile() && entry.name.endsWith('.vue') ? [path] : []
  })

describe('frontend rendering contracts', () => {
  it('never references app_name from a rendered Vue page or component', () => {
    const offenders = collectVueFiles(sourceRoot)
      .filter((path) => readFileSync(path, 'utf8').includes('app_name'))

    expect(offenders).toEqual([])
  })
})
