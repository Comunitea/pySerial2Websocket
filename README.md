# pySerial2Websocket

Crea un puente que lee datos de un SerialPort por USB y los publica en un puerto WebSocket.
Interfaz GUI

## Requisitos Despliegue

* Python 3.10+
* pip

## Instalación

1.  **Clona el repositorio:**

2.  **Crea un entorno virtual (recomendado):**

    * **Linux/macOS:**

        ```bash
        python3 -m venv venv
        source venv/bin/activate
        ```

    * **Windows (cmd):**

        ```bash
        python -m venv venv
        venv\Scripts\activate.bat
        ```

    * **Windows (PowerShell):**

        ```powershell
        python -m venv venv
        venv\Scripts\Activate.ps1
        ```

3.  **Instala las dependencias:**

    ```bash
    pip install -r requirements.txt
    ```

## Uso
1.  **Ejecuta la aplicación:**

    ```bash
    python pyserial2websocket.py
    ```

2.  **Accede a los datos a través de WebSocket:**

    * Abre un navegador web y conéctate a `ws://localhost:8765`.

## Desactivación del entorno virtual

* **Linux/macOS, Windows (cmd) y PowerShell:**

    ```bash
    deactivate
    ```

## Empaquetado de la aplicación

- **Activar venv y tener requiremnts.txt:**
- Es recomendable pasar los imports del requirements para asegurar que pyinstaller encuentra
  todas las dependencias.
- El archivo ejecutable se encontrará en la carpeta `dist`


### Ejecutar PyInstaller Windows (POWERSHELL)

    ```powershell
    pyinstaller --onefile --noconsole --add-data="icons/*;icons" `
    --hidden-import websockets `
    --hidden-import serial `
    --hidden-import serial_asyncio `
    --hidden-import customtkinter `
    --hidden-import pystray `
    --hidden-import PIL `
    --hidden-import pillow `
    pyserial2websocket.py
    ```

### Ejecutar PyInstaller Windows (CMD)

    ```cmd
    pyinstaller --onefile --noconsole --add-data="icons/*;icons" ^
    --hidden-import websockets ^
    --hidden-import serial ^
    --hidden-import serial_asyncio ^
    --hidden-import customtkinter ^
    --hidden-import pystray ^
    --hidden-import PIL ^
    --hidden-import pillow ^
    pyserial2websocket.py
    ```

    * El archivo `.exe` se encontrará en la carpeta `dist`.

### Ejecutar PyInstaller Windows (BASH)

    ```bash
    pyinstaller --onefile --noconsole --add-data="icons/*;icons" `
    --hidden-import websockets `
    --hidden-import serial `
    --hidden-import serial_asyncio `
    --hidden-import customtkinter `
    --hidden-import pystray `
    --hidden-import PIL `
    --hidden-import pillow `
    pyserial2websocket.py
    ```


# TODO
- [ ] Que no salga botón de stop si no conecta..  