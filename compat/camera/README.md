# SM-G955N camera and flash board bring-up

The Samsung Korean revision 10 board connects the S2MPB02 camera and flash
power IC to USI10 HSI2C25 at address 0x59. Its NFC and optical sensors share
the other USI10 channel, HSI2C26. Samsung selects both channels in the USI
system register. The mainline DTS fragment `compat/nfc/g955n-usi10.dtsi`
selects the corresponding dual I²C mode and enables both child controllers.

Build the optional `g955n-s2mpb02-readback` module against the running
SM-G955N kernel and load it once for diagnosis. It claims the address
only during the reads and releases it before module initialization returns.
It does not scan other addresses, register a persistent client, enable an
emitter, or change regulator settings. On the handset, the boost
configuration byte 0x90 matched Samsung's revision 1 detection. Reboot
removes the diagnostic module on kernels built without module unloading.

The result confirms communication with the shared power and flash IC.
Camera regulator control, sensor identification, flash output and V4L2
capture are separate checks.
