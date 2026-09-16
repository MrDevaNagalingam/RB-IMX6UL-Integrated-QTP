import hashlib
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
