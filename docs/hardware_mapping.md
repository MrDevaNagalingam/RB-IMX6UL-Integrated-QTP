# Hardware Mapping

Board: BOSCH-IMX8M-PLUS. User console identifies a PHYTEC phyCORE-i.MX8M Plus
Bosch Gateway running BSP-Yocto-NXP-i.MX8MP-PD24.1.0-devel. PCB revision is
not supplied. Values below follow current config.py and user-provided mappings;
unprovided physical connector/pin numbers are not inferred.

## QTP Transport

UART3 is /dev/ttymxc2 at 115200 baud, 8 data bits, no parity, one stop bit,
no flow control. UART1 (/dev/ttymxc0) is reserved for debug. Select the actual
PC COM port at startup; it is not a fixed board mapping.

## All Menu Entries

| Option / test | Board signal / connector | Linux interface / resource | Configuration / evidence |
|---|---|---|---|
| 1 / TC-01 Boot mode | X_BOOT_MODE[3:0]; physical pin numbers not supplied | SRC_SBMR2 at 0x30390070, bits [27:24]; /proc/device-tree/model | SRC_SBMR2_ADDR; user sample and register output |
| 2 / TC-02 UART1 Debug Console | UART1; physical connector not supplied | /dev/ttymxc0 | X_UART1; reserved, not opened by this test |
| 3 / TC-03 Reset Switch | S1 | No software GPIO mapping; operator observes UART1 boot | Host-only manual test; user designation |
| 4 / TC-04 SD Card | SD card; boot table labels external SD as SD2 | /dev/mmcblk1p5; /mnt/sd_test if not already mounted | SD_DEVICE, SD_MOUNT_POINT; user sample. Confirm partition before use. |
| 5 / TC-05 LED1 | GPIO2_IO06 | /sys/class/leds/led1; gpiochip1 line 6 (label) | LEDS["led1"]; user mapping |
| 6 / TC-05 LED2 | GPIO2_IO07 | /sys/class/leds/led2; gpiochip1 line 7 (label) | LEDS["led2"]; user mapping |
| 7 / TC-05 LED3 | GPIO2_IO08 | /sys/class/leds/led3; gpiochip1 line 8 (label) | LEDS["led3"]; user mapping |
| 8 / TC-05 LED4 | GPIO2_IO09 | /sys/class/leds/led4; gpiochip1 line 9 (label) | LEDS["led4"]; user mapping |
| 9 / TC-06 Ethernet0 | X8 | eth0 | ETH_INTERFACES[0]; corrected user connector mapping |
| 10 / TC-06 Ethernet1 | X9 | eth1 | ETH_INTERFACES[1]; corrected user connector mapping |
| 11 / TC-07 CAN Loopback | CAN0 and CAN1; connector/pin numbers not supplied | can0 and can1; external terminated bus | CAN_INTERFACES; user manual bidirectional traffic |
| 12 / TC-08 HDMI | HDMI; connector number not supplied | fbtest default framebuffer; weston.service and weston.socket | HDMI_WESTON_SERVICE, HDMI_WESTON_SOCKET; no explicit framebuffer device configured |
| 13 / TC-09 USB Bluetooth | USB1 or USB2; test each separately | USB ID 0cf3:e500; hci0 | BT_USB_ID, BT_HCI. Address C4:93:00:4B:8A:F6 is user-observed, not hardcoded. |
| 14 / TC-10 TPM functionality | TPM; bus/physical pins not supplied | /dev/tpm0 and /dev/tpmrm0; device:/dev/tpmrm0 transport | TPM_DEVICES, TPM_TCTI; user manual output |
| 15 / TC-11 PCIe controller | PCIe controller; connector number not supplied | 00:00.0 (0000 domain accepted); Synopsys PCI bridge; pcieport | PCIE_DEVICE, PCIE_VENDOR, PCIE_DRIVER; user lspci output |

LED tests use LED-class brightness/trigger files, not GPIO export or gpiochip
commands. GPIO signal labels are not physical package/connector pin numbers.
gpio.py remains present with no functions.

## Setup and State Changes

- S1 resets the board; restart the target QTP process after cold-start boot.
- SD testing uses a unique directory and preserves unrelated files. Existing
  mounts are reused; only a test-created mount is unmounted.
- LED ON/OFF durations are 2 seconds each; selected LED remains OFF with its
  trigger disabled.
- Ethernet uses 60 seconds, 10-second reporting and TCP port 5201. PC IPv4 is
  detected from ipconfig; board test IPv4 is derived and sent over UART.
  Before eth0/X8 testing, run ifconfig eth1 0.0.0.0 down; before eth1/X9
  testing, run ifconfig eth0 0.0.0.0 down. The opposite port is not restored.
  Use a dedicated subnet with the derived board address unused.
- CAN requires physical CAN0-to-CAN1 bus wiring and correct termination.
  Bitrate is 500000 bit/s, internal loopback and listen-only disabled.
  Receivers are opened before sending; both interfaces remain UP afterward.
- Connect the HDMI cable before running fbtest. Weston is stopped/restored;
  the operator confirms the observed image.
- Bluetooth requires a nearby discoverable/advertising device. One scan tests
  only the connected adapter/port, not both USB connectors. No pairing occurs.
  Power and HCI are taken DOWN afterward.
- TPM test files are temporary. No persistent key or TPM ownership changes
  are made; the owner hierarchy must permit the supplied createprimary command.
- PCIe inspection validates enumeration and driver binding only.

## Target Log Mapping

| Resource | Config setting | Target file |
|---|---|---|
| SD | SD_LOG_FILE | /qtp_log/sd_card.txt |
| CAN | CAN_LOG_FILE | /qtp_log/can_test.txt |
| HDMI | HDMI_LOG_FILE | /qtp_log/hdmi.txt |
| USB Bluetooth | BT_LOG_FILE | /qtp_log/usb_bluetooth.txt |
| TPM | TPM_LOG_FILE | /qtp_log/tpm.txt |
| PCIe | PCIE_LOG_FILE | /qtp_log/pcie.txt |

Boot, UART1, reset, LEDs and Ethernet have no dedicated target log configured.
Host result logs cover every menu entry. See [test_matrix.md](test_matrix.md)
for prerequisites, acceptance criteria, confirmation behavior and console output.
