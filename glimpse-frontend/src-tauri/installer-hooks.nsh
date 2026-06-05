!macro NSIS_HOOK_PREINSTALL
  DetailPrint "Closing running Glimpse processes before installing..."
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM Glimpse.exe'
  nsExec::ExecToLog '"$SYSDIR\taskkill.exe" /F /T /IM python-backend.exe'
  Sleep 1000
!macroend
