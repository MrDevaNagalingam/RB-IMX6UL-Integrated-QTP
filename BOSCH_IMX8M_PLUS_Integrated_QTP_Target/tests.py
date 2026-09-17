import hashlib
import socket
import struct
import ipaddress
import json
import queue
import threading
import os
import stat
import tempfile
import time
import re
import subprocess

import config


BOOT_MODES = {
    0x0: "Boot from internal fuses",
    0x1: "USB Serial Downloader",
    0x2: "Boot from on-board eMMC U4",
    0x3: "Boot from external SD card SD2",
    0x6: "Boot from on-board QSPI Flash U5",
    0xF: "JTAG mode",
}


def result(test_id, status, details, measurements=None, output=""):
    return {
        "test_id": test_id,
        "status": status,
        "measurements": measurements or {},
        "details": details,
        "output": output,
    }


def indication_led_test(led, stream_callback=None):
    test_id = "LED{}_TEST".format(led)
    info = config.LEDS["led{}".format(led)]
    path = info["path"]
    gpio = info["gpio"]
    output = []
    errors = []
    brightness = os.path.join(path, "brightness")
    available = False

    def write_value(filename, value):
        with open(filename, "w") as stream:
            stream.write(value)

    def emit(message):
        output.append(message)
        if stream_callback:
            stream_callback(message + "\n")

    try:
        if os.geteuid() != 0:
            raise RuntimeError("Run target QTP as root.")
        if not os.path.isfile(brightness):
            raise RuntimeError(brightness + " not found")
        available = True
        trigger = os.path.join(path, "trigger")
        if os.path.exists(trigger):
            write_value(trigger, "none")
        emit("LED{}: {} | {} line {}".format(led, gpio, info["gpiochip"], info["line"]))
        write_value(brightness, "0")
        emit("LED{} -> ON ({} seconds)".format(led, config.LED_ON_TIME))
        write_value(brightness, "1")
        time.sleep(config.LED_ON_TIME)
        emit("LED{} -> OFF ({} seconds)".format(led, config.LED_OFF_TIME))
        write_value(brightness, "0")
        time.sleep(config.LED_OFF_TIME)
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))
    finally:
        if available:
            try:
                write_value(brightness, "0")
            except OSError as exc:
                errors.append("Unable to turn LED off: " + str(exc))
    status = "FAIL" if errors else "PASS"
    details = "Status   : {}".format(status)
    if errors:
        details += "\n" + "\n".join(errors)
    return result(test_id, status, details,
                  {"led": led, "gpio": gpio, "gpiochip": info["gpiochip"], "line": info["line"]},
                  "\n".join(output))


def uart1_debug_console_test():
    return result(
        "UART1_DEBUG_CONSOLE_TEST",
        "ABORTED",
        "UART1 is used for the debug console. UART1 test aborted.",
    )


def get_board_model():
    try:
        with open("/proc/device-tree/model", "rb") as stream:
            return stream.read().replace(b"\x00", b"").decode()
    except Exception:
        return "Unknown"


def read_src_sbmr2():
    try:
        completed = subprocess.run(
            ["devmem2", config.SRC_SBMR2_ADDR, "w"],
            capture_output=True,
            text=True,
            errors="replace",
            check=True,
        )
    except FileNotFoundError as exc:
        raise RuntimeError("devmem2 command not found") from exc
    except subprocess.CalledProcessError as exc:
        message = (exc.stderr or exc.stdout or "devmem2 failed").strip()
        raise RuntimeError(message) from exc

    match = re.search(r"Read at address.*:\s*(0x[0-9A-Fa-f]+)", completed.stdout)
    if not match:
        raise RuntimeError("Unable to parse devmem2 output")
    return int(match.group(1), 16), completed.stdout.strip()


