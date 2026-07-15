@echo off
setlocal

start "cross-border-api" cmd /k "cd /d %~dp0services\catalog-service && run-local.cmd"
start "cross-border-web-next" cmd /k "cd /d %~dp0apps\web-next && run-local.cmd"

