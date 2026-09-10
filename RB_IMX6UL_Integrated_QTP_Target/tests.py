"""RAM and NAND tests. Hardware execution occurs only on explicit invocation."""
import os
from pathlib import Path
import re
import shlex
import shutil
import stat
import subprocess
import time

import config
import serial


def result(test_id, status, details, measurements=None, output=""):
    return {"test_id": test_id, "status": status, "measurements": measurements or {},
            "details": details, "output": output}


def write_target_log(file_name, output):
    log_dir = Path(config.TARGET_LOG_DIR)
    log_dir.mkdir(parents=True, exist_ok=True)
    log_file = log_dir / file_name
    log_file.write_text(output or "", encoding="utf-8", errors="replace")
    return str(log_file)


def result_details(status, log_file=None):
    lines = ["Status   : {}".format(status)]
    if log_file:
        lines.append("Log File : {}".format(log_file))
    return "\n".join(lines)


def run_process(test_id, command, stream_callback=None):
    if shutil.which(command[0]) is None:
        return result(test_id, "NOT_CONFIGURED", "Missing executable: " + command[0])
    env = os.environ.copy()
    env["LC_ALL"] = "C"
    env.pop("MEMTESTER_TEST_MASK", None)
    start = time.monotonic()
    try:
        process = subprocess.Popen(command, stdout=subprocess.PIPE,
                                   stderr=subprocess.STDOUT, universal_newlines=True,
                                   errors="replace", env=env, bufsize=1)
        chunks = []
        for line in process.stdout:
            chunks.append(line)
            if stream_callback is not None:
                stream_callback(line)
        returncode = process.wait()
    except OSError as exc:
        return result(test_id, "ERROR", str(exc), {"command": command})
    output = "".join(chunks)
    return result(test_id, "PASS" if returncode == 0 else "FAIL", "Command completed.",
                  {"command": command, "returncode": returncode,
                   "duration_seconds": round(time.monotonic() - start, 3)},
                  output)


def ram_test(test_id="DDR_TEST", stream_callback=None):
    """Run memtester with the configured size and finite loop count."""
    command = shlex.split(config.DDR_TEST)
    if (len(command) != 3 or command[0] != "memtester"
            or not re.fullmatch(r"[1-9][0-9]*M", command[1])
            or not re.fullmatch(r"[1-9][0-9]*", command[2])):
        return result(test_id, "NOT_CONFIGURED", "Set DDR_TEST to memtester <size>M <loops>.")
    answer = run_process(test_id, command, stream_callback)
    if "returncode" not in answer["measurements"]:
        return answer
    output = answer["output"]
    try:
        log_file = write_target_log("ddr_test.log", output)
    except OSError as exc:
        log_file = None
        answer["measurements"]["log_error"] = str(exc)
    answer["details"] = result_details(answer["status"], log_file)
    answer["output"] = ""
    return answer


def uart_result_details(status, device, note, message=None):
    lines = [
        "Status   : {}".format(status),
        "Device   : {}".format(device),
        "Note     : {}".format(note),
    ]
    if message is not None:
        lines.append("Message  : {}".format(message))
    return "\n".join(lines)


def uart1_debug_test(params=None):
    return result("UART1_DEBUG_TEST", "ABORTED", "Status   : ABORTED")


def uart2_rs232_test(params=None):
    return result("UART2_RS232_TEST", "ABORTED", "Status   : ABORTED")


def uart3_loopback_test(params=None):
    params = params or {}
    message = str(params.get("message", "")).strip()
    if not message:
        return result("UART3_LOOPBACK_TEST", "FAIL",
                      uart_result_details("FAIL", config.X_UART3,
                                          "No loopback message entered."))
    transmitted = (message + "\n").encode("utf-8")
    try:
        with serial.Serial(config.X_UART3, config.BAUDRATE, timeout=3) as uart:
            uart.reset_input_buffer()
            uart.write(transmitted)
            uart.flush()
            received = uart.readline().decode("utf-8", errors="replace").rstrip("\r\n")
    except (OSError, serial.SerialException) as exc:
        return result("UART3_LOOPBACK_TEST", "FAIL",
                      "Status   : FAIL\nError    : {}".format(exc))
    status = "PASS" if received == message else "FAIL"
    details = "Status   : {}\nSent     : {}\nReceived : {}".format(
        status, message, received if received else "No data received")
    return result("UART3_LOOPBACK_TEST", status, details,
                  {"sent": message, "received": received})


def uart5_ble_wifi_test(params=None):
    return result("UART5_BLE_WIFI_TEST", "ABORTED", "Status   : ABORTED")


