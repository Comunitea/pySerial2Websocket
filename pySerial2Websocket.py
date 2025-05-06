import asyncio
import websockets
import serial
import serial_asyncio
import logging
import customtkinter as ctk
import serial.tools.list_ports
import os
import sys
import tkinter.messagebox as messagebox
import threading
from pystray import Icon, MenuItem, Menu
from PIL import Image, ImageTk


logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s : %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)


def resource_path(relative_path):
    """
    Obtiene la ruta absoluta a los recursos, 
    funciona para desarrollo y para PyInstaller.
    """
    try:
        # Ruta absoluta al recurso si se ejecuta como un archivo empaquetado
        base_path = sys._MEIPASS
    except Exception:
        # Ruta absoluta al recurso si se ejecuta en desarrollo
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


WEBSOCKET_PORT = 8765  # Puerto predeterminado para WebSocket
MAX_REPEATED_READS = 100
MAX_LOG_LINES = 100

ICON_PATH_RUNNING = resource_path("icons/running.png")
ICON_PATH_STOPPED = resource_path("icons/stopped.png")
ICON_APP_PNG = resource_path("icons/app_icon.png")


class SerialToWebSocket:
    def __init__(self, serial_port, baud_rate, websocket_port, log_callback,
                 update_data_callback, device_id=None):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.websocket_port = websocket_port
        self.device_id = device_id
        self.serial_reader = None
        self.serial_writer = None
        self.websocket_clients = set()
        self.last_sent_data = None
        self.repeated_count = 0
        self.server = None  # Servidor WebSocket
        self.running = False
        self.loop = None  # Guardaremos el loop para controlarlo mejor

        self.log_callback = log_callback
        self.update_data_callback = update_data_callback

    async def handle_serial_read(self):
        while self.running:
            try:
                data = await self.serial_reader.readuntil(b'\r')
                if data:
                    self.update_data_callback(data.decode("utf-8"))
                    if self.websocket_clients:
                        if data == self.last_sent_data:
                            self.repeated_count += 1
                            if self.repeated_count <= MAX_REPEATED_READS:
                                log_message(f"Enviando datos: {data}")
                                await self.send_data_to_clients(data)
                        else:
                            self.repeated_count = 0
                            log_message(f"Nuevos datos: {data}")
                            await self.send_data_to_clients(data)
                            self.last_sent_data = data
            except Exception as e:
                logging.error(f"Error leyendo del puerto de serie: {e}")

    async def send_data_to_clients(self, data):
        if self.websocket_clients:
            if len(self.websocket_clients) > 1:
                log_message(
                    f"Enviando datos a {len(self.websocket_clients)} clientes")
            await asyncio.gather(
                *(client.send(data) for client in self.websocket_clients))

    async def handle_websocket(self, websocket):
        self.websocket_clients.add(websocket)
        log_message("NUEVO CLIENTE WEBSOCKET CONECTADO.")

        self.repeated_count = 0
        if self.last_sent_data:
            log_message(f"Reenviando últimos datos: {self.last_sent_data}")
            await self.send_data_to_clients(self.last_sent_data)

        try:
            async for message in websocket:
                if message == "ping":
                    await websocket.pong()
                log_message(f"---Mensaje recivido---: {message}")
                command = self.build_sscar_command(message)
                self.serial_writer.write(command.encode('utf-8'))
                await self.serial_writer.drain()
        except websockets.exceptions.ConnectionClosed as e:
            log_message(f"Conexión websocket cerrada: {e}")
        finally:
            self.websocket_clients.remove(websocket)
            log_message("Cliente websocket desconectado.")

    def build_sscar_command(self, message):
        command = message.strip().upper()
        if self.device_id:
            return f"S {self.device_id} {command}\r"
        else:
            return f"S{command}\r"

    async def main(self):
        try:
            self.serial_reader, self.serial_writer = \
                await serial_asyncio.open_serial_connection(
                    url=self.serial_port, baudrate=self.baud_rate,
                    parity=serial.PARITY_NONE,
                    stopbits=serial.STOPBITS_ONE,
                    bytesize=serial.EIGHTBITS, timeout=1)

            self.server = await websockets.serve(
                self.handle_websocket, "0.0.0.0", self.websocket_port)
            self.running = True
            self.log_callback("Servidor Websocket iniciado.")
            await self.handle_serial_read()

        except serial.serialutil.SerialException as e:
            root.after(0, lambda: update_ui_on_stop())
            error_message = f"Error al abrir el puerto serial: {e}"
            logging.error(error_message, "error")
            messagebox.showerror("Error de Puerto Serial", error_message)
            self.stop()

        except Exception as e:
            log_message(f"Ocurrió un error inesperado: {e}")
            messagebox.showerror(
                "Error inesperado", f"Ocurrió un error inesperado: {e}")
            self.stop()
            root.after(0, lambda: update_ui_on_stop())

    def stop(self):
        self.running = False
        if self.server:
            self.server.close()
            self.loop.call_soon_threadsafe(
                asyncio.create_task, self.server.wait_closed())
        if self.serial_writer:
            self.serial_writer.close()
        self.loop.call_soon_threadsafe(self.loop.stop)


