-- CANDIDATE ONLY. Install after the matching libspa-alsa backport is verified.
-- Stock Noble PipeWire 1.0.5 silently ignores disable-pro-audio and still probes
-- every hardware PCM. This file alone cannot make that binary safe to start.
table.insert(alsa_monitor.rules, {
  matches = {
    {
      -- prepareDevice deduplicates device.name before applying rules.
      -- Match pre-ACP hardware identity, including transient duplicate objects.
      { "device.bus-path", "equals", "platform-sound" },
      { "api.alsa.card.name", "equals", "Exynos8895-Madera" },
      { "api.alsa.card.longname", "equals", "Exynos8895-Madera" },
    },
  },
  apply_properties = {
    ["api.alsa.use-acp"] = true,
    ["api.alsa.use-ucm"] = true,
    ["api.acp.disable-pro-audio"] = true,
    ["api.acp.probe-rate"] = 48000,
    ["api.alsa.soft-mixer"] = true,
    -- If UCM fails, fall back to Off, not generic unsafe PCM enumeration.
    ["device.profile-set"] = "g955n-ucm-only.conf",
  },
})
