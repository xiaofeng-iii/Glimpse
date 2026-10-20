; Pre-install hook: close running Glimpse processes, then safely clear the
; bundled backend directory.
;
; Lesson from the v0.5.0-beta.2 update incident: the old hook slept a fixed
; 1000ms and then blindly RMDir'd the backend. The backend process is a GB
; sized PyInstaller runtime with torch DLLs mapped; releasing its handles can
; take longer than that, and antivirus/indexer handles are outside our
; control. A delete or copy interrupted halfway leaves a backend directory
; with missing DLLs, and the app can never start again. The hook now:
; 1) polls until GlimpseRuntime.exe is really gone (taskkill returns non-zero
;    when the process no longer exists; 500ms interval, 15s cap), plus one
;    extra 500ms settle delay for handle release;
; 2) verifies binaries\GlimpseRuntime is actually empty after RMDir (retries
;    up to 5 times, 1s apart);
; 3) aborts the installation with an explicit message if remnants remain,
;    because overwriting a half-deleted backend would ship a broken install.
!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Closing running Glimpse processes before installing..."
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM Glimpse.exe'
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM GlimpseRuntime.exe'
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM glimpse-backend.exe'
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM python-backend.exe'

  StrCpy $R1 0
glimpse_wait_backend_exit:
  nsExec::ExecToStack '"$SYSDIR\taskkill.exe" /F /T /IM GlimpseRuntime.exe'
  Pop $R0
  Pop $R9
  StrCmp $R0 "0" 0 glimpse_backend_exited
  IntOp $R1 $R1 + 1
  IntCmp $R1 30 glimpse_backend_exited 0 glimpse_backend_exited
  Sleep 500
  Goto glimpse_wait_backend_exit
glimpse_backend_exited:
  Sleep 500

  RMDir /r "$INSTDIR\binaries\GlimpseRuntime"
  RMDir /r "$INSTDIR\binaries\glimpse-backend"
  RMDir /r "$INSTDIR\binaries\python-backend"

  StrCpy $R1 0
glimpse_verify_backend_removed:
  IfFileExists "$INSTDIR\binaries\GlimpseRuntime\*.*" 0 glimpse_backend_removed
  IntOp $R1 $R1 + 1
  IntCmp $R1 5 glimpse_backend_locked 0 glimpse_backend_locked
  Sleep 1000
  RMDir /r "$INSTDIR\binaries\GlimpseRuntime"
  Goto glimpse_verify_backend_removed
glimpse_backend_locked:
  Abort "Cannot replace Glimpse backend files because they are locked by another process (antivirus?). Close Glimpse and retry the installation, or reboot and run the installer again."
glimpse_backend_removed:
!macroend
