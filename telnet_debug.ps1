# PowerShell script to interrogate LogSplitter Monitor via Telnet
# Usage: .\telnet_debug.ps1 -MonitorIP "192.168.1.101"

param(
    [Parameter(Mandatory=$false)]
    [string]$MonitorIP = "192.168.1.101",
    [Parameter(Mandatory=$false)]
    [int]$Port = 23
)

function Send-TelnetCommand {
    param(
        [System.Net.Sockets.TcpClient]$client,
        [System.IO.StreamWriter]$writer,
        [System.IO.StreamReader]$reader,
        [string]$command,
        [int]$timeoutMs = 3000
    )
    
    Write-Host ">> $command" -ForegroundColor Yellow
    $writer.WriteLine($command)
    $writer.Flush()
    
    Start-Sleep -Milliseconds 500  # Give command time to execute
    
    # Read response with timeout
    $response = @()
    $timeout = (Get-Date).AddMilliseconds($timeoutMs)
    
    while ((Get-Date) -lt $timeout) {
        if ($reader.Peek() -ge 0) {
            $line = $reader.ReadLine()
            if ($line -match "^>" -and $response.Count -gt 0) {
                # Found next prompt, stop reading
                break
            }
            $response += $line
        }
        Start-Sleep -Milliseconds 50
    }
    
    foreach ($line in $response) {
        if ($line.Trim() -ne "") {
            Write-Host "   $line" -ForegroundColor Green
        }
    }
    Write-Host ""
    
    return $response
}

try {
    Write-Host "=== LogSplitter Monitor Telnet Debug ===" -ForegroundColor Cyan
    Write-Host "Connecting to $MonitorIP`:$Port..." -ForegroundColor White
    
    # Create TCP connection
    $client = New-Object System.Net.Sockets.TcpClient
    $client.Connect($MonitorIP, $Port)
    
    # Create stream objects
    $stream = $client.GetStream()
    $writer = New-Object System.IO.StreamWriter($stream)
    $reader = New-Object System.IO.StreamReader($stream)
    $writer.AutoFlush = $true
    
    Write-Host "Connected successfully!" -ForegroundColor Green
    Write-Host ""
    
    # Wait for initial prompt
    Start-Sleep -Seconds 2
    while ($reader.Peek() -ge 0) {
        $line = $reader.ReadLine()
        Write-Host "   $line" -ForegroundColor Gray
    }
    
    Write-Host "=== SYSTEM STATUS CHECK ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "status"
    
    Write-Host "=== NETWORK STATUS ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "network"
    
    Write-Host "=== SENSOR READINGS ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "show"
    
    Write-Host "=== WEIGHT SENSOR STATUS ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "weight status"
    
    Write-Host "=== TEMPERATURE SENSOR STATUS ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "temp status"
    
    Write-Host "=== MQTT PUBLISHING TEST ===" -ForegroundColor Cyan
    Write-Host "Checking individual sensor reads..." -ForegroundColor White
    
    Send-TelnetCommand $client $writer $reader "weight read"
    Send-TelnetCommand $client $writer $reader "temp read"
    
    Write-Host "=== DEBUG MODE CHECK ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "set debug on"
    
    Write-Host "=== FORCE SENSOR READINGS ===" -ForegroundColor Cyan
    Write-Host "Reading sensors with debug enabled..." -ForegroundColor White
    
    Send-TelnetCommand $client $writer $reader "test sensors" 10000  # Longer timeout for sensor test
    
    Write-Host "=== MQTT STATUS ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "show mqtt"
    
    Write-Host "=== LOG LEVEL CHECK ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "loglevel"
    
    Write-Host "=== I2C BUS SCAN ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "test i2c" 5000  # Longer timeout for I2C scan
    
    Write-Host "=== SENSOR INITIALIZATION STATUS ===" -ForegroundColor Cyan
    Send-TelnetCommand $client $writer $reader "help"  # This should show available commands and sensor status
    
} catch {
    Write-Host "Error: $_" -ForegroundColor Red
    Write-Host "Make sure the monitor is connected and accessible at $MonitorIP`:$Port" -ForegroundColor Yellow
} finally {
    # Clean up connections
    if ($reader) { $reader.Close() }
    if ($writer) { $writer.Close() }
    if ($client) { $client.Close() }
    
    Write-Host ""
    Write-Host "=== Connection closed ===" -ForegroundColor Gray
}

Write-Host ""
Write-Host "=== TROUBLESHOOTING SUMMARY ===" -ForegroundColor Yellow
Write-Host "If only fuel values are appearing in MQTT:" -ForegroundColor White
Write-Host "1. Check if temperature sensor is initialized (temp status)" -ForegroundColor White
Write-Host "2. Verify MQTT connection is stable (network)" -ForegroundColor White
Write-Host "3. Look for sensor reading failures in debug output" -ForegroundColor White
Write-Host "4. Check if I2C multiplexer is working (test i2c)" -ForegroundColor White
Write-Host "5. Verify sensor polling intervals are working (show)" -ForegroundColor White