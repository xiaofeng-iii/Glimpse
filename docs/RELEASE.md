# Glimpse 发布与版本管理

本文档是发布流程与版本管理的唯一事实源：构建安装包、维护版本号、创建
Release 以及撰写面向用户的 Release 正文，都在这里维护。

## 构建安装包

构建脚本 [build_release.bat](../build_release.bat) 会做两步：

1. 用 `PyInstaller` 构建 Python 后端 sidecar
2. 用 `Tauri` 构建 NSIS 安装包

## 依赖对齐与构建失败排查

依赖声明与版本对齐是**开发时**纪律，**推送时**由 CI 机械校验，发布构建只作
最后防线。

开发时：新增任何运行时导入的包，在写 import 的同时用
`npm install <pkg>@<版本>` 落入 `package.json` 与锁文件，`await import()`
动态导入同样要声明（完整约定见根目录 `AGENTS.md`）。Tauri 系 npm 包版本取
`src-tauri/Cargo.lock` 锁定的 crate 版本（同 major.minor），不按本地残留或
“最新”选；安装后检查锁文件 diff——npm 会为满足新包的依赖范围连带升级其他
包，安装 plugin-opener@2.7.0 就曾把 @tauri-apps/api 从 2.11.0 抬到 2.12.1。

推送时：`ci.yml` 工作流在每次 push 到 main 与 PR 上运行 `npm ci` →
`vue-tsc` → `scripts/check_dependencies.mjs`（校验导入 ⊆ 声明、Tauri npm 包
与 crate 同 minor）。本地提交前可直跑同一脚本。

发布时（最后防线）：发布工作流只校验与 tag 绑定的事项——版本号同步
（`set_version.py --check`）、Python 单元测试、完整构建（PyInstaller sidecar
与签名的 NSIS 安装包）、sidecar 冒烟测试，外加兜底性质的 `vue-tsc` 与
Tauri CLI 同 minor 校验。依赖缺失或版本错位不应到发布时才首次暴露。

已发布版本构建失败的定位入口是 `gh run view <run-id> --log-failed`。修复走
「tag 拉分支 → 重指 tag 重新发布 → 合并回主线」：重推 tag 后
`gh release upload --clobber` 只补资产、不动已发布正文；主线合并保证修复
可达、后续开发不进 tag 也不丢失。v0.4.2 曾因「动态导入未声明」与「npm 包
版本高于 crate」连续两次构建失败，即以该流程修复并沉淀出本节规则。

## 版本号事实源

应用版本只在 `glimpse-frontend/src-tauri/Cargo.toml` 的
`[package].version` 中维护。Tauri 安装包和内置 Python API 都从该版本派生；
`pyproject.toml` 中的版本仅作为 Python 包元数据镜像，`Cargo.lock` 中的根包版本
由同步工具维护；这些镜像和锁文件都不要手工修改。

同步版本号并检查重复版本字段：

```powershell
python scripts/set_version.py 0.2.0
python scripts/set_version.py --check
```

## 发布脚本

一键提交当前改动、创建版本标签并推送到 GitHub：

```powershell
.\scripts\release.ps1 -Version 0.2.0
```

脚本会显示待提交文件，并要求输入 `v0.2.0` 确认。推送成功后，
`.github/workflows/release.yml` 会在 GitHub 的 Windows 服务器上运行 Python
单元测试、构建 NSIS 安装包、执行 sidecar 冒烟检查、生成 SHA-256 校验文件并
创建 GitHub Release。
可先使用 `-DryRun` 预览，或在无人值守环境中明确传入 `-Yes`。

## Release 更新说明（正式版与公开预览版必做）

正式版与公开预览版标签触发的 Workflow 都只负责上传安装包与校验文件；若 Release
尚不存在，会以 `--generate-notes` 兜底创建，自动正文只是提交列表或 compare 链接，
不能作为最终发布说明。面向用户的中文更新说明必须人工撰写，完成正文验收后才能
宣布发布完成。两个通道的写入流程完全一致，仅预览版在预创建命令上追加 `--prerelease`。

Release 标题统一为 `Glimpse <标签名>`（如 `Glimpse v0.3.2`、
`Glimpse v0.3.3-preview.20261001`）；Workflow 兜底创建的标题是裸标签名，验收发现
不符时用 `gh release edit $CurrentTag --title "Glimpse $CurrentTag"` 修正。

发布说明的内容边界：

