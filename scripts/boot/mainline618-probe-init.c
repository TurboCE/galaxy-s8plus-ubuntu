// SPDX-License-Identifier: GPL-2.0-only
/* Initial SM-G955N boot probe, with no persistent storage access. */
#include <stdio.h>
#include <string.h>
#include <sys/mount.h>
#include <sys/utsname.h>
#include <unistd.h>

static int check_model(void)
{
	char model[128] = {0};
	FILE *dt_model = fopen("/sys/firmware/devicetree/base/model", "r");
	if (!dt_model)
		return 0;

	size_t length = fread(model, 1, sizeof(model) - 1, dt_model);
	fclose(dt_model);
	return length && strcmp(model, "Samsung Galaxy S8+ (SM-G955N)") == 0;
}

int main(void)
{
	struct utsname version;

	if (mount("sysfs", "/sys", "sysfs", MS_NOSUID | MS_NODEV | MS_NOEXEC, NULL) ||
	    !check_model() || uname(&version) || strncmp(version.release, "6.18", 4)) {
		puts("SM-G955N mainline boot probe could not verify the kernel and board.");
	} else {
		printf("SM-G955N INITRAMFS OK - Linux %s\n", version.release);
		puts("The initramfs is running. No device partitions were mounted.");
	}
	fflush(stdout);

	/* Leave the result on the console until the device is restarted. */
	for (;;)
		pause();
}
