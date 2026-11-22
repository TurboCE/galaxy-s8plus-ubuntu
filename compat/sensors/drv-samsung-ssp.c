/* SPDX-License-Identifier: GPL-3.0-or-later
 * SM-G955N Samsung SSP packed-IIO backend for iio-sensor-proxy 3.5.
 * Public protocol/layout: pinned Samsung drivers/sensorhub/brcm/{ssp.h,
 * sensor_list.h,ssp_iio.c}, LSM6DSL factory range8G (4096 counts/g).
 * Native Ubuntu SensorProxy retains its original DBus/Polkit/claim machinery.
 */
#include "drivers.h"
#include "accel-mount-matrix.h"
#include <errno.h>
#include <fcntl.h>
#include <stdint.h>
#include <stdio.h>
#include <sys/stat.h>
#include <glib/gstdio.h>
#include <string.h>
#include <sys/file.h>
#include <unistd.h>

#define SSP_MASK "/sys/class/sensors/ssp_sensor/enable"
#define SSP_REV "/sys/class/sensors/ssp_sensor/mcu_rev"
typedef struct {
 GUdevDevice *dev;
 char *path;
 char *saved[4];
 char *lease;
 int fd;
 guint timer;
 guint bit;
 guint record_size;
 guint changed;
 gboolean owns_bit;
 GByteArray *pending;
 AccelVec3 *matrix;
} SSP;
static int controller_fd=-1;
static guint controller_refs;
static const char *attributes[]={"scan_elements/in_timestamp_en","buffer/length","buffer/enable","poll_delay"};
static char *read_text(const char *path){
 char *text=NULL;
 if(!g_file_get_contents(path,&text,NULL,NULL))return NULL;
 g_strstrip(text);return text;
}
static gboolean write_text(const char *path,const char *text){
 int fd=open(path,O_WRONLY|O_CLOEXEC);if(fd<0)return FALSE;
 size_t length=strlen(text),offset=0;
 while(offset<length){ssize_t n=write(fd,text+offset,length-offset);if(n<0&&errno==EINTR)continue;if(n<=0){close(fd);return FALSE;}offset+=n;}
 return close(fd)==0;
}
static gboolean ready(void){
 g_autofree char *model=read_text("/proc/device-tree/model");
 g_autofree char *revision=read_text(SSP_REV);
 guint expected=0,actual=0;
 return geteuid()==0&&model&&strstr(model,"SM-G955N")&&revision&&
  sscanf(revision,"BR0%u,BR0%u",&expected,&actual)==2&&actual>0&&actual==expected;
}
static gboolean mask_value(guint64 *mask){
 g_autofree char *text=read_text(SSP_MASK);char *end=NULL;
 if(!text||!*text)return FALSE;
 errno=0;guint64 value=g_ascii_strtoull(text,&end,10);
 if(errno||end==text||*end)return FALSE;
 *mask=value;return TRUE;
}
static gboolean change_bit(SSP *s,gboolean enable){
 guint64 mask;if(!mask_value(&mask))return FALSE;
 guint64 wanted=enable?mask|((guint64)1<<s->bit):mask&~((guint64)1<<s->bit);
 if(mask==wanted)return TRUE;
 g_autofree char *text=g_strdup_printf("%"G_GUINT64_FORMAT,wanted);
 // The vendor handler changes one bit per write; preserve all other clients.
 return write_text(SSP_MASK,text)&&mask_value(&mask)&&mask==wanted;
}
static gboolean controller_get(void){
 if(controller_refs){controller_refs++;return TRUE;}
 int fd=open("/run/g955n-ssp.lock",O_RDWR|O_CREAT|O_CLOEXEC|O_NOFOLLOW,0600);
 if(fd<0)return FALSE;
 struct stat info;if(fstat(fd,&info)||info.st_uid||!S_ISREG(info.st_mode)||(info.st_mode&077)){close(fd);return FALSE;}
 if(flock(fd,LOCK_EX|LOCK_NB)){close(fd);return FALSE;}
 controller_fd=fd;controller_refs=1;return TRUE;
}
static void controller_put(void){
 if(controller_refs&&!--controller_refs){close(controller_fd);controller_fd=-1;}
}
/* Persist before the first sysfs mutation so systemd can recover a killed
 * daemon. The controller lock serializes normal clients and lease recovery.
 */
