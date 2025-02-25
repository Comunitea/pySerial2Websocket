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

# TODO
- [ ] Que no salga botón de stop si no conecta..  