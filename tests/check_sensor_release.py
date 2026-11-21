#!/usr/bin/env python3
# SPDX-License-Identifier: GPL-3.0-only
"""Execute the real SensorProxy dispatch/ownership methods with inactive clients."""
import argparse
from pathlib import Path
import re
import subprocess
import tempfile


def function(source, name):
    match = re.search(r'static\s+void\s+' + name + r'\s*\(', source)
    if not match:
        raise ValueError('Missing reviewed method ' + name)
    opening = source.index('{', match.start())
    depth, end = 1, opening + 1
    while depth:
        depth += (source[end] == '{') - (source[end] == '}')
        end += 1
    return source[match.start():end]


parser = argparse.ArgumentParser(description=__doc__)
parser.add_argument('--source', type=Path, required=True)
args = parser.parse_args()
source = args.source.read_text()
methods = '\n'.join(function(source, name) for name in (
    'client_release', 'handle_generic_method_call', 'handle_method_call'))
shim = r'''
#include <gio/gio.h>
#include <assert.h>
typedef enum {DRIVER_TYPE_ACCEL,DRIVER_TYPE_LIGHT,DRIVER_TYPE_PROXIMITY,NUM_SENSOR_TYPES} DriverType;
typedef struct {GHashTable *clients[NUM_SENSOR_TYPES];GDBusConnection *connection;} SensorData;
typedef struct {int unused;} SensorDevice;
static SensorDevice devices[NUM_SENSOR_TYPES];
static int authorized, auth_checks, successes, errors, starts, stops;
#define DEVICE_FOR_TYPE(type) (&devices[type])
static const char *driver_type_to_str(DriverType type) {(void)type;return "fixture";}
static gboolean driver_type_exists(SensorData *data,DriverType type) {(void)data;(void)type;return TRUE;}
static void driver_set_polling(SensorDevice *device,gboolean on) {(void)device;if(on)starts++;else stops++;}
static gboolean check_claim_permission(SensorData *data,const char *sender,GError **error) {
    (void)data;(void)sender;auth_checks++;
    if(!authorized)g_set_error_literal(error,G_DBUS_ERROR,G_DBUS_ERROR_ACCESS_DENIED,"Inactive fixture client");
    return authorized;
}
static void vanished(GDBusConnection *c,const gchar *name,gpointer data) {(void)c;(void)name;(void)data;}
#define client_vanished_cb vanished
static guint watch(GDBusConnection *c,const gchar *n,GBusNameWatcherFlags f,
                   GBusNameAppearedCallback a,GBusNameVanishedCallback v,gpointer d,GDestroyNotify end) {
    (void)c;(void)n;(void)f;(void)a;(void)v;(void)d;(void)end;
    static guint next;return ++next;
}
#define g_bus_watch_name_on_connection watch
static void success(GDBusMethodInvocation *inv,GVariant *value) {(void)inv;(void)value;successes++;}
static void error_value(GDBusMethodInvocation *inv,const GError *error) {(void)inv;assert(error);errors++;}
static void error_format(GDBusMethodInvocation *inv,GQuark domain,gint code,const gchar *format,...) {
    (void)inv;(void)format;assert(domain==G_DBUS_ERROR && code==G_DBUS_ERROR_UNKNOWN_METHOD);errors++;
}
#define g_dbus_method_invocation_return_value success
#define g_dbus_method_invocation_return_gerror error_value
#define g_dbus_method_invocation_return_error error_format
'''
main = r'''
static void call(SensorData *data,const char *sender,const char *method) {
    handle_method_call(NULL,sender,"/net/hadess/SensorProxy","net.hadess.SensorProxy",method,NULL,NULL,data);
}
int main(void) {
    SensorData data={0};
    for(int i=0;i<NUM_SENSOR_TYPES;i++)data.clients[i]=g_hash_table_new_full(g_str_hash,g_str_equal,g_free,NULL);
    call(&data,":1.1","ClaimLight");
    assert(errors==1 && auth_checks==1 && !starts && !g_hash_table_size(data.clients[DRIVER_TYPE_LIGHT]));
    authorized=1;call(&data,":1.1","ClaimLight");call(&data,":1.2","ClaimLight");
    assert(successes==2 && starts==1 && g_hash_table_size(data.clients[DRIVER_TYPE_LIGHT])==2);
    authorized=0;int checked=auth_checks;
    call(&data,":1.3","ReleaseLight");
    assert(g_hash_table_size(data.clients[DRIVER_TYPE_LIGHT])==2 && !stops);
    call(&data,":1.1","ReleaseLight");
    assert(g_hash_table_size(data.clients[DRIVER_TYPE_LIGHT])==1 && !stops);
    call(&data,":1.2","ReleaseLight");
    assert(!g_hash_table_size(data.clients[DRIVER_TYPE_LIGHT]) && stops==1 && auth_checks==checked);
    call(&data,":1.1","ClaimAccelerometer");assert(errors==2 && auth_checks==checked+1);
    call(&data,":1.1","ResetLight");assert(errors==3 && auth_checks==checked+1);
    for(int i=0;i<NUM_SENSOR_TYPES;i++)g_hash_table_unref(data.clients[i]);
    g_print("Sensor release: new claims denied, own inactive release allowed, foreign ownership retained, last release stops polling\n");
}
'''
with tempfile.TemporaryDirectory(prefix='g955n-sensor-release-') as temp:
    fixture = Path(temp)/'fixture.c'
    fixture.write_text(shim + methods + main)
    binary = Path(temp)/'fixture'
    flags = subprocess.check_output(['pkg-config', '--cflags', '--libs', 'gio-2.0'], text=True).split()
    subprocess.run(['cc', '-O1', '-g', '-Wall', '-Wextra', '-Werror',
                    '-Wno-unused-parameter', '-fsanitize=address,undefined',
                    str(fixture), '-o', str(binary), *flags], check=True)
    subprocess.run([str(binary)], check=True)
