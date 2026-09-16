"""Host command lookup and target response parsing."""
import json
import base64
import re
import os
import ipaddress
import shutil
import socket
import subprocess
import time
from uart_handler import UARTCommunicator

STATUSES = {"PASS", "FAIL", "ERROR", "NOT_CONFIGURED", "NOT_IMPLEMENTED", "ABORTED"}


def detect_ethernet_network():
    completed = subprocess.run(["ipconfig"], capture_output=True, text=True,
                               errors="replace", timeout=15)
    if completed.returncode:
        raise RuntimeError("ipconfig failed: " + completed.stderr.strip())
    adapters = []
    current = None
    for raw in completed.stdout.splitlines():
        if raw and not raw[0].isspace() and raw.rstrip().endswith(":"):
            current = {"adapter": raw.strip().rstrip(":")}
            adapters.append(current)
        elif current is not None:
            for label, key in (("IPv4 Address", "host_ip"), ("Subnet Mask", "mask"),
                               ("Default Gateway", "gateway")):
                match = re.search(label + r"[^:]*:\s*(\d+\.\d+\.\d+\.\d+)", raw, re.I)
                if match:
                    current[key] = match[1]
    for adapter in adapters:
        if not adapter["adapter"].lower().startswith("ethernet adapter "):
            continue
        if any(name in adapter["adapter"].lower() for name in ("vethernet", "bluetooth", "vmware", "virtualbox")):
            continue
        if "host_ip" not in adapter or "mask" not in adapter:
            continue
        host = ipaddress.IPv4Address(adapter["host_ip"])
        if host.is_loopback or host.is_unspecified:
            continue
        network = ipaddress.IPv4Network((str(host), adapter["mask"]), strict=False)
        # Match the reference's adjacent address, respecting the actual subnet.
        candidates = (int(host) + 1, int(host) - 1)
        for candidate in candidates:
            if not 0 <= candidate <= 0xFFFFFFFF:
                continue
            board = ipaddress.IPv4Address(candidate)
            if (board in network and board not in (network.network_address, network.broadcast_address)
                    and str(board) != adapter.get("gateway")):
                return {"host_ip": str(host), "board_cidr": "{}/{}".format(board, network.prefixlen),
                        "adapter": adapter["adapter"], "gateway": adapter.get("gateway", "NONE")}
    raise RuntimeError("No usable Ethernet IPv4/subnet found in ipconfig. Connect the PC Ethernet adapter.")


