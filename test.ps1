@'
Write-Host "`n=== Python (pytest) ===" -ForegroundColor Cyan
docker compose exec agents pytest -v
$pytestExit = $LASTEXITCODE

Write-Host "`n=== Node (jest) ===" -ForegroundColor Cyan
docker compose exec backend npm test
$jestExit = $LASTEXITCODE

if ($pytestExit -eq 0 -and $jestExit -eq 0) {
    Write-Host "`nAll test suites passed." -ForegroundColor Green
} else {
    Write-Host "`nSome tests failed (pytest=$pytestExit, jest=$jestExit)." -ForegroundColor Red
}
'@ | Out-File -FilePath C:\AgentOps\test.ps1 -Encoding ascii