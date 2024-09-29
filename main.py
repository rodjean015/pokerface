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

class Boardcard:
    def  __init__(self, frame_config):
        self.stop_betting = False  # This should be a class attribute now
        self.detection_thread = None  # Use a class attribute for the thread
        self.board_regions = {
            'Flop A :': (381, 275, 40, 65),
            'Flop B :': (488, 275, 40, 65),
            'Flop C :': (595, 275, 40, 65),
            'Turn   :': (701, 275, 40, 65),
            'River  :': (808, 275, 40, 65),
        }

        self.suits = ['Diamonds', 'Clubs', 'Hearts', 'Spades']
        self.values = {'2': '2', '3': '3', '4 ': '4', '5': '5', '6': '6', '7': '7', '8': '8', '9': '9', 'T': 'T', 'J': 'J', 'Q': 'Q', 'K': 'K', 'A': 'A'}

        # Load the template images
        self.templates = {
            f'{name}_{suit}': cv2.imread(f'assets/cards/{name.lower()}/{name.lower()}{suit.lower()}.png', 0)
            for name in self.values.values() for suit in self.suits
        }

        # Check if all templates were loaded successfully
        for key, template in self.templates.items():
            if template is None:
                raise FileNotFoundError(f"Template image for '{key}' not found.")

        # Frame for the card detector view
        board_frame = tb.LabelFrame(frame_config, padding=10, text="Board Detector")
        board_frame.grid(row=0, column=0, sticky="news", padx=10, pady=5)

        # Initialize dictionaries for labels and sum labels
        self.labels = {}
        row = 0

        # Loop through the board_regions and create the necessary labels and frames
        for region_name in self.board_regions.keys():
            frame = tb.Frame(board_frame, padding=5)
            frame.grid(row=row, column=0, sticky=W)

            label_title = tb.Label(frame, text=f"{region_name}", anchor=W)
            label_title.grid(row=0, column=0, sticky=W)

            label_value = tb.Label(frame, text="--", anchor=W)
            label_value.grid(row=1, column=0, sticky=W)

            self.labels[region_name] = label_value
            row += 1

    def capture_region(self, region):
        """Capture the region of the screen for template matching."""
        x, y, w, h = region
        screenshot = pyautogui.screenshot(region=(x, y, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)
        return gray_img

    def check_cards_in_board(self, region, gray_img):
        """Perform template matching for cards in a region."""
        detected_values = set()
        region_height, region_width = gray_img.shape[:2]

        for card_name, template in self.templates.items():
            if template is None:
                continue  # Skip if the template wasn't loaded successfully
            h, w = template.shape[:2]
            if region_height < h or region_width < w:
                continue
            for scale in np.linspace(0.9, 2.2, 18):
                scaled_template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                if scaled_template.shape[0] > region_height or scaled_template.shape[1] > region_width:
                    continue
                result = cv2.matchTemplate(gray_img, scaled_template, method=cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if max_val >= 0.95:
                    value, suit_initial = card_name.split('_')
                    detected_values.add(f"{value}{suit_initial[0].upper()}")
                    top_left = max_loc
                    bottom_right = (top_left[0] + scaled_template.shape[1], top_left[1] + scaled_template.shape[0])
                    cv2.rectangle(gray_img, top_left, bottom_right, (0, 255, 0), 2)
                    break 
        return list(detected_values)
    
    def check_board_cards(self):
        found_cards = {}
        for region_name, region in self.board_regions.items():
            gray_img = self.capture_region(region)
            card_values = self.check_cards_in_board(region, gray_img)
            if card_values:
                found_cards[region_name] = card_values
        return found_cards
    
    def board_display(self, found_cards):
        """Update the display with detected card values and sums."""

        for region_name in self.labels.keys():
            if region_name in found_cards:
                cards = found_cards[region_name]
                self.labels[region_name].config(text=cards)
            else:
                self.labels[region_name].config(text="--")

class Handcard(Boardcard):
    def __init__(self, frame_config):
        super().__init__(frame_config)
        self.status_region = {
            'Start' : (343, 519, 117, 117),
            'Pause' : (556, 377, 45, 45)
        }
        self.status_templates = {
            'Start': cv2.imread('assets/status/start.png', 0),
            'Pause': cv2.imread('assets/status/pause.png', 0),
        }
        self.your_hand = {
            'Hand A': (480, 530, 42, 67),
            'Hand B': (547, 524, 42, 67),
        }
        self.high_cards = ['A', 'T', 'J', 'Q', 'K', '9']

        # Load image templates for both left and right hand sides
        self.hand_templates = {
            hand_side: {
                f'{name}_{suit}': cv2.imread(f'assets/hand/{hand_side.lower()}/{name.lower()}/{name.lower()}{suit.lower()}.png', 0)
                for name in self.values.values() for suit in self.suits
            } for hand_side in self.your_hand
        }
        self.frame_hand = tb.LabelFrame(frame_config, padding=10, text="Your Hand")
        self.frame_hand.grid(row=0, column=1, sticky="news", padx=10, pady=5)

        self.treeview = tb.Treeview(self.frame_hand, columns=("board", "hand", "position"), show="headings", height=5)
        self.treeview.heading("board", text="Board", anchor=W)
        self.treeview.heading("hand", text="Hand", anchor=W)
        self.treeview.heading("position", text="Position", anchor=W)
        self.treeview.column("board", width=100)
        self.treeview.column("hand", width=100)
        self.treeview.column("position", width=80)
        self.treeview.grid(row=0, column=0, sticky="news")

        self.scrollbar_y = tb.Scrollbar(self.frame_hand, orient="vertical", command=self.treeview.yview)
        self.scrollbar_y.grid(row=0, column=1, sticky="ns")
        self.treeview.configure(yscrollcommand=self.scrollbar_y.set)

        # Start and Stop buttons
        self.start_button = tb.Button(self.frame_hand, text="Start Bet", command=self.start_bet)
        self.start_button.grid(pady=10, column=0, row=1, sticky="news")

        self.stop_button = tb.Button(self.frame_hand, text="Stop Bet", command=self.stop_bets, bootstyle="danger")
        self.stop_button.grid(pady=10, column=0, row=1, sticky="news")
        self.stop_button.grid_remove()  # Initially hidden

        self.lower_frame = tb.Frame(self.frame_hand)
        self.lower_frame.grid(row=2, column=0, sticky="news")

        self.card_frame = tb.Frame(self.lower_frame)
        self.card_frame.grid(row=0, column=0, sticky="w")
        self.hand_labels = {}

        for index, (hand_name, _) in enumerate(self.your_hand.items(), start=0):
            frame = tb.Frame(self.card_frame, padding=5)
            frame.grid(row=index, column=0, sticky='news', padx=10)

            label_title = tb.Label(frame, text=f"{hand_name}")
            label_title.grid(row=0, column=0, sticky='w')

            label_value = tb.Label(frame, text="--")
            label_value.grid(row=1, column=0, sticky='w')

            self.hand_labels[hand_name] = label_value

        status_frame = tb.Frame(self.lower_frame, padding=5)
        status_frame.grid(row=0, column=1, sticky="news")
        self.status_label = ["Status", "Position"]  # List of status labels
        self.stat_label = {}
        row = 0

        # Check if self.status_label exists and is a list
        if hasattr(self, 'status_label') and isinstance(self.status_label, list):
            # Loop through the status_label list and create the necessary stat_label and frames
            for stat_name in self.status_label:
                # Create a frame for each status label
                frame = tb.Frame(status_frame, padding=5)
                frame.grid(row=row, column=0, sticky="news", padx=10)

                # Create a label for the status name
                label_title = tb.Label(frame, text=f"{stat_name}", anchor=W)
                label_title.grid(row=0, column=0, sticky=W)

                # Create a label for the status value, initially set to "--"
                label_value = tb.Label(frame, text="--", anchor=W)
                label_value.grid(row=1, column=0, sticky=W)

                # Store the label in the stat_label dictionary for later updates
                self.stat_label[stat_name] = label_value
                row += 1

        cbox_frame = tb.Frame(self.lower_frame, padding=5)
        cbox_frame.grid(row=0, column=2, sticky="wne")
        self.cbox_label = ["Stop Until"]  # List of status labels
        self.cbox_labels = {}
        row = 0
        if hasattr(self, 'cbox_label') and isinstance(self.cbox_label, list):
            # Loop through the cbox_label list and create the necessary cbox_labels and frames
            for cbox_name in self.cbox_label:
                # Create a frame for each status label
                frame = tb.Frame(cbox_frame, padding=5)
                frame.grid(row=row, column=0, sticky=W, padx=10)

                # Create a label for the status name
                label_title = tb.Label(frame, text=f"{cbox_name}", anchor=W)
                label_title.grid(row=0, column=0, sticky=W)

                cbox_value = tb.Combobox(frame, values=[50, 100, 300, 500, 1000], width=6)
                cbox_value.grid(row=1, column=0, sticky=W)

                # Store the label in the cbox_labels dictionary for later updates
                self.cbox_labels[cbox_name] = cbox_value
                row += 1

        self.command_sent = False 

    def check_status_area(self, region, template, method=cv2.TM_SQDIFF_NORMED, threshold=0.1):
        """Check for the presence of a template in a given screen region."""
        x, y, w, h = region  # Assuming region is a tuple (x, y, width, height)
        screenshot = pyautogui.screenshot(region=(x, y, w, h))
        img = cv2.cvtColor(np.array(screenshot), cv2.COLOR_RGB2BGR)
        gray_img = cv2.cvtColor(img, cv2.COLOR_BGR2GRAY)

        # Template matching
        result = cv2.matchTemplate(gray_img, template, method)
        min_val, _, min_loc, _ = cv2.minMaxLoc(result)
        
        return min_val < threshold

    def check_start(self):
        return self.check_status_area(self.status_region['Start'], self.status_templates['Start'])
    
    def check_pause(self):
        return self.check_status_area(self.status_region['Pause'], self.status_templates['Pause'])
    
    def check_status(self):
        # Safe extraction of the first character or None if empty
        left_text = self.hand_labels['Hand A'].cget("text")
        right_text = self.hand_labels['Hand B'].cget("text")
        left_value = left_text[0] if left_text else None
        right_value = right_text[0] if right_text else None

        flop_regions = ['Flop A :', 'Flop B :', 'Flop C :']
        flop_first_chars = []

        for region_name in flop_regions:
            if region_name in self.labels:
                label_text = self.labels[region_name].cget("text")
                flop_first_chars.append(label_text[0])  # Get the first character
                    

        if self.check_start():
            self.stat_label['Status'].config(text="Betting.")

            # Check if both left_value and right_value are in self.high_cards
            if (left_value in self.high_cards and right_value in self.high_cards) and (right_value in flop_first_chars or left_value in flop_first_chars or '-' in flop_first_chars):
                if not self.command_sent:  # Check if a command has not been sent yet
                    ards.send_command('call')
                    self.command_sent = True  # Set the flag as true after sending command
            else:
                if not self.command_sent:  # Check if a command has not been sent yet
                    ards.send_command('fold')
                    self.command_sent = True  # Set the flag as true after sending command
        elif self.check_pause():
            if not self.command_sent:
                self.stat_label['Status'].config(text="Pause.")
                ards.send_command('start')      
                self.command_sent = True 
        else:
            self.stat_label['Status'].config(text="Processing.")
            self.command_sent = False

    def check_cards_in_hand(self, region, gray_img, hand_side):
        """Perform template matching for cards in a specified region based on the hand side."""
        detected_values = set()
        region_height, region_width = gray_img.shape[:2]
        templates = self.hand_templates[hand_side]  # Access the correct dictionary for the hand side

        for card_name, template in templates.items():
            if template is None:
                continue  # Skip if the template wasn't loaded successfully or is None

            try:
                h, w = template.shape[:2]  # Attempt to unpack the shape
            except AttributeError:
                continue  # Skip if the template is not an image (or None)

            if region_height < h or region_width < w:
                continue
            
            for scale in np.linspace(0.9, 2.2, 18):
                scaled_template = cv2.resize(template, None, fx=scale, fy=scale, interpolation=cv2.INTER_AREA)
                if scaled_template.shape[0] > region_height or scaled_template.shape[1] > region_width:
                    continue
                result = cv2.matchTemplate(gray_img, scaled_template, method=cv2.TM_CCOEFF_NORMED)
                _, max_val, _, max_loc = cv2.minMaxLoc(result)
                if max_val >= 0.95:
                    value, suit_initial = card_name.split('_')
                    detected_values.add(f"{value}{suit_initial[0].upper()}")
                    top_left = max_loc
                    bottom_right = (top_left[0] + scaled_template.shape[1], top_left[1] + scaled_template.shape[0])
                    cv2.rectangle(gray_img, top_left, bottom_right, (0, 255, 0), 2)
                    break
        return list(detected_values)

    def check_hand_cards(self):
        """Check all hands for cards, iterate over both hand sides."""
        found_cards = {}
        for region_name, region in self.your_hand.items():
            for hand_side in self.your_hand:
                gray_img = self.capture_region(region)
                card_values = self.check_cards_in_hand(region, gray_img, hand_side)
                if card_values:
                    found_cards[region_name] = card_values
        return found_cards
    
    def hand_display(self, found_cards):
        """Update the display with detected card values and sums."""

        for region_name in self.hand_labels.keys():
            if region_name in found_cards:
                cards = found_cards[region_name]
                self.hand_labels[region_name].config(text=cards)
            else:
                self.hand_labels[region_name].config(text="--")
    
    def main_loop(self):
            """Main loop for detecting cards and updating the display."""
            while not self.stop_betting:  # Control the loop with the stop_betting flag
                board_detected = self.check_board_cards()
                self.board_display(board_detected)   
                hand_detected = self.check_hand_cards()
                self.hand_display(hand_detected)
                self.check_status()
                # try:
                #     board_detected = self.check_board_cards()
                #     self.board_display(board_detected)   
                #     hand_detected = self.check_hand_cards()
                #     self.hand_display(hand_detected)
                # except Exception as e:
                #     print(f"Error during loop execution: {e}")
                #     # Optionally, break or continue based on error severity
                #     continue  # or 'break' to exit the loop on error
            # Cleanup or finalize operations after the loop
            print("Stopping the betting session and cleaning up resources.")

    # Define placeholder methods for start_bet and stop_bets
    def start_bet(self):
        selected_port = arduino.com_entry.get().strip()

        if not selected_port:
            messagebox.showerror("Error", "Please select a COM port.")
            return
        
        else:
            """Start the betting session."""
            self.stop_betting = False  # Reset the flag to allow betting
            self.stop_button.grid()  # Show the stop button when bet starts
            self.start_button.grid_remove()  # Hide start button
            self.game_count = 0

            messagebox.showinfo("Info", "Game Started")

            # Start the detection thread if it's not already running
            if self.detection_thread is None or not self.detection_thread.is_alive():
                self.detection_thread = threading.Thread(target=self.main_loop)
                self.detection_thread.daemon = True  # Ensures the thread exits when the main program does
                self.detection_thread.start()

    def stop_bets(self):
        """Stop the betting session."""
        if messagebox.askokcancel("Warning", "Are you sure you want to stop?"):
            self.stop_betting = True  # Set the flag to stop betting

            self.start_button.grid()  # Show the start button again
            self.stop_button.grid_remove()  # Hide stop button
        
class ConsoleLog:
    def __init__(self, root, log_file=None):
        self.root = root
        formatted_now = datetime.now().strftime("%Y%m%d_%H%M%S")
        self.log_file = log_file if log_file else f"logs/log{formatted_now}.txt"

        # Create the console frame
        console_frame = tb.LabelFrame(self.root, text="Console", padding=10)
        console_frame.grid(row=4, column=0, sticky="news", padx=10, pady=5)

        # Create a ScrolledText widget for the console log
        self.console = scrolledtext.ScrolledText(console_frame, wrap=tb.WORD, width=51, height=5, state='normal')
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
    root.title("Poker Texas Hold'em")

    frame_config = tb.Frame(root)
    frame_config.grid(row=1, column=0, sticky="news")

    # Create an instance of ArduinoPort and pass the root window
    arduino = ArduinoPort(root)
    board = Boardcard(frame_config) 
    hand = Handcard(frame_config)
    console_log = ConsoleLog(root)  # Create the logging system instance

    sys.stdout = console_log  # Redirect stdout to console_log
    sys.stderr = console_log  # Also capture any error messages
    # Start the Tkinter event loop
    root.mainloop()