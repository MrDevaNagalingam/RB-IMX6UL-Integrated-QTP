# Hardware mapping

Board: RB-IMX6UL. Revision and running BSP version: unconfirmed.
Latest user notes take precedence over older test-case examples.

| Signal | Role | Linux device | Evidence |
|---|---|---|---|
| X_UART1 | Debug console | /dev/ttymxc0 | Explicit user mapping |
| X_UART2 | RS232; intended QTP console | /dev/ttymxc1 | Role from user; device supported by RS2332_testcase, verify on BSP |
| X_UART3 | MikroBUS and expansion header | /dev/ttymxc2 | Role from user; device mapping provisional |
| X_UART5 | BLE and Wi-Fi module UART | /dev/ttymxc4 | Role from user; BLE notes use this device, verify on BSP |
| X_UART6 | RS485 | /dev/ttymxc5 | Role from user; RS485 notes include this device, verify on BSP |
| GPIO2_IO11_ULED1 | Indication User LED1, active-low | /sys/class/gpio/gpio43 | Explicit user mapping and User_led_testcase |
| GPIO2_IO12_ULED2 | Indication User LED2, active-low | /sys/class/gpio/gpio44 | Explicit user mapping and User_led_testcase |
| GPIO2_IO8_INT_SW | User Switch input, active-low | /sys/class/gpio/gpio40 | Explicit user mapping and User_switch_testcase |

User device listing: ttymxc0, ttymxc1, ttymxc2, ttymxc4, ttymxc5.
QTP uses 115200 baud, 8N1, no flow control by default, matching the reference.
This is a software default, not a new board measurement. The host COM port is
selected at startup; other peripheral baud rates remain unconfigured.
Confirm device associations using the running device tree and board wiring.
Older BE33 notes use ttymxc2 and older RS485 examples also mention ttymxc1;
do not copy those assignments over the latest role mapping.

QTP wiring will use an appropriate RS232 adapter on X_UART2; connector pinout
and cable wiring remain to be confirmed. Check UART ownership before enabling
QTP. An RS232 loopback test on the command UART needs a separate execution or
fixture plan so it does not disrupt the QTP session.

## ADC

IIO path from existing notes: /sys/bus/iio/devices/iio:device0.
User reports in_voltage0_raw through in_voltage3_raw and in_voltage_scale.

| Board signal | Intended raw attribute |
|---|---|
| X_GPIO1_1_ADC1_IN1 | in_voltage1_raw |
| X_GPIO1_3_ADC1_IN3 | in_voltage3_raw |
| ADC1 scale | in_voltage_scale |

Verify physical routing and IIO identity on the actual revision.
Channels 0 and 2 being exposed does not confirm connector availability.
Scaling units, external divider, permitted input voltage, fixture and acceptance
tolerances remain unconfigured. The old ADC example's 5 V stimulus is not adopted
as a confirmed input limit.

## Remaining configuration

GPIO logical names, pin mappings, direction, polarity and backend are unconfigured.
Verify them against schematics and the running BSP before adding GPIO entries.
I2C buses/addresses, network interfaces, storage test paths and acceptance
thresholds are unconfigured. Verify per test as it is added.
NAND_RW_TEST uses the user-specified /dev/mtd2 region: offset 0x1e700000,
length 0xA00000 (10 MiB), exclusive end 0x1f100000, one pass with -k.
The runner checks NAND type, partition size, erase alignment, mounts and UBI
attachment. Region reservation and absence of concurrent users must be established
on the board. Interruption can prevent content restoration.
DDR_TEST uses 10 MiB for one loop.
Storage writes must use designated test files or explicitly configured regions.
Reset tests require a recovery/observation plan and documented fixture.
