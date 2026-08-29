# Glimpse 发布与版本管理

本文档是发布流程与版本管理的唯一事实源：构建安装包、维护版本号、创建
Release 以及撰写面向用户的 Release 正文，都在这里维护。

## 构建安装包

构建脚本 [build_release.bat](../build_release.bat) 会做两步：

1. 用 `PyInstaller` 构建 Python 后端 sidecar
2. 用 `Tauri` 构建 NSIS 安装包

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

## 正式版发布后的 Release 说明（必做）

正式版标签触发的 Workflow 使用 `--generate-notes` 创建 Release；自动正文只是
提交列表或 compare 链接，不能作为最终发布说明。Workflow 成功且安装包上传后，
必须补写面向用户的中文说明，完成正文验收后才能宣布发布完成。

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
  不写“调整了某组件”这类实现过程。

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

   - 每条只写一句话且不超过 30 个字，说明用户实际得到的结果。
   - 删除锁、死代码、SemVer、通道名等实现或发布术语。
   - 使用“默认”“不再”“支持”“移除”等准确的结果表述。
   - 没有用户可感知变化的改动不写；某分类无内容时保留标题，不编造条目。
   - `Full Changelog` 使用 `v上一版...v本版` 的 GitHub compare 链接。

3. 用填写后的文件覆盖 Release 正文：

   ```powershell
   gh release edit $CurrentTag --notes-file $NotesFile
   ```

标准流程是先由 Workflow 创建 Release，再使用上面的命令覆盖正文。若需要在长时间
构建开始前就准备好正式文案，也可以在标签已推送且 Release 尚不存在时手动执行
`gh release create $CurrentTag --verify-tag --notes-file $NotesFile`；随后 Workflow
会检测到已有 Release，只上传安装包和 `SHA256SUMS.txt`，不会自动覆盖正文。无论采用
哪种写入方式，都必须在最后回读正文、发布状态和资产。

4. 重新读取 GitHub Release，确认正文、正式发布状态和链接都正确：

   ```powershell
   gh release view $CurrentTag --json name,tagName,isDraft,isPrerelease,body,url
   ```

   同时确认安装包和 `SHA256SUMS.txt` 已上传。验收完成后删除临时说明文件；
   在此之前不得把发布报告为完成。`v0.2.1` 的发布说明是文案风格范本。

## 公开预览版的 Release 说明

发布公开预览版时同样应提供面向用户的中文说明。素材范围从最近一个正式版或公开
预览版标签（取最近者）到当前预览版标签；后续正式版则仍以两个正式版标签之间的
全部变化为范围，可参考这期间的预览版说明进行归纳。

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