def start_server_in_thread(serial_to_ws):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    serial_to_ws.loop = loop

    async def start_all():
        await serial_to_ws.main()
        log_message("Tarea main() terminada.")

    try:
        loop.create_task(start_all())
        loop.run_forever()
    finally:
        log_message("Cerrando loop asyncio.")
        loop.close()



def start_server(serial_port, websocket_port, 
                 log_callback, update_data_callback):
    serial_to_ws = SerialToWebSocket(
        serial_port, 9600, websocket_port, log_callback, update_data_callback)
    thread = threading.Thread(
        target=start_server_in_thread, args=(serial_to_ws,), daemon=True)
    thread.start()
    return serial_to_ws


def stop_server(serial_to_ws):
    serial_to_ws.stop()


def log_message(message):
    message = "[+] " + message
    log_textbox.insert("end", message + "\n")
    # Limitar el número de líneas
    lines = log_textbox.get("1.0", "end-1c").splitlines()
    # Eliminar las líneas más antiguas
    if len(lines) > MAX_LOG_LINES:
        log_textbox.delete("1.0", f"{len(lines) - MAX_LOG_LINES + 1}.0")
    # Asegurarse de que siempre se vea el final del texto
    log_textbox.see("end")
    logging.info(message)


def update_last_data(data):
    last_data_label.configure(text=f"Última lectura: {data}")


def start_stop_server():
    global server_instance
    if start_stop_button.cget("text") == "Iniciar Servidor":
        selected_port = port_combobox.get()
        websocket_port = websocket_port_entry.get()
        if selected_port and websocket_port:
            try:
                websocket_port = int(websocket_port)
                start_stop_button.configure(state="disabled", fg_color="green")
                log_message(
                    f"Inicializando servidor. "
                    f"Leyendo de {selected_port} "
                    f"Publicando en WebSocket {websocket_port}...")

                # Iniciar el servidor en un hilo
                server_instance = start_server(
                    selected_port, websocket_port, 
                    log_message, update_last_data)

                # Actualizar el botón y el ícono en el hilo principal
                root.after(0, lambda: update_ui_on_start())
            except ValueError:
                messagebox.showerror(
                    "Error", "El puerto del Websocket no es válido.")
                start_stop_button.configure(state="normal", fg_color="green")
        else:
            messagebox.showerror(
                "Error",
                "Seleciona puerto de serie y websocker válidos.")
            start_stop_button.configure(state="normal", fg_color="green")
    else:
        # Deshabilitar el botón mientras se detiene el servidor
        start_stop_button.configure(state="disabled", fg_color="red")
        log_message("Parando servidor...")
        stop_server(server_instance)

        # Volver a habilitar el botón en el hilo principal
        root.after(0, lambda: update_ui_on_stop())


