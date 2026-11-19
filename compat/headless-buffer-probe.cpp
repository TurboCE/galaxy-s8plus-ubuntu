/* Bounded Android9 native-buffer diagnostic. No HWC, window, display/power or
 * service activation. Only a previously registered allocator may be used.
 */
#include <android/hardware/graphics/allocator/2.0/IAllocator.h>
#include <android/hardware/graphics/mapper/2.0/IMapper.h>
#include <android/hidl/manager/1.0/IServiceManager.h>
#include <hidl/ServiceManagement.h>
#include <cerrno>
#include <cstdio>
#include <cstdlib>
#include <cstring>
#include <dlfcn.h>
#include <fcntl.h>
#include <initializer_list>
#include <poll.h>
#include <sys/prctl.h>
#include <sys/stat.h>
#include <sys/statvfs.h>
#include <sys/system_properties.h>
#include <unistd.h>
using android::sp;
using android::hardware::hidl_handle;
using android::hardware::hidl_vec;
using android::hardware::graphics::allocator::V2_0::IAllocator;
using android::hardware::graphics::mapper::V2_0::IMapper;
using android::hardware::graphics::mapper::V2_0::Error;
using android::hardware::graphics::mapper::V2_0::BufferDescriptor;
using android::hardware::graphics::common::V1_0::PixelFormat;
using android::hardware::graphics::common::V1_0::BufferUsage;
static constexpr uint32_t side = 64;
static constexpr const char *allocator_descriptor = "android.hardware.graphics.allocator@2.0::IAllocator";

