$Origen  = 'E:\'
$Destino = '.'

Get-ChildItem $Origen -Recurse -Filter *.ts | ForEach-Object {
    Write-Host $_.FullName
    $dest = Join-Path $Destino $_.Name
    if (-not (Test-Path $dest)) {
        Copy-Item $_.FullName $dest
    }
}
