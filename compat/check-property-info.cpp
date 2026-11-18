// Validate staged metadata using the unmodified pinned AOSP property-info parser.
#include <property_info_parser/property_info_parser.h>
#include <cstring>
#include <cstdio>
int main(int argc, char **argv) {
    if (argc != 2) return 2;
    android::properties::PropertyInfoAreaFile file;
    if (!file.LoadPath(argv[1])) return 1;
    if (file->current_version() != 1 || file->minimum_supported_version() != 1 ||
        file->num_contexts() != 1 || file->num_types() != 1) return 1;
    const char *names[] = {"hwservicemanager.ready", "ro.hardware.hwcomposer", "ro.property_service.version"};
    for (const char *name : names) {
        const char *context = nullptr, *type = nullptr;
        file->GetPropertyInfo(name, &context, &type);
        if (!context || !type || std::strcmp(context, "u:object_r:default_prop:s0") ||
            std::strcmp(type, "string")) return 1;
    }
    std::puts("Pinned AOSP parser accepted all property-context lookups");
    return 0;
}
