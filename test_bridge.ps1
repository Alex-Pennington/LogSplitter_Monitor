# LogSplitter Monitor Bridge Testing Script
# Tests Serial1 bridge functionality via Telnet

param(
    [Parameter(Mandatory=$true)]
    [string]$MonitorIP,
    [int]$Port = 23
)

Write-Host "Testing LogSplitter Monitor Bridge at $MonitorIP:$Port" -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green

# Function to send telnet command and get response
function Send-TelnetCommand {
    param(
        [string]$Command,
        [string]$IP,
        [int]$Port,
        [int]$TimeoutMs = 3000
    )
    
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.ReceiveTimeout = $TimeoutMs
        $tcpClient.SendTimeout = $TimeoutMs
        
        Write-Host "Connecting to $IP:$Port..." -ForegroundColor Yellow
        $tcpClient.Connect($IP, $Port)
        
        $stream = $tcpClient.GetStream()
        $writer = New-Object System.IO.StreamWriter($stream)
        $reader = New-Object System.IO.StreamReader($stream)
        
        # Send command
        Write-Host "Sending: $Command" -ForegroundColor Cyan
        $writer.WriteLine($Command)
        $writer.Flush()
        
        # Read response (give time for processing)
        Start-Sleep -Milliseconds 500
        $response = ""
        while ($stream.DataAvailable) {
            $response += $reader.ReadLine() + "`n"
        }
        
        Write-Host "Response:" -ForegroundColor White
        Write-Host $response -ForegroundColor Gray
        
        $tcpClient.Close()
        return $response
    }
    catch {
        Write-Host "Error: $_" -ForegroundColor Red
        if ($tcpClient) { $tcpClient.Close() }
        return $null
    }
}

# Test Bridge Commands
Write-Host "`nTesting Bridge Commands:" -ForegroundColor Green
Write-Host "========================" -ForegroundColor Green

$commands = @(
    "help",
    "bridge",
    "bridge status", 
    "bridge stats",
    "bridge telemetry",
    "bridge telemetry on",
    "bridge stats",
    "show",
    "status"
)

foreach ($cmd in $commands) {
    Write-Host "`n--- Testing: $cmd ---" -ForegroundColor Yellow
    $result = Send-TelnetCommand -Command $cmd -IP $MonitorIP -Port $Port
    Start-Sleep -Milliseconds 1000  # Delay between commands
}

Write-Host "`n==============================================================" -ForegroundColor Green
Write-Host "Bridge testing complete. Check above output for results." -ForegroundColor Green
Write-Host "Expected: Bridge status shows connection state and statistics" -ForegroundColor Green
Write-Host "==============================================================" -ForegroundColor Green