- **正式版**以最近一个正式版本标签到当前正式版标签之间的变化为范围。期间发布的
  预览版可以作为整理素材的参考，但不改变正式版的统计范围。
- **公开预览版**以上一个正式版或公开预览版标签（取最近者）到当前预览版标签之间的
  变化为范围。
- 只写最终用户能感知的能力、体验优化和修复。
- 某项主功能本来就必须具备的搜索、筛选、索引或接口适配，不单独包装成发布亮点；
  可以合并到主功能描述中。
- 开发过程中的返工、设计波折、临时方案、内部重构、测试补充、文档和版本元数据不
  写入 Release 正文。
- 独立影响用户操作的人机交互或稳定性改进可以保留，但文案应描述用户得到的结果，
  不写“调整了某组件”这类实现过程。每条说明只应让用户的注意力停留一次：以一个
  界面上看得见、叫得出的东西为锚点（搜索栏、卡片、滚动条、日期与寄语），直接说出
  获得感；“装饰面板”“常驻分割线”“随滑块变色”“时长自适应”这类词要求用户先
  理解实现才能读懂，写得再准确也是在消耗注意力。

1. 从上一正式版到本版的提交记录收集素材，只保留用户能感知的变化：

   ```powershell
   $PreviousTag = "v0.2.1"
   $CurrentTag = "v0.2.2"
   git log --oneline "$PreviousTag..$CurrentTag"
   ```

2. 在 `.tmp/` 中准备临时发布说明文件：

   ```powershell
   $NotesFile = ".tmp/release-notes-$CurrentTag.md"
   ```

   正文使用以下骨架：

   ```markdown
   ## Glimpse vX.Y.Z

   **新特性**
   - 用户可感知的新能力

   **优化**
   - 用户能感知的体验改善

   **修复**
   - 用户能感知的修复结果

   **Full Changelog**: https://github.com/xiaofeng-iii/Glimpse/compare/v上一版...v本版
   ```

   编写时遵循以下规则：

   - 每条只写一句话且不超过 40 个字，说明用户实际得到的结果。
   - 删除锁、死代码、SemVer、通道名等实现或发布术语；“随滑块变色”“时长自适应”
     “单调增减”这类表述同理——读起来像成果，却要用户先理解实现，转写成
     “更顺滑”“更居中”这样一眼可感的利好。
   - 使用“默认”“不再”“支持”“移除”等准确的结果表述。
   - 某分类无内容时保留标题、内容为空（如「**修复**」后不接任何条目），不得编造条目；只有整段分类在正文中被按规定保留后，方可宣布发布完成。
   - `Full Changelog` 使用 `v上一版...v本版` 的 GitHub compare 链接。

3. 用填写后的文件覆盖 Release 正文：

   ```powershell
   gh release edit $CurrentTag --notes-file $NotesFile
   ```

推荐流程：推送标签后立即用说明文件预创建 Release，Workflow 检测到已有 Release，
只上传安装包和 `SHA256SUMS.txt`，不会覆盖正文：

```powershell
gh release create $CurrentTag --verify-tag --title "Glimpse $CurrentTag" --notes-file $NotesFile
# 公开预览版追加 --prerelease：
gh release create $CurrentTag --verify-tag --prerelease --title "Glimpse $CurrentTag" --notes-file $NotesFile
```

若 Release 已由 Workflow 兜底创建，则改用上面的 `gh release edit` 覆盖正文。无论
采用哪种写入方式，都必须在最后回读正文、发布状态和资产。

4. 重新读取 GitHub Release，确认正文、正式发布状态和链接都正确：

   ```powershell
   gh release view $CurrentTag --json name,tagName,isDraft,isPrerelease,body,url
   ```

   同时确认安装包和 `SHA256SUMS.txt` 已上传，标题（`name`）为
`Glimpse <标签名>`。验收完成后删除临时说明文件；
   在此之前不得把发布报告为完成。`v0.2.1` 的发布说明是文案风格范本。

## 公开预览版的 Release 说明

公开预览版的说明撰写与发布流程和正式版完全一致（见上节），差异仅有两点：预创建
命令追加 `--prerelease`；素材范围为最近一个正式版或公开预览版标签（取最近者）到
当前预览版标签。后续正式版仍以两个正式版标签之间的全部变化为范围，可参考这期间
的预览版说明进行归纳。

## 应用内更新（GitHub Pages）

桌面设置页的「软件更新」提供手动检查、确认下载和安装。正式通道只接收正式版；
预览通道接收最新的预览版或版本更高的正式版。首次启用更新器的安装包仍须手动
安装一次。源码启动或浏览器调试时不提供安装更新。

