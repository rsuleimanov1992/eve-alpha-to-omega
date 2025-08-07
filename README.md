## Полная инструкция по установке и запуску eve-memory-reader

Эта инструкция охватывает все шаги, начиная с клонирования репозитория и заканчивая запуском приложения, включая все известные нам исправления.

**Предварительные требования:**

1.  **Git:** Убедитесь, что у вас установлен Git ([https://git-scm.com/downloads](https://git-scm.com/downloads)).
2.  **Visual Studio:** Установите Visual Studio (Community Edition достаточно) с рабочей нагрузкой **"Разработка классических приложений на C++"**. Это необходимо для сборки C-библиотеки. ([https://visualstudio.microsoft.com/downloads/](https://visualstudio.microsoft.com/downloads/))
3.  **Python 3.11:** Мы будем использовать именно эту версию, так как с ней удалось решить проблемы зависимостей.

**Шаг 1: Установка Python 3.11**

1.  Скачайте установщик Windows (64-bit) для последней версии Python 3.11 (например, 3.11.9) с официального сайта: [https://www.python.org/downloads/release/python-3119/](https://www.python.org/downloads/release/python-3119/) (Раздел "Files").
2.  Запустите установщик.
3.  **Важно:** На первом экране **обязательно поставьте галочку "Add python.exe to PATH"**.
4.  Нажмите "Install Now" и дождитесь завершения.
5.  Нажмите "Disable path length limit", если появится такая опция.
6.  Закройте установщик.
7.  Откройте *новую* командную строку (CMD или PowerShell) и проверьте версию: `py -3.11 --version`.

**Шаг 2: Клонирование репозитория**

1.  Откройте командную строку или Git Bash.
2.  Перейдите в каталог, где вы хотите разместить проект (например, `C:\dev`).
3.  Клонируйте репозиторий (замените URL, если он другой):
    ```bash
    git clone -
    ```
4.  Перейдите в папку проекта:
    ```bash
    cd eve-memory-reader
    ```

**Шаг 3: Сборка C-библиотеки (eve-memory-reader.dll)**

1.  Откройте Visual Studio.
2.  Выберите `Файл` -> `Открыть` -> `Проект/Решение`.
3.  Найдите и откройте файл `eve-memory-reader.sln` в папке проекта.
4.  В Visual Studio установите конфигурацию сборки:
    *   В выпадающем меню выберите **`Release`**.
    *   Рядом выберите платформу **`x64`**.
5.  Соберите решение:
    *   Меню `Сборка` -> `Собрать решение` (или нажмите `F7`).
6.  Дождитесь завершения сборки. В окне вывода вы увидите **предупреждения** (warnings), но сборка основной библиотеки должна завершиться **успешно**.
    *   *Примечание: Тестовый проект `eve-memory-reader-test` может не собраться из-за ошибки пути - это нормально для запуска основного приложения.*
7.  Убедитесь, что файл `eve-memory-reader.dll` появился по пути: `.\x64\Release\eve-memory-reader.dll` (относительно корневой папки проекта).

**Шаг 4: Настройка Python окружения**

1.  Откройте командную строку (CMD или PowerShell) **в корневой папке проекта** (`C:\dev\eve-memory-reader`).
2.  Создайте виртуальное окружение с помощью Python 3.11:
    ```bash
    py -3.11 -m venv venv
    ```
3.  Активируйте виртуальное окружение:
    *   **Для PowerShell:**
        ```powershell
        .\.venv\Scripts\Activate.ps1
        Set-ExecutionPolicy -ExecutionPolicy RemoteSigned -Scope CurrentUser
        ```
        *(Если возникает ошибка политики выполнения, запустите PowerShell от имени администратора и выполните `Set-ExecutionPolicy RemoteSigned -Scope CurrentUser`, подтвердите `Y`, закройте и попробуйте активацию снова в обычном PowerShell).*
    *   **Для CMD:**
        ```cmd
        .\venv\Scripts\activate.bat
        ```
4.  После активации вы увидите `(venv)` в начале строки приглашения.

**Шаг 5: Установка Python зависимостей**

1.  **Убедитесь, что виртуальное окружение `venv` активно.**
2.  Установите зависимости из файла `requirements.txt` (он должен быть в подпапке `eve-bot-framework`):
    ```bash
    python.exe -m pip install --upgrade pip
    pip install -r eve-bot-framework/requirements.txt
    ```
3.  **Исправьте проблему с PySimpleGUI:**
    *   Удалите стандартную версию:
        ```bash
        pip uninstall -y PySimpleGUI
        ```
    *   Очистите кэш pip:
        ```bash
        pip cache purge
        ```
    *   Установите правильную версию с частного сервера:
        ```bash
        pip install --upgrade --extra-index-url https://PySimpleGUI.net/install PySimpleGUI
        ```

**Шаг 6: Сборка Python приложения (eve-bot-application.exe)**

1.  **Убедитесь, что виртуальное окружение `venv` активно.**
2.  **Создайте файл спецификации** (`.spec`) для PyInstaller (если его еще нет):
    ```bash
    pyinstaller --name="eve-bot-application" --paths ".\eve-bot-framework" --add-data=".\x64\Release\eve-memory-reader.dll;." .\eve-bot-framework\app\app.py --onefile --noconfirm
    ```
**Шаг 7: Запуск приложения**

1.  Запустите исполняемый файл:
    ```bash
    .\dist\eve-bot-application.exe
    ```

**Дебаг**
*   Файл debug.json с выгруженными из памяти данными о игре создается в корне

**Что ожидать при запуске:**

*   Должны открыться два окна:
    *   Консольное окно с логами Flask-сервера (он используется для управления ботом).
    *   Графическое окно PySimpleGUI для взаимодействия с пользователем (загрузка конфигураций ботов и т.д.).
*   Приложение должно попытаться найти запущенный процесс EVE Online (`exefile.exe`).
*   Если все прошло успешно, вы сможете через UI загрузить пример конфигурации бота и запустить его.



** New билд и запуск **

* Команда билда, (запускать в папке рядом с eve-bot-framework)
```
 pyinstaller --name="eve-bot-application" --paths ".\eve-bot-framework" --add-data=".\eve-bot-framework\eve-memory-reader.dll;." .\eve-bot-framework\app.py --onefile --noconfirm
```

* Запуск .exe (запускать в папке рядом с eve-bot-framework)
```
.\dist\eve-bot-application.exe
```
```
.\dist\eve-bot-application.exe set_location_and_autopilot
```
```
.\dist\eve-bot-application.exe asteroid_belt_scanner
```
```
.\dist\eve-bot-application.exe autopilot_simple
```