static bool contains(const char *path, const char *value) {
    char text[1024] = {};
    int fd = open(path, O_RDONLY | O_CLOEXEC);
    if (fd < 0) return false;
    ssize_t n = read(fd, text, sizeof(text)-1);
    close(fd);
    return n > 0 && strstr(text, value);
}
static bool readonly(const char *path) {
    struct statvfs fs;
    return statvfs(path, &fs) == 0 && (fs.f_flag & ST_RDONLY);
}
static bool char_node(const char *path) {
    struct stat st;
    return lstat(path, &st) == 0 && S_ISCHR(st.st_mode);
}
static bool guard(int allocator_pid, const char *boot, bool gpu, bool display=false) {
    if ((!contains("/sys/firmware/devicetree/base/model", "SM-G955N") &&
         !contains("/proc/device-tree/model", "SM-G955N")) ||
        !contains("/proc/sys/kernel/osrelease", "g955n-ubuntu") || strlen(boot) != 36 ||
        !contains("/proc/sys/kernel/random/boot_id", boot)) return false;
    const char *marker = getenv("G955N_ANDROID_PRIVATE_RUNTIME");
    if (!marker || strcmp(marker,"1")) return false;
    for (const char *kind : {"pid", "mnt"}) {
        char path[64], value[128] = {};
        snprintf(path,sizeof(path),"/proc/self/ns/%s",kind);
        const char *parent = getenv(!strcmp(kind,"pid") ? "G955N_PARENT_PID_NS" : "G955N_PARENT_MOUNT_NS");
        if (!parent || readlink(path,value,sizeof(value)-1) < 0 || !strcmp(value,parent)) return false;
    }
    if (prctl(PR_GET_NO_NEW_PRIVS,0,0,0,0) != 1) return false;
    for (int cap : {16,17,21,22,27}) if (prctl(PR_CAPBSET_READ,cap,0,0,0) != 0) return false;
    for (const char *path : {"/proc","/sys","/system","/vendor"}) if (!readonly(path)) return false;
    for (const char *path : {"/efs","/proc/1/root/efs","/dev/block","/dev/snd","/dev/graphics","/dev/fb0","/dev/dri","/dev/video0","/dev/sw_sync"})
        if (!(display && (!strcmp(path,"/dev/graphics")||!strcmp(path,"/dev/fb0")||!strcmp(path,"/dev/sw_sync"))) &&
            (access(path,F_OK) == 0 || errno != ENOENT)) return false;
    if (display && (!char_node("/dev/fb0")||!char_node("/dev/graphics/fb0"))) return false;
    if (!char_node("/dev/ion") || (gpu ? !char_node("/dev/mali0") : (access("/dev/mali0",F_OK) == 0 || errno != ENOENT))) return false;
    char ready[PROP_VALUE_MAX] = {};
    if (__system_property_get("hwservicemanager.ready",ready) <= 0 || strcmp(ready,"true")) return false;
    if (allocator_pid == 0) return true; // Real list-only absence check.
    char command[512] = {}, path[64];
    snprintf(path,sizeof(path),"/proc/%d/cmdline",allocator_pid);
    int fd = open(path,O_RDONLY|O_CLOEXEC);
    if (fd < 0) return false;
    ssize_t n = read(fd,command,sizeof(command)-1); close(fd);
    return n > 0 && !strcmp(command,"/vendor/bin/hw/android.hardware.graphics.allocator@2.0-service");
}
static bool wait_fence(const hidl_handle &fence) {
    const native_handle_t *h = fence.getNativeHandle();
    if (!h) return true;
    if (h->numFds == 0 && h->numInts == 0) return true;
    if (h->numFds != 1 || h->numInts != 0) return false;
    struct pollfd p = {h->data[0],POLLIN,0};
    int r = poll(&p,1,1000);
    return r == 1 && (p.revents & POLLIN) && !(p.revents & (POLLERR|POLLNVAL));
}
struct BufferOwner {
    sp<IMapper> mapper;
    uint32_t stride=0;
    hidl_handle raw;
    void *imported = nullptr;
    bool locked = false, closed = false, clean = true, unsafe = false;
    [[noreturn]] void quarantine(const char *reason) {
        fprintf(stderr,"unsafe_buffer_state=%s; no explicit free/FD reuse; process teardown required\n",reason);
        _exit(21); // Stops every thread and lets the kernel close FDs/mappings.
    }
    bool unlock() {
        if (!locked) return true;
        Error error = Error::BAD_BUFFER;
        hidl_handle fence;
        bool callback=false,clone_ok=true;
        auto ret = mapper->unlock(imported,[&](Error e,const hidl_handle &f){callback=true;error=e;fence=f;if(f.getNativeHandle()&&!fence.getNativeHandle())clone_ok=false;});
        if (!ret.isOk() || !callback || !clone_ok || error != Error::NONE) {unsafe=true;return false;}
        locked = false;
        if (!wait_fence(fence)) {unsafe=true;return false;}
        return true;
    }
    bool close() {
        if (closed) return clean;
        closed = true;
        if (unsafe || !unlock()) quarantine("unknown_lock_or_unsignaled_release_fence");
        if (imported) {
            void *buffer=imported; imported=nullptr;
            auto ret=mapper->freeBuffer(buffer);
            if (!ret.isOk() || static_cast<Error>(ret) != Error::NONE) quarantine("mapper_free_failed");
        }
        raw=hidl_handle(); // closes cloned raw native-handle FDs, never borrowed FDs
        return clean;
    }
    ~BufferOwner(){close();}
};
static bool cpu_roundtrip(BufferOwner &owner,uint32_t stride,bool write,bool gpu_result,uint32_t gpu_red=191) {
    void *data=nullptr;
    Error error=Error::BAD_BUFFER;
    uint64_t cpu=static_cast<uint64_t>(write ? BufferUsage::CPU_WRITE_OFTEN : BufferUsage::CPU_READ_OFTEN);
    IMapper::Rect rect={0,0,side,side};
    bool callback=false;
    auto ret=owner.mapper->lock(owner.imported,cpu,rect,hidl_handle(),[&](Error e,void *p){callback=true;error=e;data=p;if(e==Error::NONE)owner.locked=true;});
    if (!ret.isOk() || !callback || (error != Error::NONE && data)) {owner.unsafe=true;return false;}
    if (error != Error::NONE || !data) return false;
    auto bytes=static_cast<unsigned char *>(data);
    bool good=true;
    for (uint32_t y=0;y<side;++y) for(uint32_t x=0;x<side;++x) {
        unsigned char *p=bytes+(static_cast<size_t>(y)*stride+x)*4;
        const unsigned char expected[4]={static_cast<unsigned char>(gpu_result ? gpu_red : 17),
                                        static_cast<unsigned char>(gpu_result ? 128 : 33),
                                        static_cast<unsigned char>(gpu_result ? 191 : 65),255};
        for(int c=0;c<4;++c) if(write) p[c]=expected[c]; else if(abs(p[c]-expected[c])>(gpu_result ? 2 : 0)) good=false;
    }
    return owner.unlock() && good;
}

static int verify_gpu_frame(void *cookie,uint32_t red) {
    return cpu_roundtrip(*static_cast<BufferOwner *>(cookie),static_cast<BufferOwner *>(cookie)->stride,false,true,red) ? 0:1;
}

