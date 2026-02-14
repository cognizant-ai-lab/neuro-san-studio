@echo off
rem Copyright (c) 2025-2026 Cognizant Technology Solutions Corp, www.cognizant.com.
rem
rem Licensed under the Apache License, Version 2.0 (the "License");
rem you may not use this file except in compliance with the License.
rem You may obtain a copy of the License at
rem
rem     http://www.apache.org/licenses/LICENSE-2.0
rem
rem Unless required by applicable law or agreed to in writing, software
rem distributed under the License is distributed on an "AS IS" BASIS,
rem WITHOUT WARRANTIES OR CONDITIONS OF ANY KIND, either express or implied.
rem See the License for the specific language governing permissions and
rem limitations under the License.
rem
rem END COPYRIGHT

rem Startup script for the Neuro SAN server on Windows.
rem Usage: start_server.bat [additional run.py arguments]

set SCRIPT_DIR=%~dp0

if not exist "%SCRIPT_DIR%venv\Scripts\activate.bat" (
    echo Virtual environment not found. Please run 'make install' first.
    exit /b 1
)

call "%SCRIPT_DIR%venv\Scripts\activate.bat"
set PYTHONPATH=%SCRIPT_DIR%

python -m run --server-only %*
