// 校验前端依赖声明与 Tauri npm/crate 版本对齐（CI 与本地共用同一脚本）。
// 规则与背景见 docs/RELEASE.md「依赖对齐与构建失败排查」：
// 1) 源码中一切运行时导入的包必须已在 package.json 声明（动态导入同样算）；
// 2) @tauri-apps/* npm 包必须与 src-tauri/Cargo.lock 锁定的同名 crate 同 major.minor
//    （@tauri-apps/api 对应 tauri，@tauri-apps/plugin-X 对应 tauri-plugin-X）。
// 用法：node scripts/check_dependencies.mjs [仓库根目录]，缺省为本脚本上一级目录。
import { readFileSync, readdirSync } from 'node:fs'
import { dirname, join, relative } from 'node:path'
import { fileURLToPath } from 'node:url'

const root = process.argv[2] ?? join(dirname(fileURLToPath(import.meta.url)), '..')
const frontend = join(root, 'glimpse-frontend')
const problems = []

// --- 1) 导入 ⊆ 声明 ---
const pkg = JSON.parse(readFileSync(join(frontend, 'package.json'), 'utf8'))
const declared = new Set([
  ...Object.keys(pkg.dependencies ?? {}),
  ...Object.keys(pkg.devDependencies ?? {}),
])

const SOURCE_EXT = /\.(ts|tsx|js|jsx|mts|mjs|vue)$/
// from 'x' / import 'x' / import('x') / export … from 'x' 一律提取说明符。
const IMPORT_RE = /(?:from|import)\s*\(?\s*['"]([^'"]+)['"]/g
const isInternal = (spec) =>
  spec.startsWith('.') || spec.startsWith('/') || spec.startsWith('@/') || spec.startsWith('node:')
const packageNameOf = (spec) =>
  spec.startsWith('@') ? spec.split('/').slice(0, 2).join('/') : spec.split('/')[0]

const auditImports = (dir) => {
  for (const entry of readdirSync(dir, { withFileTypes: true })) {
    const path = join(dir, entry.name)
    if (entry.isDirectory()) {
      auditImports(path)
      continue
    }
    if (!SOURCE_EXT.test(entry.name)) continue
    const text = readFileSync(path, 'utf8')
    for (const match of text.matchAll(IMPORT_RE)) {
      const spec = match[1]
      if (isInternal(spec)) continue
      const name = packageNameOf(spec)
      if (!declared.has(name)) {
        problems.push(
          `未声明的依赖 "${name}"（导入 "${spec}"，位于 ${relative(frontend, path)}）；` +
            '请用 npm install <pkg>@<版本> 写入 package.json 与锁文件',
        )
      }
    }
  }
}
auditImports(join(frontend, 'src'))

// --- 2) Tauri npm 包 ↔ Rust crate 同 major.minor ---
const npmLock = JSON.parse(readFileSync(join(frontend, 'package-lock.json'), 'utf8'))
const npmTauri = new Map()
for (const [key, entry] of Object.entries(npmLock.packages ?? {})) {
  const match = key.match(/^node_modules\/(@tauri-apps\/[^/]+)$/)
  if (match && entry.version) npmTauri.set(match[1], entry.version)
}

const crates = new Map()
const cargoText = readFileSync(join(frontend, 'src-tauri', 'Cargo.lock'), 'utf8')
for (const block of cargoText.split('[[package]]').slice(1)) {
  const name = block.match(/^name = "(.+)"$/m)?.[1]
  const version = block.match(/^version = "(.+)"$/m)?.[1]
  if (name && version) crates.set(name, version)
}

// tauri-plugin-* 而无对应 npm 包属正常（如 updater 只在 Rust 侧使用），只查 npm 侧。
const crateForNpm = (npmName) => {
  if (npmName === '@tauri-apps/api') return 'tauri'
  const match = npmName.match(/^@tauri-apps\/plugin-(.+)$/)
  return match ? `tauri-plugin-${match[1]}` : null
}
const minorOf = (version) => version.split('.').slice(0, 2).join('.')

let alignedPairs = 0
for (const [npmName, npmVersion] of [...npmTauri].sort(([a], [b]) => a.localeCompare(b))) {
  const crateName = crateForNpm(npmName)
  if (!crateName) continue
  const crateVersion = crates.get(crateName)
  if (!crateVersion) {
    problems.push(`npm 包 ${npmName}@${npmVersion} 在 src-tauri/Cargo.lock 中找不到对应 crate ${crateName}`)
    continue
  }
  if (minorOf(npmVersion) !== minorOf(crateVersion)) {
    problems.push(
      `Tauri 版本错位：npm ${npmName}@${npmVersion} 与 crate ${crateName}@${crateVersion} 不同 minor；` +
        'npm 版本以 Cargo.lock 锁定的 crate 为准选择',
    )
  } else {
    alignedPairs += 1
  }
}

if (problems.length > 0) {
  console.error('依赖检查失败：')
  for (const problem of problems) console.error(`  - ${problem}`)
  process.exit(1)
}
console.log(`依赖检查通过：导入均已声明，Tauri npm/crate ${alignedPairs} 组对齐。`)
