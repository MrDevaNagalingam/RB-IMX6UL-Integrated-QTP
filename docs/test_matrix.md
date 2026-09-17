# Test Matrix

This document covers all 15 host menu entries (TC-01 through TC-11).
LEDs share TC-05; Ethernet ports share TC-06. Procedures describe the current
implementation, not a claim that every hardware test has been validated.

## Commands and Acceptance

| Option | Test | Host command | Target command | Procedure and acceptance |
|---|---|---|---|---|
| 1 | TC-01 Boot mode | TEST_BOOT_MODE | BOOT_MODE_TEST | Read SRC_SBMR2, decode bits [27:24], and report model, pins and boot source. PASS when register read and parsing succeed; unknown table values are reported, not failed. Operator checks the expected boot source. |
| 2 | TC-02 UART1 Debug Console | TEST_UART1_DEBUG_CONSOLE | UART1_DEBUG_CONSOLE_TEST | Report UART1 reserved for debug; do not open it. Always ABORTED. |
| 3 | TC-03 Reset Switch (S1) | TEST_RESET_SWITCH | None (host only) | Press S1, observe cold-start boot on UART1. Operator YES gives PASS; NO gives FAIL. Restart target QTP after reboot before the next test. |
| 4 | TC-04 SD Card Write/ Read / Delete | TEST_SD_CARD_RW_DELETE | SD_CARD_RW_DELETE_TEST | Five 10 MiB random write/read/delete cycles. Verify full SHA256 and byte count. PASS requires all cycles, cleanup and log saving to succeed. |
| 5 | TC-05 Indication LED1 Pin no.(GPIO2_IO06) | TEST_LED1 | LED1_TEST | Disable selected LED trigger; ON 2 seconds, OFF 2 seconds, leave OFF. Successful sequence plus operator YES gives PASS; NO or hardware failure gives FAIL. |
| 6 | TC-05 Indication LED2 Pin no.(GPIO2_IO07) | TEST_LED2 | LED2_TEST | Same procedure and acceptance as LED1, using LED2 only. |
| 7 | TC-05 Indication LED3 Pin no.(GPIO2_IO08) | TEST_LED3 | LED3_TEST | Same procedure and acceptance as LED1, using LED3 only. |
| 8 | TC-05 Indication LED4 Pin no.(GPIO2_IO09) | TEST_LED4 | LED4_TEST | Same procedure and acceptance as LED1, using LED4 only. |
| 9 | TC-06 Ethernet0 throughput test pin no.(X8) | TEST_ETHERNET0 | ETHERNET0_PREPARE, ETHERNET0_TEST | Disable eth1, enable eth0; detect PC IPv4, assign test IP, check carrier and ping, run TCP iperf3 for 60 seconds. PASS requires successful run, receiver throughput greater than ETH_MIN_MBPS, and successful cleanup. |
| 10 | TC-06 Ethernet1 throughput test pin no.(X9) | TEST_ETHERNET1 | ETHERNET1_PREPARE, ETHERNET1_TEST | Disable eth0, enable eth1; otherwise same procedure and acceptance as Ethernet0. |
| 11 | TC-07 CAN0 and CAN1 Loopback test | TEST_CAN_LOOPBACK | CAN_LOOPBACK_TEST | Configure both at 500000 bit/s with internal loopback/listen-only OFF. Receive 123#1122334455667788 on can1 from can0, then 456#AABBCCDDEEFF0011 on can0 from can1. Both IDs, lengths and payloads must match; receive timeout is 5 seconds per direction. |
| 12 | TC-08 HDMI Test case | TEST_HDMI | HDMI_TEST | Stop active Weston socket and service; run fbtest; restart Weston. Successful execution and operator YES on visual patterns gives PASS. NO or command/restoration failure gives FAIL. |
| 13 | TC-09 USB Bluetooth (USB1, USB2) | TEST_USB_BLUETOOTH | USB_BLUETOOTH_TEST | Check USB adapter and HCI, start service, bring HCI up, select controller in persistent bluetoothctl session, power on and scan 15 seconds. PASS requires at least one observed device and no execution/cleanup errors. Scanning only: no pairing or connection. |
| 14 | TC-10 TPM functionality | TEST_TPM | TPM_TEST | Check TPM character devices; validate 16 random bytes; create primary and RSA key, load, encrypt test text, remove plaintext file, decrypt and compare exact bytes. PASS requires all checks and logging to succeed. |
| 15 | TC-11 PCIe controller verify | TEST_PCIE | PCIE_TEST | Run lspci -k; require Synopsys PCI bridge at 00:00.0 (also accepts domain 0000) and active pcieport driver on that same device. This checks enumeration/binding, not endpoint connectivity or throughput. |

## Prerequisites and Cleanup