def update_ui_on_start():
    start_stop_button.configure(
        text="Parar Servidor", state="normal", fg_color="red")
    tray_icon.icon = Image.open(ICON_PATH_RUNNING)


def update_ui_on_stop():
    start_stop_button.configure(
        text="Iniciar Servidor", state="normal", fg_color="green")
    tray_icon.icon = Image.open(ICON_PATH_STOPPED)


def on_closing():
    if messagebox.askokcancel(
            "Salir", "Estas seguro de que deseas cerrar la aplicación?"):
        log_message("Ventana cerrada, parando servidor.")
        if server_instance:
            stop_server(server_instance)
        root.quit()


def tray_toggle_server(icon, item):
    root.after(0, start_stop_server)


def tray_exit(icon, item):
    root.after(0, on_closing)


def get_serial_ports():
    if os.name == 'posix':  # Linux
        return [port.device for port in serial.tools.list_ports.comports() 
                if 'ttyUSB' in port.device]
    elif os.name == 'nt':  # Windows
        return [port.device for port in serial.tools.list_ports.comports() 
                if 'COM' in port.device]
    else:
        return []  # No support for other OS


# Configuración de la ventana principal
root = ctk.CTk()
root.title("Serial to WebSocket Server")

# argar el icono PNG usando Pillow
icon_image = Image.open(ICON_APP_PNG)
icon_photo = ImageTk.PhotoImage(icon_image)
root.wm_iconphoto(True, icon_photo)

# Obtener los puertos seriales disponibles
ports = get_serial_ports()
# Establecer el puerto predeterminado
default_port = (
    ports[0] if ports else ("COM1" if os.name == "nt" else "/dev/ttyUSB0")
)
# Widgets
port_label = ctk.CTkLabel(root, text="Select Serial Port:")
port_label.grid(row=0, column=0, padx=10, pady=10)

port_combobox = ctk.CTkComboBox(root, values=ports, width=200)
port_combobox.set(default_port)
port_combobox.grid(row=0, column=1, padx=10, pady=10)

websocket_port_label = ctk.CTkLabel(root, text="WebSocket Port:")
websocket_port_label.grid(row=1, column=0, padx=10, pady=10)

websocket_port_entry = ctk.CTkEntry(root, width=200)
websocket_port_entry.insert(0, str(WEBSOCKET_PORT))
websocket_port_entry.grid(row=1, column=1, padx=10, pady=10)

start_stop_button = ctk.CTkButton(
    root, text="Iniciar Servidor", command=start_stop_server, fg_color="green")
start_stop_button.grid(row=4, column=0, columnspan=2, pady=20)

last_data_label = ctk.CTkLabel(root, text="Last Data: ")
last_data_label.grid(row=5, column=0, columnspan=2, pady=5)

# Ajustamos el grid para que el Textbox sea responsivo
log_textbox = ctk.CTkTextbox(root)
log_textbox.grid(row=6, column=0, columnspan=2, pady=5, sticky="nsew")

# Configurar las filas y columnas para que sean expansibles
root.grid_rowconfigure(6, weight=1)  # Hacer que la fila del log sea expansible
root.grid_columnconfigure(0, weight=1)
root.grid_columnconfigure(1, weight=1)

root.protocol("WM_DELETE_WINDOW", on_closing)

# Crear la instancia de SerialToWebSocket antes de la interfaz gráfica
server_instance = None

# Systray Setup
menu = Menu(
    MenuItem("Iniciar/Parar Servidor", tray_toggle_server),
    MenuItem("Salir", tray_exit)
)
tray_icon = Icon("SerialToWS", Image.open(ICON_PATH_STOPPED), menu=menu)
threading.Thread(target=tray_icon.run, daemon=True).start()

server_instance = None
root.mainloop()
