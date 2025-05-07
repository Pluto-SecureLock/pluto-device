# Pluto Device Project

Pluto Device is a secure hardware-based password manager and authenticator, designed to enhance both security and ease of use. It consists of multiple software modules that run on a microcontroller, handling fingerprint authentication, secure password storage, USB HID output for password auto-fill, and a rotary encoder for navigation.

---

## Architecture Overview

The project is organized around a central `ApplicationContext` that handles all interactions between modules:

* **Fingerprint Authentication**
* **USB Serial Communication**
* **HID Output (Keyboard Emulation)**
* **Secure Storage (KeyStore)**
* **Display Interface (Screen)**
* **Rotary Encoder for navigation**
* **State Management** for user interaction flows

The main application loop is initiated in `main.py`, where the `ApplicationContext` is created and updated in a continuous loop.

---

## Main Components

### 1. **ApplicationContext**

The core of the application that manages interactions between all components. It holds the current state, handles transitions, and interacts with hardware components:

* USB communication (`USBSerial`)
* HID output (`HIDOutput`)
* Fingerprint authentication (`FingerprintAuthenticator`)
* Secure vault management (`AuthManager` → `KeyStore`)
* Screen display (`Screen`)
* Rotary Encoder (`RotaryEncoderWithButton`)

### 2. **FingerprintAuthenticator**

Handles all interactions with the fingerprint sensor. It supports:

* Authentication (`authenticate`)
* Enrollment (`enroll`)
* Deletion (`delete`)
* Finger detection via IRQ (`finger_irq`)
* PIN-based protection

### 3. **USBSerial**

Manages communication over USB CDC:

* Reading commands from a host computer
* Writing responses or logs back to the host

### 4. **HIDOutput**

Emulates keyboard actions over USB:

* Typing text directly to the host computer (`type_text`)
* Sending special key strokes (Enter, Tab, etc.)

### 5. **AuthManager**

Manages user authentication, including:

* Verifying PINs
* Attaching fingerprint authenticator
* Loading and saving user credentials
* Accessing the `KeyStore` for password retrieval

### 6. **KeyStore**

Handles secure storage of credentials:

* Passwords are encrypted with AES before saving
* Supports CRUD operations for sites and credentials

### 7. **CommandProcessor**

Parses commands received via USB Serial and triggers the appropriate action:

* Commands like `get`, `add`, `delete` are processed here

### 8. **RotaryEncoderWithButton**

Handles user input through a rotary encoder with an integrated button:

* Rotation is mapped to scrolling or selection
* Button press is used for confirmation

### 9. **Screen**

Manages the display interface, including:

* Writing text and prompts
* Clearing the screen
* Updating text in specific positions

---

## State Management

Pluto Device uses a state-driven architecture for user flows:

* **SetupState** → Initial configuration, setting PIN.
* **UnblockState** → PIN verification to unlock the device.
* **AutoState** → Default mode, waiting for commands.
* **MenuState** → Navigation of options (Manual Mode, Password Suggestion, Settings).
* **AuthState** → Authentication mode for sensitive operations.
* **LoginState** → Allows credential selection and auto-fill.
* **PassLengthState** → Sets the length of generated passwords.
* **PassComplexState** → Defines password complexity.
* **PassSaveState** → Prompts to save newly generated passwords.
* **DomainEntryState** → Authenticates before saving credentials.
* **SettingsState** → Manages settings like changing PIN and updating fingerprints.

Each state inherits from `BaseState` and manages its own `enter`, `handle`, and `exit` logic.

---

## Getting Started

To run the application:

1. Deploy the code to your CircuitPython-compatible board.
2. Ensure the fingerprint sensor, rotary encoder, and display are correctly wired.
3. Ensure main is inside `code.py`, the could should auto-run in the device and auto compile for every line changed.
4. If you experience a ` Value Error: LED in use ` just press the BOOT button on the board, 
---

## Commands

The Pluto Device listens for specific commands over USB:

* `get <domain>`  → Retrieve credentials for a specific site.
* `add domain:username,password` → Add new credentials.
* `delete domain:username,password` → Remove credentials.

---

## Security Considerations

* All passwords are AES-encrypted before being saved.
* Fingerprint authentication is required for sensitive operations.
* PIN-based unlock mechanism prevents unauthorized access.

---

## Future Enhancements

* Enhanced brute-force protection
* Fingerprint image as AES Key
* Integration of Crypto Accelerator

---

## Contributing

* Feel free to submit PRs for bug fixes or feature improvements. Ensure code is well-documented and tested.
* To resolve an issue please add issue in PR `#IssueNumber` 
[AutoLink Issue with PR](https://docs.github.com/en/get-started/writing-on-github/working-with-advanced-formatting/autolinked-references-and-urls#issues-and-pull-requests)

---

## License

Apache 2.0 - See `LICENSE.md` for details.
""

