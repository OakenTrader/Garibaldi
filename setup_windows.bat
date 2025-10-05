@echo off
setlocal

REM Check if venv already exists
if exist "venv\" (
    echo Virtual environment already exists in this folder.
    goto end
)

REM Ask for confirmation in a loop
:ask_confirm
set /p userinput=Do you want to create a new virtual environment and install packages? Type y to confirm, n to abort: 
if /i "%userinput%"=="y" (
    goto continue_setup
) else if /i "%userinput%"=="n" (
    echo Aborted by user.
    goto end
) else (
    echo Please type y or n.
    goto ask_confirm
)
:continue_setup
REM Create virtual environment
python -m venv venv
if errorlevel 1 (
    echo Failed to create virtual environment.
    goto end
)

REM Activate the virtual environment
call venv\Scripts\activate.bat

REM Install packages from requirements.txt
if exist requirements.txt (
    pip install -r requirements.txt
) else (
    echo requirements.txt not found. No packages installed.
)

echo.
echo Virtual environment setup complete.
:end
endlocal
pause
