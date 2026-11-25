# SM-G955N NFC

The Korean Dream2 board connects the S3NRN82 to USI10 HSI2C26,
address 0x27. VEN is active low. The other output is sampled for
firmware mode at startup and reused as WAKE in normal mode. Linux
must keep it low when enabling the controller, then assert it after
power-up. The Samsung PMU supplies the external reference on CLKOUT1.
The shared 1.8 V I/O rail was enabled by firmware in the tested boot.

## Transport trial

The reset-only device tree fragment is for an explicit lab test.
Writing `1` to its root-only `core_reset` attribute sends
CORE_RESET with Keep Configuration. Writing `wake` repeats the
same transaction with the additional post-enable wake signal. This
test keeps the radio inactive, restores the clock register bits and
switches the controller off after the attempt.

The first handset test received an address NACK. Two attempts with
the wake signal succeeded, reporting status 0 and NCI 1.0. The handset
returned to the verified Ubuntu boot without the temporary driver.

## Linux NFC transport

Enable the trial kernel configuration fragment and build the modules
against that kernel. Include `g955n-s3nrn82.dtsi` after the USI10
fragment. This selects the normal NCI transport through the kernel's
NFC class. The reference clock is enabled only while the NCI device
is open, with no firmware download hooks. The diagnostic and NCI
fragments are alternative bindings for one physical device.

The driver keeps the IRQ masked until the first successful write and
checks READY before reading. It uses a level interrupt so a second
pending frame can still wake the reader without another rising edge.
With it, the Linux NFC generic netlink interface powered the controller
up, started and stopped discovery, and powered it down. The same
sequence passed after s2idle and an ordinary reboot. The physical
tag path still needs a known tag and has yet to be qualified.