发布准备（只需做一次）：

1. 在仓库 Settings → Pages 中选择 **GitHub Actions** 作为 Build and deployment source。
   站点预计为 `https://xiaofeng-iii.github.io/Glimpse/`；启用后须实际打开并验证
   `updates/stable.json` 和 `updates/preview.json` 地址，再交付安装包。
2. 更新公钥已经写入 `glimpse-frontend/src-tauri/tauri.conf.json`。相应私钥保存在
   本地忽略的 `.tmp/glimpse-updater.key`；将该文件**完整内容**放进仓库 Actions
   Secret `TAURI_SIGNING_PRIVATE_KEY`，不要提交、上传或放进 Release/Pages。
   当前密钥未设置密码；如日后更换为有密码的密钥，需同时配置
   `TAURI_SIGNING_PRIVATE_KEY_PASSWORD`，且更换公钥会影响旧版更新能力，
   因此不要随意轮换。务必离线备份私钥。其他构建环境也需设置上述环境变量。
3. 正式版和预览版工作流在构建时生成 NSIS `.exe.sig`，与安装包、校验文件一起
   上传 Release。仅 `SHA256SUMS.txt` 不足以让 Tauri Updater 验证更新。
4. 任一发布工作流成功完成后，`updater-pages.yml` 会重新扫描已发布且具备签名的
   GitHub Releases，按版本号生成 `updates/stable.json` 和 `updates/preview.json`，
   部署至 Pages；工作流也支持手动触发以重建索引。检查 Pages 工作流已成功，
   并回读 JSON 的版本、安装包 URL 和签名，再将更新视为可用。未签名的旧版
   Release 不会进入索引；第一个签名发布版之前对应 JSON 可能尚不存在。
5. 使用已安装的上一版本测试「检查更新 → 下载并安装 → 重启」，并检查后台
   `GlimpseRuntime.exe` 是否正常退出与重启、`GlimpseData` 是否保留。只在
   GitHub Pages 已启用、安装包已签名及测试通过之后对用户公布应用内更新。

私钥丢失会导致已有安装版本无法验证后续更新。发布流程不擅自修改版本号；
版本仍按本文现有规则由发布者决定。

## 版本命名规范

项目统一采用 SemVer + 预发布后缀，三个发布通道，不再混用日历版本：

| 通道 | 版本号 | Git 标签 | GitHub Release 形态 | 可见性 |
|---|---|---|---|---|
| 正式版 | `0.2.0`、`0.3.0`、`1.0.0` | `v0.2.0` | Release | 所有人可见 |
| 公开预览 | `0.2.0-preview.20260806` | `v0.2.0-preview.20260806` | Pre-release | 所有人可见（带 prerelease 标记） |
| 私密开发版 | `0.2.0-dev.20260806` | `v0.2.0-dev.20260806` | Draft | 仅仓库协作者可见 |

- **正式版**：功能稳定后发布，推送纯 SemVer 标签后触发 `.github/workflows/release.yml`
- **公开预览（preview）**：功能完成、准备收集外部反馈时发布，推送 Preview 标签后触发 `.github/workflows/preview-release.yml`
- **私密开发版（dev）**：开发中途自测用，不对外暴露半成品，通过 GitHub Actions 的 `workflow_dispatch` 手动触发 `.github/workflows/dev-release.yml`

同一天需要重新构建同一基础版本时，在日期后追加递增序号，例如
`0.2.0-preview.20260806.1`、`0.2.0-preview.20260806.2`；不要移动或覆盖已经推送的预览标签。

三个通道都会校验 `scripts/set_version.py --check`（仓库版本必须与标签/输入完全一致）。
`scripts/set_version.py` 接受标准 SemVer 预发布后缀（`-preview.20260806`、`-dev.20260806`、`-rc.1`）和构建元数据（`+build.5`）。

## 发布产物与运行时

安装包输出目录：

- `glimpse-frontend/src-tauri/target/release/bundle/nsis/`

发布版运行时：

- 数据默认写入 `%LOCALAPPDATA%\Glimpse\GlimpseData`
- 可将 `.env` 放在应用根目录，或放在 `%LOCALAPPDATA%\Glimpse\GlimpseData\.env`
- 内置 API 进程文件名为 `GlimpseRuntime.exe`，Windows 友好名称为 `Glimpse 核心服务`
