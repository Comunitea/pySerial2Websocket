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
    """Obtiene la ruta absoluta a los recursos, funciona para desarrollo y para PyInstaller."""
    try:
        # Ruta absoluta al recurso si se ejecuta como un archivo empaquetado
        base_path = sys._MEIPASS
    except Exception:
        # Ruta absoluta al recurso si se ejecuta en desarrollo
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)


WEBSOCKET_PORT = 8765  # Puerto predeterminado para WebSocket
MAX_REPEATED_READS = 100
ICON_PATH_RUNNING = resource_path("icons/running.png")
ICON_PATH_STOPPED = resource_path("icons/stopped.png")
ICON_APP = resource_path("icons/app.ico")
ICON_APP_PNG = resource_path("icons/app_icon.png")


class SerialToWebSocket:
    def __init__(self, serial_port, baud_rate, websocket_port, device_id=None):
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

    async def handle_serial_read(self):
        while self.running:
            try:
                data = await self.serial_reader.readuntil(b'\r')
                if data:
                    if self.websocket_clients:
                        if data == self.last_sent_data:
                            self.repeated_count += 1
                            if self.repeated_count <= MAX_REPEATED_READS:
                                logging.info(f"Sending: {data}")
                                await self.send_data_to_clients(data)
                        else:
                            self.repeated_count = 0
                            logging.info(f"Sending new: {data}")
                            await self.send_data_to_clients(data)
                            self.last_sent_data = data
            except Exception as e:
                logging.error(f"Error reading from serial port: {e}")

    async def send_data_to_clients(self, data):
        if self.websocket_clients:
            if len(self.websocket_clients) > 1:
                logging.info(f"Sending data to {len(self.websocket_clients)} clients")
            await asyncio.gather(*(client.send(data) for client in self.websocket_clients))

    async def handle_websocket(self, websocket):
        self.websocket_clients.add(websocket)
        logging.info("New WebSocket client connected.")

        self.repeated_count = 0
        if self.last_sent_data:
            logging.info(f"Resending last data: {self.last_sent_data}")
            await self.send_data_to_clients(self.last_sent_data)

        try:
            async for message in websocket:
                if message == "ping":
                    await websocket.pong()
                logging.info(f"---Received message---: {message}")
                command = self.build_sscar_command(message)
                self.serial_writer.write(command.encode('utf-8'))
                await self.serial_writer.drain()
        except websockets.exceptions.ConnectionClosed as e:
            logging.info(f"WebSocket connection closed: {e}")
        finally:
            self.websocket_clients.remove(websocket)
            logging.info("WebSocket client disconnected.")

    def build_sscar_command(self, message):
        command = message.strip().upper()
        if self.device_id:
            return f"S {self.device_id} {command}\r"
        else:
            return f"S{command}\r"

    async def main(self):
        try:
            self.serial_reader, self.serial_writer = await serial_asyncio.open_serial_connection(
                url=self.serial_port, baudrate=self.baud_rate, parity=serial.PARITY_NONE,
                stopbits=serial.STOPBITS_ONE, bytesize=serial.EIGHTBITS, timeout=1
            )

            self.server = await websockets.serve(self.handle_websocket, "0.0.0.0", self.websocket_port)
            self.running = True
            logging.info("WebSocket server started.")
            await self.handle_serial_read()

        except serial.serialutil.SerialException as e:
            error_message = f"Error al abrir el puerto serial: {e}"
            logging.error(error_message)
            messagebox.showerror("Error de Puerto Serial", error_message)
            self.stop()  #detener el servidor si no se pudo abrir el puerto serial.

        except Exception as e:
            logging.error(f"Error inesperado: {e}", exc_info=True)
            messagebox.showerror("Error inesperado", f"Ocurrió un error inesperado: {e}")
            self.stop()

    def stop(self):
        self.running = False
        if self.server:
            self.server.close()
            logging.info("WebSocket server stopped.")
        if self.serial_writer:
            self.serial_writer.close()
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)


def start_server_in_thread(serial_to_ws):
    loop = asyncio.new_event_loop()
    asyncio.set_event_loop(loop)
    serial_to_ws.loop = loop  # Guardamos el loop en la instancia
    try:
        loop.run_until_complete(serial_to_ws.main())
    finally:
        loop.close()


def start_server(serial_port, websocket_port):
    serial_to_ws = SerialToWebSocket(serial_port, 9600, websocket_port)
    thread = threading.Thread(target=start_server_in_thread, args=(serial_to_ws,), daemon=True)
    thread.start()
    return serial_to_ws


def stop_server(serial_to_ws):
    serial_to_ws.stop()

def start_stop_server():
    global server_instance
    if start_button.cget("text") == "Start Server":
        selected_port = port_combobox.get()
        websocket_port = websocket_port_entry.get()
        if selected_port and websocket_port:
            try:
                websocket_port = int(websocket_port)
                start_button.configure(state="disabled", fg_color="green")  # Cambiar a verde
                logging.info(f"Starting server on serial port {selected_port} and websocket port {websocket_port}...")
                server_instance = start_server(selected_port, websocket_port)
                start_button.configure(state="normal", text="Stop Server", fg_color="red")  # Cambiar a rojo
                tray_icon.icon = Image.open(ICON_PATH_RUNNING)
            except ValueError:
                messagebox.showerror("Error", "Invalid WebSocket port.")
                start_button.configure(state="normal", fg_color="green")  # Restaurar verde si hay error
        else:
            messagebox.showerror("Error", "Please select a serial port and enter a valid WebSocket port.")
            start_button.configure(state="normal", fg_color="green")  # Restaurar verde si hay error
    else:
        logging.info("Stopping server...")
        stop_server(server_instance)
        start_button.configure(text="Start Server", fg_color="green")  # Volver a verde
        tray_icon.icon = Image.open(ICON_PATH_STOPPED)


def on_closing():
    if messagebox.askokcancel("Quit", "Do you want to quit?"):
        logging.info("Window closed, stopping server.")
        if server_instance:
            stop_server(server_instance)
        root.quit()


def tray_toggle_server(icon, item):
    root.after(0, start_stop_server)


def tray_exit(icon, item):
    root.after(0, on_closing)

def get_serial_ports():
    if os.name == 'posix':  # Linux
        return [port.device for port in serial.tools.list_ports.comports() if 'ttyUSB' in port.device]
    elif os.name == 'nt':  # Windows
        return [port.device for port in serial.tools.list_ports.comports() if 'COM' in port.device]
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

# Entry para mostrar logs
logs_entry = ctk.CTkEntry(root, width=400, height=200, state="readonly")
logs_entry.grid(row=2, column=0, columnspan=2, padx=10, pady=10)

# Entry para mostrar el último dato
last_data_entry = ctk.CTkEntry(root, width=200)
last_data_entry.grid(row=3, column=0, columnspan=2, padx=10, pady=10)

start_button = ctk.CTkButton(
    root, text="Start Server", command=start_stop_server, fg_color="green")
start_button.grid(row=4, column=0, columnspan=2, pady=20)

root.protocol("WM_DELETE_WINDOW", on_closing)

# Crear la instancia de SerialToWebSocket antes de la interfaz gráfica
server_instance = None

# Systray Setup
menu = Menu(
    MenuItem("Start/Stop Server", tray_toggle_server),
    MenuItem("Exit", tray_exit)
)
tray_icon = Icon("SerialToWS", Image.open(ICON_PATH_STOPPED), menu=menu)
threading.Thread(target=tray_icon.run, daemon=True).start()

server_instance = None
root.mainloop()