def boot_mode_test():
    test_id = "BOOT_MODE_TEST"
    board = get_board_model()
    try:
        register_value, devmem_output = read_src_sbmr2()
    except RuntimeError as exc:
        return result(test_id, "FAIL", "Status   : FAIL\nError    : {}".format(exc))

    boot_mode = (register_value >> 24) & 0xF
    boot_mode0 = (boot_mode >> 0) & 1
    boot_mode1 = (boot_mode >> 1) & 1
    boot_mode2 = (boot_mode >> 2) & 1
    boot_mode3 = (boot_mode >> 3) & 1
    boot_source = BOOT_MODES.get(
        boot_mode, "Unknown / not defined in PHYTEC boot-mode table"
    )

    details = "\n".join(
        [
            "Status   : PASS",
            "Board       : {}".format(board),
            "SRC_SBMR2   : {}".format(config.SRC_SBMR2_ADDR),
            "SRC_SBMR2 value : 0x{:08X}".format(register_value),
            "X_BOOT_MODE3    : {}".format(boot_mode3),
            "X_BOOT_MODE2    : {}".format(boot_mode2),
            "X_BOOT_MODE1    : {}".format(boot_mode1),
            "X_BOOT_MODE0    : {}".format(boot_mode0),
            "BOOT_MODE[3:0]  : {}{}{}{}".format(
                boot_mode3, boot_mode2, boot_mode1, boot_mode0
            ),
            "Boot Mode       : {} (0x{:X})".format(boot_mode, boot_mode),
            "Boot Source     : {}".format(boot_source),
        ]
    )
    measurements = {
        "board": board,
        "src_sbmr2_addr": config.SRC_SBMR2_ADDR,
        "src_sbmr2_value": "0x{:08X}".format(register_value),
        "boot_mode": boot_mode,
        "boot_mode_bits": "{}{}{}{}".format(
            boot_mode3, boot_mode2, boot_mode1, boot_mode0
        ),
        "boot_source": boot_source,
    }
    return result(test_id, "PASS", details, measurements, devmem_output)


def logged_result(test_id, status, details, output, log_file, measurements=None):
    measurements = dict(measurements or {})
    try:
        os.makedirs(os.path.dirname(log_file), exist_ok=True)
        with open(log_file, "a", encoding="utf-8") as stream:
            stream.write("\n{} | {}\n{}\nResult: {}\n{}\n".format(
                time.strftime("%Y-%m-%d %H:%M:%S"), test_id, "\n".join(output), status, details))
            stream.flush()
            os.fsync(stream.fileno())
        measurements["log_file"] = log_file
    except OSError as exc:
        status = "FAIL"
        details = "Status   : FAIL\nUnable to save target log: {}\n{}".format(exc, details)
    return result(test_id, status, details, measurements)


def tpm_test(stream_callback=None):
    output = []
    measurements = {}

    def emit(text):
        output.append(text)

    try:
        for device in config.TPM_DEVICES:
            if not stat.S_ISCHR(os.stat(device).st_mode):
                raise RuntimeError("Not a TPM character device: " + device)
        emit("[TPM] Devices detected: " + ", ".join(config.TPM_DEVICES))
        # The kernel resource manager releases each tool's transient handles.
        env = dict(os.environ, TPM2TOOLS_TCTI=config.TPM_TCTI)
        with tempfile.TemporaryDirectory(prefix="qtp_tpm_") as directory:
            def command(args):
                emit("[TPM] Running: " + " ".join(args))
                completed = subprocess.run(args, cwd=directory, env=env,
                                           capture_output=True, text=True, errors="replace",
                                           timeout=config.TPM_COMMAND_TIMEOUT)
                output.extend([completed.stdout.strip(), completed.stderr.strip()])
                if completed.returncode:
                    raise RuntimeError("{} failed: {}".format(
                        args[0], completed.stderr.strip() or completed.stdout.strip()
                        or "exit code " + str(completed.returncode)))
                return completed.stdout.strip()

            random_hex = command(["tpm2_getrandom", "--hex", str(config.TPM_RANDOM_BYTES)])
            if re.fullmatch(r"[0-9a-fA-F]{" + str(config.TPM_RANDOM_BYTES * 2) + "}", random_hex) is None:
                raise RuntimeError("TPM random output has invalid length or format")
            measurements["random_bytes"] = config.TPM_RANDOM_BYTES
            emit("[TPM] Random data: PASS ({} bytes)".format(config.TPM_RANDOM_BYTES))
            command(["tpm2_createprimary", "-C", "o", "-g", "sha256", "-G", "rsa", "-c", "primary.ctx"])
            command(["tpm2_create", "-C", "primary.ctx", "-g", "sha256", "-G", "rsa",
                     "-u", "key.pub", "-r", "key.priv"])
            command(["tpm2_load", "-C", "primary.ctx", "-u", "key.pub", "-r", "key.priv", "-c", "key.ctx"])
            plaintext = config.TPM_TEST_TEXT.encode("utf-8")
            plain_path = os.path.join(directory, "plaintext.txt")
            with open(plain_path, "wb") as stream:
                stream.write(plaintext)
            command(["tpm2_rsaencrypt", "-c", "key.ctx", "-o", "ciphertext.bin", "plaintext.txt"])
            with open(os.path.join(directory, "ciphertext.bin"), "rb") as stream:
                ciphertext = stream.read()
            if not ciphertext or ciphertext == plaintext:
                raise RuntimeError("RSA encryption did not produce ciphertext")
            output.append("Ciphertext (hex): " + ciphertext.hex())
            os.remove(plain_path)
            command(["tpm2_rsadecrypt", "-c", "key.ctx", "-o", "decrypted.txt", "ciphertext.bin"])
            with open(os.path.join(directory, "decrypted.txt"), "rb") as stream:
                decrypted = stream.read()
            if decrypted != plaintext:
                raise RuntimeError("Decrypted data does not match the original plaintext")
            measurements["round_trip_verified"] = True
            emit("[TPM] RSA encrypt/decrypt data verification: PASS")
        status = "PASS"
        details = "TPM functionality: PASS | Random: PASS | RSA encrypt/decrypt: PASS | Data verify: PASS"
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        status = "FAIL"
        details = "TPM functionality: FAIL | " + str(exc)
        output.append(details)
    return logged_result("TPM_TEST", status, details, output, config.TPM_LOG_FILE, measurements)


