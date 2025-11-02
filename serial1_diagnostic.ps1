# LogSplitter Monitor Serial1 Bridge Diagnostic Script
# Verifies Serial1 bridge functionality and readiness for controller telemetry

param(
    [Parameter(Mandatory=$false)]
    [string]$MonitorIP,
    [int]$Port = 23
)

if (-not $MonitorIP) {
    Write-Host "Usage: .\serial1_diagnostic.ps1 -MonitorIP <ip_address>" -ForegroundColor Red
    Write-Host "Example: .\serial1_diagnostic.ps1 -MonitorIP 192.168.1.155" -ForegroundColor Yellow
    exit 1
}

Write-Host "LogSplitter Monitor Serial1 Bridge Diagnostic" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green
Write-Host "Monitor IP: $MonitorIP" -ForegroundColor Cyan
Write-Host "Telnet Port: $Port" -ForegroundColor Cyan
Write-Host ""

# Function to send telnet command and get response
function Test-TelnetCommand {
    param(
        [string]$Command,
        [string]$IP,
        [int]$Port,
        [int]$TimeoutMs = 5000
    )
    
    try {
        $tcpClient = New-Object System.Net.Sockets.TcpClient
        $tcpClient.ReceiveTimeout = $TimeoutMs
        $tcpClient.SendTimeout = $TimeoutMs
        
        $tcpClient.Connect($IP, $Port)
        $stream = $tcpClient.GetStream()
        $writer = New-Object System.IO.StreamWriter($stream)
        $reader = New-Object System.IO.StreamReader($stream)
        
        # Send command
        $writer.WriteLine($Command)
        $writer.Flush()
        
        # Read response
        Start-Sleep -Milliseconds 1000
        $response = ""
        while ($stream.DataAvailable) {
            $response += $reader.ReadLine() + "`n"
        }
        
        $tcpClient.Close()
        return $response.Trim()
    }
    catch {
        if ($tcpClient) { $tcpClient.Close() }
        return $null
    }
}

# Test Monitor Connectivity
Write-Host "1. Testing Monitor Connectivity..." -ForegroundColor Yellow
$response = Test-TelnetCommand -Command "status" -IP $MonitorIP -Port $Port
if ($response) {
    Write-Host "   ✅ Monitor is responding" -ForegroundColor Green
} else {
    Write-Host "   ❌ Cannot connect to monitor at $MonitorIP:$Port" -ForegroundColor Red
    exit 1
}

# Test Serial1 Bridge Status
Write-Host "`n2. Testing Serial1 Bridge Status..." -ForegroundColor Yellow
$bridgeStatus = Test-TelnetCommand -Command "bridge status" -IP $MonitorIP -Port $Port
if ($bridgeStatus) {
    Write-Host "   Bridge Status:" -ForegroundColor White
    Write-Host "   $bridgeStatus" -ForegroundColor Gray
    
    # Parse bridge status
    if ($bridgeStatus -match "connected") {
        Write-Host "   ✅ Serial1 bridge is connected" -ForegroundColor Green
    } else {
        Write-Host "   ⚠️  Serial1 bridge shows disconnected (normal if no controller connected)" -ForegroundColor Yellow
    }
} else {
    Write-Host "   ❌ Bridge command failed" -ForegroundColor Red
}

# Test Bridge Statistics
Write-Host "`n3. Testing Bridge Statistics..." -ForegroundColor Yellow
$bridgeStats = Test-TelnetCommand -Command "bridge stats" -IP $MonitorIP -Port $Port
if ($bridgeStats) {
    Write-Host "   Bridge Statistics:" -ForegroundColor White
    Write-Host "   $bridgeStats" -ForegroundColor Gray
} else {
    Write-Host "   ❌ Bridge statistics command failed" -ForegroundColor Red
}

# Test System Status  
Write-Host "`n4. Testing System Status..." -ForegroundColor Yellow
$systemStatus = Test-TelnetCommand -Command "show" -IP $MonitorIP -Port $Port
if ($systemStatus) {
    Write-Host "   ✅ System status retrieved" -ForegroundColor Green
    # Don't print full status to keep output clean
} else {
    Write-Host "   ❌ System status command failed" -ForegroundColor Red
}

# Test Network Status
Write-Host "`n5. Testing Network Status..." -ForegroundColor Yellow
$networkStatus = Test-TelnetCommand -Command "network" -IP $MonitorIP -Port $Port
if ($networkStatus) {
    Write-Host "   Network Status:" -ForegroundColor White
    Write-Host "   $networkStatus" -ForegroundColor Gray
    
    if ($networkStatus -match "wifi.*connected|wifi.*OK") {
        Write-Host "   ✅ WiFi is connected" -ForegroundColor Green
    }
    if ($networkStatus -match "mqtt.*connected|mqtt.*OK") {
        Write-Host "   ✅ MQTT is connected" -ForegroundColor Green
    }
} else {
    Write-Host "   ❌ Network status command failed" -ForegroundColor Red
}

Write-Host "`n=============================================" -ForegroundColor Green
Write-Host "Serial1 Bridge Diagnostic Complete" -ForegroundColor Green
Write-Host "=============================================" -ForegroundColor Green

Write-Host "`n📋 Ready for Controller Connection:" -ForegroundColor Cyan
Write-Host "   • Connect Controller Serial1 TX to Monitor Serial1 RX" -ForegroundColor White
Write-Host "   • Expected message format: timestamp|LEVEL|content" -ForegroundColor White
Write-Host "   • Monitor bridge status with: bridge stats" -ForegroundColor White
Write-Host "   • Check MQTT topics: r4/controller/*" -ForegroundColor White

Write-Host "`n🔍 Monitoring Commands:" -ForegroundColor Cyan
Write-Host "   telnet $MonitorIP 23" -ForegroundColor White
Write-Host "   > bridge status    # Check connection and message counts" -ForegroundColor Gray
Write-Host "   > bridge stats     # Detailed statistics" -ForegroundColor Gray
Write-Host "   > show            # System sensor readings" -ForegroundColor Gray
Write-Host "   > network         # Network connectivity" -ForegroundColor Gray