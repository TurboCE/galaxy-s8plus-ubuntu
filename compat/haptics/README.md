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

The first PWM-enabled handset trial registered the input device
and produced real pulses that stopped normally or on cancellation.
The trial also exposed a sensor hub regression from the build's
baseline source. The original BOOT was restored. Use the exact
integrated clock and SPI source when building the next trial.
Suspend cancellation still requires a handset test.

The read-only probe also checks the notification LED registers on
the same PMIC address. Stock Dream2 maps red, green and blue to
MAX77865 outputs 1, 2 and 3. The handset reported all three off.
A future Linux LED class driver must share the existing PMIC client
with haptics.

The notification LED driver registers `red:indicator`,
`green:indicator`, and `blue:indicator`. It limits each channel
to the corresponding Samsung normal-mode current value and
reads the current and enable state back from the PMIC. The
PWM haptic driver shares its regmap with these LED class devices.
For a kernel without PWM, an explicit LED-only I²C binding is
available at the same address. The handset passed a temporary
LED-only trial on the known-good BOOT. Each color was switched to
level 3 and back to off through the Linux LED class.
