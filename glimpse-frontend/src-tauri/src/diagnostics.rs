// 本地诊断日志宿主侧：前端结构化事件落盘（JSONL）、日志目录入口、诊断包导出。
// 全部核心逻辑是纯函数（传入目录与限额），Tauri command 只做路径解析与包装，
// 便于在临时目录里做单元测试，绝不触碰真实 GlimpseData。
use serde_json::{json, Map, Value};
use std::fmt::Write as FmtWrite;
use std::fs::{self, File, OpenOptions};
use std::io::{Read, Seek, SeekFrom, Write};
use std::path::{Path, PathBuf};
use std::sync::Mutex;
use std::time::{SystemTime, UNIX_EPOCH};
use tauri::AppHandle;

use crate::backend_data_root;

const FRONTEND_LOG_FILE: &str = "glimpse-frontend.jsonl";
const BACKEND_LOG_FILE: &str = "glimpse.log";
pub const BACKEND_SESSION_ID_ENV: &str = "GLIMPSE_SESSION_ID";
const MAX_LINE_BYTES: usize = 16 * 1024;
const MAX_FILE_BYTES: u64 = 2 * 1024 * 1024;
const BACKUP_COUNT: usize = 3;
const EXPORT_TAIL_CAP_BYTES: u64 = 2 * 1024 * 1024;

/// 写入限额参数化：生产用默认值，测试注入小值验证滚动与截断。
pub(crate) struct WriteLimits {
    pub max_line_bytes: usize,
    pub max_file_bytes: u64,
    pub backup_count: usize,
}

impl Default for WriteLimits {
    fn default() -> Self {
        Self {
            max_line_bytes: MAX_LINE_BYTES,
            max_file_bytes: MAX_FILE_BYTES,
            backup_count: BACKUP_COUNT,
        }
    }
}

/// 每次宿主进程启动生成一次；前端、Python sidecar 与诊断包 manifest 共用。
pub fn generate_session_id() -> String {
    let mut bytes = [0_u8; 16];
    if getrandom::fill(&mut bytes).is_err() {
        let fallback = format!(
            "{}:{}",
            std::process::id(),
            SystemTime::now()
                .duration_since(UNIX_EPOCH)
                .map(|value| value.as_nanos())
                .unwrap_or_default()
        );
        bytes.fill(0);
        for (index, byte) in fallback.as_bytes().iter().enumerate() {
            bytes[index % bytes.len()] ^= *byte;
        }
    }

    let mut session_id = String::with_capacity(bytes.len() * 2);
    for byte in bytes {
        let _ = write!(session_id, "{byte:02x}");
    }
    session_id
}

/// 串行化宿主侧文件写入，避免并发 command 在滚动窗口互相踩踏。
pub struct DiagnosticsState {
    io_lock: Mutex<()>,
    session_id: String,
}

impl Default for DiagnosticsState {
    fn default() -> Self {
        Self {
            io_lock: Mutex::new(()),
            session_id: generate_session_id(),
        }
    }
}

impl DiagnosticsState {
    pub fn session_id(&self) -> &str {
        &self.session_id
    }
}

fn diagnostics_logs_dir(app: &AppHandle) -> Option<PathBuf> {
    backend_data_root(app).map(|root| root.join("logs"))
}