def pcie_test(stream_callback=None):
    output = ["$ lspci -k"]
    measurements = {}
    try:
        completed = subprocess.run(["lspci", "-k"], capture_output=True, text=True,
                                   errors="replace", timeout=config.PCIE_COMMAND_TIMEOUT)
        output.extend([completed.stdout.strip(), completed.stderr.strip()])
        if completed.returncode:
            raise RuntimeError("lspci failed: " + (completed.stderr.strip()
                               or "exit code " + str(completed.returncode)))
        blocks = re.split(r"(?m)(?=^\S)", completed.stdout)
        device = next((block for block in blocks
                       if block.startswith(config.PCIE_DEVICE + " ")
                       or block.startswith("0000:" + config.PCIE_DEVICE + " ")), "")
        header = device.splitlines()[0] if device else ""
        if "PCI bridge:" not in header or config.PCIE_VENDOR not in header:
            raise RuntimeError("Expected PCIe bridge not found at " + config.PCIE_DEVICE)
        driver = re.search(r"Kernel driver in use:\s*(\S+)", device)
        if driver is None or driver.group(1) != config.PCIE_DRIVER:
            raise RuntimeError("Expected active driver {} on {}".format(config.PCIE_DRIVER, config.PCIE_DEVICE))
        measurements = {"device": config.PCIE_DEVICE, "driver": driver.group(1)}
        status = "PASS"
        details = "PCIe controller: PASS | Device: {} | Driver: {}".format(config.PCIE_DEVICE, driver.group(1))
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        status = "FAIL"
        details = "PCIe controller: FAIL | " + str(exc)
        output.append(details)
    return logged_result("PCIE_TEST", status, details, output, config.PCIE_LOG_FILE, measurements)