static gboolean save_lease(SSP *s){
 const char *directory="/run/g955n-ssp-leases";
 if(g_mkdir_with_parents(directory,0700))return FALSE;
 struct stat info;
 if(lstat(directory,&info)||!S_ISDIR(info.st_mode)||info.st_uid||(info.st_mode&077))return FALSE;
 g_autofree char *path=g_strdup_printf("%s/%u.ini",directory,s->bit);
 if(g_file_test(path,G_FILE_TEST_EXISTS))return FALSE;
 s->lease=g_steal_pointer(&path);
 g_autofree char *boot=read_text("/proc/sys/kernel/random/boot_id");if(!boot)return FALSE;
 g_autoptr(GKeyFile) record=g_key_file_new();
 g_key_file_set_string(record,"sensor","boot",boot);
 g_key_file_set_string(record,"sensor","path",s->path);
 g_key_file_set_uint64(record,"sensor","bit",s->bit);
 for(guint i=0;i<G_N_ELEMENTS(attributes);i++){
  g_autofree char *key=g_strdup_printf("saved%u",i);
  g_key_file_set_string(record,"sensor",key,s->saved[i]);
 }
 gsize length;g_autofree char *data=g_key_file_to_data(record,&length,NULL);
 return g_file_set_contents(s->lease,data,length,NULL)&&g_chmod(s->lease,0600)==0;
}
static void restore(SSP *s){
 gboolean restored=TRUE;
 if(s->owns_bit){if(!change_bit(s,FALSE)){restored=FALSE;g_warning("SSP sensor enable restore failed");}s->owns_bit=FALSE;}
 if(s->fd>=0){close(s->fd);s->fd=-1;}
 // Stop the FIFO before restoring its scan/length settings.
 if(s->changed>2){g_autofree char *path=g_build_filename(s->path,"buffer/enable",NULL);if(!write_text(path,s->saved[2])){restored=FALSE;g_warning("SSP buffer restore failed");}}
 for(int i=3;i>=0;i--){
  if(i==2||s->changed<=(guint)i)continue;
  g_autofree char *path=g_build_filename(s->path,attributes[i],NULL);
  if(!write_text(path,s->saved[i])){restored=FALSE;g_warning("SSP attribute restore failed: %s",attributes[i]);}
 }
 for(guint i=0;i<G_N_ELEMENTS(attributes);i++)g_clear_pointer(&s->saved[i],g_free);
 if(s->lease&&restored)g_unlink(s->lease);
 g_clear_pointer(&s->lease,g_free);
 s->changed=0;if(s->pending)g_byte_array_set_size(s->pending,0);
}
static gboolean start(SSP *s){
 if(!ready())return FALSE;
 g_autofree char *node=NULL;
 guint64 mask;if(!mask_value(&mask)||(mask&((guint64)1<<s->bit)))return FALSE;
 const char *values[]={"1","128","1","100000000"};
 for(guint i=0;i<G_N_ELEMENTS(attributes);i++){
  g_autofree char *path=g_build_filename(s->path,attributes[i],NULL);
  s->saved[i]=read_text(path);
  if(!s->saved[i]||!*s->saved[i]||strlen(s->saved[i])>19||strspn(s->saved[i],"0123456789")!=strlen(s->saved[i])||(i==2&&strcmp(s->saved[i],"0")))goto failed;
 }
 if(!save_lease(s))goto failed;
 node=g_strdup_printf("/dev/%s",g_udev_device_get_name(s->dev));
 s->fd=open(node,O_RDONLY|O_NONBLOCK|O_CLOEXEC|O_NOFOLLOW);if(s->fd<0)goto failed;
 for(guint i=0;i<G_N_ELEMENTS(attributes);i++){
  g_autofree char *path=g_build_filename(s->path,attributes[i],NULL);
  s->changed=i+1;if(!write_text(path,values[i]))goto failed;
 }
 s->owns_bit=TRUE;if(!change_bit(s,TRUE))goto failed;
 return TRUE;
failed:restore(s);return FALSE;
}
static gint16 little_s16(const guint8 *p){guint16 v;memcpy(&v,p,2);return (gint16)GUINT16_FROM_LE(v);}
static guint32 little_u32(const guint8 *p){guint32 v;memcpy(&v,p,4);return GUINT32_FROM_LE(v);}
static gboolean sample(gpointer data){
 SensorDevice *device=data;SSP *s=device->priv;guint8 raw[4096];
 for(guint batches=0;batches<8;batches++){
  ssize_t n=read(s->fd,raw,sizeof(raw));
  if(n<0&&(errno==EAGAIN||errno==EWOULDBLOCK))break;
  if(n<0&&errno==EINTR)continue;
  if(n<=0){g_warning("SSP stream stopped: %s",device->name);s->timer=0;restore(s);controller_put();return G_SOURCE_REMOVE;}
  g_byte_array_append(s->pending,raw,n);
  guint complete=s->pending->len/s->record_size;
  if(!complete)continue;
  const guint8 *p=s->pending->data+(complete-1)*s->record_size;
  if(device->drv->type==DRIVER_TYPE_ACCEL){
   AccelVec3 vector={little_s16(p),little_s16(p+2),little_s16(p+4)};
   gboolean mapped=apply_mount_matrix(s->matrix,&vector);
   AccelReadings readings={.accel_x=vector.x,.accel_y=vector.y,.accel_z=vector.z};
   set_accel_scale(&readings.scale,9.81/4096.0);
   if(mapped)device->callback_func(device,&readings,device->user_data);
  }else if(device->drv->type==DRIVER_TYPE_LIGHT){
   // CONFIG_SENSORS_SSP_LIGHT_REPORT_LUX: real MCU lux is the first u32.
   LightReadings readings={.level=little_u32(p),.uses_lux=TRUE};
   device->callback_func(device,&readings,device->user_data);
  }else if(p[0]<=1){
   // The vendor report is a detect byte followed by a kernel timestamp.
   ProximityReadings readings={.is_near=p[0]?PROXIMITY_NEAR_TRUE:PROXIMITY_NEAR_FALSE};
   device->callback_func(device,&readings,device->user_data);
  }
  g_byte_array_remove_range(s->pending,0,complete*s->record_size);
 }
 return G_SOURCE_CONTINUE;
}
static gboolean discover_accel(GUdevDevice *d){return drv_check_udev_sensor_type(d,"samsung-ssp-accel","Samsung SSP accel");}
static gboolean discover_light(GUdevDevice *d){return drv_check_udev_sensor_type(d,"samsung-ssp-als","Samsung SSP lux");}
static gboolean discover_proximity(GUdevDevice *d){return drv_check_udev_sensor_type(d,"samsung-ssp-proximity","Samsung SSP proximity");}
static SensorDevice *open_device(GUdevDevice *d){
 static const struct {const char *name,*format;guint bit,size;} sensors[]={
  {"accelerometer_sensor","le:s112/112>>0",0,14},
  {"light_sensor","le:s208/208>>0",9,26},
  {"proximity_sensor","le:s72/72>>0",7,9},
 };
 const char *name=g_udev_device_get_sysfs_attr(d,"name");
 guint i;
 if(!ready())return NULL;
 for(i=0;i<G_N_ELEMENTS(sensors);i++)if(!g_strcmp0(name,sensors[i].name))break;
 if(i==G_N_ELEMENTS(sensors))return NULL;
 g_autofree char *format_path=g_build_filename(g_udev_device_get_sysfs_path(d),"scan_elements/in_timestamp_type",NULL);
 g_autofree char *format=read_text(format_path);
 if(g_strcmp0(format,sensors[i].format))return NULL;
 gboolean accel=sensors[i].bit==0;
 AccelVec3 *matrix=accel?setup_mount_matrix(d):NULL;
 if(accel&&!matrix)return NULL;
 SensorDevice *device=g_new0(SensorDevice,1);SSP *s=g_new0(SSP,1);device->priv=s;device->name=g_strdup(name);s->dev=g_object_ref(d);s->path=g_strdup(g_udev_device_get_sysfs_path(d));s->fd=-1;s->bit=sensors[i].bit;s->record_size=sensors[i].size;s->pending=g_byte_array_new();
 s->matrix=matrix;
 return device;
}
static void polling(SensorDevice *device,gboolean state){
 SSP *s=device->priv;
 if(state){
  if(s->timer)return;
  if(!controller_get())return;
  if(!start(s)){controller_put();g_warning("SSP sensor claim failed: %s",device->name);return;}
  s->timer=g_timeout_add(100,sample,device);
 }else if(s->timer){g_source_remove(s->timer);s->timer=0;restore(s);controller_put();}
}
static void close_device(SensorDevice *device){SSP *s=device->priv;g_clear_object(&s->dev);g_free(s->path);g_clear_pointer(&s->matrix,g_free);g_byte_array_unref(s->pending);g_free(s);g_free(device);}
SensorDriver samsung_ssp_accel={.driver_name="samsung-ssp-accel",.type=DRIVER_TYPE_ACCEL,.discover=discover_accel,.open=open_device,.set_polling=polling,.close=close_device};
SensorDriver samsung_ssp_light={.driver_name="samsung-ssp-als",.type=DRIVER_TYPE_LIGHT,.discover=discover_light,.open=open_device,.set_polling=polling,.close=close_device};
SensorDriver samsung_ssp_proximity={.driver_name="samsung-ssp-proximity",.type=DRIVER_TYPE_PROXIMITY,.discover=discover_proximity,.open=open_device,.set_polling=polling,.close=close_device};