fn redact_text(text: &str) -> String {
    static PATTERNS: std::sync::OnceLock<Vec<(regex::Regex, &'static str)>> =
        std::sync::OnceLock::new();
    let patterns = PATTERNS.get_or_init(|| {
        [
            (r#"(?i)\bBearer\s+[^\s"'<>]+"#, "Bearer <redacted>"),
            (r#"//[^\s/@]+@"#, "//<redacted>@"),
            (r#"(?i)(\b(?:api[_-]?key|secret(?:[_-]?key)?|password|authorization|access[_-]?token|auth[_-]?token|token|signature)["']?\s*[=:]\s*["']?)[^\s&"'<> ,}]+"#, "${1}<redacted>"),
        ].into_iter().map(|(pattern, replacement)| (regex::Regex::new(pattern).expect("valid redaction pattern"), replacement)).collect()
    });
    patterns
        .iter()
        .fold(text.to_owned(), |value, (pattern, replacement)| {
            pattern.replace_all(&value, *replacement).into_owned()
        })
}

fn redact_value(value: &mut Value) {
    match value {
        Value::String(text) => *text = redact_text(text),
        Value::Array(items) => items.iter_mut().for_each(redact_value),
        Value::Object(fields) => {
            for (key, value) in fields {
                let normalized = key.to_ascii_lowercase().replace(['_', '-'], "");
                if [
                    "apikey",
                    "secret",
                    "secretkey",
                    "password",
                    "authorization",
                    "accesstoken",
                    "authtoken",
                    "token",
                    "signature",
                ]
                .contains(&normalized.as_str())
                {
                    *value = json!("<redacted>");
                } else {
                    redact_value(value);
                }
            }
        }
        _ => {}
    }
}

fn export_text(name: &str, bytes: &[u8], truncated: bool) -> String {
    let text = String::from_utf8_lossy(bytes);
    if name.starts_with(FRONTEND_LOG_FILE) {
        text.lines()
            .enumerate()
            .filter_map(|(index, line)| {
                if truncated && index == 0 {
                    return None;
                }
                let mut value = serde_json::from_str::<Value>(line).ok()?;
                redact_value(&mut value);
                Some(format!("{value}\n"))
            })
            .collect()
    } else {
        redact_text(&text)
    }
}

fn cut(value: &str, cap: usize) -> String {
    if value.len() <= cap {
        return value.to_string();
    }
    let mut end = cap;
    while end > 0 && !value.is_char_boundary(end) {
        end -= 1;
    }
    format!("{}…<truncated>", &value[..end])
}

fn take_str(obj: &Map<String, Value>, key: &str, cap: usize) -> Option<Value> {
    obj.get(key)
        .and_then(Value::as_str)
        .map(|text| json!(cut(text, cap)))
}

/// 按白名单重建事件行；字段缺失或 `v` 不合法时返回 None（该条跳过，不连坐整批）。
fn build_line(event: &Value, limits: &WriteLimits) -> Option<String> {
    let obj = event.as_object()?;
    if obj.get("v").and_then(Value::as_u64) != Some(1) {
        return None;
    }
    let ts = obj.get("ts")?.as_str()?;
    let level = match obj.get("level")?.as_str()? {
        "debug" | "info" | "warning" | "error" => obj.get("level")?.as_str()?,
        _ => "info",
    };
    let context = obj.get("context")?.as_str()?;
    let message = obj.get("message")?.as_str()?;

    let mut out = Map::new();
    out.insert("v".to_string(), json!(1));
    out.insert("ts".to_string(), json!(cut(ts, 64)));
    out.insert("level".to_string(), json!(level));
    out.insert("context".to_string(), json!(cut(context, 200)));
    out.insert("message".to_string(), json!(cut(message, 2000)));
    for (key, cap) in [
        ("sessionId", 64),
        ("event", 100),
        ("operationId", 64),
        ("outcome", 32),
    ] {
        if let Some(value) = take_str(obj, key, cap) {
            out.insert(key.to_string(), value);
        }
    }
    if let Some(duration) = obj.get("durationMs").and_then(Value::as_u64) {
        out.insert("durationMs".to_string(), json!(duration));
    }
    if let Some(args) = obj.get("args").and_then(Value::as_array) {
        let texts: Vec<String> = args
            .iter()
            .filter_map(Value::as_str)
            .take(6)
            .map(|text| cut(text, 1000))
            .collect();
        if !texts.is_empty() {
            out.insert("args".to_string(), json!(texts));
        }
    }
    if let Some(error) = obj.get("error").and_then(Value::as_object) {
        let mut block = Map::new();
        if let Some(name) = error.get("name").and_then(Value::as_str) {
            block.insert("name".to_string(), json!(cut(name, 100)));
        }
        if let Some(text) = error.get("message").and_then(Value::as_str) {
            block.insert("message".to_string(), json!(cut(text, 2000)));
        }
        if let Some(stack) = error.get("stack").and_then(Value::as_str) {
            block.insert("stack".to_string(), json!(cut(stack, 2000)));
        }
        out.insert("error".to_string(), Value::Object(block));
    }
    if let Some(data) = obj.get("data") {
        // 附带数据只允许小体量；超限直接替换为标记，避免单行日志膨胀。
        let value = if data.to_string().len() > 4096 {
            json!({ "truncated": true })
        } else {
            data.clone()
        };
        out.insert("data".to_string(), value);
    }

    let mut line = Value::Object(out.clone()).to_string();
    if line.len() <= limits.max_line_bytes {
        return Some(line);
    }
    // 逐级减载：先丢 data，再丢 args，再硬截 message，最后退到最小骨架。
    let mut slim = out;
    slim.remove("data");
    line = Value::Object(slim.clone()).to_string();
    if line.len() <= limits.max_line_bytes {
        return Some(line);
    }
    slim.remove("args");
    line = Value::Object(slim.clone()).to_string();
    if line.len() <= limits.max_line_bytes {
        return Some(line);
    }
    slim.insert("message".to_string(), json!(cut(message, 256)));
    line = Value::Object(slim).to_string();
    if line.len() <= limits.max_line_bytes {
        return Some(line);
    }
    Some(
        json!({
            "v": 1,
            "ts": cut(ts, 64),
            "level": level,
            "context": cut(context, 200),
            "message": "<oversize-event-dropped>",
            "sessionId": obj.get("sessionId"),
        })
        .to_string(),
    )
}

fn rotation_path(path: &Path, index: usize) -> PathBuf {
    PathBuf::from(format!("{}.{}", path.display(), index))
}

fn rotate_if_needed(path: &Path, incoming_bytes: u64, limits: &WriteLimits) -> std::io::Result<()> {
    let Ok(meta) = fs::metadata(path) else {
        return Ok(());
    };
    if meta.len().saturating_add(incoming_bytes) <= limits.max_file_bytes {
        return Ok(());
    }
    let _ = fs::remove_file(rotation_path(path, limits.backup_count));
    for index in (1..limits.backup_count).rev() {
        let from = rotation_path(path, index);
        if from.exists() {
            let _ = fs::rename(&from, rotation_path(path, index + 1));
        }
    }
    fs::rename(path, rotation_path(path, 1))
}

/// 追加事件到前端诊断日志；返回实际写入条数（被跳过的无效事件不计入）。
pub(crate) fn append_events_to(
    logs_dir: &Path,
    events: &[Value],
    limits: &WriteLimits,
    session_id: &str,
) -> std::io::Result<usize> {
    fs::create_dir_all(logs_dir)?;
    let path = logs_dir.join(FRONTEND_LOG_FILE);
    let mut written = 0;
    for event in events {
        let mut event = event.clone();
        if let Some(fields) = event.as_object_mut() {
            fields.insert("sessionId".to_owned(), json!(session_id));
        }
        let Some(line) = build_line(&event, limits) else {
            continue;
        };
        rotate_if_needed(&path, line.len() as u64 + 1, limits)?;
        let mut file = OpenOptions::new().create(true).append(true).open(&path)?;
        file.write_all(line.as_bytes())?;
        file.write_all(b"\n")?;
        written += 1;
    }
    Ok(written)
}

fn read_tail(path: &Path, cap: u64) -> std::io::Result<(Vec<u8>, bool)> {
    let mut file = File::open(path)?;
    let len = file.metadata()?.len();
    if len > cap {
        file.seek(SeekFrom::Start(len - cap))?;
        let mut buffer = vec![0u8; cap as usize];
        file.read_exact(&mut buffer)?;
        Ok((buffer, true))
    } else {
        let mut buffer = Vec::new();
        file.read_to_end(&mut buffer)?;
        Ok((buffer, false))
    }
}

// 无 chrono 依赖的 UTC 时间格式化：Howard Hinnant civil_from_days 算法。
fn civil_from_days(days: i64) -> (i64, u32, u32) {
    let z = days + 719_468;
    let era = if z >= 0 { z } else { z - 146_096 } / 146_097;
    let doe = (z - era * 146_097) as u64;
    let yoe = (doe - doe / 1460 + doe / 36524 - doe / 146_096) / 365;
    let year = yoe as i64 + era * 400;
    let doy = doe - (365 * yoe + yoe / 4 - yoe / 100);
    let mp = (5 * doy + 2) / 153;
    let day = (doy - (153 * mp + 2) / 5 + 1) as u32;
    let month = if mp < 10 { mp + 3 } else { mp - 9 } as u32;
    (year + i64::from(month <= 2), month, day)
}

fn utc_now_secs() -> u64 {
    SystemTime::now()
        .duration_since(UNIX_EPOCH)
        .map(|elapsed| elapsed.as_secs())
        .unwrap_or(0)
}

fn format_stamp(secs: u64) -> (String, String) {
    let days = (secs / 86_400) as i64;
    let (year, month, day) = civil_from_days(days);
    let sod = secs % 86_400;
    let stamp = format!(
        "{year:04}{month:02}{day:02}-{hour:02}{minute:02}{second:02}",
        hour = sod / 3600,
        minute = (sod % 3600) / 60,
        second = sod % 60,
    );
    let iso = format!(
        "{year:04}-{month:02}-{day:02}T{hour:02}:{minute:02}:{second:02}Z",
        hour = sod / 3600,
        minute = (sod % 3600) / 60,
        second = sod % 60,
    );
    (stamp, iso)
}

/// 打包诊断快照：前端诊断日志（含备份）+ 后端结构化日志 + sidecar 原始输出（各限尾部 2MiB）
/// + manifest。只读固定文件集合，收集不到的条目在 manifest 里如实标注 missing。
pub(crate) fn build_export_bundle(
    logs_dir: &Path,
    session_id: Option<&str>,
    app_version: &str,
) -> std::io::Result<PathBuf> {
    let exports_dir = logs_dir.join("exports");
    fs::create_dir_all(&exports_dir)?;

    let mut sources: Vec<String> = vec![FRONTEND_LOG_FILE.to_string()];
    for index in 1..=BACKUP_COUNT {
        sources.push(format!("{}.{}", FRONTEND_LOG_FILE, index));
    }
    sources.push(BACKEND_LOG_FILE.to_string());
    for index in 1..=BACKUP_COUNT {
        sources.push(format!("{}.{}", BACKEND_LOG_FILE, index));
    }
    sources.push("glimpse-sidecar.out.log".to_string());

    let (stamp, iso) = format_stamp(utc_now_secs());
    // 临时文件与最终文件在同一目录；只有完整 ZIP 才原子发布，不覆盖已有导出。
    let mut temporary = tempfile::NamedTempFile::new_in(&exports_dir)?;
    let mut zip = zip::ZipWriter::new(temporary.as_file_mut());
    let options = zip::write::SimpleFileOptions::default()
        .compression_method(zip::CompressionMethod::Deflated);

    let mut manifest_files = Vec::new();
    for name in &sources {
        let source = logs_dir.join(name);
        let status = match read_tail(&source, EXPORT_TAIL_CAP_BYTES) {
            Ok((bytes, truncated)) => {
                zip.start_file(name.as_str(), options)?;
                zip.write_all(export_text(name, &bytes, truncated).as_bytes())?;
                if truncated {
                    "truncated"
                } else {
                    "included"
                }
            }
            Err(_) => "missing",
        };
        manifest_files.push(json!({ "name": name, "status": status }));
    }

    let manifest = json!({
        "schemaVersion": 1,
        "appVersion": app_version,
        "platform": std::env::consts::OS,
        "exportedAt": iso,
        "sessionId": session_id,
        "files": manifest_files,
    });
    zip.start_file("manifest.json", options)?;
    zip.write_all(serde_json::to_string_pretty(&manifest)?.as_bytes())?;
    zip.finish()?;
    temporary.as_file().sync_all()?;
    loop {
        let zip_path = exports_dir.join(format!(
            "glimpse-diagnostics-{stamp}-{}.zip",
            generate_session_id()
        ));
        match temporary.persist_noclobber(&zip_path) {
            Ok(_) => return Ok(zip_path),
            Err(error) if error.error.kind() == std::io::ErrorKind::AlreadyExists => {
                temporary = error.file;
            }
            Err(error) => return Err(error.error),
        }
    }
}

#[tauri::command]
pub fn append_diagnostic_logs(
    app: AppHandle,
    state: tauri::State<'_, DiagnosticsState>,
    events: Vec<Value>,
) -> Result<usize, String> {
    let logs_dir = diagnostics_logs_dir(&app).ok_or("unable to resolve logs directory")?;
    let _guard = state.io_lock.lock().map_err(|error| error.to_string())?;
    append_events_to(
        &logs_dir,
        &events,
        &WriteLimits::default(),
        state.session_id(),
    )
    .map_err(|error| error.to_string())
}

#[tauri::command]
pub fn open_logs_directory(app: AppHandle) -> Result<(), String> {
    use tauri_plugin_opener::OpenerExt;
    let dir = diagnostics_logs_dir(&app).ok_or("unable to resolve logs directory")?;
    fs::create_dir_all(&dir).map_err(|error| error.to_string())?;
    app.opener()
        .open_path(dir.to_string_lossy().to_string(), None::<&str>)
        .map_err(|error| error.to_string())
}

#[tauri::command]
pub fn diagnostic_session_id(state: tauri::State<'_, DiagnosticsState>) -> String {
    state.session_id().to_owned()
}

#[tauri::command]
pub fn export_diagnostics(
    app: AppHandle,
    state: tauri::State<'_, DiagnosticsState>,
) -> Result<String, String> {
    use tauri_plugin_opener::OpenerExt;
    let logs_dir = diagnostics_logs_dir(&app).ok_or("unable to resolve logs directory")?;
    let zip_path = build_export_bundle(
        &logs_dir,
        Some(state.session_id()),
        env!("CARGO_PKG_VERSION"),
    )
    .map_err(|error| error.to_string())?;
    // 定位失败不影响导出结果本身，静默降级为只返回路径。
    let _ = app
        .opener()
        .reveal_item_in_dir(zip_path.to_string_lossy().to_string());
    Ok(zip_path.to_string_lossy().to_string())
}

#[cfg(test)]
mod tests {
    use super::*;

    fn temp_logs_dir(label: &str) -> PathBuf {
        let unique = SystemTime::now()
            .duration_since(UNIX_EPOCH)
            .expect("system clock after epoch")
            .as_nanos();
        std::env::temp_dir().join(format!(
            "glimpse-diag-test-{}-{unique}-{label}",
            std::process::id()
        ))
    }

    fn event(message: &str) -> Value {
        json!({
            "v": 1,
            "ts": "2026-01-02T03:04:05.678Z",
            "level": "info",
            "context": "tests",
            "message": message,
            "sessionId": "session-1",
        })
    }

    #[test]
    fn append_writes_jsonl_and_skips_invalid_events() {
        let dir = temp_logs_dir("append");
        let events = vec![
            event("hello"),
            json!({ "v": 2, "ts": "x", "level": "info", "context": "c", "message": "m" }),
            json!({ "message": "missing required fields" }),
        ];
        let written = append_events_to(&dir, &events, &WriteLimits::default(), "session-1")
            .expect("append events");
        assert_eq!(written, 1);

        let content = fs::read_to_string(dir.join(FRONTEND_LOG_FILE)).expect("read jsonl");
        let lines: Vec<&str> = content.lines().collect();
        assert_eq!(lines.len(), 1);
        let parsed: Value = serde_json::from_str(lines[0]).expect("valid json line");
        assert_eq!(parsed["sessionId"], "session-1");
        assert_eq!(parsed["level"], "info");
        fs::remove_dir_all(dir).expect("cleanup");
    }

    #[test]
    fn oversize_line_is_shrunk_to_limit() {
        let dir = temp_logs_dir("oversize");
        let limits = WriteLimits {
            max_line_bytes: 400,
            max_file_bytes: 8192,
            backup_count: 2,
        };
        let mut value = event(&"x".repeat(3000));
        value["data"] = json!({ "blob": "y".repeat(500) });
        append_events_to(&dir, &[value], &limits, "session-1").expect("append events");

        let content = fs::read_to_string(dir.join(FRONTEND_LOG_FILE)).expect("read jsonl");
        let line = content.lines().next().expect("one line");
        assert!(
            line.len() <= limits.max_line_bytes,
            "line must respect the byte cap: {}",
            line.len()
        );
        let parsed: Value = serde_json::from_str(line).expect("shrunk line stays valid json");
        assert_eq!(parsed["v"], 1);
        fs::remove_dir_all(dir).expect("cleanup");
    }

    #[test]
    fn unknown_level_falls_back_to_info() {
        let dir = temp_logs_dir("level");
        let mut value = event("m");
        value["level"] = json!("verbose");
        append_events_to(&dir, &[value], &WriteLimits::default(), "session-1")
            .expect("append events");
        let content = fs::read_to_string(dir.join(FRONTEND_LOG_FILE)).expect("read jsonl");
        assert!(content.contains("\"level\":\"info\""));
        fs::remove_dir_all(dir).expect("cleanup");
    }

    #[test]
    fn rotation_shifts_backups_when_file_exceeds_limit() {
        let dir = temp_logs_dir("rotate");
        let limits = WriteLimits {
            max_line_bytes: 2048,
            max_file_bytes: 300,
            backup_count: 2,
        };
        for index in 0..8 {
            append_events_to(
                &dir,
                &[event(&format!("message-{index}"))],
                &limits,
                "session-1",
            )
            .expect("append events");
        }
        assert!(dir.join(format!("{FRONTEND_LOG_FILE}.1")).exists());
        assert!(dir.join(format!("{FRONTEND_LOG_FILE}.2")).exists());
        assert!(!dir.join(format!("{FRONTEND_LOG_FILE}.3")).exists());
        let active = fs::read_to_string(dir.join(FRONTEND_LOG_FILE)).expect("active log");
        assert!(active.contains("message-7"));
        let backup2 =
            fs::read_to_string(dir.join(format!("{FRONTEND_LOG_FILE}.2"))).expect("oldest backup");
        assert!(backup2.contains("message-2") || backup2.contains("message-3"));
        let active_meta = fs::metadata(dir.join(FRONTEND_LOG_FILE)).expect("active meta");
        assert!(active_meta.len() <= limits.max_file_bytes);
        fs::remove_dir_all(dir).expect("cleanup");
    }

    #[test]
    fn export_bundle_contains_files_and_manifest_statuses() {
        let dir = temp_logs_dir("export");
        fs::create_dir_all(&dir).expect("create logs dir");

        append_events_to(
            &dir,
            &[event("in export")],
            &WriteLimits::default(),
            "session-1",
        )
        .expect("append events");

        let mut backend_log = File::create(dir.join("glimpse.log")).expect("create backend log");
        backend_log
            .write_all(&vec![b'a'; (EXPORT_TAIL_CAP_BYTES + 1024) as usize])
            .expect("write oversized backend log");

        // glimpse-sidecar.out.log 故意缺失，manifest 必须如实标注。

        let zip_path =
            build_export_bundle(&dir, Some("session-9"), "0.0.0-test").expect("build bundle");
        assert!(zip_path.exists());

        let file = File::open(&zip_path).expect("open zip");
        let mut archive = zip::ZipArchive::new(file).expect("read zip");
        let names: Vec<String> = archive.file_names().map(str::to_string).collect();
        assert!(names.contains(&"glimpse-frontend.jsonl".to_string()));
        assert!(names.contains(&"glimpse.log".to_string()));
        assert!(names.contains(&"manifest.json".to_string()));
        let mut manifest_bytes = Vec::new();
        {
            let mut manifest_entry = archive.by_name("manifest.json").expect("manifest entry");
            assert!(manifest_entry.size() > 0);
            manifest_entry
                .read_to_end(&mut manifest_bytes)
                .expect("read manifest");
        }
        let manifest: Value = serde_json::from_slice(&manifest_bytes).expect("parse manifest");
        assert_eq!(manifest["appVersion"], "0.0.0-test");
        assert_eq!(manifest["sessionId"], "session-9");

        let files = manifest["files"].as_array().expect("files array");
        let status_of = |name: &str| {
            files
                .iter()
                .find(|entry| entry["name"] == name)
                .map(|entry| entry["status"].as_str().expect("status string"))
                .expect("file entry present")
        };
        assert_eq!(status_of("glimpse-frontend.jsonl"), "included");
        assert_eq!(status_of("glimpse.log"), "truncated");
        assert_eq!(status_of("glimpse-sidecar.out.log"), "missing");

        fs::remove_dir_all(dir).expect("cleanup");
    }

    #[test]
    fn export_redacts_all_text_sources_and_excludes_private_files() {
        let dir = temp_logs_dir("redaction");
        fs::create_dir_all(&dir).unwrap();
        let secret = "https://alice:pass-secret@host/v1?token=query-secret&model=demo Bearer bearer-secret api_key=key-secret";
        for name in [
            "glimpse.log",
            "glimpse.log.1",
            "glimpse.log.2",
            "glimpse.log.3",
            "glimpse-sidecar.out.log",
        ] {
            fs::write(dir.join(name), secret).unwrap();
        }
        for name in ["settings.json", ".env", "image.png", "memory.db"] {
            fs::write(dir.join(name), "private").unwrap();
        }
        let mut value = event(secret);
        value["data"] = json!({"api_key": "nested-secret", "ok": 42});
        for name in [
            FRONTEND_LOG_FILE,
            "glimpse-frontend.jsonl.1",
            "glimpse-frontend.jsonl.2",
            "glimpse-frontend.jsonl.3",
        ] {
            fs::write(
                dir.join(name),
                format!("invalid token=invalid-secret\n{value}\n"),
            )
            .unwrap();
        }
        let path = build_export_bundle(&dir, Some("host-session"), "test").unwrap();
        let mut archive = zip::ZipArchive::new(File::open(path).unwrap()).unwrap();
        assert_eq!(archive.len(), 10);
        for index in 0..archive.len() {
            let mut entry = archive.by_index(index).unwrap();
            let mut text = String::new();
            entry.read_to_string(&mut text).unwrap();
            for secret in [
                "alice",
                "pass-secret",
                "query-secret",
                "bearer-secret",
                "key-secret",
                "nested-secret",
            ] {
                assert!(!text.contains(secret), "{} leaked {secret}", entry.name());
            }
            if entry.name().starts_with(FRONTEND_LOG_FILE) {
                let parsed: Value = serde_json::from_str(text.trim()).unwrap();
                assert_eq!(parsed["data"]["ok"], 42);
                assert_eq!(parsed["sessionId"], "session-1");
            }
            if entry.name() != "manifest.json" {
                assert!(text.contains("host/v1"));
                assert!(text.contains("model=demo"));
            }
        }
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn truncated_jsonl_export_remains_valid_and_keeps_historical_session() {
        let dir = temp_logs_dir("truncated-jsonl");
        fs::create_dir_all(&dir).unwrap();
        let value = event("token=historical-secret");
        let text = format!("{}\n{value}\n", "x".repeat(EXPORT_TAIL_CAP_BYTES as usize));
        fs::write(dir.join(FRONTEND_LOG_FILE), text).unwrap();
        let path = build_export_bundle(&dir, Some("new-session"), "test").unwrap();
        let mut zip = zip::ZipArchive::new(File::open(path).unwrap()).unwrap();
        let mut text = String::new();
        zip.by_name(FRONTEND_LOG_FILE)
            .unwrap()
            .read_to_string(&mut text)
            .unwrap();
        let value: Value = serde_json::from_str(text.trim()).unwrap();
        assert_eq!(value["sessionId"], "session-1");
        assert!(!text.contains("historical-secret"));
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn host_session_overrides_missing_empty_and_spoofed_frontend_sessions() {
        let dir = temp_logs_dir("host-session");
        let mut missing = event("early startup");
        missing.as_object_mut().unwrap().remove("sessionId");
        let mut empty = event("empty session");
        empty["sessionId"] = json!("");
        append_events_to(
            &dir,
            &[missing, empty, event("spoofed")],
            &WriteLimits::default(),
            "host-session",
        )
        .unwrap();
        let text = fs::read_to_string(dir.join(FRONTEND_LOG_FILE)).unwrap();
        for line in text.lines() {
            let value: Value = serde_json::from_str(line).unwrap();
            assert_eq!(value["sessionId"], "host-session");
        }
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn consecutive_exports_are_distinct_complete_and_do_not_overwrite() {
        let dir = temp_logs_dir("unique-exports");
        fs::create_dir_all(&dir).unwrap();
        fs::write(dir.join(BACKEND_LOG_FILE), "first snapshot").unwrap();
        let first = build_export_bundle(&dir, Some("session"), "test").unwrap();
        let first_bytes = fs::read(&first).unwrap();
        fs::write(dir.join(BACKEND_LOG_FILE), "second snapshot").unwrap();
        let second = build_export_bundle(&dir, Some("session"), "test").unwrap();
        assert_ne!(first, second);
        assert_eq!(fs::read(&first).unwrap(), first_bytes);
        for (path, expected) in [(&first, "first snapshot"), (&second, "second snapshot")] {
            let mut zip = zip::ZipArchive::new(File::open(path).unwrap()).unwrap();
            let mut text = String::new();
            zip.by_name(BACKEND_LOG_FILE)
                .unwrap()
                .read_to_string(&mut text)
                .unwrap();
            assert_eq!(text, expected);
            assert!(zip.by_name("manifest.json").is_ok());
        }
        assert_eq!(fs::read_dir(dir.join("exports")).unwrap().count(), 2);
        fs::remove_dir_all(dir).unwrap();
    }

    #[test]
    fn civil_from_days_matches_known_dates() {
        assert_eq!(civil_from_days(0), (1970, 1, 1));
        assert_eq!(civil_from_days(20_453), (2025, 12, 31));
        assert_eq!(civil_from_days(20_454), (2026, 1, 1));
        let (stamp, iso) = format_stamp(1_767_225_600);
        assert_eq!(stamp, "20260101-000000");
        assert_eq!(iso, "2026-01-01T00:00:00Z");
    }
}