def uart6_rs485_test(params=None):
    params = params or {}
    message = str(params.get("message", "")).strip()
    if not message:
        return result("UART6_RS485_TEST", "FAIL",
                      uart_result_details("FAIL", config.X_UART6,
                                          "No RS485 transmit message entered."))
    transmitted = (message + "\n").encode("utf-8")
    received_bytes = bytearray()
    last_received = None
    try:
        with serial.Serial(config.X_UART6, config.BAUDRATE, timeout=0.1) as uart:
            written = uart.write(transmitted)
            uart.flush()
            while True:
                chunk = uart.read(256)
                if chunk:
                    finished = False
                    for character in chunk:
                        if character in (10, 13) and received_bytes:
                            finished = True
                            break
                        if character not in (10, 13):
                            received_bytes.append(character)
                    last_received = time.monotonic()
                    if finished:
                        break
                elif (last_received is not None
                      and time.monotonic() - last_received >= 1.0):
                    break
    except (OSError, serial.SerialException) as exc:
        return result("UART6_RS485_TEST", "FAIL",
                      "Status   : FAIL\nError    : {}".format(exc))
    received = received_bytes.decode("utf-8", errors="replace").rstrip("\r\n")
    status = "PASS" if written == len(transmitted) and received else "FAIL"
    details = "Status   : {}\nSent     : {}\nReceived : {}".format(
        status, message, received if received else "No data received")
    return result("UART6_RS485_TEST", status, details,
                  {"bytes_sent": written, "received": received,
                   "bytes_received": len(received_bytes)})


def parse_nand_command(command_text):
    command = shlex.split(command_text)
    if not command or command[0] != "nandtest":
        raise ValueError("NAND_RW_TEST must start with nandtest.")
    try:
        passes = int(command[command.index("-p") + 1])
        offset = int(command[command.index("-o") + 1], 0)
        length = int(command[command.index("-l") + 1], 0)
        device = command[-1]
    except (ValueError, IndexError):
        raise ValueError("NAND_RW_TEST must include -p <passes> -o <offset> -l <length> <device>.")
    return command, device, offset, length, passes


def nand_preflight(command_text):
    try:
        command, device, offset, length, passes = parse_nand_command(command_text)
    except ValueError as exc:
        return None, str(exc)
    if (not re.fullmatch(r"/dev/mtd[0-9]+", device) or offset < 0
            or length <= 0 or passes < 1):
        return None, "Invalid NAND device, region or pass count."
    try:
        if not stat.S_ISCHR(Path(device).stat().st_mode):
            return None, "NAND device must be an MTD character device."
        info = Path("/sys/class/mtd") / Path(device).name
        if info.joinpath("type").read_text().strip() not in ("nand", "mlc-nand"):
            return None, "Configured device is not NAND."
        size = int(info.joinpath("size").read_text().strip(), 0)
        erase = int(info.joinpath("erasesize").read_text().strip(), 0)
        if erase <= 0 or offset % erase or length % erase or offset + length > size:
            return None, "Region must be erase-block aligned and within the MTD partition."
        number = device[8:]
        for entry in Path("/sys/class/ubi").glob("ubi*/mtd_num"):
            if entry.read_text().strip() == number:
                return None, "Configured MTD is attached to UBI; use an offline test environment."
        name = info.joinpath("name").read_text().strip()
        for line in Path("/proc/mounts").read_text().splitlines():
            source = line.split()[0]
            if source in (device, "/dev/mtdblock" + number, "mtd:" + name):
                return None, "Configured MTD is mounted; use an offline test environment."
    except (OSError, ValueError) as exc:
        return None, "Cannot verify NAND region: " + str(exc)
    return command, None


def nand_test(test_id="NAND_RW_TEST"):
    """Run the explicitly configured NAND region with content restoration (-k)."""
    command, problem = nand_preflight(config.NAND_RW_TEST)
    if problem:
        return result(test_id, "NOT_CONFIGURED", problem)
    answer = run_process(test_id, command)
    answer["details"] += " NAND contents may not be restored after interruption or failure."
    if "returncode" not in answer["measurements"]:
        return answer
    output = answer["output"]
    passes = [int(n) for n in re.findall(r"Finished pass (\d+) successfully", output)]
    for label, key in (("ECC corrections", "initial_ecc_corrections"),
                       ("ECC failures", "initial_ecc_failures"),
                       ("Bad blocks", "initial_bad_blocks"),
                       ("BBT blocks", "bbt_blocks")):
        match = re.search(re.escape(label) + r"\s*:\s*(\d+)", output)
        answer["measurements"][key] = int(match.group(1)) if match else None
    answer["measurements"]["completed_passes"] = passes
    errors = re.search(r"\bfailed\b|\bfailure\b|\berror\b|short read|short write", output, re.I)
    passed = (answer["measurements"]["returncode"] == 0 and not errors
              and passes == list(range(1, parse_nand_command(config.NAND_RW_TEST)[4] + 1))
              and answer["measurements"]["initial_ecc_failures"] == 0
              and re.search(r"[0-9a-fA-F]+:\s*checking", output))
    answer["status"] = "PASS" if passed else "FAIL"
    try:
        log_file = write_target_log("nand_test.log", output)
    except OSError as exc:
        log_file = None
        answer["measurements"]["log_error"] = str(exc)
    answer["details"] = result_details(answer["status"], log_file)
    answer["output"] = ""
    return answer
