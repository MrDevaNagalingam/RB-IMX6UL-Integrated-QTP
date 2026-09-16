# BOSCH-IMX8M-PLUS Integrated QTP

Start the target UART server on the board, then run the host and select the
numbered test. The host sends commands over the UART3 QTP console, the target
executes the test, and the host displays status/details and saves text logs.

## Project structure

```text
BOSCH-IMX8M-PLUS-Integrated-QTP/
|-- BOSCH_IMX8M_PLUS_Integrated_QTP_Host/
|   |-- main.py
|   |-- command_handler.py
|   |-- uart_handler.py
|   |-- interactive_menu.py
|   '-- requirements.txt
|-- BOSCH_IMX8M_PLUS_Integrated_QTP_Target/
|   |-- main.py
|   |-- config.py
|   |-- dispatcher.py
|   |-- tests.py
|   '-- requirements.txt
|-- docs/
|   |-- hardware_mapping.md
|   '-- test_matrix.md
'-- README.md
```

## Wiring and startup

Use UART3 as the QTP console. The target default is `/dev/ttymxc2` at 115200
baud, 8 data bits, no parity, one stop bit, and no flow control.

Copy `BOSCH_IMX8M_PLUS_Integrated_QTP_Target` to the board. From that directory,
install pyserial if it is not already in the BSP image, then start the server:

```sh
python3 -m pip install pyserial==3.5
python3 main.py
```

The server listens on `/dev/ttymxc2`. Override the configured link if needed:

```sh
python3 main.py --port /dev/ttymxc2 --baud 115200
```

On the PC, open `BOSCH_IMX8M_PLUS_Integrated_QTP_Host` and run:

```powershell
python -m pip install -r requirements.txt
python main.py COM4
```

Replace `COM4` with the adapter's actual COM port. On Linux, use a device such
as `/dev/ttyUSB0`.

## Test menu

```text
1. TC-01 Boot mode
2. TC-02 UART1 Debug Console
3. TC-03 Reset Switch (S1)
4. TC-04 SD Card Write/ Read / Delete
5. TC-05 Indication LED1 Pin no.(GPIO2_IO06)
6. TC-05 Indication LED2 Pin no.(GPIO2_IO07)
7. TC-05 Indication LED3 Pin no.(GPIO2_IO08)
8. TC-05 Indication LED4 Pin no.(GPIO2_IO09)
9. TC-06 Ethernet0 throughput test pin no.(X8)
10. TC-06 Ethernet1 throughput test pin no.(X9)
q. Quit
```

Entering `q`, `quit` or `exit` sends `STOP_QTP` to the target. The target
acknowledges the command, exits its dispatcher loop, closes the QTP UART and
stops `main.py` before the host exits interactive mode.

## TC-01 Boot Mode

Host option 1 sends `TEST_BOOT_MODE`, which maps to target command
`BOOT_MODE_TEST`. The target reads `SRC_SBMR2` address `0x30390070` with
`devmem2`, decodes `BOOT_MODE[3:0]` from bits `[27:24]`, and reports:

- board model from `/proc/device-tree/model`
- raw `SRC_SBMR2` value
- `X_BOOT_MODE3` through `X_BOOT_MODE0`
- decoded boot mode value
- boot source text from the i.MX8M Plus boot-mode table

The boot-source table used by the test is:

| Value | Boot source |
|---|---|
| 0x0 | Boot from internal fuses |
| 0x1 | USB Serial Downloader |
| 0x2 | Boot from on-board eMMC U4 |
| 0x3 | Boot from external SD card SD2 |
| 0x6 | Boot from on-board QSPI Flash U5 |
| 0xF | JTAG mode |

`devmem2` must be available on the target image and the test must run with
permission to read the register.

## TC-02 UART1 Debug Console

Host option 2 sends `TEST_UART1_DEBUG_CONSOLE`, which maps to target command
`UART1_DEBUG_CONSOLE_TEST`. It returns `ABORTED` with the message
"UART1 is used for the debug console. UART1 test aborted." No UART1 port is
opened or tested. QTP communication continues over UART3.

## TC-03 Reset Switch (S1)

