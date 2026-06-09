@echo off
echo Starting Watermark...
C:\eve-firmainvisible\dist\Watermark.exe > "C:\eve-firmainvisible\build\exe_out.txt" 2>&1
echo EXIT CODE: %ERRORLEVEL%
type "C:\eve-firmainvisible\build\exe_out.txt"
pause
