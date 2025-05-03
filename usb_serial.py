import usb_cdc
import sys
import supervisor

class USBSerial:
    """Reads a line from usb_cdc.data (non-blocking, up to end_char)"""
    def __init__(self):
        self._buffer = ''

    # def read(self, end_char='\n', echo=True):
    #     # Asegura que el puerto esté disponible y conectado
    #     if usb_cdc.data and usb_cdc.data.connected and usb_cdc.data.in_waiting > 0:
    #         incoming = usb_cdc.data.read(usb_cdc.data.in_waiting).decode('utf-8')
    #         if echo:
    #             usb_cdc.data.write(incoming.encode('utf-8'))  # eco si se desea
    #         self._buffer += incoming
    #         if self._buffer.endswith(end_char):
    #             command = self._buffer.strip()
    #             self._buffer = ''
    #             return command
    #     return None
    def read(self, end_char='\n', echo=True):
        n = supervisor.runtime.serial_bytes_available
        if n > 0:
            s = sys.stdin.read(n)
            if echo:
                sys.stdout.write(s)
            self._buffer += s
            if s.endswith(end_char):
                command = self._buffer.strip()
                self._buffer = ''
                return command
        return None
    def write(self, text):
        """Escribe texto al puerto usb_cdc.data."""
        if usb_cdc.data and usb_cdc.data.connected:
            usb_cdc.data.write(text.encode('utf-8'))
