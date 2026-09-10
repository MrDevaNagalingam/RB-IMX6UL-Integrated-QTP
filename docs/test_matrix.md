# Test matrix

The reference inventory below remains unimplemented. DDR, NAND and the first UART
operator-verification tests are now available through the host menu and UART server;
runner validation on
hardware remains NOT_RUN.

| Test ID / command | Purpose and prerequisites | Procedure / expected result | Acceptance | Mode | Status |
|---|---|---|---|---|---|
| DDR_TEST | Check 10 MiB RAM; root, memtester, available RAM | memtester 10M 1; all 16 named checks ok and Done. | Exit 0, full allocation locked, exact loop count, all checks ok, no reported failure | Automatic | Implemented; mocked checks only |
| NAND_RW_TEST | Check configured NAND region; root, nandtest, offline reserved region, backup and valid geometry | nandtest -k -p 1 -o 0x1e700000 -l 0xA00000 /dev/mtd2; pass 1 completes | Exit 0, checking output, exact completed passes, initial ECC failures 0, no reported errors | Automatic after fixture preparation | Implemented; mocked checks only |
| UART1_DEBUG_TEST | UART1 debug console note; /dev/ttymxc0 | Report that UART1 is used as debug console | ABORTED with note | Operator note | Implemented |
| UART2_RS232_TEST | UART2 QTP communication note; /dev/ttymxc1 | Report that UART2 is used for QTP communication | ABORTED with note | Operator note | Implemented |
| UART3_LOOPBACK_TEST | UART3 physical loopback; /dev/ttymxc2 on MikroBUS and expansion header; TX connected to RX | Operator enters a message; target writes it to UART3 and reads it back | PASS only when received text exactly matches transmitted text | Automatic with loopback jumper | Implemented; hardware validation pending |
| UART5_BLE_WIFI_TEST | UART5 BLE/WiFi hardware note; /dev/ttymxc4 | Report that BLE/WiFi hardware is not mounted right now | ABORTED with note | Operator note | Implemented |
| UART6_RS485_TX_TEST | UART6 transmit through RS485 hardware; /dev/ttymxc5 | Open as a normal UART, write the operator message plus newline and keep the session open | PASS when the complete message is written | Automatic transmit start | Implemented; hardware validation pending |
| UART6_RS485_TX_STOP | Stop UART6 transmit | Close the transmit serial session | PASS after the transmit session is closed | Automatic stop | Implemented; hardware validation pending |
| UART6_RS485_RX_TEST | UART6 receive through RS485 hardware; /dev/ttymxc5 | Open as a normal UART and start a background reader | PASS after receive starts | Automatic receive start | Implemented; hardware validation pending |
| UART6_RS485_RX_STOP | Stop UART6 receive | Stop the reader, close UART6 and report buffered data | PASS when non-empty data was received | Automatic stop and validation | Implemented; hardware validation pending |

Host option 1 sends TEST_DDR; option 2 sends TEST_NAND; options 3-10 send the UART
verification commands.
The host command mapping is TEST_DDR -> test_ddr() -> DDR_TEST and
TEST_NAND -> test_nand() -> NAND_RW_TEST. Add future host methods to self.commands.
Start target main.py once, then select tests on the host. Both responses use a type-2 TLV carrying
status, measurements, details and raw output as JSON; request ID type 3 is echoed.
Type 4 carries live output chunks and type 5 carries JSON parameters for
operator-entered messages.
The target debug console prints each received command before executing it.
Host reports preserve every status. Simulated menu/UART/target/report checks
passed; no physical serial or hardware test was executed by this implementation.

NAND initial ECC corrections, bad blocks and BBT blocks are recorded, not treated
as independent failures; BBT blocks = 4 in the sample is informational.
Reported ECC failures or compare errors fail even if nandtest exits 0.
An interrupted NAND test may not restore contents despite -k.

## Remaining reference inventory

Command IDs, purpose, prerequisites, procedure, expected result, acceptance
criteria and automatic/manual classification are pending per-test review.
Some files are overlapping notes or supporting logs rather than distinct tests.

| Reference file | Command | Implementation | Hardware validation |
|---|---|---|---|
| adc_test-cases | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| BE33 and WIFI Test Case | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| Ble_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| Ble_testcase_scan.txt | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| can_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| debug_console | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| digital_inputs_testcases | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| digital_output_testcases | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| ethernet_testcases | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| expnsion_headers | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| gpio_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| gsm.sh | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| health_led | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| i2c_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| mmc_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| mPCIe_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| pwm_testcases | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| RB-imx6ul_automatic_work.txt | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| reset _switch | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| RS2332_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| RS485_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| RTC_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| spi_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| test | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| USB_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| User_led_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| User_switch_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| wifi_hotspot_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |
| wifi_testcase | Unassigned | NOT_IMPLEMENTED | NOT_RUN |

## Fields to complete when adding a test

- Test ID and command
- Purpose and prerequisites, including fixtures
- Procedure and expected result
- Acceptance criteria and configured thresholds
- Automatic or manual classification
- Implementation status and hardware-validation evidence
