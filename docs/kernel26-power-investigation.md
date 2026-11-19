# Kernel26 screen-power investigation, 2026-11-19

Kernel26's short boot, five greeter DPMS cycles, owner-confirmed touch login and
three ordinary Mali GNOME composition/popup trials passed. It is **not stability
qualified**. A subsequent desktop power trial lost both Wi-Fi and USB-console
responses. The owner had also pressed the physical power button during that
trial. A short press did not recover it; the owner manually rebooted.

The previous journal contains no recorded systemd suspend entry. That absence
alone does not prove that suspend never began. The partially damaged retained
kernel buffer, after its matching kernel26 banner, contains a NULL-pointer
exception in `_raw_spin_lock` called from `rcu_read_unlock_special`; the visible
stack includes scheduler CPU accounting and the GPU DVFS thread. This identifies
a fault site, not the original corrupting writer. Do not insert a NULL guard to
hide broken RCU state. Damaged retained bytes cannot be treated as exact intact
register values or proof of defective physical RAM.

Address decoding must account for KASLR. For this retained fault, the matching
System.map `_raw_spin_lock` plus its printed function offset gives relocation
0x5c000. Subtracting that displacement resolves the shown caller addresses to
rcu_read_unlock_special, __rcu_read_unlock, cpuacct_charge and update_curr in the
matching kernel26 vmlinux. Unadjusted addr2line output is unrelated and invalid.
Do not carry this displacement to a different boot.

After the owner's reboot, a real password/PAM login was performed remotely using
the owner-provided credentials, preserving manual-login configuration. A first
five-cycle desktop DPMS repeat passed with taint0. A subsequent 20-cycle attempt,
without physical input, stopped during its fourth off/on cycle. Progress records
showed suspended/off and the start of the on request. A foreground SSH kernel
stream saved the last live messages on the host: primary panel power-down,
MIF/INT/display screen-off QoS, and duplicate blank notifications. Both remote
transports stopped responding. No final exception was delivered by that stream.
Thus physical power-button input is not required for this new reproduction.
This does not prove the memory/bus driver caused the halt merely because its
messages were last.

The first attempted host capture used an untracked child process and ended with
its launcher; it was not a continuing crash capture. The second used a managed
foreground tool session and did preserve the failure interval. Keep this
transport distinction when evaluating evidence.

Source review found an additional concrete decon_blank error: bus/CPU QoS is
restored after decon_enable, invalid/failed requests still change global suspend
state, and secondary blank operations change the primary's shared QoS state.
Proposal30 makes the primary operation a serialized QoS transaction, restores
active constraints before wake-up hardware access, publishes low-power state
only after successful disable, and rolls back failed wake-ups. Seven extracted
actual-function cases pass; the original reproduces the pre-enable ordering
violation. These are source-level fixes; hardware root cause remains unproven.
Kernel27 is a build-only candidate until installed and qualified separately.

The phone is presently unresponsive after the repeated trial. The owner is away
and cannot provide physical recovery. Continue host-side review/build/test;
do not claim a new deployment or successful device test without reconnection.

Private evidence remains under artifacts/panel-safety: power-hang26-*;
desktop-power-cycles26-live.log; desktop-power-cycles26-20.log;
kernel26-live-follow2.raw. Neither raw logs nor credentials are committed.