static int registration_query(int expected_pid,bool absence_only) {
    auto manager=android::hardware::defaultServiceManager();
    if(!manager)return 5;
    bool listed=false;
    auto listing=manager->list([&](const auto &names){for(const auto &n:names)if(!strcmp(n.c_str(),"android.hardware.graphics.allocator@2.0::IAllocator/default"))listed=true;});
    if(!listing.isOk())return 5;
    if(!listed){puts("allocator_registration=absent");return absence_only ? 0:3;}
    if(absence_only){puts("allocator_registration=unexpected_existing");return 4;}
    int peer=-1,debug_pid=-2;
    auto dump=manager->debugDump([&](const auto &entries){for(const auto &e:entries)if(!strcmp(e.interfaceName.c_str(),allocator_descriptor)&&!strcmp(e.instanceName.c_str(),"default"))peer=e.pid;});
    if(!dump.isOk())return 5;
    auto got=manager->get(allocator_descriptor,"default");
    if(!got.isOk())return 5;
    sp<android::hidl::base::V1_0::IBase> base=got;
    if(!base||!base->isRemote())return 5;
    auto info=base->getDebugInfo([&](const auto &d){debug_pid=d.pid;});
    if(!info.isOk())return 5;
    bool match=peer==expected_pid&&(debug_pid==expected_pid||debug_pid==-1);
    printf("allocator_registration=%s namespace_pid=%d expected_pid=%d transport=hwbinder debug_pid=%d pid_source=manager_registration\n",match ? "present":"pid_mismatch",peer,expected_pid,debug_pid);
    return match ? 0:4;
}