| Options | Prerequisites / setup | Cleanup and limitations |
|---|---|---|
| All target tests | Board running target main.py; UART3 QTP link at 115200 8N1. Run target as root for hardware access. | Settings in target config.py; tests in tests.py; UART routing in dispatcher.py. gpio.py is retained as a placeholder with no functions. |
| 1 | devmem2 and register-read permission. | Read-only register access; boot source must be checked against physical setup. |
| 2 | UART1 reserved for debug. | No hardware operation. |
| 3 | Access to S1 and UART1 debug output. | Reset stops target QTP; restart it after boot. No target reply is awaited. |
| 4 | Confirm /dev/mmcblk1p5, sufficient free space, mount/umount/sync tools. | Reuse existing mount or mount /mnt/sd_test; unique temporary directory avoids overwriting other files. Unmount only a mount created by this test. Reads may use kernel cache. |
| 5-8 | Selected /sys/class/leds/ledN/brightness present. | Selected LED left OFF, trigger left disabled; other LEDs unchanged. GPIO numbers are labels, not direct gpiochip operations. |
| 9-10 | Cable on selected port, PC Ethernet IPv4, unused adjacent board IP on dedicated subnet; English Windows ipconfig. PC/target iperf3; target ifconfig, ip with JSON support, ping, iperf3 --bind-dev. | PC server stopped and original firewall states restored; added test IP removed. Opposite interface has IPv4 cleared and stays DOWN, not restored. Selected interface remains UP. Threshold defaults to 0 Mbit/s, not rated-speed certification. |
| 11 | CAN0 and CAN1 physically connected on a correctly terminated bus; ip, cansend and Python SocketCAN. | Receiver bound before sending. Both interfaces remain configured and UP. This is an external two-controller test, not internal loopback. |
| 12 | Connect HDMI cable and display before starting; systemctl and fbtest. | fbtest timeout 120 seconds. Restart attempts also occur on failure; socket restarted only if initially active, service started afterward. |
| 13 | Configured USB Bluetooth adapter, nearby discoverable/advertising device; lsusb, hciconfig, bluetoothctl, systemctl/BlueZ. | Controller discovery timeout 20 seconds; host polls until reply or Ctrl+C. Exit session, power OFF and HCI DOWN. Repeat with adapter in the other physical USB port; one run does not validate both ports. |
| 14 | Access to /dev/tpm0 and /dev/tpmrm0; tpm2_getrandom, tpm2_createprimary, tpm2_create, tpm2_load, tpm2_rsaencrypt, tpm2_rsadecrypt. | Per-command timeout 60 seconds. Kernel resource-manager transport; generated files removed with temporary directory. No TPM clear, persistent-key changes or global handle flush. |
| 15 | lspci available; expected controller enumerated. | Command timeout 15 seconds; read-only inspection. |

Windows Ethernet setup temporarily disables firewall profiles and restores their
original state after the test. Use an isolated test network. Run as Administrator
or approve the implementation's elevation requests. No firewall changes occur
merely by starting QTP.

## Console and Logs

All tests save final result, details, operator answer and timestamps in host
test_log/test_log_<timestamp>.txt and the session summary. --report-dir changes
the host destination. Live output is not universally retained in the host file;
use the dedicated target logs below for full diagnostics.

| Options | Console output | Dedicated target log |
|---|---|---|
| 1 | Board, register, boot bits and source; final result | None |
| 2 | Reserved-debug-console note; ABORTED | None |
| 3 | Reset instructions and one YES/NO prompt; final result | None |
| 4 | Iterations with last six SHA256 characters; final result and log location | /qtp_log/sd_card.txt (full hashes and operations) |
| 5-8 | Selected LED identity and ON/OFF progress; operator decision | None |
| 9-10 | ESR0C-style steps, network detection, 10-second interval rows and final summary | None; Ethernet report is saved in host log |
| 11 | Bitrate setup and both sent/received frames; result and log location. Link dumps and up/down commands are hidden. | /qtp_log/can_test.txt (full diagnostics) |
| 12 | Connection note, result, log location and visual YES/NO prompt; commands and fbtest output hidden | /qtp_log/hdmi.txt |
| 13 | Bluetooth progress and observed-device messages; final result and log location | /qtp_log/usb_bluetooth.txt |
| 14 | Final result, summary and log location; TPM progress/key output hidden | /qtp_log/tpm.txt |
| 15 | Final result, summary and log location; lspci command/output hidden | /qtp_log/pcie.txt |

Target logs are appended. Failure to save a required target log makes the test
FAIL. Unexpected execution/protocol errors may return ERROR without a log path.

## Operator Confirmation and Evidence

Reset, LEDs and HDMI use the operator answer to determine the final status
(after successful automated execution where applicable). For the other tests,
the answer is recorded as Working as Expected and does not override the
automated status. UART1 stays ABORTED. NO does not trigger a second confirmation
or rerun; invalid input is prompted again.

All 15 menu entries are implemented. User-provided evidence includes boot/SD
results, Ethernet reported working, and a Bluetooth PASS with 33 observed
devices on the connected adapter. These are not independent hardware
certification. TPM/PCIe manual examples are separate from validation of the
automated QTP flow. Record each actual run in host logs; do not infer a PASS
for untested ports or other hardware from implementation status.
