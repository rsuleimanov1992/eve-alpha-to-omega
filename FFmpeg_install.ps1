# Install FFmpeg via winget (Gyan.FFmpeg, full build)

# Проверка наличия winget
if (-not (Get-Command winget -ErrorAction SilentlyContinue)) {
    Write-Host "winget не найден. Установите Windows Package Manager или используйте вариант B." -ForegroundColor Yellow
    exit 1
}

# Установка FFmpeg
winget install -e --id Gyan.FFmpeg --accept-package-agreements --accept-source-agreements

# Обновить PATH в текущей сессии (если установщик прописал системный PATH, может потребоваться новый сеанс)
# Проверка доступности ffmpeg
if (Get-Command ffmpeg -ErrorAction SilentlyContinue) {
    Write-Host "FFmpeg установлен и доступен: $(ffmpeg -version | Select-Object -First 1)"
} else {
    Write-Host "FFmpeg установлен, но не найден в PATH текущей сессии. Откройте новое окно PowerShell и проверьте командой: ffmpeg -version" -ForegroundColor Yellow
}