def usb_bluetooth_test(params=None, stream_callback=None):
    output = []
    errors = []
    devices = []
    powered = False

    def command(args, timeout=15):
        output.append("$ " + " ".join(args))
        if stream_callback:
            stream_callback("[BT] Running: " + " ".join(args) + "\n")
        completed = subprocess.run(args, capture_output=True, text=True, errors="replace", timeout=timeout)
        text = (completed.stdout or "") + (completed.stderr or "")
        text = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", text)
        output.append(text.strip())
        if completed.returncode or re.search(r"Failed|not available|No default controller", text, re.I):
            raise RuntimeError(text.strip() or "Command failed: " + " ".join(args))
        return text

    try:
        usb = command(["lsusb"])
        if config.BT_USB_ID.lower() not in usb.lower():
            raise RuntimeError("Expected USB Bluetooth adapter {} not found".format(config.BT_USB_ID))
        command(["systemctl", "start", config.BT_SERVICE])
        powered = True
        command(["hciconfig", config.BT_HCI, "up"])
        hci = command(["hciconfig", config.BT_HCI, "-a"])
        address = re.search(r"BD Address:\s*([0-9A-F:]{17})", hci, re.I)
        if "Bus: USB" not in hci or not address:
            raise RuntimeError("Configured HCI is not a USB Bluetooth controller")
        process = subprocess.Popen(["bluetoothctl"], stdin=subprocess.PIPE,
                                   stdout=subprocess.PIPE, stderr=subprocess.STDOUT,
                                   text=True, errors="replace", bufsize=1)
        pending = queue.Queue()
        scan_lines = []

        def read_session():
            try:
                for line in process.stdout:
                    pending.put(line)
            finally:
                pending.put(None)

        reader = threading.Thread(target=read_session, daemon=True)
        reader.start()

        def send(text):
            output.append("[bluetoothctl] " + text)
            if stream_callback:
                stream_callback("[BT] " + text + "\n")
            process.stdin.write(text + "\n")
            process.stdin.flush()

        def receive(wait=0.25, scanning=False):
            try:
                raw = pending.get(timeout=wait)
            except queue.Empty:
                return ""
            if raw is None:
                raise RuntimeError("bluetoothctl session exited unexpectedly")
            line = re.sub(r"\x1b\[[0-?]*[ -/]*[@-~]", "", raw).strip()
            if line:
                output.append(line)
                if scanning:
                    scan_lines.append(line)
                if stream_callback and (scanning or "Device " in line):
                    stream_callback(line + "\n")
            return line

        def expect(text, pattern, scanning=False):
            send(text)
            deadline = time.monotonic() + config.BT_CONTROLLER_TIMEOUT
            while time.monotonic() < deadline:
                line = receive(scanning=scanning)
                if re.search(pattern, line, re.I):
                    return
                if re.search(r"Failed|not available|No default controller", line, re.I):
                    raise RuntimeError(text + ": " + line)
            raise RuntimeError("No confirmation for bluetoothctl " + text)

        scanning = False
        try:
            # Keep one client alive while BlueZ discovers its controllers.
            deadline = time.monotonic() + config.BT_CONTROLLER_TIMEOUT
            ready = False
            while time.monotonic() < deadline and not ready:
                send("list")
                poll_until = min(deadline, time.monotonic() + 1)
                while time.monotonic() < poll_until:
                    line = receive()
                    if re.search(r"Controller\s+" + re.escape(address[1]), line, re.I):
                        ready = True
                        break
            if not ready:
                raise RuntimeError("Configured Bluetooth controller was not registered with BlueZ")
            # BlueZ silently succeeds when this controller is already selected.
            send("select " + address[1])
            expect("show", r"Controller\s+" + re.escape(address[1]) + r"(?:\s+\((?:public|random)\))?\s*$")
            expect("power on", r"Changing power on succeeded|Powered:\s*yes")
            expect("agent on", r"Agent registered|Agent is already registered")
            expect("default-agent", r"Default agent request successful")
            scanning = True
            expect("scan on", r"Discovery started|Discovering:\s*yes", scanning=True)
            deadline = time.monotonic() + config.BT_SCAN_SECONDS
            while time.monotonic() < deadline:
                line = receive(scanning=True)
                if re.search(r"Failed to start discovery|Discovery stopped", line, re.I):
                    raise RuntimeError("Discovery stopped before the scan completed")
            expect("scan off", r"Discovery stopped|Discovering:\s*no")
            scanning = False
            devices = sorted(set(re.findall(
                r"\[(?:NEW|CHG)\]\s+Device\s+([0-9A-F:]{17})", "\n".join(scan_lines), re.I)))
        finally:
            try:
                if process.poll() is None:
                    if scanning:
                        send("scan off")
                    send("quit")
                    process.wait(timeout=5)
            except (OSError, subprocess.TimeoutExpired):
                process.kill()
                process.wait()
            finally:
                if process.poll() is None:
                    process.kill()
                    process.wait()
                reader.join(timeout=5)
                process.stdin.close()
                process.stdout.close()
        if not devices:
            raise RuntimeError("No devices observed during this scan. Enable discovery on a nearby device and retry.")
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        errors.append(str(exc))
    finally:
        if powered:
            # Exiting the persistent bluetoothctl client releases discovery and its agent.
            for args in (["bluetoothctl", "power", "off"], ["hciconfig", config.BT_HCI, "down"]):
                try:
                    command(args)
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    errors.append("Cleanup failed: " + str(exc))
    status = "FAIL" if errors else "PASS"
    details = "USB Bluetooth: {} | Devices observed: {}".format(status, len(devices))
    if errors:
        details += "\n" + "\n".join(errors)
    return logged_result("USB_BLUETOOTH_TEST", status, details, output, config.BT_LOG_FILE,
                         {"controller": config.BT_HCI, "devices": devices})


def hdmi_test(stream_callback=None):
    output = []
    errors = []
    stopped = False
    socket_active = False

    def emit(message):
        output.append(message)

    def command(args, timeout=20):
        emit("$ " + " ".join(args))
        completed = subprocess.run(args, capture_output=True, text=True, timeout=timeout)
        for text in (completed.stdout, completed.stderr):
            if text and text.strip():
                emit(text.strip())
        if completed.returncode:
            raise RuntimeError("Command failed: " + " ".join(args))
        return completed.stdout

    try:
        check = subprocess.run(["systemctl", "is-active", config.HDMI_WESTON_SOCKET],
                               capture_output=True, text=True, timeout=20)
        socket_active = check.returncode == 0
        # Prevent socket activation from restarting Weston while fbtest owns the display.
        stopped = True
        if socket_active:
            command(["systemctl", "stop", config.HDMI_WESTON_SOCKET])
        command(["systemctl", "stop", config.HDMI_WESTON_SERVICE])
        emit("Observe the HDMI display while fbtest runs.")
        text = command(["fbtest"], timeout=config.HDMI_FBTEST_TIMEOUT)
        if re.search(r"\bFAILED\b", text, re.IGNORECASE):
            raise RuntimeError("fbtest reported a failed test")
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        errors.append(str(exc))
    finally:
        if stopped:
            units = ([config.HDMI_WESTON_SOCKET] if socket_active else []) + [config.HDMI_WESTON_SERVICE]
            for unit in units:
                try:
                    command(["systemctl", "start", unit])
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    errors.append("Weston restart failed: " + str(exc))
    status = "FAIL" if errors else "PASS"
    details = "Status   : {}\n{}".format(status, "\n".join(errors) if errors else
        "fbtest completed; Weston restarted. HDMI visual confirmation required.")
    return logged_result("HDMI_TEST", status, details, output, config.HDMI_LOG_FILE)


