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

  it('routes every dropdown through the canonical authored AppSelect', () => {
    const selectTags = collectVueFiles(sourceRoot)
      .flatMap((path) => readFileSync(path, 'utf8').match(/<select\b[^>]*>/g) ?? [])

    expect(selectTags).toEqual([])

    const settingsSource = readFileSync(resolve(sourceRoot, 'views/Settings.vue'), 'utf8')
    expect(settingsSource.match(/<AppSelect\b/g)).toHaveLength(2)

    const selectSource = readFileSync(resolve(sourceRoot, 'components/AppSelect.vue'), 'utf8')
    expect(selectSource).toContain('<SelectPortal>')
    expect(selectSource).toContain('position="popper"')
    expect(selectSource).toContain('width: var(--reka-select-trigger-width);')
  })

  it('lets narrow settings pages grow naturally instead of collapsing navigation', () => {
    const settingsSource = readFileSync(resolve(sourceRoot, 'views/Settings.vue'), 'utf8')
    const narrowStart = settingsSource.indexOf('@media (max-width: 900px)')
    const narrowEnd = settingsSource.indexOf('@media (max-width: 720px)')
    const narrowLayoutContract = settingsSource.slice(narrowStart, narrowEnd)

    expect(narrowStart).toBeGreaterThan(-1)
    expect(narrowEnd).toBeGreaterThan(narrowStart)
    expect(narrowLayoutContract).toMatch(/\.settings-layout\s*{[^}]*flex:\s*none;/)
    expect(narrowLayoutContract).toMatch(/grid-template-rows:\s*auto auto;/)
  })
})
