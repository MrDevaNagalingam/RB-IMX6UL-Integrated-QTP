"""Host UART lifecycle and ESR0C-compatible V2 framing."""
import uuid

import struct
import time

# ESR0C active V2 format. Kept here to preserve the requested module layout.
def pack_frame(entries):
    payload = b""
    for kind, value in entries.items():
        raw = value.encode("utf-8") if isinstance(value, str) else value
        payload += struct.pack(">BH", kind, len(raw)) + raw
    if not 3 <= len(payload) <= 65535:
        raise ValueError("TLV payload exceeds V2 frame capacity")
    return struct.pack(">BHH", 0xAA, len(payload), sum(payload) % 0xFFFF) + payload + b"\xbb"


def unpack_frame(frame):
    if len(frame) < 9:
        raise ValueError("Short frame")
    start, length, checksum = struct.unpack(">BHH", frame[:5])
    payload = frame[5:-1]
    if (start != 0xAA or frame[-1] != 0xBB or length != len(payload)
            or sum(payload) % 0xFFFF != checksum):
        raise ValueError("Invalid frame or checksum")
    entries = {}
    pos = 0
    while pos < len(payload):
        if pos + 3 > len(payload):
            raise ValueError("Truncated TLV header")
        kind, size = struct.unpack(">BH", payload[pos:pos + 3])
        pos += 3
        if pos + size > len(payload) or kind in entries:
            raise ValueError("Truncated or duplicate TLV")
        entries[kind] = payload[pos:pos + size].decode("utf-8")
        pos += size
    return entries


class FrameReader:
    def __init__(self, serial_port, frame_timeout=15):
        self.serial = serial_port
        self.buffer = b""
        self.started = None
        self.frame_timeout = frame_timeout

    def read(self, timeout=None):
        deadline = None if timeout is None else time.monotonic() + timeout
        while deadline is None or time.monotonic() < deadline:
            start = self.buffer.find(b"\xaa")
            if start < 0:
                self.buffer = b""
                self.started = None
            elif start:
                self.buffer = self.buffer[start:]
                self.started = None
            if self.buffer:
                if self.started is None:
                    self.started = time.monotonic()
                if len(self.buffer) >= 5:
                    size = struct.unpack(">H", self.buffer[1:3])[0]
                    if size < 3:
                        self.buffer = self.buffer[1:]
                        self.started = None
                        continue
                    if len(self.buffer) >= size + 6:
                        frame = self.buffer[:size + 6]
                        try:
                            entries = unpack_frame(frame)
                        except (ValueError, UnicodeError):
                            self.buffer = self.buffer[1:]
                            self.started = None
                            continue
                        self.buffer = self.buffer[size + 6:]
                        self.started = None
                        return entries
                if time.monotonic() - self.started > self.frame_timeout:
                    self.buffer = self.buffer[1:]
                    self.started = None
                    continue
            chunk = self.serial.read(min(max(self.serial.in_waiting, 1), 4096))
            self.buffer += chunk
        return None


def write_frame(serial_port, frame):
    deadline = time.monotonic() + 15
    offset = 0
    while offset < len(frame):
        if time.monotonic() >= deadline:
            raise TimeoutError("UART write timed out")
        written = serial_port.write(frame[offset:])
        if not written:
            raise OSError("UART write made no progress")
        offset += written


class UARTCommunicator:
    def __init__(self, port, baudrate=115200):
        self.port = port
        self.baudrate = baudrate
        self.ser = None
        self.reader = None

    def connect(self):
        import serial
        self.ser = serial.Serial(self.port, self.baudrate, timeout=0.1)
        self.reader = FrameReader(self.ser)

    def disconnect(self):
        if self.ser is not None:
            self.ser.close()
            self.ser = None

    def send_and_receive(self, command, params=None, output_callback=None):
        if self.ser is None:
            raise OSError("UART is not connected")
        request_id = uuid.uuid4().hex
        # Type 3 is an RB correlation extension; types 1/2 retain ESR0C meanings.
        entries = {1: command, 3: request_id}
        if params is not None:
            entries[5] = params
        write_frame(self.ser, pack_frame(entries))
        while True:
            response = self.reader.read(1)
            if response is not None and response.get(3) == request_id and 4 in response:
                if output_callback is not None:
                    output_callback(response[4])
                continue
            if response is not None and response.get(3) == request_id and 2 in response:
                return response[2]