def can_loopback_test(stream_callback=None):
    output = []
    host_output = []
    directions = []

    def emit(message, quiet=False):
        output.append(message)
        if not quiet:
            host_output.append(message)
            if stream_callback:
                stream_callback(message + "\n")

    def command(args, quiet=False):
        emit("$ " + " ".join(args), quiet=quiet)
        completed = subprocess.run(args, capture_output=True, text=True, timeout=10)
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or completed.stdout.strip() or "CAN command failed")
        if completed.stdout.strip():
            emit(completed.stdout.strip(), quiet=quiet)

    status = "FAIL"
    try:
        for interface in config.CAN_INTERFACES:
            command(["ip", "link", "set", interface, "down"], quiet=True)
        for interface in config.CAN_INTERFACES:
            command(["ip", "link", "set", interface, "type", "can", "bitrate",
                     str(config.CAN_BITRATE), "loopback", "off", "listen-only", "off"])
        for interface in config.CAN_INTERFACES:
            command(["ip", "link", "set", interface, "up"], quiet=True)
        for interface in config.CAN_INTERFACES:
            command(["ip", "-details", "link", "show", interface], quiet=True)

        for index, frame in enumerate(config.CAN_TEST_FRAMES):
            source = config.CAN_INTERFACES[index]
            destination = config.CAN_INTERFACES[1 - index]
            frame_id, payload = frame.split("#")
            expected_id = int(frame_id, 16)
            expected_data = bytes.fromhex(payload)
            emit("\n{} -> {} | Expected: {}".format(source, destination, frame))
            # Bind before transmitting; receive only the requested standard data ID.
            with socket.socket(socket.AF_CAN, socket.SOCK_RAW, socket.CAN_RAW) as receiver:
                # CAN_ERR_FLAG in the mask selects error frames, not data frames.
                receiver.setsockopt(socket.SOL_CAN_RAW, socket.CAN_RAW_FILTER,
                                    struct.pack("=II", expected_id, 0xC00007FF))
                receiver.bind((destination,))
                command(["cansend", source, frame])
                deadline = time.monotonic() + config.CAN_RX_TIMEOUT
                while True:
                    remaining = deadline - time.monotonic()
                    if remaining <= 0:
                        raise RuntimeError("Timeout waiting for {} on {}".format(frame, destination))
                    receiver.settimeout(remaining)
                    try:
                        packet = receiver.recv(16)
                    except socket.timeout as exc:
                        raise RuntimeError("Timeout waiting for {} on {}".format(frame, destination)) from exc
                    if len(packet) != 16:
                        continue
                    received_id, size, data = struct.unpack("=IB3x8s", packet)
                    if received_id != expected_id:
                        continue
                    if size != len(expected_data) or data[:size] != expected_data:
                        raise RuntimeError("CAN payload mismatch on {}: {}#{}, length {}".format(
                            destination, frame_id, data[:size].hex().upper(), size))
                    break
            emit("Received: {} {} [{}] {} | PASS".format(
                destination, frame_id, size, " ".join("{:02X}".format(b) for b in data[:size])))
            directions.append({"source": source, "destination": destination, "frame": frame, "status": "PASS"})
        status = "PASS"
        details = "CAN0 -> CAN1: PASS | CAN1 -> CAN0: PASS | Bitrate: {}".format(config.CAN_BITRATE)
    except (OSError, RuntimeError, ValueError, AttributeError, subprocess.TimeoutExpired) as exc:
        details = "CAN loopback failed: " + str(exc)
        emit(details)
    answer = logged_result("CAN_LOOPBACK_TEST", status, details, output, config.CAN_LOG_FILE,
                           {"bitrate": config.CAN_BITRATE, "directions": directions})
    answer["output"] = "\n".join(host_output)
    return answer


