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
from PIL import Image

logging.basicConfig(
    level=logging.INFO,
    format='%(asctime)s - %(name)s - %(levelname)s : %(message)s',
    datefmt='%Y-%m-%d %H:%M:%S'
)

def resource_path(relative_path):
    try:
        base_path = sys._MEIPASS
    except Exception:
        base_path = os.path.abspath(".")
    return os.path.join(base_path, relative_path)

WEBSOCKET_PORT = 8765
ICON_PATH_RUNNING = resource_path("icons/running.png")
ICON_PATH_STOPPED = resource_path("icons/stopped.png")

class SerialToWebSocket:
    def __init__(self, serial_port, baud_rate, websocket_port, log_callback, update_data_callback):
        self.serial_port = serial_port
        self.baud_rate = baud_rate
        self.websocket_port = websocket_port
        self.websocket_clients = set()
        self.running = False
        self.server = None
        self.loop = None
        self.log_callback = log_callback
        self.update_data_callback = update_data_callback

    async def handle_serial_read(self):
        while self.running:
            try:
                data = await self.serial_reader.readuntil(b'\r')
                if data:
                    self.update_data_callback(data.decode("utf-8"))
                    await self.send_data_to_clients(data)
            except Exception as e:
                self.log_callback(f"Error reading serial: {e}")

    async def send_data_to_clients(self, data):
        if self.websocket_clients:
            await asyncio.gather(*(client.send(data) for client in self.websocket_clients))

    async def handle_websocket(self, websocket):
        self.websocket_clients.add(websocket)
        try:
            async for message in websocket:
                if message == "ping":
                    await websocket.pong()
        except websockets.exceptions.ConnectionClosed as e:
            self.log_callback(f"WebSocket closed: {e}")
        finally:
            self.websocket_clients.remove(websocket)

    async def main(self):
        try:
            self.serial_reader, self.serial_writer = await serial_asyncio.open_serial_connection(
                url=self.serial_port, baudrate=self.baud_rate)
            self.server = await websockets.serve(self.handle_websocket, "0.0.0.0", self.websocket_port)
            self.running = True
            self.log_callback("WebSocket server started.")
            await self.handle_serial_read()
        except Exception as e:
            self.log_callback(f"Error starting server: {e}")
            self.running = False
            self.stop()
    
    def stop(self):
        self.running = False
        if self.server:
            self.server.close()
            self.log_callback("WebSocket server stopped.")
        if self.serial_writer:
            self.serial_writer.close()
        if self.loop and self.loop.is_running():
            self.loop.call_soon_threadsafe(self.loop.stop)

def start_server(serial_port, websocket_port, log_callback, update_data_callback):
    serial_to_ws = SerialToWebSocket(serial_port, 9600, websocket_port, log_callback, update_data_callback)
    thread = threading.Thread(target=lambda: asyncio.run(serial_to_ws.main()), daemon=True)
    thread.start()
    return serial_to_ws

def start_stop_server():
    global server_instance
    if start_button.cget("text") == "Start Server":
        selected_port = port_combobox.get()
        websocket_port = websocket_port_entry.get()
        if selected_port and websocket_port:
            try:
                websocket_port = int(websocket_port)
                log_message(f"Starting server on {selected_port}, WebSocket {websocket_port}...")
                server_instance = start_server(selected_port, websocket_port, log_message, update_last_data)
                if server_instance.running:
                    start_button.configure(text="Stop Server")
                    tray_icon.icon = Image.open(ICON_PATH_RUNNING)
            except ValueError:
                messagebox.showerror("Error", "Invalid WebSocket port.")
        else:
            messagebox.showerror("Error", "Select a serial port and enter a WebSocket port.")
    else:
        if server_instance:
            log_message("Stopping server...")
            server_instance.stop()
            start_button.configure(text="Start Server")
            tray_icon.icon = Image.open(ICON_PATH_STOPPED)

def log_message(message):
    log_textbox.insert("end", message + "\n")
    log_textbox.see("end")
    logging.info(message)

def update_last_data(data):
    last_data_label.configure(text=f"Last Data: {data}")

root = ctk.CTk()
root.title("Serial to WebSocket")

port_label = ctk.CTkLabel(root, text="Select Serial Port:")
port_label.grid(row=0, column=0, padx=10, pady=5)
port_combobox = ctk.CTkComboBox(root, values=["COM1", "/dev/ttyUSB0"], width=200)
port_combobox.grid(row=0, column=1, padx=10, pady=5)
websocket_port_label = ctk.CTkLabel(root, text="WebSocket Port:")
websocket_port_label.grid(row=1, column=0, padx=10, pady=5)
websocket_port_entry = ctk.CTkEntry(root, width=200)
websocket_port_entry.insert(0, str(WEBSOCKET_PORT))
websocket_port_entry.grid(row=1, column=1, padx=10, pady=5)
start_button = ctk.CTkButton(root, text="Start Server", command=start_stop_server)
start_button.grid(row=2, column=0, columnspan=2, pady=10)
last_data_label = ctk.CTkLabel(root, text="Last Data: ")
last_data_label.grid(row=3, column=0, columnspan=2, pady=5)
log_textbox = ctk.CTkTextbox(root, width=400, height=150)
log_textbox.grid(row=4, column=0, columnspan=2, pady=5)

def tray_toggle_server(icon, item):
    root.after(0, start_stop_server)

def tray_exit(icon, item):
    root.quit()

menu = Menu(MenuItem("Start/Stop Server", tray_toggle_server), MenuItem("Exit", tray_exit))
tray_icon = Icon("SerialToWS", Image.open(ICON_PATH_STOPPED), menu=menu)
threading.Thread(target=tray_icon.run, daemon=True).start()

server_instance = None
root.mainloop()
