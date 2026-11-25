# SM-G955N charger input detection

The MAX77865 charger at I²C address 0x69 reports the wired and wireless
input states in INT_OK. Its input status is independent of the fuel
gauge at 0x36 and of whether charging is in progress.

Build the module against the target kernel and include
[g955n-max77865-input.dtsi](g955n-max77865-input.dtsi) after the Dream2
board tree to autoload it. It publishes two Linux power supply devices
with a read-only `online` property and sends change events on a
freezable workqueue. It does not access the interrupt latch or program
charging thresholds, current limits or mode.

On a handset with a USB cable and no Qi charger, an explicit temporary
binding reported wired online and wireless offline. Ubuntu's UPower
reported the same values for both supply devices. The independent
charger status was 0xb in the low nibble of DTLS01, which the Samsung
driver classifies as discharging. A detected input alone does not
establish battery charging. Verify wired and wireless charge transitions
and add normal battery charge-state reporting before qualifying charging.