def prepare_ethernet(index, stream_callback=None):
    test_id = "ETHERNET{}_PREPARE".format(index)
    interface = config.ETH_INTERFACES[index]
    other = config.ETH_INTERFACES[1 - index]
    output = []
    try:
        for args in (["ifconfig", other, "0.0.0.0", "down"],
                     ["ifconfig", interface, "up"]):
            message = "[TARGET] " + " ".join(args)
            output.append(message)
            if stream_callback:
                stream_callback(message + "\n")
            completed = subprocess.run(args, capture_output=True, text=True, timeout=15)
            if completed.returncode:
                raise RuntimeError(completed.stderr.strip() or "Command failed: " + " ".join(args))
        return result(test_id, "PASS", "{} enabled; {} disabled".format(interface, other),
                      {"interface": interface}, "\n".join(output))
    except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
        return result(test_id, "FAIL", str(exc), output="\n".join(output))


def ethernet_throughput_test(index, params=None, stream_callback=None):
    test_id = "ETHERNET{}_TEST".format(index)
    interface = config.ETH_INTERFACES[index]
    output = []
    process = None
    reader = None
    added_address = False
    board = None
    status = "FAIL"
    details = ""
    measurements = {"interface": interface, "duration": config.ETH_DURATION,
                    "threshold_mbps": config.ETH_MIN_MBPS, "samples": []}
    separator = "-" * 62

    def emit(message):
        output.append(message)
        if stream_callback:
            stream_callback(message + "\n")

    def command(args):
        completed = subprocess.run(args, capture_output=True, text=True, timeout=15)
        if completed.returncode:
            raise RuntimeError(completed.stderr.strip() or "Command failed: " + " ".join(args))
        return completed.stdout

    try:
        host = str(ipaddress.IPv4Address(params["host_ip"]))
        board = ipaddress.IPv4Interface(params["board_cidr"])
        if ipaddress.IPv4Address(host) not in board.network or host == str(board.ip):
            raise ValueError("Host and board need different addresses in the same subnet")
        emit("  [STEP-3] Ethernet PHY / Interface Detection")
        command(["ip", "link", "show", "dev", interface])
        emit("  Interface         : {}\n  Connector         : X{}\n  Status            : PASS".format(interface, index + 8))
        emit(separator)
        emit("  [STEP-4] Ethernet Interface Status Check")
        emit("  Command           : ip link show dev " + interface)
        link_deadline = time.monotonic() + config.ETH_LINK_TIMEOUT
        while True:
            with open("/sys/class/net/{}/carrier".format(interface)) as stream:
                if stream.read().strip() == "1":
                    break
            if time.monotonic() >= link_deadline:
                raise RuntimeError("No Ethernet link. Connect the cable to the selected port.")
            time.sleep(0.5)
        emit("  Link Status       : ACTIVE\n  Status            : PASS")
        emit(separator)
        emit("  [STEP-5] Network Configuration")
        addresses = json.loads(command(["ip", "-j", "-4", "addr", "show", "dev", interface]))
        existing = [a["local"] for entry in addresses for a in entry.get("addr_info", [])]
        if str(board.ip) not in existing:
            command(["ip", "addr", "add", str(board), "dev", interface])
            added_address = True
        emit("  Assigned IP Address : {}\n  PC IP Address       : {}".format(board, host))
        command(["ping", "-I", interface, "-c", "3", "-W", "2", host])
        emit("  Ping Status         : PASS\n  Status              : PASS")
        emit(separator)
        emit("  [STEP-6] iPerf Client Execution (i.MX8M Plus)")
        emit("  Command Executed  : iperf3 -c {} -p {} -t {} -i {} -B {} --bind-dev {} --forceflush -f m".format(
            host, config.ETH_PORT, config.ETH_DURATION, config.ETH_INTERVAL, board.ip, interface))
        emit("  Test Duration     : {} seconds".format(config.ETH_DURATION))
        emit(separator)
        emit("  [INFO] Throughput Monitoring Started")
        process = subprocess.Popen(
            ["iperf3", "-c", host, "-p", str(config.ETH_PORT),
             "-t", str(config.ETH_DURATION), "-i", str(config.ETH_INTERVAL),
             "-B", str(board.ip), "--bind-dev", interface, "--forceflush", "-f", "m"],
            stdout=subprocess.PIPE, stderr=subprocess.STDOUT, text=True)
        lines = queue.Queue()

        def read_output():
            try:
                for line in process.stdout:
                    lines.put(line.rstrip())
            finally:
                lines.put(None)

        reader = threading.Thread(target=read_output, daemon=True)
        reader.start()
        deadline = time.monotonic() + config.ETH_DURATION + 30
        receiver = None
        while True:
            if time.monotonic() >= deadline:
                raise RuntimeError("iperf3 timed out")
            try:
                line = lines.get(timeout=0.5)
            except queue.Empty:
                continue
            if line is None:
                break
            interval = re.search(
                r"\]\s+(\d+(?:\.\d+)?)-(\d+(?:\.\d+)?)\s+sec\s+"
                r"(\d+(?:\.\d+)?)\s+([KMGT]?Bytes)\s+(\d+(?:\.\d+)?)\s+Mbits/sec", line)
            if interval and "sender" not in line and "receiver" not in line:
                start, end, transfer, unit, bandwidth = interval.groups()
                measurements["samples"].append({"start": float(start), "end": float(end),
                    "transfer": float(transfer), "unit": unit, "mbps": float(bandwidth)})
                emit("{} | TC-06 | ETH{} | Interval {}-{} sec | Transfer: {} {} | Bandwidth: {} Mbits/sec | {}".format(
                    time.strftime("%Y-%m-%d %H:%M:%S"), index, start, end, transfer, unit, bandwidth,
                    "PASS" if float(bandwidth) > config.ETH_MIN_MBPS else "FAIL"))
            elif "error" in line.lower():
                emit(line)
            match = re.search(r"(\d+(?:\.\d+)?)\s+Mbits/sec.*receiver", line)
            if match:
                receiver = float(match[1])
                if interval:
                    measurements["completed_seconds"] = float(interval[2]) - float(interval[1])
                    measurements["receiver_transfer"] = "{} {}".format(interval[3], interval[4])
        if process.wait(timeout=5) != 0 or receiver is None or receiver <= config.ETH_MIN_MBPS:
            raise RuntimeError("iperf3 failed or receiver throughput was missing/below threshold")
        measurements["receiver_mbps"] = receiver
        if measurements["samples"]:
            measurements["min_mbps"] = min(s["mbps"] for s in measurements["samples"])
        status = "PASS"
        details = "{} throughput: {:.2f} Mbit/s | Duration: {} sec".format(
            interface, receiver, config.ETH_DURATION)
    except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as exc:
        details = str(exc)
    finally:
        if process is not None:
            if process.poll() is None:
                process.kill()
            process.wait()
            if reader is not None:
                reader.join(timeout=5)
            if process.stdout:
                process.stdout.close()
        if added_address:
            try:
                command(["ip", "addr", "del", str(board), "dev", interface])
            except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                status = "FAIL"
                details += "\nAddress cleanup failed: " + str(exc)
    return result(test_id, status, details, measurements, "\n".join(output))


