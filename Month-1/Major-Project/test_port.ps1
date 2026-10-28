$listener = [System.Net.Sockets.TcpListener]::new([System.Net.IPAddress]::Loopback, 15001)
$listener.Start()
Write-Host "Listening on 15001"
Start-Sleep 10