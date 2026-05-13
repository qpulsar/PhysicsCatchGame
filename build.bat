@echo off
echo Proje derleniyor (Python 3.12)...

if not exist venv312 (
    echo Hata: venv312 klasoru bulunamadi.
    echo Lutfen 'py -3.12 -m venv venv312' ile ortam olusturup paketleri yukleyin.
    pause
    exit /b
)

rmdir /s /q dist build
call .\venv312\Scripts\activate
pyinstaller --noconfirm installer.spec
echo.
echo Dosyalar kopyalaniyor (assets ve game_data.db)...
xcopy /E /I /Y "assets" "dist\assets"
copy /Y "game_data.db" "dist\game_data.db"
echo.
echo Derleme tamamlandi! 
echo 'dist' klasoru icindeki 'PhysicsCatchGame.exe' dosyasini,
echo yanindaki 'assets' ve 'game_data.db' dosyalariyla birlikte dagitabilirsiniz.
pause
