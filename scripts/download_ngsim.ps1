param([string]$OutputDirectory="data/public/ngsim")
$ErrorActionPreference="Stop"
$trafficFolder=[IO.Path]::GetFullPath($OutputDirectory)
New-Item -ItemType Directory -Path $trafficFolder -Force | Out-Null
$trafficQuery="location='lankershim' and vehicle_id>=100 and vehicle_id<=160 and global_time<1118936580200"
$trafficUrl='https://data.transportation.gov/resource/8ect-6jqj.json?%24where='+[uri]::EscapeDataString($trafficQuery)+'&%24order=vehicle_id%2Cglobal_time&%24limit=50000'
$trafficRequest=@{url=$trafficUrl;where=$trafficQuery;limit=50000;order="vehicle_id,global_time";source="FHWA NGSIM via US DOT";license="CC BY-SA 3.0";license_url="https://creativecommons.org/licenses/by-sa/3.0/";retrieved_utc=[DateTime]::UtcNow.ToString("o")}
$trafficRequest | ConvertTo-Json | Set-Content -LiteralPath (Join-Path $trafficFolder "request.json") -Encoding utf8
Invoke-WebRequest -Uri $trafficUrl -OutFile (Join-Path $trafficFolder "lankershim_raw.json") -TimeoutSec 60
$trafficRows=Get-Content -LiteralPath (Join-Path $trafficFolder "lankershim_raw.json") -Raw | ConvertFrom-Json
if($trafficRows.Count -eq 50000){throw "Result reaches API limit; subset may be truncated. Paginate before analysis."}
Write-Output ("Downloaded "+$trafficRows.Count+" rows; capped selection, not full NGSIM dataset.")

