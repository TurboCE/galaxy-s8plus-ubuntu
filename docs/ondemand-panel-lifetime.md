# Ondemand private-data lifetime in the panel callback

The pinned custom kernel's update_gov_tunables() follows per-CPU Ondemand state
without a policy reference or lifetime lock. It unconditionally casts
policy->governor_data to dbs_data and its tuners to od_dbs_tuners. A different
active governor, a stopped governor or CPU-policy teardown can invalidate those
assumptions. This is a concrete source-level lifetime/type-safety bug.

Proposal31 obtains a referenced policy with cpufreq_cpu_get, holds policy->rwsem
against governor transitions, checks the actual governor pointer, and uses the
Ondemand common-data mutex plus cdata/tuners checks before touching the private
fields. It updates one online policy representative per cluster and balances
all references/locks. It does not switch governors, pin CPU clocks, or disable
thermal/idle handling.

The extracted actual old callback reproduces an ASan heap-buffer-overflow when
handed another governor's smaller private storage. The fixed actual helper and
callback pass that case, normal suspend/resume values, absent governor_data and
wrong common-data cleanup. These fixtures are not on-device race reproduction.
The observed device's latest policies both reported ondemand and the desktop
power-profiles service was inactive: a foreign-governor switch is **not proven
to have caused the retained RCU fault**. Concurrent teardown also remains
unproven. Do not label the entire kernel corruption problem solved by this patch.

Kernel28 is a build-only candidate adding proposal31 to kernel27's primary-QoS
transaction and kernel26's DPP/pan lifetime fixes. Hardware acceptance and actual
kernel fault evidence remain separate. Private build/tests live under
artifacts/ondemand-safety.
