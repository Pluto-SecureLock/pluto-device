import board
import displayio
import terminalio
from adafruit_display_text import label
from adafruit_displayio_ssd1306 import SSD1306
import busio

class Screen:
    def __init__(self, i2c=None, width=128, height=32, address=0x3C):
        # Release any previous displays
        displayio.release_displays()

        # Initialize I2C if not provided
        if i2c is None:
            i2c = busio.I2C(board.SCL, board.SDA)

        # Initialize display bus
        display_bus = displayio.I2CDisplay(i2c, device_address=address)

        # Create the display object
        self.display = SSD1306(display_bus, width=width, height=height)
        # Rotate the display 180 degrees
        self.display.rotation = 180  
        # Create a group to manage display content
        self.splash = displayio.Group()
        self.display.root_group = self.splash

        # Dictionary to store text dlabels
        self.text_labels = {}

        # Mapping for line numbers to coordinates
        self.line_map = {
            1: (0, 10),
            2: (0, 20),
            3: (0, 30),
            4: (0, 40)
        }

    def clear(self):
        """Clears the screen by removing all elements from the group."""
        self.splash = displayio.Group()
        self.display.root_group = self.splash
        self.text_labels.clear()

    def write(self, text, line=1, color=0xFFFFFF, background_color=None, scale=1, identifier=None):
        """
        Displays the provided text on the screen at the specified line.

        :param text: Text to display.
        :param line: Line number (1, 2, 3, 4, etc.)
        :param color: Text color in hexadecimal format (default: white).
        :param background_color: Background color in hexadecimal format (default: None).
        :param scale: Text scale (size).
        :param identifier: Unique identifier for the text label.
        """
        if line not in self.line_map:
            raise ValueError(f"Line {line} is not valid. Available lines: {list(self.line_map.keys())}")

        x, y = self.line_map[line]

        text_area = label.Label(
            terminalio.FONT,
            text=text,
            color=color,
            background_color=background_color,
            scale=scale,
            x=x,
            y=y
        )
        self.splash.append(text_area)
        if identifier:
            self.text_labels[identifier] = text_area

    def update(self, identifier, new_text):
        """
        Updates the text of an existing label identified by 'identifier'.

        :param identifier: Unique identifier of the text label to update.
        :param new_text: New text to display.
        """
        if identifier in self.text_labels:
            self.text_labels[identifier].text = new_text
        else:
            raise ValueError(f"No text label found with identifier '{identifier}'.")
        
    def save_state(self):
        """
        Saves the current state of the screen labels.
        Returns a dictionary with the identifier as key and text as value.
        """
        saved_state = {}
        for identifier, text_label in self.text_labels.items():
            saved_state[identifier] = text_label
        return saved_state
    
    def restore_state(self, saved_state):
        """
        Restores the screen to a previously saved state.

        :param saved_state: A dictionary with the identifier as key and text as value.
        """
        self.clear()
        # Re-create the text labels exactly as they were
        for identifier, text_area in saved_state.items():
            if identifier not in self.text_labels:
                self.text_labels[identifier] = text_area
            else:
                pass

                
    def remove(self, identifier):
        """
        Removes the text label identified by 'identifier' from the display.

        :param identifier: Unique identifier of the text label to remove.
        """
        if identifier in self.text_labels:
            text_area = self.text_labels.pop(identifier)
            self.splash.remove(text_area)
        else:
            raise ValueError(f"No text label found with identifier '{identifier}'.")
""
