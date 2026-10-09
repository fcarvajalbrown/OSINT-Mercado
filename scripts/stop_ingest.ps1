$patterns = @('osint_mercado.ingest', 'ingest_range.sh')
$targets = Get-CimInstance Win32_Process | Where-Object {
    $_.Name -in @('python.exe', 'bash.exe') -and $_.ProcessId -ne $PID -and $(
        $line = $_.CommandLine
        ($patterns | Where-Object { $line -and $line.Contains($_) }).Count -gt 0
    )
}
foreach ($t in $targets) {
    Stop-Process -Id $t.ProcessId -Force -ErrorAction SilentlyContinue
    Write-Output ("stopped {0} {1}" -f $t.ProcessId, $t.Name)
}
$left = Get-CimInstance Win32_Process -Filter "Name='python.exe'" | Where-Object { $_.CommandLine -and $_.CommandLine.Contains($patterns[0]) }
Write-Output ("ingest processes left: {0}" -f @($left).Count)
