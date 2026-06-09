@echo off
C:\eve-firmainvisible\dist\Watermark.exe 2>&1 > "C:\eve-firmainvisible\build\exe_output.txt"
echo EXIT CODE: %ERRORLEVEL% >> "C:\eve-firmainvisible\build\exe_output.txt"
type "C:\eve-firmainvisible\build\exe_output.txt"
pause
