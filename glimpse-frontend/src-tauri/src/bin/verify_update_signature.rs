#[path = "../updater_signature.rs"]
mod updater_signature;

use std::env;
use std::fs;
use std::process::ExitCode;

fn main() -> ExitCode {
    let args: Vec<String> = env::args().collect();
    if args.len() != 4 {
        eprintln!("usage: verify_update_signature <installer> <signature-file> <version>");
        return ExitCode::FAILURE;
    }

    let installer = match fs::read(&args[1]) {
        Ok(installer) => installer,
        Err(error) => {
            eprintln!("failed to read installer {}: {error}", args[1]);
            return ExitCode::FAILURE;
        }
    };
    let signature = match fs::read_to_string(&args[2]) {
        Ok(signature) => signature.trim().to_owned(),
        Err(error) => {
            eprintln!("failed to read signature {}: {error}", args[2]);
            return ExitCode::FAILURE;
        }
    };
    let file_name = args[1]
        .rsplit(['\\', '/'])
        .next()
        .unwrap_or(&args[1])
        .to_owned();

    if let Err(error) =
        updater_signature::verify_update_signature(&installer, &signature, &args[3], &file_name)
    {
        eprintln!("update signature verification failed: {error}");
        return ExitCode::FAILURE;
    }

    println!("update signature verified for {} {}", args[3], file_name);
    ExitCode::SUCCESS
}
