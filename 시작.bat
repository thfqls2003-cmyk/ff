@echo off
chcp 65001 >nul
cd /d "%~dp0"
echo ========================================
echo   [1/2] 깃허브에서 최신 코드 받는 중...
echo ========================================
git pull origin claude/admiring-goldberg-ti6ypc
echo.
echo ========================================
echo   [2/2] Rojo 동기화 서버 시작!
echo   이제 Roblox Studio에서:
echo   플러그인 탭 - Rojo - Connect 클릭
echo ========================================
echo   (이 창은 켜 두세요. 끝낼 땐 창을 닫으면 됩니다)
echo.
rojo serve
pause
