from datetime import datetime
import sys
import time
import cv2
import numpy as np
import pyautogui
import threading
import ttkbootstrap as tb
from ttkbootstrap.constants import *
import arduino as ards
from tkinter import messagebox
import database as db
from tkinter import scrolledtext
import threading

class ArduinoPort:
    def __init__(self, root):
        # Create the ttkbootstrap-themed window
        self.root = root
        self.root.title("Poker Texas Hold'em")

        # Port frame
        self.port_frame = tb.LabelFrame(self.root, padding=7, text="Available COM Ports")
        self.port_frame.grid(row=0, column=0, sticky="nsew", padx=10)

        # List available COM ports
        self.ports_list = ards.list_ports()

        self.com_entry = tb.Combobox(self.port_frame, values=self.ports_list, width=10)
        self.com_entry.grid(row=0, column=0, sticky="w", padx=5)

        # Buttons
        self.connect_button = tb.Button(self.port_frame, text="Connect", command=self.select_port, width=12)
        self.connect_button.grid(row=0, column=1, padx=5, pady=5, sticky="w")

        self.disconnect_button = tb.Button(self.port_frame, text="Disconnect", command=self.disconnect, bootstyle="danger", width=12)
        self.disconnect_button.grid(row=0, column=2, padx=5, pady=5, sticky="w")
        self.disconnect_button.grid_remove()  # Initially hidden

        self.upload_button = tb.Button(self.port_frame, text="Upload", command=ards.upload_code, state=DISABLED, width=9)
        self.upload_button.grid(row=0, column=3, padx=5, pady=5, sticky="w")

        self.reports_button = tb.Button(self.port_frame, text="Reports", width=9, bootstyle="success")
        self.reports_button.grid(row=0, column=4, padx=5, pady=5, sticky="w")

    def select_port(self):
        selected_port = self.com_entry.get().strip()
        if not selected_port:
            print(f"COM port not found. Please try again.")
            messagebox.showerror("Error", f"COM port not found. Please try again.")
        else:
            if ards.init_serial(selected_port):
                messagebox.showinfo("Info", f"Connected to {selected_port}.")
                self.connect_button.grid_remove()
                self.disconnect_button.grid()
                self.upload_button['state'] = 'normal'
            else:
                print(f"Failed to connect to {selected_port}. Please check the connection.")
                messagebox.showerror("Error", f"Failed to connect to {selected_port}. Please check the connection.")

    def disconnect(self):
        if messagebox.askokcancel("Warning", "Are you sure you want to disconnect?"):
            ards.close_serial()
            self.disconnect_button.grid_remove()
            self.connect_button.grid()
            self.upload_button['state'] = 'disabled'

class ConsoleLog:
    def __init__(self, root, log_file=None):
        self.root = root
        formatted_now = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = log_file if log_file else f"logs/log{formatted_now}.txt"

        # Create the console frame
        console_frame = tb.LabelFrame(self.root, text="Console", padding=10)
        console_frame.grid(row=4, column=0, sticky="news", padx=10, pady=5)

        # Create a ScrolledText widget for the console log
        self.console = scrolledtext.ScrolledText(console_frame, wrap=tb.WORD, width=60, height=7, state='normal')
        self.console.grid(row=0, column=0, sticky="news", padx=5, pady=5)
        self.console.insert(tb.END, "Console Log Started...\n")
        self.console.see(tb.END)

    def write(self, message):
        if message.strip() and self.root:  # Avoid logging empty messages
            current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
            self.console.insert(tb.END, f"[{current_time}] {message}\n")
            self.console.see(tb.END)  # Scroll to the end

    def flush(self):
        pass  # Needed for Python's file-like objects, especially when redirecting stdout

    def save_to_file(self):
        try:
            with open(self.log_file, "w") as file:
                file.write(self.console.get("1.0", tb.END))  # Get all text from the start to the end
            print("Success: Logs saved successfully!")
        except Exception as e:
            print(f"Error: Failed to save logs: {e}")

    def stop_logging(self):
        print("Logging stopped.")

    def resume_logging(self):
        print("Logging resumed.")

if __name__ == "__main__":
    # Create the ttkbootstrap-themed window
    root = tb.Window(themename="darkly")

    # Create an instance of ArduinoPort and pass the root window
    arduino = ArduinoPort(root)
    console_log = ConsoleLog(root)  # Create the logging system instance
    sys.stdout = console_log  # Redirect stdout to console_log
    sys.stderr = console_log  # Also capture any error messages

    # Start the Tkinter event loop
    root.mainloop()