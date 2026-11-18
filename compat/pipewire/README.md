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
`plugin_search_mode: "private-only"` and `original_plugin_sha256` matching the
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