class CommandHandler:
    def __init__(self, uart_comm: UARTCommunicator):
        self.uart = uart_comm
        self.commands = {
            "TEST_ETHERNET0": self.test_ethernet0,
            "TEST_ETHERNET1": self.test_ethernet1,
            "TEST_LED1": self.test_led1,
            "TEST_LED2": self.test_led2,
            "TEST_LED3": self.test_led3,
            "TEST_LED4": self.test_led4,
            "STOP_TARGET": self.stop_target,
            "TEST_BOOT_MODE": self.test_boot_mode,
            "TEST_SD_CARD_RW_DELETE": self.test_sd_card_rw_delete,
            "TEST_UART1_DEBUG_CONSOLE": self.test_uart1_debug_console,
        }

    def execute_command(self, command_id, params=None, output_callback=None):
        if isinstance(command_id, str) and command_id in self.commands:
            return self.commands[command_id](params, output_callback)
        answer = {"test_id": command_id, "status": "NOT_IMPLEMENTED",
                  "measurements": {}, "details": "Unsupported host command", "output": ""}
        return answer

    def stop_target(self, params=None, output_callback=None):
        """Tell the target QTP server to stop."""
        return self._run_test("STOP_QTP", params, output_callback)

    def test_ethernet0(self, params=None, output_callback=None):
        return self._test_ethernet(0, params, output_callback)

    def test_ethernet1(self, params=None, output_callback=None):
        return self._test_ethernet(1, params, output_callback)

    def _test_ethernet(self, index, params, output_callback):
        command = "ETHERNET{}_TEST".format(index)
        answer = {"test_id": command, "status": "ERROR", "measurements": {},
                  "details": "", "output": ""}
        server = None
        profiles = []
        elevate_firewall = False

        def powershell(script, elevate=False):
            if elevate:
                encoded = base64.b64encode((
                    "$ErrorActionPreference = 'Stop'; try { " + script +
                    "; exit 0 } catch { exit 1 }").encode("utf-16-le")).decode("ascii")
                script = (
                    "$p = Start-Process -FilePath powershell.exe -Verb RunAs "
                    "-WindowStyle Hidden -ArgumentList '-NoProfile -NonInteractive -EncodedCommand "
                    + encoded + "' -PassThru; $p.WaitForExit(); exit $p.ExitCode")
            completed = subprocess.run(
                ["powershell", "-NoProfile", "-NonInteractive", "-Command",
                 "$ErrorActionPreference = 'Stop'; " + script],
                capture_output=True, text=True, timeout=60 if elevate else 20)
            if completed.returncode:
                raise RuntimeError(completed.stderr.strip() or "Firewall command failed")
            return completed.stdout

        def emit(message):
            if output_callback:
                output_callback(message + "\n")

        try:
            emit("[HOST] Preparing Ethernet{} / X{} over UART before PC IP detection.".format(index, index + 8))
            preparation = self._run_test("ETHERNET{}_PREPARE".format(index), output_callback=output_callback)
            if preparation["status"] != "PASS":
                raise RuntimeError("Target port preparation failed: " + preparation["details"] +
                                   ". Ensure the updated target QTP is running.")
            if params is None:
                emit("[HOST] Waiting up to 30 seconds for PC Ethernet IPv4...")
                network_deadline = time.monotonic() + 30
                while True:
                    try:
                        params = detect_ethernet_network()
                        break
                    except RuntimeError:
                        if time.monotonic() >= network_deadline:
                            raise
                        time.sleep(1)
                emit("[HOST] Network detected using ipconfig")
                emit("  Adapter           : {}\n  PC IPv4           : {}\n  Board test IPv4    : {}\n  Default Gateway   : {}".format(
                    params["adapter"], params["host_ip"], params["board_cidr"], params["gateway"]))
            host = str(ipaddress.IPv4Address(params["host_ip"]))
            emit("\n" + "=" * 62)
            emit("  ETHERNET THROUGHPUT TEST START")
            emit("=" * 62)
            emit("  [TEST CASE] TC-06 : Ethernet{} Throughput | Connector X{}".format(index, index + 8))
            emit("-" * 62)
            emit("  [STEP-1] Board Power ON\n  System Boot Status : Operator to confirm; UART response checked during test")
            emit("-" * 62)
            emit("  [STEP-2] iPerf Server Initialization (PC Side)")
            folder = os.path.dirname(os.path.abspath(__file__))
            executable = "iperf3.exe" if os.name == "nt" else "iperf3"
            candidates = [os.path.join(folder, "iperf3", executable),
                          os.path.join(folder, "iperf3.5_64", executable),
                          os.path.join(folder, executable)]
            binary = next((p for p in candidates if os.path.isfile(p)), None) or shutil.which(executable)
            if not binary:
                raise RuntimeError("iperf3 not found on PC. Install it or place it in the host iperf3 or iperf3.5_64 folder.")
            with socket.socket() as probe:
                probe.bind((host, 5201))
            if os.name == "nt":
                import ctypes
                elevate_firewall = not ctypes.windll.shell32.IsUserAnAdmin()
                profiles = json.loads(powershell(
                    "@(Get-NetFirewallProfile | Select-Object Name,@{Name='Enabled';Expression={[int]$_.Enabled}}) | ConvertTo-Json -Compress"))
                if not isinstance(profiles, list) or any(
                        p["Name"] not in ("Domain", "Private", "Public") or p["Enabled"] not in (0, 1, 2)
                        for p in profiles):
                    profiles = []
                    raise RuntimeError("Unable to capture firewall profile state")
                if elevate_firewall:
                    emit("[HOST] Accept the Windows UAC prompt for temporary firewall setup.")
                powershell("Set-NetFirewallProfile -Profile Domain,Private,Public -Enabled False", elevate_firewall)
                emit("[HOST] Windows Firewall temporarily disabled.")
            else:
                emit("[HOST] Ensure TCP 5201 and ICMP are allowed by the PC firewall.")
            server = subprocess.Popen([binary, "-s", "-B", host, "-p", "5201"],
                                      stdout=subprocess.DEVNULL, stderr=subprocess.DEVNULL,
                                      creationflags=subprocess.CREATE_NO_WINDOW if os.name == "nt" else 0)
            time.sleep(1)
            if server.poll() is not None:
                raise RuntimeError("PC iperf3 server failed to start")
            emit("  Command Executed  : iperf3 -s -B {} -p 5201".format(host))
            emit("  Launched Via      : QTP host process")
            emit("  Server Status     : RUNNING (PID {})".format(server.pid))
            emit("-" * 62)
            answer = self._run_test(command, params, output_callback)
        except (OSError, ValueError, KeyError, TypeError, RuntimeError, subprocess.TimeoutExpired) as exc:
            answer.update(status="ERROR", details=str(exc))
        finally:
            if server is not None:
                if server.poll() is None:
                    server.terminate()
                try:
                    server.wait(timeout=5)
                except subprocess.TimeoutExpired:
                    server.kill()
                    server.wait()
            if profiles:
                try:
                    if elevate_firewall:
                        emit("[HOST] Accept the Windows UAC prompt to restore the original firewall settings.")
                    restore = []
                    for profile in profiles:
                        enabled = {0: "False", 1: "True", 2: "NotConfigured"}[profile["Enabled"]]
                        restore.append("Set-NetFirewallProfile -Profile {} -Enabled {}".format(profile["Name"], enabled))
                    powershell("; ".join(restore), elevate_firewall)
                except (OSError, RuntimeError, subprocess.TimeoutExpired) as exc:
                    answer.update(status="ERROR", details=answer["details"] + "\nFirewall restore failed: " + str(exc))
                    emit("[HOST] Firewall restore failed: " + str(exc))
            if profiles and "Firewall restore failed" not in answer["details"]:
                emit("[HOST] Original Windows Firewall settings restored.")
        metrics = answer.get("measurements", {})
        emit("\n" + "-" * 62)
        emit("  [FINAL RESULT SUMMARY]")
        emit("-" * 62)
        emit("  Test Duration Completed : {} seconds".format(metrics.get("completed_seconds", "N/A")))
        emit("  Samples Collected       : {}".format(len(metrics.get("samples", []))))
        emit("  Total Data Transferred  : {}".format(metrics.get("receiver_transfer", "N/A")))
        emit("  Average Throughput      : {} Mbits/sec".format(metrics.get("receiver_mbps", "N/A")))
        emit("  Min Throughput          : {} Mbits/sec".format(metrics.get("min_mbps", "N/A")))
        emit("  Threshold               : {} Mbits/sec".format(metrics.get("threshold_mbps", "N/A")))
        emit("  Packet Loss             : N/A (TCP test)")
        emit("  Test Completion         : {}".format("SUCCESS" if answer["status"] == "PASS" else "FAILED"))
        emit("-" * 62)
        emit("  [RESULT] Test Status : " + answer["status"])
        emit("  [RESULT] " + answer["details"])
        emit("=" * 62)
        emit("  ETHERNET THROUGHPUT TEST END")
        emit("=" * 62)
        return answer

    def test_led1(self, params=None, output_callback=None):
        return self._run_test("LED1_TEST", params, output_callback)

    def test_led2(self, params=None, output_callback=None):
        return self._run_test("LED2_TEST", params, output_callback)

    def test_led3(self, params=None, output_callback=None):
        return self._run_test("LED3_TEST", params, output_callback)

    def test_led4(self, params=None, output_callback=None):
        return self._run_test("LED4_TEST", params, output_callback)

    def test_boot_mode(self, params=None, output_callback=None):
        """Read SRC_SBMR2 and decode BOOT_MODE[3:0]."""
        return self._run_test("BOOT_MODE_TEST", params, output_callback)

    def test_sd_card_rw_delete(self, params=None, output_callback=None):
        return self._run_test("SD_CARD_RW_DELETE_TEST", params, output_callback)

    def test_uart1_debug_console(self, params=None, output_callback=None):
        return self._run_test("UART1_DEBUG_CONSOLE_TEST", params, output_callback)

    def _run_test(self, command, params=None, output_callback=None):
        """Shared UART response validation and reporting for named test methods."""
        answer = {"test_id": command, "status": "ERROR", "measurements": {},
                  "details": "", "output": ""}
        try:
            raw = self.uart.send_and_receive(
                command, json.dumps(params) if params is not None else None, output_callback)
            parsed = json.loads(raw)
            if (not isinstance(parsed, dict) or parsed.get("test_id") != command
                    or parsed.get("status") not in STATUSES
                    or not isinstance(parsed.get("measurements"), dict)
                    or not isinstance(parsed.get("details"), str)
                    or not isinstance(parsed.get("output"), str)):
                raise ValueError("Invalid target result schema or test ID")
            answer = parsed
        except (OSError, TimeoutError, ValueError, TypeError) as exc:
            answer.update(status="ERROR", details=str(exc))
        except KeyboardInterrupt:
            answer.update(status="ERROR", details="Host interrupted; target may still be running")
            raise
        return answer