Host option 3 prompts the operator to press reset button S1 and observe the
cold-start boot sequence on the debug console. After checking the reset and
boot, enter `YES` (`y`) for PASS or `NO` (`n`) for FAIL on the host. The host records that result in the
test log and summary without sending a target command or waiting for a UART
response. Restart target QTP with `python3.12 main.py` after boot before
running another target test.

## TC-04 SD Card Write/ Read / Delete

Option 4 sends `SD_CARD_RW_DELETE_TEST` through the host command
`TEST_SD_CARD_RW_DELETE`. The target runs five cycles on `/dev/mmcblk1p5`:
write 10 MiB of random data, flush it to storage, read and compare size and
SHA256, then delete the test file. All cycles and cleanup must succeed for PASS.
Progress displays the last six SHA256 characters on the host. Full hashes
are compared for verification and saved only on the target in
`/qtp_log/sd_card.txt` (configured by `SD_LOG_FILE`). Each completed run is
appended with its start time, operations, and final result. The host displays
the target log location and saves only abbreviated progress. A target log
write failure makes the test FAIL.

Run target QTP as root. Confirm the SD partition in `config.py` before use.
An existing mount is reused; otherwise QTP mounts at `/mnt/sd_test` and
unmounts afterward. Files are created in a unique temporary directory;
existing files are not overwritten. This is a filesystem readback test;
reads can use the kernel cache. The SD-card test functions are in `tests.py`.

## TC-05 Indication LEDs

Options 5-8 test LED1-LED4 individually through `/sys/class/leds/led1` to
`led4`. GPIO mappings are GPIO2_IO06, GPIO2_IO07, GPIO2_IO08, GPIO2_IO09
(gpiochip1 lines 6-9). Menu pin labels show these GPIO signal names.
LED paths, GPIO mappings, and ON/OFF timings are defined in target `config.py`.
Run as root. The selected LED's trigger is disabled, and it is turned on for
two seconds, then off for two seconds and left off. Other LEDs are unchanged.
After a successful sequence, operator YES records PASS and NO records FAIL.
Hardware access failures remain FAIL regardless of acknowledgment.

## TC-06 Ethernet Throughput

Options 9 and 10 test Ethernet0/X8 and Ethernet1/X9 for 60 seconds each.
The PC report follows the ESR0C numbered-step layout, with timestamped
interval rows and a final summary showing duration, samples, received data,
average/minimum throughput, threshold, and result. Packet loss is N/A for
this TCP test; link stability is not inferred from throughput alone.
Target `config.py` contains `ETH_INTERFACES` (defaults `eth0` and `eth1`),
duration, port 5201, reporting interval 10 seconds, and minimum throughput.
Confirm interface names with `ip link` and the board connector mapping.
Bring the selected interface up before testing.

Install iperf3 on PC and target. On the PC it can be on PATH or in the host
`iperf3` folder with its required DLLs. Run the Windows host as Administrator.
Connect the selected port to the PC. The host reads `ipconfig`, selects the
first usable Ethernet adapter (excluding Wi-Fi and common virtual adapters),
and derives an adjacent board address within its subnet, excluding the gateway.
There are no IP prompts. Use a dedicated test network where this adjacent
address is unused. Automatic parsing expects English Windows `ipconfig` output.
The detected adapter and addresses are printed before the test. QTP starts the PC server,
checks target link, adds the board address if absent, pings the PC, and runs
TCP iperf3 bound to the selected interface. Target tools required: `ip`
(with JSON support), `ping`, and iperf3 with `--bind-dev` support.

Windows Firewall profiles are temporarily disabled during the test and their
original states restored afterward, including on errors or Ctrl+C. The PC
server is stopped and any added board address removed. Pre-existing IPs are
preserved. Linux host firewall configuration is manual (TCP 5201 and ICMP).
No firewall changes are made merely by starting QTP or editing the project.

PASS requires link, ping, and a successful iperf3 run with receiver throughput
above `ETH_MIN_MBPS` (default 0: connectivity/throughput validation, not a rated
speed certification). Streamed results and cleanup messages are saved in the
host log. Hardware validation is pending.

Host logs are saved under `test_log/` relative to the host working directory.
Use `--report-dir` to change the output directory.
