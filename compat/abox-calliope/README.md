# SM-G955N Calliope bring-up

This out-of-tree Linux 6.18 test uses the audio device's existing Exynos
System MMU domain. It validates the firmware files, stages the vendor DRAM and IVA images at their fixed addresses, checks the translations,
and releases the mappings. It maps the stock VSS address window to
private, zeroed memory for the diagnostic. The modem's memory is
outside that mapping. The stage uses firmware from the handset's own
read-only SYSTEM partition. Use the provisioning script with `--with-dsm`
to include the six additional files listed by Samsung's Exynos8895 DT.

Build against the matching running kernel with the Makefile in this
directory. A successful one-shot stage prints its receipt and returns
`ECANCELED` from module initialization so that the module does not remain
loaded.

The explicit `try_boot=1` diagnostic requires idle native playback and
capture. It loads the SRAM image, asserts the firmware's DRAM request,
starts CA7, and checks the vendor SRAM mailbox for BOOT_DONE or a fault.
Entering the boot test holds the runtime PM reference that powers
the audio IOMMU. With no PCM open, the software mappings alone do not
activate the hardware page-table walker. Boot observation validates
component descriptors in SRAM or DRAM and acknowledges the reports.
An unsupported request ends the diagnostic.
The separate `try_resume=1` option sends system RESUME only after
BOOT_DONE and checks whether firmware clears the TX acknowledgment. It shuts down CA7 before reclaiming
its buffers. An unconfirmed shutdown retains the mappings until reboot.

Use `try_boot=1 try_resume=1 try_dsm_read=1` for the read-only DSM query.
It checks the inherited CA7 boot clock and responds to the boot gear
request with the actual CA7 rate. It reports the number of returned words
and the DSM enable flag. The query runs with both ALSA streams idle and
does not change calibration or start a stream.

Add `try_pcm=1` for the bounded, silent RDMA0 test. It requires both native
PCMs to be closed and the speaker amplifier to stay off. The diagnostic
uses the advertised ERAP DSM On control, sets up the stock UAIF4 output
selectors, and drives a zero-filled ring through the Samsung PCM mailbox.
It checks the hardware position and records whether firmware also reports
an IPC position. The module stops the DMA before restoring registers and
releasing the ring. This test is separate from the ALSA PCM opened by
desktop applications.

Add `try_feedback=1` to that silent test to verify the MAX98506 monitor
registers and the UAIF4 receive enable. The handset's factory layout
assigns IMON to slots 0–1 and VMON to slots 2–3. The test checks that
MAX98506 output is disabled and restores its monitor registers afterward.
Register readback shows that the monitor path is configured. The test uses
no speaker load, so it does not establish valid voltage or current samples.

## Experimental ALSA playback driver

Build against the native G955N audio driver and build output for the
same kernel release with `build-alsa-module.sh KERNEL_SOURCE KERNEL_BUILD OUTPUT_DIRECTORY`.
The resulting module replaces `g955n-abox-speaker.ko` for a trial boot.
Load it with `use_dsm=1` to route ALSA speaker playback through Calliope.
The ALSA card and PCM names stay the same. Playback uses the existing
ALSA ring as an IOMMU alias and waits for the firmware preparation and
trigger acknowledgments.

For the receiver-capable R100 source, append `--receiver` to the build
command and use the RDMA0 source against which patch 0131 applies.
This applies patches 0131, 0133, and 0135 in the output directory. Only PCM 0
uses Calliope when enabled. PCM 1 stays on the native microphone route
and PCM 2 on the native receiver route. Either PCM can start or stop first. The host holds the UAIF0 bit clock,
format and ABOX power while either stream uses them. Calliope adds only
the UAIF0 transmit enable and its playback route fields. The microphone
keeps its receive route and WDMA1 buffer. This sharing applies to the
receiver-capable driver. The older standalone and ALSA trial paths
still require an idle ABOX before firmware startup.

The R100 trial reproduced underruns when SIFS0 had no clocked sink and
when an optional DSP dump report ended the stream. The stock UAIF0
clock path and mailbox handling let normal ALSA playback complete at
48 kHz. Keep this driver opt-in until acoustic output and live
amplifier feedback are qualified.

For the #58 PCM routing comparison, load the receiver-capable module
with `use_dsm=1 kernel58_asrc0=1` on R100 with the 6.144 MHz AUDIF
profile. Calliope configures the output rate and format and starts
RDMA0. The driver selects ASRC0 and SPUS OUT0 through SIFS1 to UAIF4.
It skips the unused SIFS0 mixer format and keeps UAIF4 transmit-only.
The route is checked after the firmware trigger. The #58 route uses a
64 KiB playback ring with eight 8 KiB periods. At 48 kHz stereo S16,
this is a 16,384-frame buffer with 2,048 frames per period. Direct
ALSA playback and microphone capture completed together on the
handset. The speaker test tones were still absent from the recording.

The boot option exercises the Samsung nonsecure-GIC handoff available on
the tested silicon revision. A recurring ALSA stream, amplifier feedback,
and the secure-GIC path are outstanding. The module is a
diagnostic with no boot-time service or automatic loading.

On the handset qualification run, powering the audio IOMMU made the CA7
read the correct DRAM data. Starting the stock image with that fix was
followed by a device hang, including with RESUME disabled. Keep the boot
options out of unattended startup. The default staging-only path has
no CA7 start or doorbell write.

The receive-only boot trial left a pstore record reporting a write fault
at 0xa0570000. That address falls inside the stock six MiB VSS window.
With private backing for that window, the handset remained responsive and
Calliope reported two components, sent BOOT_DONE, and acknowledged RESUME.
The DSM query returned 146 words with enable=1 at idle. Playback through
DSM and microphone capture remain unverified.

### Wired jack insertion detection

The receiver module build also contains the SM-G955N CS47L93 jack
detector. The `g955n-wired-jack.dtsi` fragment separately enables it.
The detector follows the stock Korean board's combined JD1/JD2 clamp,
uses both clamp interrupts, and reports stable samples through the
ALSA `Headphone Jack` control. It releases the interrupts and restores
its detector fields when the codec link is removed. The existing PCM
routes remain available if the optional detector fails to initialize.

The HiFi UCM profile offers Wired Headphones when the ALSA jack
control is available. It uses the existing AIF1 playback PCM 2 to
feed HPOUT2L/HPOUT2R and keeps the codec's short-circuit protection
enabled. The two playback routes share the ABOX RDMA, so UCM marks
Headphones and Speaker as conflicting devices. The headphone route
initializes its two digital volumes to -28 dB. The built-in microphone
remains available on PCM 1.

The stock headset microphone uses IN1BL with MICBIAS2A. Physical jack
state, actual headphone sound and headset microphone classification
and recording remain separate handset checks.

For headset microphone qualification, include `g955n-wired-mic.dtsi`
as well. The optional MICDET1 measurement uses the Samsung MICDET1
input and ground settings and temporarily biases through MICBIAS2A.
The driver exposes a separate ALSA Headset Mic Jack status when the
measurement reaches the headset range. It restores the detector and
bias settings after completion or timeout. Capture routing and
classification across physical CTIA and three-pole plugs still
require handset validation before enabling the microphone in UCM.