def run_command(command):
    completed = subprocess.run(command, capture_output=True, text=True, check=False)
    if completed.returncode:
        raise RuntimeError(completed.stderr.strip() or "Command failed: " + " ".join(command))


def mounted_at(device):
    with open("/proc/mounts", encoding="utf-8") as stream:
        for line in stream:
            fields = line.split()
            if len(fields) >= 2:
                source, destination = [
                    re.sub(r"\\([0-7]{3})", lambda m: chr(int(m[1], 8)), field)
                    for field in fields[:2]
                ]
                if os.path.realpath(source) == os.path.realpath(device):
                    return destination
    return None


def sd_card_rw_delete_test(stream_callback=None):
    output = []
    full_output = ["=" * 42, "SD Card Read / Write / Delete Test",
                   time.strftime("Started: %Y-%m-%d %H:%M:%S"), "=" * 42]
    cycles = []
    errors = []
    mounted_by_test = False
    mount_point = None

    def emit(message, target_only=False):
        full_output.append(message)
        if not target_only:
            compact = re.sub(r"\b[0-9a-f]{64}\b", lambda match: "..." + match[0][-6:], message)
            output.append(compact)
            if stream_callback:
                stream_callback(compact + "\n")

    try:
        if os.geteuid() != 0:
            raise RuntimeError("Run target QTP as root.")
        if not stat.S_ISBLK(os.stat(config.SD_DEVICE).st_mode):
            raise RuntimeError("SD device is not a block device: " + config.SD_DEVICE)
        emit("Device: {} | File size: {} bytes | Iterations: {}".format(
            config.SD_DEVICE, config.SD_FILE_SIZE, config.SD_ITERATIONS))
        mount_point = mounted_at(config.SD_DEVICE)
        if mount_point is None:
            mount_point = config.SD_MOUNT_POINT
            os.makedirs(mount_point, exist_ok=True)
            if os.path.ismount(mount_point):
                raise RuntimeError("Mount point is already occupied: " + mount_point)
            emit("Mounting {} at {}...".format(config.SD_DEVICE, mount_point), target_only=True)
            run_command(["mount", config.SD_DEVICE, mount_point])
            mounted_by_test = True
        emit("Mount point: " + mount_point)
        with tempfile.TemporaryDirectory(prefix="qtp_sd_", dir=mount_point) as directory:
            path = os.path.join(directory, "sd_rw_test_10MB.bin")
            for iteration in range(1, config.SD_ITERATIONS + 1):
                cycle = {"iteration": iteration, "status": "FAIL"}
                emit("ITERATION {}/{}".format(iteration, config.SD_ITERATIONS))
                try:
                    emit("Writing {} bytes -> {}".format(config.SD_FILE_SIZE, path), target_only=True)
                    start = time.monotonic()
                    write_hash = hashlib.sha256()
                    remaining = config.SD_FILE_SIZE
                    with open(path, "xb") as stream:
                        while remaining:
                            data = os.urandom(min(config.SD_CHUNK_SIZE, remaining))
                            stream.write(data)
                            write_hash.update(data)
                            remaining -= len(data)
                        stream.flush()
                        os.fsync(stream.fileno())
                    cycle.update(write_seconds=time.monotonic() - start,
                                 write_sha256=write_hash.hexdigest())
                    if os.path.getsize(path) != config.SD_FILE_SIZE:
                        raise RuntimeError("Written file size mismatch")
                    emit("Written: {} bytes".format(os.path.getsize(path)), target_only=True)
                    emit("Write SHA256: {} | Time: {:.2f} sec".format(
                        cycle["write_sha256"], cycle["write_seconds"]))
                    start = time.monotonic()
                    emit("Reading complete test file...", target_only=True)
                    read_hash = hashlib.sha256()
                    total = 0
                    with open(path, "rb") as stream:
                        while True:
                            data = stream.read(config.SD_CHUNK_SIZE)
                            if not data:
                                break
                            read_hash.update(data)
                            total += len(data)
                    cycle.update(read_seconds=time.monotonic() - start,
                                 read_sha256=read_hash.hexdigest(), bytes_read=total)
                    emit("Read SHA256: {} | Bytes: {} | Time: {:.2f} sec".format(
                        cycle["read_sha256"], total, cycle["read_seconds"]))
                    if total != config.SD_FILE_SIZE or read_hash.digest() != write_hash.digest():
                        raise RuntimeError("Read size or SHA256 verification failed")
                    emit("Data verify: PASS")
                    emit("Deleting " + path, target_only=True)
                    os.remove(path)
                    run_command(["sync"])
                    if os.path.lexists(path):
                        raise RuntimeError("File deletion failed")
                    emit("Delete: PASS")
                    cycle["status"] = "PASS"
                except (OSError, RuntimeError) as exc:
                    cycle["error"] = str(exc)
                    emit("Reason: " + str(exc))
                finally:
                    if os.path.lexists(path):
                        os.remove(path)
                cycles.append(cycle)
                emit("ITERATION {}: {}".format(iteration, cycle["status"]))
                emit("")
    except (OSError, RuntimeError) as exc:
        errors.append(str(exc))
        emit("ERROR: " + str(exc))
    finally:
        if mounted_by_test:
            try:
                emit("Unmounting {}...".format(mount_point), target_only=True)
                run_command(["umount", mount_point])
            except (OSError, RuntimeError) as exc:
                errors.append("Unmount failed: " + str(exc))
                emit(errors[-1])
    passed = sum(cycle["status"] == "PASS" for cycle in cycles)
    status = "PASS" if passed == config.SD_ITERATIONS and not errors else "FAIL"
    emit("\nFINAL RESULT\nTotal Tests: {}\nPassed: {}\nFailed: {}\nSD CARD TEST: {}".format(
        config.SD_ITERATIONS, passed, len(cycles) - passed, status), target_only=True)
    log_saved = False
    try:
        os.makedirs(os.path.dirname(config.SD_LOG_FILE), exist_ok=True)
        with open(config.SD_LOG_FILE, "a", encoding="utf-8") as stream:
            stream.write("\n".join(full_output) + "\n" + "=" * 42 + "\n\n")
            stream.flush()
            os.fsync(stream.fileno())
        log_saved = True
    except OSError as exc:
        errors.append("Unable to save target SD log: " + str(exc))
        status = "FAIL"
    details = "SD card test: {} | Passed: {}/{}".format(status, passed, config.SD_ITERATIONS)
    if errors:
        details += "\n" + "\n".join(errors)
    for cycle in cycles:
        for key in ("write_sha256", "read_sha256"):
            if key in cycle:
                cycle[key + "_suffix"] = cycle.pop(key)[-6:]
    return {"test_id": "SD_CARD_RW_DELETE_TEST", "status": status,
            "details": details, "output": "\n".join(output),
            "measurements": {"device": config.SD_DEVICE, "iterations": cycles,
                             "passed": passed, "file_size": config.SD_FILE_SIZE,
                             "log_file": config.SD_LOG_FILE if log_saved else None}}
