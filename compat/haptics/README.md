# SM-G955N haptics

The Korean revision 10 board uses the MAX77865 motor bridge on
the same I²C bus as its USB switch and fuel gauge. Earlier Korean
Dream2 revisions use DRV2624 and have different wiring. The revision
10 Samsung DT routes PWM channel 1 to pin `gpd0-5`.

The default module is a read-only identification probe. It reserves
the unused PMIC I²C address for the duration of four byte reads.
On the target handset it returned PMIC ID 0x65, revision 0x02,
and a disabled motor. It does not request a PWM or pulse the motor.

For a kernel with PWM support, build the force-feedback driver using
[haptics.config](haptics.config) and include
[g955n-haptic.dtsi](g955n-haptic.dtsi) after the target board tree.
The driver exposes `FF_RUMBLE` through Linux input. Its amplitude
range spans neutral to the Samsung alert waveform. It clears the
motor enable and stops PWM on cancellation, suspend, shutdown or
timeout. It preserves the initial mode and bias settings and leaves
the PMIC's shared boost configuration alone.

Build against the integrated BCM4773 kernel with the corrected USI8
clock and short SPI delay changes. The first PWM-enabled trial built
without those changes and the sensor hub could no longer initialize.
The corrected handset image ran the sensor hub and both MAX77865
drivers together. The hub accelerometer measured vibration during
force feedback, then returned to baseline after timeout or cancellation.
During an RTC-woken s2idle test, a read-only PM notifier observed
the motor enabled before suspend and disabled after resume. Force
feedback worked again after waking.

The notification LED driver registers `red:indicator`,
`green:indicator`, and `blue:indicator`. It limits each channel
to the corresponding Samsung normal-mode current value and
reads the current and enable state back from the PMIC. The
PWM haptic driver shares its regmap with these LED class devices.
For a kernel without PWM, an explicit LED-only I²C binding is
available at the same address. The handset passed a temporary
LED-only trial on the known-good BOOT. Each color was switched to
level 3 and back to off through the Linux LED class.

## Charging indicator

The Ubuntu rootfs connects the MAX77865 battery and charger uevents to
the red and green LED class devices. With a wired or wireless input
online, the red LED marks Charging and the green LED marks Full. Both
turn off for other battery states. The rules also refresh the indicator
when the LED devices appear during boot. They use the Korean board's
low-power current codes and leave the blue LED available for other uses.
