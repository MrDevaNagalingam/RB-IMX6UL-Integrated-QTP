"""Target UART protocol, frame parsing and command dispatch."""
import json
import struct
import time

import tests

COMMANDS = {
    "DDR_TEST": lambda stream_callback=None, params=None: tests.ram_test("DDR_TEST", stream_callback),
    "NAND_RW_TEST": lambda stream_callback=None, params=None: tests.nand_test("NAND_RW_TEST"),
    "UART1_DEBUG_TEST": lambda stream_callback=None, params=None: tests.uart1_debug_test(params),
    "UART2_RS232_TEST": lambda stream_callback=None, params=None: tests.uart2_rs232_test(params),
    "UART3_LOOPBACK_TEST": lambda stream_callback=None, params=None: tests.uart3_loopback_test(params),
    "UART5_BLE_WIFI_TEST": lambda stream_callback=None, params=None: tests.uart5_ble_wifi_test(params),
    "UART6_RS485_TEST": lambda stream_callback=None, params=None: tests.uart6_rs485_test(params),
}


def handle_command(command, parameters=None, stream_callback=None):
    if not isinstance(command, str) or command not in COMMANDS:
        return tests.result(command if isinstance(command, str) else None,
                            "NOT_IMPLEMENTED", "Unsupported command.")
    try:
        return COMMANDS[command](stream_callback, parameters)
    except KeyboardInterrupt:
        details = "Interrupted by user."
        if command == "NAND_RW_TEST":
            details += " NAND contents may not be restored."
        return tests.result(command, "ERROR", details)
    except Exception as exc:
        return tests.result(command, "ERROR", str(exc))


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

    def read(self, timeout):
        deadline = time.monotonic() + timeout
        while time.monotonic() < deadline:
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
    offset = 0
    while offset < len(frame):
        written = serial_port.write(frame[offset:offset + 1024])
        if not written:
            raise OSError("UART write made no progress")
        offset += written
    serial_port.flush()


def build_response(entries, stream_callback=None):
    command = entries.get(1)
    request_id = entries.get(3)
    parameters = None
    if 5 in entries:
        try:
            parameters = json.loads(entries[5])
        except (TypeError, ValueError):
            parameters = "__INVALID_JSON__"
    if (command is None or len(command) > 64 or set(entries) - {1, 3, 5}
            or (request_id is not None and (len(request_id) != 32
                or any(c not in "0123456789abcdef" for c in request_id)))):
        answer = tests.result(None, "ERROR", "Invalid command TLVs")
    elif parameters == "__INVALID_JSON__":
        answer = tests.result(command, "ERROR", "Invalid parameter JSON")
    else:
        answer = handle_command(command, parameters=parameters, stream_callback=stream_callback)
    encoded = json.dumps(answer, ensure_ascii=True)
    while len(encoded.encode("utf-8")) > 60000 and answer.get("output"):
        answer["output"] = answer["output"][:len(answer["output"]) // 2]
        answer["output_truncated"] = True
        encoded = json.dumps(answer, ensure_ascii=True)
    if len(encoded.encode("utf-8")) > 60000:
        encoded = json.dumps(tests.result(command, "ERROR", "Result exceeds protocol capacity"))
    response = {2: encoded}
    if request_id is not None and len(request_id) <= 64:
        response[3] = request_id
    return pack_frame(response)


def serve(serial_port, stop=None):
    reader = FrameReader(serial_port)
    while stop is None or not stop.is_set():
        entries = reader.read(0.5)
        if entries is not None:
            command = entries.get(1)
            request_id = entries.get(3)
            print("Received command: {}".format(command), flush=True)
            def stream_callback(text):
                response = {4: text}
                if request_id is not None and len(request_id) <= 64:
                    response[3] = request_id
                write_frame(serial_port, pack_frame(response))
            try:
                write_frame(serial_port, build_response(entries, stream_callback))
            except (OSError, TimeoutError) as exc:
                print("[QTP] Target error: {}".format(exc), flush=True)
