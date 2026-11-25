# SM-G955N optical sensor identification

The Korean Dream2 revision 10 Samsung board tree puts the optical chip
at address 0x64 on USI10 HSI2C26. S2DOS03 at 0x60 on USI5 HSI2C24
supplies its 1.8 V logic and 3.3 V LED rails through LDO2 and LDO4.
The stock config selects ADPD143.

The temporary test DT binds both addresses to a diagnostic. At boot,
it does not read or modify device registers. Root can use the S2DOS03
`rail_state` attribute to read the enable byte and two voltage selectors.
The optical `chip_id` attribute reads the identification register with
the power already in place.

The `powered_chip_id` attribute requires both optical rails to be off
and LDO2 already selected at 1.8 V. It temporarily enables only LDO2,
verifies the PMIC state, reads the optical ID and restores the LDO2 bit.
It does not enable LDO4, change voltages, configure emission or take
a biosignal sample. It is for the test DT only.

The handset returned 0x0316 with LDO2 enabled. Its original PMIC enable
byte was 0x15, and it returned to 0x15 after the test. The installed
sensor matches the Samsung ADPD143 identification table.

## Linux IIO

Use `g955n-adpd143.dtsi` with `g955n-s2dos03-optical` and
`g955n-adpd143`. The supply driver verifies both programmed voltages
and only controls S2DOS03 LDO2 and LDO4. The driver turns on logic
for chip identification and keeps both supplies off while idle.
Starting the IIO buffer enables sampling. Stopping the buffer puts
the sensor in standby and disables VLED, then VDD.

The `g955n-adpd143` IIO device publishes raw red and infrared
intensity samples and an optional host timestamp. A channel is
the sum of its four photodiode values. The board acquisition
profile uses fixed coarse LED code 1 in both slots. It does not run
Samsung's auto-gain, physiological estimation or calibration
routines, so the IIO values are raw optical measurements.
