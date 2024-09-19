import pyautogui
import tkinter as tk
from tkinter import filedialog
from datetime import datetime
import os

# Create the main window
root = tk.Tk()
root.title("Auto Screenshot")

# Set the size of the window
root.geometry("300x200")

# Default save folder
save_folder = ""

# Function to set the save folder
def choose_folder():
    global save_folder
    folder_selected = filedialog.askdirectory()
    if folder_selected:
        save_folder = folder_selected
        folder_label.config(text=f"Folder: {save_folder}")

# Function to capture a screenshot and save it in the selected folder
def take_screenshot():
    if save_folder:
        # Generate a filename with the current date and time
        screenshot_name = f"screenshot_{datetime.now().strftime('%Y%m%d_%H%M%S')}.png"
        screenshot_path = os.path.join(save_folder, screenshot_name)
        
        # Capture screenshot
        screenshot = pyautogui.screenshot()
        
        # Save the screenshot in the chosen folder
        screenshot.save(screenshot_path)
        result_label.config(text=f"Screenshot saved as {screenshot_path}")
    else:
        result_label.config(text="Please select a folder first!")

# Create a button to choose the folder to save screenshots
choose_folder_button = tk.Button(root, text="Choose Save Folder", command=choose_folder)
choose_folder_button.pack(pady=10)

# Label to display the selected folder
folder_label = tk.Label(root, text="No folder selected")
folder_label.pack(pady=5)

# Create a button to take a screenshot
screenshot_button = tk.Button(root, text="Take Screenshot", command=take_screenshot)
screenshot_button.pack(pady=10)

# Label to display the result
result_label = tk.Label(root, text="")
result_label.pack(pady=10)

# Run the GUI loop
root.mainloop()
