use base64::Engine;
use semver::Version;
use std::str::FromStr;

/// 与 tauri.conf.json > plugins > updater > pubkey 保持一致；修改公钥时必须同步。
pub const UPDATER_PUBKEY: &str = "dW50cnVzdGVkIGNvbW1lbnQ6IG1pbmlzaWduIHB1YmxpYyBrZXk6IEU0RUVCMzE2RTdGQTg5QzQKUldURWlmcm5GclB1NUNKVU91SXZHTndtc1M1VlNTaTNXcTZMUHpobG5WUTRyNWNlSVAzRk1pSXcK";

fn base64_to_string(base64_string: &str) -> Result<String, String> {
    let decoded = base64::engine::general_purpose::STANDARD
        .decode(base64_string)
        .map_err(|error| error.to_string())?;
    String::from_utf8(decoded).map_err(|error| error.to_string())
}

fn trusted_comment_field<'a>(trusted_comment: &'a str, key: &str) -> Option<&'a str> {
    trusted_comment
        .split('\t')
        .find_map(|field| field.strip_prefix(key))
}

fn versions_equivalent(left: &str, right: &str) -> bool {
    match (Version::from_str(left), Version::from_str(right)) {
        (Ok(left), Ok(right)) => left == right,
        _ => left == right,
    }
}

pub fn installer_version_from_file_name(file_name: &str) -> Option<&str> {
    let without_prefix = file_name.strip_prefix("Glimpse_")?;
    without_prefix.strip_suffix("_x64-setup.exe")
}

pub fn verify_update_signature(
    data: &[u8],
    release_signature: &str,
    announced_version: &str,
    expected_file_name: &str,
) -> Result<(), String> {
    let pub_key_decoded = base64_to_string(UPDATER_PUBKEY)?;
    let public_key =
        minisign_verify::PublicKey::decode(&pub_key_decoded).map_err(|error| error.to_string())?;
    let signature_base64_decoded = base64_to_string(release_signature)?;
    let signature = minisign_verify::Signature::decode(&signature_base64_decoded)
        .map_err(|error| error.to_string())?;

    public_key
        .verify(data, &signature, true)
        .map_err(|error| error.to_string())?;

    let trusted_comment = signature.trusted_comment();
    let signed_file = trusted_comment_field(trusted_comment, "file:").ok_or_else(|| {
        format!(
            "updater signature trusted comment is missing file name: {}",
            trusted_comment
        )
    })?;
    if signed_file != expected_file_name {
        return Err(format!(
            "signed file mismatch: signed={}, expected={}",
            signed_file, expected_file_name
        ));
    }

    let file_version = installer_version_from_file_name(expected_file_name).ok_or_else(|| {
        format!(
            "cannot derive updater version from installer file name: {}",
            expected_file_name
        )
    })?;
    if !versions_equivalent(file_version, announced_version.trim_start_matches('v')) {
        return Err(format!(
            "installer version mismatch: file={}, announced={}",
            file_version, announced_version
        ));
    }

    Ok(())
}

#[cfg(test)]
mod tests {
    use super::*;

    #[test]
    fn derives_version_from_the_windows_installer_name() {
        assert_eq!(
            installer_version_from_file_name("Glimpse_0.5.0-beta.5_x64-setup.exe"),
            Some("0.5.0-beta.5")
        );
        assert_eq!(
            installer_version_from_file_name("Glimpse_0.5.0_x64-setup.exe"),
            Some("0.5.0")
        );
        assert_eq!(installer_version_from_file_name("other-setup.exe"), None);
    }

    #[test]
    fn treats_equivalent_versions_the_same() {
        assert!(versions_equivalent("0.5.0", "0.5.0"));
        assert!(versions_equivalent("v0.5.0-beta.1", "v0.5.0-beta.1"));
        assert!(!versions_equivalent("0.5.0", "0.5.1"));
    }

    #[test]
    fn reads_tab_separated_trusted_comment_fields() {
        let comment = "timestamp:123\tfile:Glimpse_0.5.0_x64-setup.exe";
        assert_eq!(
            trusted_comment_field(comment, "file:"),
            Some("Glimpse_0.5.0_x64-setup.exe")
        );
        assert_eq!(trusted_comment_field(comment, "version:"), None);
    }
}
