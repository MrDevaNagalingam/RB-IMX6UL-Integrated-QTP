# Test matrix

| Test ID / command | Purpose and prerequisites | Procedure / expected result | Acceptance | Mode | Status |
|---|---|---|---|---|---|
| BOOT_MODE_TEST | Detect the i.MX8M Plus boot mode; requires root/register access and `devmem2` | Read `SRC_SBMR2` at `0x30390070`, decode bits `[27:24]`, and print boot-mode pins plus source | PASS when register read succeeds and `BOOT_MODE[3:0]` is decoded; FAIL when `devmem2` is missing, fails, or output cannot be parsed | Automatic | Implemented; hardware validation pending |
| UART1_DEBUG_CONSOLE_TEST | UART1 is reserved for the debug console | Report that UART1 is used for the debug console without accessing the port | ABORTED | Automatic | Implemented |
| TEST_RESET_SWITCH (host only) | TC-03 Reset Switch (S1); operator observes debug console | Press S1, observe cold-start boot, then enter YES or NO on the host; restart target QTP after boot | YES = PASS; NO = FAIL | Manual | Implemented; hardware validation pending |
| SD_CARD_RW_DELETE_TEST | TC-04; root, SD partition `/dev/mmcblk1p5`, sufficient free space, mount/umount/sync tools | Five 10 MiB write/read/SHA256/delete cycles in a unique temporary directory | PASS only when all cycles and cleanup succeed | Automatic | Implemented; hardware validation pending |

Host option 2 sends `TEST_UART1_DEBUG_CONSOLE`, which maps to target command
`UART1_DEBUG_CONSOLE_TEST`.

Host option 1 sends `TEST_BOOT_MODE`, which maps to target command
`BOOT_MODE_TEST`. UART3 is the QTP console.
