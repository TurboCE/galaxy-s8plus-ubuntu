# Limit ACP probing to the validated G955N UCM paths

The installed Ubuntu package is `libspa-0.2-modules 1.0.5-1ubuntu3.3`.
Its ACP implementation always constructs Pro Audio, even after finding UCM.
`add_pro_profile()` enumerates every playback/capture PCM and calls HW_PARAMS.
A valid HiFi definition therefore does not prevent probing call/realtime/VTS
or unvalidated WDMA endpoints. The observed Abox SysMMU panic during broad capability probing makes unrestricted
hardware probing unsafe during bring-up. Fixing the underlying driver remains
necessary; this scope rule is not a kernel memory-safety fix.

Upstream introduced the exact opt-out property `api.acp.disable-pro-audio` in
commit [a8b9ce2050dfb3f91c19061562d0a161117c3ab8](https://github.com/PipeWire/pipewire/commit/a8b9ce2050dfb3f91c19061562d0a161117c3ab8).
The small backport preserves its author and semantics. Default behavior on other
cards is unchanged. Stock Noble does not implement this property; adding the
Lua rule without the patched plugin still allows unrestricted probing.

The candidate rule matches only `alsa_card.platform-sound` **and** card name
`Exynos8895-Madera`. UCM remains enabled; its HiFi mapping exposes only the
validated normal RDMA0 speaker PCM. The empty fallback profile-set has no
mappings: if UCM cannot load, the card has Off only, rather than probing guessed
generic endpoints. The separate `51-g955n-abox-dump.lua` rule excludes only the
internal DSP-buffer debug card. Camera monitors and actual microphone hardware
are not hidden by these rules; capture needs its own validated UCM definition.

## Exact Ubuntu source and build

Private handset workspace: `/home/ubuntu/g955n-pipewire-build`.
Source was fetched using a private APT lists/cache and explicit `deb-src` entries
with `/usr/share/keyrings/ubuntu-archive-keyring.gpg`. Authenticated Sources hashes
were independently checked for the orig archive, Ubuntu archive and DSC.
`source-authentication.json`, APT logs and the original archives remain there.
`dpkg-source -x` applied all 31 distribution patches, including the existing
CVE-2026 patches, before the local backport. Vanilla upstream replacement is not
used. Source archive and patched-file hashes are pinned in the build runner.
`prepare-ubuntu-source-native.py` reproduces the private signed-metadata download,
independent pinned checksum check, Ubuntu extraction and local backport. Keep it
beside the build runner and `patches/` directory. It never changes system APT
configuration or installs a dependency, and refuses a different source version.

Required additional build packages: `meson ninja-build libasound2-dev`.
The existing GCC/pkg-config/libudev development files are also required.
Flatpak/GSettings and unrelated integration are disabled for this plugin-only
build, so GLib/DBus development packages are unnecessary. Installed PipeWire
executables and all other SPA plugins remain the Ubuntu versions.

`build-alsa-plugin-native.py` builds only `spa/plugins/alsa/libspa-alsa.so` in HOME.
It never runs an install target or opens ALSA. Ubuntu's hardening flags are kept.
The compile-time `/usr` resource prefix is intentional and does not install there.
The runner checks ELF64/AArch64, absence of RPATH/RUNPATH and exact exported-symbol
agreement with the installed plugin. `candidate/build.json` records source and
binary hashes. A successful build is not a live audio acceptance result.

## Candidate installation layout and startup guard

Installation and activation are separate explicit operations. These candidate
files must not be activated while the stock ALSA plugin is selected.

| Candidate | Intended installed path |
| --- | --- |
| `candidate/libspa-alsa.so` from native build | `/usr/local/lib/g955n/spa-0.2/alsa/libspa-alsa.so` |
| `52-g955n-ucm-only.lua` | `/etc/wireplumber/main.lua.d/52-g955n-ucm-only.lua` |
| `g955n-ucm-only.conf` | `/usr/share/alsa-card-profile/mixer/profile-sets/g955n-ucm-only.conf` |
| `g955n-wireplumber` | `/usr/local/libexec/g955n-wireplumber` |
| `10-g955n-validated-plugin.conf` | `/etc/systemd/user/wireplumber.service.d/10-g955n-validated-plugin.conf` |

The launcher requires a root-owned `/usr/local/share/g955n/pipewire-plugin.json`
with exact hashes for the private plugin, both card rules, fallback and both UCM
files. All parents must also be root-managed and not group/world writable. It
checks the installed Ubuntu source version and UCM lookup link. Missing or changed
inputs produce exit 78 before WirePlumber starts; the drop-in prevents a restart
loop for that configuration error. Future rootfs construction must preserve this
guard when the private plugin is not staged, rather than enabling stock probing.

The manifest's `files` dictionary must contain exactly these absolute keys:

```text
/usr/local/lib/g955n/spa-0.2/alsa/libspa-alsa.so
/etc/wireplumber/main.lua.d/51-g955n-abox-dump.lua
/etc/wireplumber/main.lua.d/52-g955n-ucm-only.lua
/usr/share/alsa-card-profile/mixer/profile-sets/g955n-ucm-only.conf
/usr/share/alsa/ucm2/Samsung/SM-G955N/SM-G955N.conf
/usr/share/alsa/ucm2/Samsung/SM-G955N/HiFi.conf
```

Each value is that installed file's SHA-256. Other required fields are
`feature: "api.acp.disable-pro-audio"` and
`ubuntu_source_version: "1.0.5-1ubuntu3.3"`, plus
`plugin_search_mode: "private-only"`,
`hardware_open_scope: "g955n-rdma0-playback-ucm-v2"`, the reviewed
`scope_patch_sha256` and `patched_source_files`, and `original_plugin_sha256` matching the
unchanged Ubuntu ALSA plugin. The generator also records the upstream commit
and candidate hash. The UCM lookup symlink must resolve to the
listed master file. The guard itself is installed root-owned executable and the
systemd drop-in is root-owned 0644; neither is loaded from the user's build tree.

`create-install-manifest.py --build-record PATH` prints manifest JSON for reviewed
installed files; `--stage-root PATH` supports image staging. The installer owns
writing it with root ownership and then running `g955n-wireplumber --check`.
That check does not start WirePlumber or an audio monitor.
If the generator is copied separately, pass
`--guard /usr/local/libexec/g955n-wireplumber` to read the installed guard's exact
file list without executing its startup entry point.

For a quiet profile-enumeration trial, stage a reviewed HiFi configuration with
**both** Speaker.EnableSequence and SectionVerb.EnableSequence setting Speaker
Gain to **0**. Hash that actual staged file, not the future audible Gain=1
configuration. Verb-level base routing is necessary because ACP validates PCM
HW_PARAMS before enabling an individual Speaker device. It can power clocks and
the DPCM backend even without writing PCM samples; mute is retained throughout
the trial. This is a profile/metadata check, not an acoustic or playback test.
The guard must pass before a bounded, separately named user unit is allowed to
run WirePlumber. Keep ordinary/global WirePlumber activation masked during the
trial. Expected profiles are HiFi and Off, with no Pro Audio and no capture/VTS/
call hardware probing. Never infer physical silence or complete device safety
solely from a missing playback stream; retain kernel-log monitoring and the
separate driver-fault investigation.

The exact Ubuntu 1.0.5 loader uses `pw_split_walk(..., ":", ...)` and retries the
next root when a plugin cannot load. A private-plus-stock search path would
therefore still be unsafe if private ALSA has a dependency/load error. The
launcher instead sets `SPA_PLUGIN_DIR` to the **single private root**. Its `alsa`
directory contains only the patched real file. Every other installed stock SPA
family must have a root-owned absolute directory symlink from the private tree
to `/usr/lib/aarch64-linux-gnu/spa-0.2/FAMILY`. The guard checks the complete family
set, ownership, non-writable parents and exact link targets. No ALSA-family link
to the stock module is permitted. Thus a private ALSA load error produces an
audio error instead of unrestricted stock probing. No global library is
replaced. An Ubuntu package upgrade requires a reviewed rebuild/version update
before the guard permits use.

Automatic activation is outside these build steps. A bounded quiet trial remains
a separate root-coordinated operation after the guarded configuration is checked;
it does not resolve the independent kernel DMA fault. Do not run a tone or
microphone capture while the owner has postponed physical tests.

### Quiet trial: partial success, unsafe initial probing unresolved

The bounded UID 105 trial at monotonic 2195.9–2225.7 seconds on boot
identified in the private evidence produced HiFi/Off only, a speaker sink,
no capture node, and Speaker Gain 0. PID 10858 mapped only the private patched
ALSA plugin at the captured midpoint. This verifies final profile integration,
**not** complete prevention of hardware probing. The kernel log at 2196 seconds
still contains 20 HW_PARAMS failures per unsupported RDMA/WDMA endpoint, plus
VTS opens. The 32-bit, eight-channel, 1024-frame requests and sequential PCM
order strongly resemble the Pro Audio scan. No new playback/recording or repeat
trial is authorized by these observations; the independent DMA fault remains.
The interval contained 211 special PCM/backend/VTS events. Ordinary WirePlumber
stays globally masked, including in new image overlays, and both user audio
engines were stopped. Do not unmask based only on correct final profiles.

Saved evidence is under the private inventory directory:
`quiet-profile-trial-{raw.txt,live.txt,kernel.txt,journal.txt,end.txt}`. Device 85
and sink 86 belong to WirePlumber export client 34, PID 10858; the final device
has every intended ACP property. Read-only journal review found one logged
WirePlumber PID and the greeter PipeWire PID 10829 in this interval, without a
logged PulseAudio/second-user session manager. Journald is not a process audit
and cannot exclude a silent transient process. No core map snapshot was saved.

Source review separates the roles: WirePlumber 0.4.17 `SpaDevice` loads the
factory locally with the supplied properties (`lib/wp/device.c:606–625`). Its
`monitors/alsa.lua` applies rules before `createDevice`. PipeWire 1.0.5
`module-client-device.c` creates an exported proxy; it does not instantiate a
second ACP as part of this export. The patched ACP parses the opt-out before
profile probing and has one guarded `add_pro_profile` call. UCM mappings open
only their declared PCM; its `ps->probed` suppresses generic profile probing.
No automatic nested-core ACP cause has been established.

A concrete rule weakness exists: WirePlumber deduplicates `device.name` before
matching rules (`monitors/alsa.lua:219–230`), so a transient second object can be
named `alsa_card.platform-sound.2` and miss the old exact-name rule. The trial's
ReserveDevice duplicate-owner assertion is consistent with duplicate creation,
but does not prove this was the cause. The host candidate now matches the
verified pre-ACP `device.bus-path=platform-sound`, card name and longname instead.
The debug-card rule likewise uses its bus path plus both `abox_dump` names.
`api.alsa.card.driver` is not present in the saved pre-ACP/card properties; adding
it as a mandatory rule condition would fail closed incorrectly. The actual
platform drivers were separately verified through sysfs.

These revised rules pass Lua syntax checks and have **not** been deployed or
retried. Installing them changes guarded file hashes and requires an updated
reviewed manifest. After the kernel's unsafe DMA paths are fixed, a future
bounded quiet trial should retain ACP init logs (PID, card, supplied name,
opt-out value and profile-set) and process/open attribution from startup,
including the PipeWire core. Acceptance requires zero special-PCM opens over
the entire interval, not only correct final profile metadata. If duplicates
still escape policy, enforce the verified-card restriction before ACP probing
rather than merely suppressing profiles after enumeration.

### Scoped PCM candidate (not installed)

`patches/0002-g955n-pcm-open-scope.patch` adds a second boundary below
WirePlumber's mutable object names. Apply it after 0001 to the authenticated
Ubuntu source. The standalone `g955n-scope.h` is the exact header included in
that patch, not a separately installed runtime file.

The dedicated candidate requires a readable DT model containing SM-G955N.
Before ACP discovery it queries ALSA **control-card INFO**, requiring all four
primary identity fields: driver `Exynos8895-Made`, card ID `Exynos8895Mader`, name
and longname `Exynos8895-Madera`. A partial identity match is an error. Primary
ACP forces UCM, disables Pro Audio, fixes the probe rate to 48000 and rejects
UCM failure before generic fallback. The exact debug-card driver/name/longname
`abox_dump` and ID `aboxdump` are rejected before ACP profiling.

Both production `snd_pcm_open` entry points, ACP `alsa-util.c` and runtime
`alsa-pcm.c`, additionally validate the actual control-card identity **before**
opening the requested PCM. Protected primary hardware accepts only PCM 0,
subdevice 0, playback. Capture, CALL, VTS and realtime PCM addresses are refused.
DSP dump and unknown/external cards are refused pending separate qualification.
This dedicated development build refuses ALSA aliases and
plug wrappers on this handset because they can resolve to a protected card
behind another name; the verified UCM speaker's direct hardware string remains
supported. Model/identity/permission errors reject the request rather than
falling back. This is not a general-purpose upstream ALSA policy.

Every requested production open has a `G955N_PCM_SCOPE` journal line **before**
`snd_pcm_open_lconf`, including rejected attempts. Fields include origin (`acp` or
`runtime`), PID, per-origin sequence, actual control-card number, parsed PCM,
direction, hardware scope, policy result and requested device. A zero result
means permission to attempt the isolated open, not successful playback. Unresolvable identity
is explicitly card=-1; this is not reported as a verified card. ACP initialization
also logs its hardware scope. These logs permit startup-wide attribution and
counts; no PCM contents or microphone audio are collected.

Control resolution uses a private minimal `ctl.g955n_native` type-hw
configuration via `snd_ctl_open_lconf`. PCM open uses a separate private minimal
`pcm.g955n_native` type-hw configuration via `snd_pcm_open_lconf`, with the actual
control INFO card number and only the validated PCM/subdevice. Global ALSA
configuration, `pcm.hw` redefinition, user hooks and aliases cannot redirect
these calls. Pure control `snd_ctl_pcm_info` additionally requires ID
`RDMA0 (*)`, empty name, playback/card/device/subdevice/count matching the saved
`/proc/asound/card0/pcm0p/info` (card0/device0/sub0/count1). The pinned kernel
PCM_INFO ioctl copies metadata without DPCM startup or HW_PARAMS.

The launcher also clears inherited ALSA_* overrides, pins the default system
ALSA configuration and passwd HOME/XDG directory for UCM/mixer setup, and refuses
per-user .asoundrc or .config/alsa/asoundrc. These checks supplement the isolated
PCM/control roots; they are not the sole PCM boundary.

The C test `test-g955n-scope.c` supplies mock implementations of every ALSA
control/config/PCM call and does not link libasound. It verifies no global
snd_ctl_open/snd_pcm_open is called, including with a hostile ALSA_CONFIG_PATH.
`test-g955n-config.c` separately exercises only the real configuration parser
and checks the three minimal roots, with no control/PCM API calls. It covers primary playback allow,
32 denied capture addresses, unsupported playback/debug paths, aliases,
malformed/overflow addresses, inconsistent card identity, permission failure, wrong PCM identity, unknown cards,
and a nonmatching model. Its only file is a temporary model fixture, removed at
exit. Native compilation uses actual ALSA headers, `-Wall -Wextra -Werror`.
No production factory/plugin is loaded by this test.

Keep the original reviewed source/build/candidate intact. Create a separate
HOME `pipewire-1.0.5-scoped-v2` source copy, apply 0002, and run
`build-alsa-plugin-native.py --g955n-scope`. It uses `build-alsa-scoped-v2` and
`candidate-scoped-v2`, verifies all source/archive/scope-patch hashes and preserves
the complete 31-patch Ubuntu series. Build metadata adds
`hardware_open_scope=g955n-rdma0-playback-ucm-v2` and `scope_patch_sha256`.
The candidate manifest generator and guard now require these fields, so the
old Pro-only build cannot satisfy the revised launcher. Installing the revised
launcher, plugin, candidate rules and corresponding manifest is a separate
root-reviewed operation; these source/build steps do not change the installed
prefix or start an audio service. A successful build/test is not a live claim
that all unsafe kernel entry paths are fixed.

Stable pre-rule matching evidence: Ubuntu's `spa/plugins/alsa/alsa-udev.c:543–547`
emits `device.bus-path` from udev `ID_PATH` into the object properties before
`spa_device_emit_object_info`; card name/longname are emitted at lines 526–529.
WirePlumber's `monitors/alsa.lua:209–230` changes only `device.name` for
deduplication, then `rulesApplyProperties` at line 279 receives the original
bus path. The saved trial device has bus path `platform-sound`; the saved debug
card has `platform-samsung-abox-dump.20`. Candidate matching uses these stable
pre-rule identities rather than the potentially suffixed presentation name.

Historical v1 isolated build validation (before its incomplete trial): native
`candidate-scoped/build.json` records ELF SHA-256
`4c44529fc5599b8069dd76653b29c8eeabc7c11d0bff91fe0280963a3984200b`
(2,959,088 bytes), scope-patch SHA-256
`434c849ca354e5a5611ab8519bd9ffae197f5df127d21cbb610a72269e01079b`.
The copied private host artifact matches that hash. Both mocked policy/lconf
and real parser-only tests passed. ELF exported symbols match the Ubuntu
plugin; RELRO/BIND_NOW/NX stack remain enabled and no RPATH/RUNPATH is present.
ELF imports `snd_pcm_open_lconf`, with no `snd_pcm_open` import. Existing
control/mixer routines still import `snd_ctl_open`; scoped identity resolution
uses `snd_ctl_open_lconf`. The installed stock and private Pro-only plugin
hashes remained unchanged during build and verification. No daemon, production
plugin factory or physical PCM was started by this work.

### UCM namespace correction, v2

The root-coordinated muted v1 trial lasted 21.2 seconds without a reset. It
loaded the expected private plugin in both relevant processes and attempted
`_ucm0001.hw:Exynos8895Mader,0` and `_ucm0002.hw:Exynos8895Mader,0`. V1 refused
those names before opening any PCM. The result was **Off only, no HiFi and no
sink**; zero special-PCM opens demonstrates containment, not working audio.
Evidence is privately retained under `artifacts/scoped-quiet-trial-evidence`.

ALSA 1.2.11 [`src/ucm/main.c:668`](https://github.com/alsa-project/alsa-lib/blob/v1.2.11/src/ucm/main.c#L668)
adds `_ucm%04X.` to local-configuration PCM names. Although printf's width is a
minimum, the actual consumer
[`uc_mgr_alibcfg_by_device`](https://github.com/alsa-project/alsa-lib/blob/v1.2.11/src/ucm/utils.c#L837)
requires a dot at byte eight, parses exactly four hexadecimal characters, and
rejects values outside 0..0xffff. V2 accepts exactly one such canonical generated
namespace: `_ucm` + four uppercase hex digits + `.` immediately followed by
`hw:`. It deliberately rejects lowercase/noncanonical prefixes, long/truncated
IDs, nested namespaces and aliases. No UCM namespace is looked up or trusted as
authority: only its decoration is removed, after which the full independent
control-card/PCM INFO/direction policy and numeric private lconf open remain.

The extended mock tests cover both observed IDs, a hexadecimal ID, the 16-bit
limit, plain addresses, malformed prefixes, other cards, capture and PCM/subdevice
redirection. Every accepted form must reach the same literal numeric RDMA0
lconf; every denied form must leave the mock open count unchanged. Global
snd_ctl_open/snd_pcm_open calls must remain zero with a hostile configuration
environment. No real PCM is opened by these tests.

The v2 source/build/candidate directories are separate from v1 and use attestation
`hardware_open_scope=g955n-rdma0-playback-ucm-v2`. The host guard and manifest
generator require that reviewed v2 field and updated source/patch/plugin hashes.
Installation and activation remain separate reviewed operations. The live
checkpoint below qualifies bounded metadata probing only; acoustic, microphone
and kernel DMA-fault acceptance remain separate.

The completed v2 native build candidate is
`~/g955n-pipewire-build/candidate-scoped-v2/libspa-alsa.so`, SHA-256
`f1ac9da4dac0d462f0ccaa6807d0b8dcacb90c40d8cb4cf3ec67c91a453426a8`
(2,960,888 bytes); scope patch SHA-256
`8f2edae1cfbe22f243011f691eb20eebe8a563f3f2347141297f8aa3f867031a`.
Mock UCM/full-policy/global-open-zero tests and real parser-only tests passed;
all 31 Ubuntu patches and symbol ABI are preserved. The copied host ELF and
source/patch pins match its build record. Its only PCM-open import is
`snd_pcm_open_lconf`. Raw build/test evidence stays privately in
`artifacts/pipewire-plugin-scoped-v2/`.

### Installed v2 quiet checkpoint and core guard

The reviewed v2 binary is installed in the private SPA tree, with an updated
root-owned manifest and all four runtime UCM Speaker Gain values fixed at 0.
A bounded 21.2-second greeter trial exported Off/HiFi and the normal speaker
sink, no capture node. Both WirePlumber and the actual PipeWire core mapped
only the reviewed private ALSA plugin. Full-interval open/openat traces in both
processes contain only `/dev/snd/pcmC0D0p`; no call/realtime/VTS/capture PCM was
opened. Gain stayed 0, the boot stayed unchanged, and every test audio engine
was stopped. VTS mixer-control reads are not VTS PCM opens. This is containment
and profile integration evidence, not audible playback or a kernel-fault cure.

The launcher also accepts `--pipewire` to apply the same manifest/configuration
guard and private-only SPA root to the actual PCM engine. The separate
`10-g955n-validated-core.conf` user-service drop-in selects that mode. A default
core must not load the stock unscoped plugin after the policy daemon exports a
node. Both drop-ins and the launcher are staged by image finalization; an image
without the reviewed binary/manifest fails closed rather than probing hardware.
Global WirePlumber activation remains masked until fuller qualification.

### Ubuntu image integration

`scripts/build_rootfs.py --audio-build DIRECTORY` optionally stages
the matching reviewed audio ABI in a private SPA tree and enables
the standard WirePlumber service for the Ubuntu desktop account. The
directory contains the native build's `build.json` and `libspa-alsa.so`.
The installer checks the two startup guards, distro package version and
both plugin hashes before removing the mask. Without this explicit
input, the image keeps WirePlumber masked.

### WDMA1 microphone scope, v3

Stage `pipewire-1.0.5-scoped-v3` from the authenticated source with `0001`
and `0002` applied. Run `build-alsa-plugin-native.py --g955n-scope` and use
`candidate-scoped-v3` for image staging. The runtime manifest requires
`hardware_open_scope=g955n-rdma0-wdma1-ucm-v3`. The policy verifies the
card and exact PCM ID before opening RDMA0 playback or WDMA1 capture.
The HiFi microphone sends the main digital mic to both PCM channels
through UAIF0, NSRC0 and SIFM0. Normal PipeWire playback and capture have
passed on kernel36 with no partition changes. See [hardware validation](../../docs/VALIDATION.md).

### Kernel54 desktop continuity

The scoped RDMA0/WDMA1 nodes use 2,048-frame periods, eight periods and
4,096 frames of scheduling headroom at 48 kHz S16LE stereo. This requests a
64 KiB hardware ring instead of the default 128 KiB. On the installed ABOX
firmware, the larger playback ring repeatedly reset the reported ALSA pointer
around its halfway point and caused internal PipeWire errors and audible gaps.
The exact firmware/register cause is not yet established. The extra headroom
also removed a rarer underrun seen after reducing the ring alone.

After updating these guarded rules, regenerate the installation manifest from
the reviewed build record and run the startup guard before restarting
WirePlumber. Keep the original private plugin and its exact PCM-open scope.
Speaker/mic defaults are normal persistent WirePlumber selections; GNOME's
volume and mute controls use the ordinary PipeWire/Pulse services.

`check-desktop-audio.py --test-speaker-microphone` explicitly performs a bounded
five-second duplex test through the desktop defaults. Microphone bytes remain
in memory, and only numeric statistics are printed. It restores volume/mute and
checks actual hardware error counters, PCM progress and new kernel faults.
Missing counters fail qualification. Client completion and a nonconstant signal
are not acoustic-quality acceptance. The first quarter-second is reported
separately: cold microphone activation still has a measured startup transient.

### Kernel endpoint scope with stock Ubuntu audio

The diagnostic kernel's `--native-alsa-scope` option adds a board-only
check before native ALSA dispatches a device open. On the built-in Madera
card it accepts RDMA0 playback, WDMA1 capture and ordinary mixer control.
It rejects other built-in PCM opens, compressed playback and the ABOX
debug card before their handlers can open or power those endpoints.
Other audio cards are outside this restriction.

The standard UCM speaker/microphone routes and WirePlumber settings remain
the userspace routing policy. On a boot with the verified kernel scope,
`check-desktop-audio.py --test-speaker-microphone --kernel-alsa-scope`
requires the Ubuntu ALSA SPA plugin to be mapped and the private SPA tree
to be absent from the actual audio processes. It then tests playback and
capture on the same published hardware endpoints. The existing private
launcher continues to protect boots without the new kernel policy.

The optional `g955n-native-alsa.service` records the active boot ID only
after the board's device tree and the kernel startup message both confirm
the scope. The launcher selects Ubuntu's SPA directory with a root-owned
receipt under `/var/lib/g955n-native-alsa` that matches the current boot ID.
An old receipt cannot authorize a later boot. Standard UCM and WirePlumber
policy hashes are still checked. Without a valid receipt, the existing
private-plugin checks apply.
Install and enable this unit only after the Ubuntu stock playback and
capture trial has passed on the target kernel.

On the native SM-G955N Linux 6.18 boot, the launcher runs the installed
Ubuntu PipeWire and WirePlumber binaries with the default SPA search
path. This permits Ubuntu package updates independently of the
vendor-kernel PCM guard. Speaker and microphone qualification still
requires an ALSA card exposed by the 6.18 audio drivers.
