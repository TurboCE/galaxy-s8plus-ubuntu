# SM-G955N Ubuntu port

Target only SM-G955N / dream2lteks / Exynos 8895. Never reuse G965N images.
Record device changes and evidence in docs/CHANGELOG.md and docs/VALIDATION.md.
Build success is not hardware success. Track Android baseline and Ubuntu separately.
Keep identifiers, dumps, backups, credentials and vendor firmware out of Git.
Build and inventory scripts must never flash, reboot, root or change device settings.
Before any device write verify model, matching stock recovery materials, private
backups with hashes, and the exact authorized write targets. Preserve RECOVERY,
EFS, RADIO, bootloaders and calibration. Never downgrade or relock bootloaders.
Retain upstream attribution and licenses. Review redistribution before publishing binaries.
5G NR is unsupported hardware; 5 GHz Wi-Fi is a separate validation target.