static int run(int expected_pid,bool gpu,const char *plugin,BufferOwner &owner) {
    auto manager=android::hardware::defaultServiceManager();
    if (!manager) return 3;
    bool listed=false;
    auto listing=manager->list([&](const auto &names){for(const auto &n:names) if(!strcmp(n.c_str(),"android.hardware.graphics.allocator@2.0::IAllocator/default")) listed=true;});
    if (!listing.isOk() || !listed) return 3; // never get an absent/lazy service
    int peer=-1;
    auto dump=manager->debugDump([&](const auto &entries){for(const auto &e:entries) if(!strcmp(e.interfaceName.c_str(),allocator_descriptor)&&!strcmp(e.instanceName.c_str(),"default")) peer=e.pid;});
    if (!dump.isOk() || peer != expected_pid) return 3;
    auto got=manager->get(allocator_descriptor,"default");
    if (!got.isOk()) return 3;
    sp<android::hidl::base::V1_0::IBase> base=got;
    if (!base || !base->isRemote()) return 3;
    auto cast=IAllocator::castFrom(base);
    if (!cast.isOk()) return 3;
    sp<IAllocator> allocator=cast;
    owner.mapper=IMapper::getService("default",true); // declared stock passthrough mapper, not a new daemon
    if (!allocator || !owner.mapper || owner.mapper->isRemote()) return 4;
    uint64_t usage=static_cast<uint64_t>(BufferUsage::CPU_READ_OFTEN)|static_cast<uint64_t>(BufferUsage::CPU_WRITE_OFTEN);
    if(gpu) usage|=static_cast<uint64_t>(BufferUsage::GPU_TEXTURE)|static_cast<uint64_t>(BufferUsage::GPU_RENDER_TARGET);
    IMapper::BufferDescriptorInfo info={side,side,1,PixelFormat::RGBA_8888,usage};
    BufferDescriptor descriptor;
    Error error=Error::BAD_DESCRIPTOR;
    auto desc=owner.mapper->createDescriptor(info,[&](Error e,const BufferDescriptor &d){error=e;descriptor=d;});
    if (!desc.isOk() || error != Error::NONE) {printf("create_descriptor_error=%d\n",static_cast<int>(error));return 5;}
    uint32_t stride=0;
    bool one=false;
    auto allocation=allocator->allocate(descriptor,1,[&](Error e,uint32_t s,const hidl_vec<hidl_handle> &buffers){error=e;stride=s;if(e==Error::NONE&&buffers.size()==1){owner.raw=buffers[0];one=true;}});
    printf("allocate_error=%d stride=%u one_buffer=%s\n",static_cast<int>(error),stride,one ? "yes":"no");
    if (!allocation.isOk() || error != Error::NONE || !one || stride<side || stride>4096 || !owner.raw.getNativeHandle()) return 6;
    owner.stride=stride;
    printf("owned_raw_handle_fds=%d ints=%d\n",owner.raw.getNativeHandle()->numFds,owner.raw.getNativeHandle()->numInts);
    void *candidate=nullptr;
    bool import_callback=false;
    auto imported=owner.mapper->importBuffer(owner.raw,[&](Error e,void *buffer){import_callback=true;error=e;candidate=buffer;});
    if (!imported.isOk() || !import_callback || (error != Error::NONE && candidate) ||
        (error == Error::NONE && !candidate)) {owner.unsafe=true;return 7;}
    if (error != Error::NONE) return 7;
    owner.imported=candidate;
    printf("headless_buffer_imported_pid=%d\n",getpid());
    usleep(40000); // Bounded evidence window: capture actual gralloc maps/FDs.
    if (!cpu_roundtrip(owner,stride,true,false) || !cpu_roundtrip(owner,stride,false,false)) return 8;
    if(gpu) {
        void *library=dlopen(plugin,RTLD_NOW|RTLD_LOCAL);
        if (!library) {fprintf(stderr,"plugin_load_failed=%s\n",dlerror());return 9;}
        using Test=int (*)(const native_handle_t *,uint32_t,uint32_t,uint32_t,uint64_t,int (*)(void *,uint32_t),void *);
        auto test=reinterpret_cast<Test>(dlsym(library,"g955n_test_native_buffer"));
        int result=test ? test(static_cast<const native_handle_t *>(owner.imported),side,side,stride,usage,verify_gpu_frame,&owner) : 1;
        // Do not dlclose a successfully loaded vendor EGL driver while it may
        // retain internal thread/TLS destructors. Process exit owns that module.
        if(result || !cpu_roundtrip(owner,stride,false,true)) return 10;
    }
    printf("buffer_roundtrip_passed=yes gpu_native_buffer=%s desktop_acceleration_qualified=no\n",gpu ? "yes":"not_tested");
    return 0;
}
int main(int argc,char **argv) {
    if(argc==3&&(!strcmp(argv[1],"--list-services-gles")||!strcmp(argv[1],"--list-services-display"))) {
        if(!guard(0,argv[2],true,!strcmp(argv[1],"--list-services-display")))return 2;
        alarm(5);setvbuf(stdout,nullptr,_IONBF,0);
        auto manager=android::hardware::defaultServiceManager();
        if(!manager)return 5;
        auto alive=manager->list([](const auto &names){for(const auto &name:names)printf("live_service=%s\n",name.c_str());});
        if(!alive.isOk())return 5;
        auto listing=manager->debugDump([](const auto &entries){
            for(const auto &entry:entries)printf("service_registration=%s/%s namespace_pid=%d\n",entry.interfaceName.c_str(),entry.instanceName.c_str(),entry.pid);
        });
        return listing.isOk() ? 0:5;
    }
    const bool display_query=argc>=2&&(!strcmp(argv[1],"--expect-allocator-absent-display")||!strcmp(argv[1],"--registration-only-display"));
    const bool gpu_query=display_query||(argc>=2&&(!strcmp(argv[1],"--expect-allocator-absent-gles")||!strcmp(argv[1],"--registration-only-gles")));
    const bool absent=argc==3&&(!strcmp(argv[1],"--expect-allocator-absent")||gpu_query);
    const bool query=argc==4&&(!strcmp(argv[1],"--registration-only")||gpu_query);
    if(absent){if(!guard(0,argv[2],gpu_query,display_query))return 2;alarm(5);return registration_query(0,true);}
    const bool gpu=argc==5&&!strcmp(argv[1],"--gles-native-buffer");
    if(!(query || gpu || (argc==4&&!strcmp(argv[1],"--allocate-only")))) return 2;
    char *end=nullptr; errno=0;long pid=strtol(argv[2],&end,10);
    if(errno||!end||*end||pid<=1||pid>2147483647||!guard(static_cast<int>(pid),argv[3],gpu||gpu_query,display_query)) return 2;
    // Explicit only; no ABI-selftest path loads mapper/ION/Mali or starts HALs.
    setvbuf(stdout,nullptr,_IONBF,0);
    if(query){alarm(5);return registration_query(static_cast<int>(pid),false);}
    alarm(10);
    printf("headless_probe_pid=%d\n",getpid());
    usleep(40000); // Bounded pre-driver evidence window, not a speed benchmark.
    BufferOwner owner;
    int result=run(static_cast<int>(pid),gpu,gpu ? argv[4]:nullptr,owner);
    bool clean=owner.close();
    printf("probe_exit=%d buffers_cleanup=%s allocation_only=%s\n",result,clean ? "yes":"failed",gpu ? "no":"yes");
    return result ? result : clean ? 0:11;
}
