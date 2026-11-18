-- WirePlumber 0.4.x: do not expose ABOX internal DSP buffer dumps as microphones.
-- Verified driver: samsung-abox-dump; native card name: abox_dump.
-- Its platform instance is the last registered dump buffer ID, so match that
-- instance suffix in the stable bus path and both diagnostic card names.
-- Do not rely on device.name, which WirePlumber may deduplicate before rules.
-- The Exynos8895-Madera playback/capture card and camera monitors are unchanged.
table.insert(alsa_monitor.rules, {
  matches = {
    {
      { "device.bus-path", "matches", "platform-samsung-abox-dump.*" },
      { "api.alsa.card.name", "equals", "abox_dump" },
      { "api.alsa.card.longname", "equals", "abox_dump" },
    },
  },
  apply_properties = {
    ["device.disabled"] = true,
  },
})
