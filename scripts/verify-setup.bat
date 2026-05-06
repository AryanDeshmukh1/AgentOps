@echo off
REM ============================================================
REM  AgentOps - Setup Verification Script (Windows)
REM ============================================================
REM  Run this from C:\AgentOps to verify your setup is correct.
REM ============================================================

echo.
echo ================================================
echo   AgentOps Setup Verification
echo ================================================
echo.

REM Check Node
echo [1/6] Checking Node.js...
where node >nul 2>nul
if errorlevel 1 (
    echo   FAIL: Node.js not found
    goto :fail
) else (
    node --version
)

REM Check Python
echo [2/6] Checking Python...
where python >nul 2>nul
if errorlevel 1 (
    echo   FAIL: Python not found
    goto :fail
) else (
    python --version
)

REM Check Docker
echo [3/6] Checking Docker...
where docker >nul 2>nul
if errorlevel 1 (
    echo   FAIL: Docker not found
    goto :fail
) else (
    docker --version
)

REM Check AWS CLI
echo [4/6] Checking AWS CLI...
where aws >nul 2>nul
if errorlevel 1 (
    echo   FAIL: AWS CLI not found
    goto :fail
) else (
    aws --version
)

REM Check Git
echo [5/6] Checking Git...
where git >nul 2>nul
if errorlevel 1 (
    echo   FAIL: Git not found
    goto :fail
) else (
    git --version
)

REM Check .env file
echo [6/6] Checking .env file...
if not exist ".env" (
    echo   WARNING: .env file not found. Copy .env.example to .env and fill in values.
) else (
    echo   .env file exists
)

echo.
echo ================================================
echo   ALL CHECKS PASSED
echo ================================================
echo.
echo Next steps:
echo   1. Copy .env.example to .env and fill in your values
echo   2. Run: docker compose up
echo   3. Open http://localhost:3000
echo.
goto :end

:fail
echo.
echo Setup verification FAILED. Install missing tools and try again.
exit /b 1

:end
