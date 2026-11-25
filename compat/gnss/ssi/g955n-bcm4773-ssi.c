// SPDX-License-Identifier: GPL-2.0-only
/* BCM4773 half-duplex SSI transport for the SM-G955N. */
#include <crypto/sha2.h>
#include <linux/delay.h>
#include <linux/device/class.h>
#include <linux/firmware.h>
#include <linux/fs.h>
#include <linux/gpio/consumer.h>
#include <linux/interrupt.h>
#include <linux/iio/iio.h>
#if IS_ENABLED(CONFIG_IIO_TRIGGERED_BUFFER)
#include <linux/iio/buffer.h>
#include <linux/iio/trigger.h>
#include <linux/iio/trigger_consumer.h>
#include <linux/iio/triggered_buffer.h>
#endif
#include <linux/iopoll.h>
#include <linux/kfifo.h>
#include <linux/kref.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/poll.h>
#include <linux/string.h>
#include <linux/sysfs.h>
#include <linux/regulator/consumer.h>
#include <linux/slab.h>
#include <linux/spi/spi.h>
#include <linux/uaccess.h>
#include <linux/unaligned.h>
#include <linux/workqueue.h>

#include "g955n-heading.h"

#define SSI_WRITE	0x00
#define SSI_READ	0x20
#define SSI_HEADER	2
#define SSI_PAYLOAD	254
#define SSI_STREAM_SIZE	(32 * 1024)
#define SSI_WORK_BUDGET	16
#define BBD_PATCH_NAME	"samsung/g955n/bbd-patch.bin"
#define BBD_CONTROL_MAX	64
#define BBD_PATCH_SIZE	1023148
#define BBD_FRAME_MAX	(2048 + 14)
#define SSP_SENSOR_RPC	33
#define SSP_ADD_SENSOR	0xa1
#define SSP_REMOVE_SENSOR 0xa2
#define SSP_SENSOR_PERIOD_MS 100
#define SSP_SENSOR_IDLE_MS 2500
#define SSP_SENSOR_RECORD_MAX 128

static bool expose_legacy_patch;
module_param(expose_legacy_patch, bool, 0400);
MODULE_PARM_DESC(expose_legacy_patch, "Expose the verified board patch through /dev/bbd_patch");

static bool expose_legacy_control;
module_param(expose_legacy_control, bool, 0400);
MODULE_PARM_DESC(expose_legacy_control, "Expose the legacy firmware lifecycle control device");

static bool expose_legacy_stream;
module_param(expose_legacy_stream, bool, 0400);
MODULE_PARM_DESC(expose_legacy_stream, "Expose an experimental queued /dev/ttyBCM stream");

static bool expose_legacy_power;
module_param(expose_legacy_power, bool, 0400);
MODULE_PARM_DESC(expose_legacy_power, "Let the legacy daemon control the hub and GNSS power");

static bool probe_legacy_ssp;
module_param(probe_legacy_ssp, bool, 0400);
MODULE_PARM_DESC(probe_legacy_ssp, "Issue a read-only SSP chip-ID request through the legacy daemon");

static bool expose_legacy_accel;
module_param(expose_legacy_accel, bool, 0400);
MODULE_PARM_DESC(expose_legacy_accel, "Expose the BCM4773 accelerometer through IIO");

static bool expose_legacy_environment;
module_param(expose_legacy_environment, bool, 0400);
MODULE_PARM_DESC(expose_legacy_environment, "Expose the BCM4773 light and proximity sensors through IIO");

static bool expose_legacy_motion;
module_param(expose_legacy_motion, bool, 0400);
MODULE_PARM_DESC(expose_legacy_motion, "Expose gyroscope, magnetometer, barometer and steps through IIO");

enum ssi_iio_kind {
	SSI_ACCEL,
	SSI_LIGHT,
	SSI_PROX,
	SSI_GYRO,
	SSI_MAGN,
	SSI_PRESS,
	SSI_STEPS,
	SSI_HEADING,
	SSI_IIO_COUNT,
};

struct ssi_sensor_slot {
	struct iio_dev *iio;
#if IS_ENABLED(CONFIG_IIO_TRIGGERED_BUFFER)
	struct iio_trigger *trigger;
#endif
	int sample[3];
	s64 steps;
	unsigned long stamp, access;
	bool requested, running, valid, buffered;
};

static const u8 ssi_sensor_ids[] = {
	[SSI_ACCEL] = 0,
	[SSI_LIGHT] = 9,
	[SSI_PROX] = 7,
	[SSI_GYRO] = 1,
	[SSI_MAGN] = 4,
	[SSI_PRESS] = 5,
	[SSI_STEPS] = 18,
	[SSI_HEADING] = 17,
};

static const u8 ssi_sensor_lengths[] = {
	[SSI_ACCEL] = 6,
	[SSI_LIGHT] = 18,
	[SSI_PROX] = 3,
	[SSI_GYRO] = 12,
	[SSI_MAGN] = 8,
	[SSI_PRESS] = 6,
	[SSI_STEPS] = 4,
	[SSI_HEADING] = 17,
};

struct ssi_bbd_rx {
	u8 frame[BBD_FRAME_MAX];
	size_t size;
	bool receiving;
	bool escaped;
};

/* Little-endian BBD length, SSP command, response size, options and data. */
static const u8 ssi_ssp_whoami[] = { 9, 0, 0x0f, 1, 0, 0, 0, 0, 0, 0, 0 };

struct ssi_saved_gpio {
	int direction;
	int value;
	bool saved;
};

enum bbd_firmware_state {
	BBD_FIRMWARE_UNKNOWN,
	BBD_FIRMWARE_NOT_READY,
	BBD_FIRMWARE_READY,
	BBD_FIRMWARE_CRASHED,
};

struct g955n_ssi {
	struct kref refs;
	struct mutex lock;
	wait_queue_head_t wait;
	struct miscdevice misc;
	struct miscdevice patch;
	struct miscdevice control;
	struct miscdevice sensor;
	u8 sensor_request[12];
	size_t sensor_size, sensor_offset;
	bool sensor_open;
	struct ssi_sensor_slot slots[SSI_IIO_COUNT];
	struct ssi_sensor_slot *sensor_transfer;
	bool transfer_enable;
	struct delayed_work sensor_idle;
	struct ssi_bbd_rx bbd;
	u8 sensor_record[SSP_SENSOR_RECORD_MAX + 4];
	size_t sensor_record_size, sensor_record_skip;
	struct miscdevice stream;
	struct delayed_work stream_work;
	struct kfifo stream_tx, stream_rx;
	u64 stream_tx_bytes, stream_rx_bytes;
	int stream_error;
	unsigned int empty_receives;
	bool stream_open;
	enum bbd_firmware_state firmware_state;
	bool patch_transfer;
	struct spi_device *spi;
	struct regulator *supply;
	struct gpio_desc *request;
	struct gpio_desc *response;
	struct gpio_desc *host;
	struct gpio_desc *enable;
	struct gpio_desc *gnss_enable;
	struct ssi_saved_gpio enable_original, gnss_original;
	struct class *sec_class;
	struct device *power_device, *gnss_device;
	u8 *tx, *rx;
	size_t pending;
	int irq;
	bool opened;
	bool powered;
	bool removed;
};

static void ssi_free(struct kref *refs)
{
	struct g955n_ssi *ssi = container_of(refs, struct g955n_ssi, refs);

	kfree(ssi);
}

static irqreturn_t ssi_host_irq(int irq, void *data)
{
	struct g955n_ssi *ssi = data;

	if (READ_ONCE(ssi->stream_open))
		queue_delayed_work(system_freezable_wq, &ssi->stream_work, 0);
	else
		wake_up_interruptible(&ssi->wait);
	return IRQ_HANDLED;
}

/* Each /dev/bbd_sensor request has a little-endian byte count. */
static void ssi_sensor_queue(struct g955n_ssi *ssi, const u8 *packet, size_t size)
{
	memcpy(ssi->sensor_request, packet, size);
	ssi->sensor_offset = 0;
	ssi->sensor_size = size;
	wake_up_interruptible(&ssi->wait);
}

static void ssi_sensor_update(struct g955n_ssi *ssi)
{
	u8 header[] = { 9, 0, 0, 0, 0, 1, 0, 0, 0, 0, 0 };
	unsigned int i;

	if (ssi->removed || !ssi->sensor_open ||
	    ssi->firmware_state != BBD_FIRMWARE_READY ||
	    ssi->sensor_transfer || ssi->sensor_size)
		return;

	for (i = 0; i < SSI_IIO_COUNT; i++) {
		struct ssi_sensor_slot *slot = &ssi->slots[i];

		if (!slot->iio || slot->requested == slot->running)
			continue;

		ssi->sensor_transfer = slot;
		ssi->transfer_enable = slot->requested;
		header[2] = ssi->transfer_enable ? SSP_ADD_SENSOR : SSP_REMOVE_SENSOR;
		header[3] = ssi->transfer_enable ? 10 : 5;
		ssi_sensor_queue(ssi, header, sizeof(header));
		break;
	}
}

static void ssi_sensor_reset(struct g955n_ssi *ssi)
{
	unsigned int i;

	ssi->sensor_size = 0;
	ssi->sensor_transfer = NULL;
	for (i = 0; i < SSI_IIO_COUNT; i++) {
		ssi->slots[i].running = false;
		WRITE_ONCE(ssi->slots[i].valid, false);
	}
	ssi->sensor_record_size = 0;
	ssi->sensor_record_skip = 0;
	ssi->bbd.receiving = false;
	ssi->bbd.escaped = false;
}

static void ssi_sensor_report(struct g955n_ssi *ssi, const u8 *data, size_t size)
{
	/* Bypass instruction, sensor ID, sample, and 8-byte MCU timestamp. */
	while (size >= 2 && data[0] == 0x37) {
		struct ssi_sensor_slot *slot;
		unsigned int i, length;
		const u8 *sample = data + 2;

		for (i = 0; i < SSI_IIO_COUNT; i++)
			if (data[1] == ssi_sensor_ids[i])
				break;
		if (i == SSI_IIO_COUNT)
			return;

		length = ssi_sensor_lengths[i] + 10;
		if (size < length)
			return;

		slot = &ssi->slots[i];
		data += length;
		size -= length;
		if (!slot->running)
			continue;

		switch (i) {
		case SSI_GYRO:
			slot->sample[0] = (s32)get_unaligned_le32(sample);
			slot->sample[1] = (s32)get_unaligned_le32(sample + 4);
			slot->sample[2] = (s32)get_unaligned_le32(sample + 8);
			break;
		case SSI_MAGN:
			if (sample[7])
				continue;
			fallthrough;
		case SSI_ACCEL:
			slot->sample[0] = (s16)get_unaligned_le16(sample);
			slot->sample[1] = (s16)get_unaligned_le16(sample + 2);
			slot->sample[2] = (s16)get_unaligned_le16(sample + 4);
			break;
		case SSI_LIGHT: {
			u32 lux = get_unaligned_le32(sample);

			if (lux > INT_MAX)
				continue;
			slot->sample[0] = lux;
			break;
		}
		case SSI_PROX:
			if (*sample > 1)
				continue;
			slot->sample[0] = *sample;
			slot->sample[1] = get_unaligned_le16(sample + 1);
			break;
		case SSI_PRESS:
			slot->sample[0] = (s32)get_unaligned_le32(sample);
			slot->sample[1] = (s16)get_unaligned_le16(sample + 4);
			break;
		case SSI_STEPS: {
			u32 delta = get_unaligned_le32(sample);

			/* The firmware reports deltas, as in the Samsung SSP driver. */
			slot->steps += min_t(u64, delta, S64_MAX - slot->steps);
			break;
		}
		case SSI_HEADING: {
			s32 q[4] = {
				get_unaligned_le32(sample),
				get_unaligned_le32(sample + 4),
				get_unaligned_le32(sample + 8),
				get_unaligned_le32(sample + 12),
			};

			if (!g955n_heading_mdeg(q, &slot->sample[0]))
				continue;
			break;
		}
		}
		WRITE_ONCE(slot->stamp, jiffies);
		WRITE_ONCE(slot->valid, true);
#if IS_ENABLED(CONFIG_IIO_TRIGGERED_BUFFER)
		if (slot->buffered)
			iio_trigger_poll_nested(slot->trigger);
#endif
		wake_up_interruptible(&ssi->wait);
	}
}

static void ssi_sensor_feed(struct g955n_ssi *ssi, const u8 *data, size_t size)
{
	u8 *record = ssi->sensor_record;
	size_t length, target;
	u16 options;

	while (size) {
		if (ssi->sensor_record_skip) {
			length = min(size, ssi->sensor_record_skip);
			ssi->sensor_record_skip -= length;
			size -= length;
			data += length;
			continue;
		}
		target = 4;
		if (ssi->sensor_record_size >= target) {
			options = get_unaligned_le16(record);
			length = get_unaligned_le16(record + 2);
			if ((options & 3) != 1)
				target += length;
		}
		length = min(size, target - ssi->sensor_record_size);
		memcpy(record + ssi->sensor_record_size, data, length);
		ssi->sensor_record_size += length;
		data += length;
		size -= length;

		if (ssi->sensor_record_size < 4)
			continue;
		options = get_unaligned_le16(record);
		length = get_unaligned_le16(record + 2);
		if ((options & 3) == 1) {
			struct ssi_sensor_slot *slot = ssi->sensor_transfer;
			u8 payload[12] = { 0 };
			unsigned int expected = ssi->transfer_enable ? 10 : 5;

			if (options == 1 && slot && !ssi->sensor_size &&
			    length == expected) {
				put_unaligned_le16(expected, payload);
				payload[2] = ssi_sensor_ids[slot - ssi->slots];
				put_unaligned_le32(SSP_SENSOR_PERIOD_MS, payload + 3);
				ssi_sensor_queue(ssi, payload, expected + 2);
				slot->running = ssi->transfer_enable;
				if (slot == &ssi->slots[SSI_STEPS] && slot->running) {
					WRITE_ONCE(slot->valid, true);
					wake_up_interruptible(&ssi->wait);
				}
				ssi->sensor_transfer = NULL;
			}
		} else {
			if (length > SSP_SENSOR_RECORD_MAX) {
				ssi->sensor_record_size = 0;
				ssi->sensor_record_skip = length;
				continue;
			}
			if (ssi->sensor_record_size < length + 4)
				continue;
			if ((options & 3) == 2)
				ssi_sensor_report(ssi, record + 4, length);
		}
		ssi->sensor_record_size = 0;
	}
}

static int ssi_bbd_number(const u8 **p, const u8 *end)
{
	u16 value;

	if (*p == end)
		return -EINVAL;
	value = *(*p)++;
	if (value & 0x80) {
		if (*p == end)
			return -EINVAL;
		value = ((value & 0x7f) << 8) | *(*p)++;
	}
	return value;
}

static void ssi_bbd_frame(struct g955n_ssi *ssi)
{
	const u8 *frame = ssi->bbd.frame;
	const u8 *end;
	const u8 *p;
	u16 length, flags;
	u8 crc = 0;
	unsigned int bit;

	if (ssi->bbd.size < 4)
		return;
	end = frame + ssi->bbd.size - 1;
	for (p = frame + 1; p < end; p++) {
		crc ^= *p;
		for (bit = 0; bit < 8; bit++)
			crc = (crc << 1) ^ (crc & 0x80 ? 0x4d : 0);
	}
	if ((u8)((crc << 4) | (crc >> 4)) != *end)
		return;

	length = frame[1];
	flags = frame[2];
	p = frame + 3;
	for (bit = 0; bit < 10; bit++) {
		u8 detail;

		if (!(flags & BIT(bit)))
			continue;
		if (p == end)
			return;
		detail = *p++;
		if (bit == 6)
			length |= detail << 8;
		else if (bit == 7)
			flags |= detail << 8;
	}
	if (flags & ~GENMASK(9, 0) || flags & BIT(8) || end - p != length)
		return;

	while (p < end) {
		int kind = ssi_bbd_number(&p, end);
		int size = ssi_bbd_number(&p, end);

		if (kind < 0 || size < 0 || end - p < size)
			return;
		if (kind == SSP_SENSOR_RPC && size >= 2 &&
		    get_unaligned_le16(p) == size - 2)
			ssi_sensor_feed(ssi, p + 2, size - 2);
		p += size;
	}
}

static void ssi_bbd_feed(struct g955n_ssi *ssi, const u8 *data, size_t size)
{
	struct ssi_bbd_rx *rx = &ssi->bbd;

	while (size--) {
		u8 byte = *data++;

		if (byte == 0x11 || byte == 0x13)
			continue;
		if (rx->escaped) {
			rx->escaped = false;
			switch (byte) {
			case 0:
				rx->receiving = true;
				rx->size = 0;
				continue;
			case 1:
				if (rx->receiving)
					ssi_bbd_frame(ssi);
				rx->receiving = false;
				continue;
			case 3:
				byte = 0xb0;
				break;
			case 4:
				byte = 0x11;
				break;
			case 5:
				byte = 0x13;
				break;
			default:
				rx->receiving = false;
				rx->escaped = byte == 0xb0;
				continue;
			}
		} else if (byte == 0xb0) {
			rx->escaped = true;
			continue;
		}

		if (rx->receiving) {
			if (rx->size == sizeof(rx->frame))
				rx->receiving = false;
			else
				rx->frame[rx->size++] = byte;
		}
	}
}

static void ssi_sensor_schedule_idle(struct g955n_ssi *ssi)
{
	unsigned long now = jiffies, earliest = 0;
	unsigned int i;

	for (i = 0; i < SSI_IIO_COUNT; i++) {
		struct ssi_sensor_slot *slot = &ssi->slots[i];
		unsigned long expires, delay;

		if (!slot->requested || slot->buffered || i == SSI_STEPS)
			continue;
		expires = slot->access + msecs_to_jiffies(SSP_SENSOR_IDLE_MS);
		delay = time_after(expires, now) ? expires - now : 1;
		if (!earliest || delay < earliest)
			earliest = delay;
	}

	if (earliest && !ssi->removed)
		mod_delayed_work(system_freezable_wq, &ssi->sensor_idle, earliest);
}

static void ssi_sensor_idle(struct work_struct *work)
{
	struct g955n_ssi *ssi = container_of(to_delayed_work(work),
					    struct g955n_ssi, sensor_idle);
	unsigned int i;

	mutex_lock(&ssi->lock);
	for (i = 0; i < SSI_IIO_COUNT; i++) {
		struct ssi_sensor_slot *slot = &ssi->slots[i];
		unsigned long expires = slot->access + msecs_to_jiffies(SSP_SENSOR_IDLE_MS);

		if (i != SSI_STEPS && slot->requested && !slot->buffered &&
		    time_after_eq(jiffies, expires)) {
			slot->requested = false;
			WRITE_ONCE(slot->valid, false);
		}
	}
	ssi_sensor_update(ssi);
	ssi_sensor_schedule_idle(ssi);
	mutex_unlock(&ssi->lock);
}

struct ssi_iio_priv {
	struct g955n_ssi *ssi;
	enum ssi_iio_kind kind;
};

static bool ssi_sensor_fresh(struct ssi_sensor_slot *slot, enum ssi_iio_kind kind)
{
	if (!READ_ONCE(slot->valid))
		return false;
	if (kind == SSI_LIGHT || kind == SSI_PROX || kind == SSI_STEPS)
		return true;
	return !time_after(jiffies, READ_ONCE(slot->stamp) + msecs_to_jiffies(600));
}

static int ssi_iio_read_raw(struct iio_dev *indio, const struct iio_chan_spec *chan,
			    int *value, int *value2, long mask)
{
	struct ssi_iio_priv *priv = iio_priv(indio);
	struct g955n_ssi *ssi = priv->ssi;
	struct ssi_sensor_slot *slot = &ssi->slots[priv->kind];
	int ret;

	if (mask == IIO_CHAN_INFO_SCALE) {
		*value = 0;
		if (priv->kind == SSI_LIGHT) {
			/* The hub reports illuminance in lux. */
			*value = 1;
			return IIO_VAL_INT;
		}
		if (priv->kind == SSI_HEADING) {
			*value2 = 1000;
			return IIO_VAL_INT_PLUS_MICRO;
		}
		if (priv->kind == SSI_PRESS) {
			if (chan->type == IIO_TEMP) {
				/* Samsung's LPS22H factory interface reports centidegrees. */
				*value = 10;
				return IIO_VAL_INT;
			}
			/* LPS22H pressure is 4096 counts/hPa. IIO uses kPa. */
			*value = 1;
			*value2 = 40960;
			return IIO_VAL_FRACTIONAL;
		}
		if (priv->kind == SSI_PROX) {
			*value2 = 500000;
			return IIO_VAL_INT_PLUS_MICRO;
		}
		*value2 = 2394202; /* 9.80665 m/s² divided by 4096 counts/g. */
		return IIO_VAL_INT_PLUS_NANO;
	}
	if (mask != IIO_CHAN_INFO_RAW && mask != IIO_CHAN_INFO_PROCESSED)
		return -EINVAL;

	mutex_lock(&ssi->lock);
	if (ssi->removed || !ssi->sensor_open ||
	    ssi->firmware_state != BBD_FIRMWARE_READY) {
		mutex_unlock(&ssi->lock);
		return -ENODEV;
	}
	slot->access = jiffies;
	slot->requested = true;
	ssi_sensor_update(ssi);
	ssi_sensor_schedule_idle(ssi);
	mutex_unlock(&ssi->lock);

	ret = wait_event_interruptible_timeout(ssi->wait,
			READ_ONCE(ssi->removed) || ssi_sensor_fresh(slot, priv->kind),
			msecs_to_jiffies(1000));
	if (ret < 0)
		return ret;

	mutex_lock(&ssi->lock);
	if (ssi->removed)
		ret = -ENODEV;
	else if (!ssi_sensor_fresh(slot, priv->kind))
		ret = -EAGAIN;
	else if (priv->kind == SSI_STEPS) {
		*value = lower_32_bits(slot->steps);
		*value2 = upper_32_bits(slot->steps);
		ret = IIO_VAL_INT_64;
	} else {
		*value = slot->sample[chan->address];
		/* Keep the firmware's binary flag and the ADC in separate channels. */
		if (priv->kind == SSI_PROX && !chan->address)
			*value *= 2;
		ret = IIO_VAL_INT;
	}
	mutex_unlock(&ssi->lock);
	return ret;
}

#if IS_ENABLED(CONFIG_IIO_TRIGGERED_BUFFER)
#define SSI_SCAN_CHANNEL(index) \
	.scan_index = index, \
	.scan_type = { \
		.sign = 's', \
		.realbits = 32, \
		.storagebits = 32, \
		.endianness = IIO_LE, \
	},
#else
#define SSI_SCAN_CHANNEL(index)
#endif

#define SSI_ACCEL_AXIS(axis, index) {				\
	.type = IIO_ACCEL,					\
	.modified = 1,						\
	.channel2 = IIO_MOD_##axis,				\
	.address = index,					\
	.info_mask_separate = BIT(IIO_CHAN_INFO_RAW),		\
	.info_mask_shared_by_type = BIT(IIO_CHAN_INFO_SCALE),	\
	SSI_SCAN_CHANNEL(index)				\
}

static const struct iio_chan_spec ssi_accel_channels[] = {
	SSI_ACCEL_AXIS(X, 0),
	SSI_ACCEL_AXIS(Y, 1),
	SSI_ACCEL_AXIS(Z, 2),
};

static const struct iio_chan_spec ssi_light_channels[] = {
	{
		.type = IIO_LIGHT,
		.info_mask_separate = BIT(IIO_CHAN_INFO_PROCESSED),
		.scan_index = -1,
	},
#if IS_ENABLED(CONFIG_IIO_TRIGGERED_BUFFER)
	{
		.type = IIO_INTENSITY,
		.modified = 1,
		.channel2 = IIO_MOD_LIGHT_BOTH,
		.info_mask_separate = BIT(IIO_CHAN_INFO_RAW) | BIT(IIO_CHAN_INFO_SCALE),
		SSI_SCAN_CHANNEL(0)
	},
#endif
};

static const struct iio_chan_spec ssi_prox_channels[] = {
	{
		.type = IIO_PROXIMITY,
		.info_mask_separate = BIT(IIO_CHAN_INFO_RAW) | BIT(IIO_CHAN_INFO_SCALE),
	},
	{
		.type = IIO_PROXIMITY,
		.indexed = 1,
		.channel = 1,
		.address = 1,
		.info_mask_separate = BIT(IIO_CHAN_INFO_RAW),
	},
};

#define SSI_RAW_AXIS(kind, axis, index) {			\
	.type = IIO_##kind,					\
	.modified = 1,						\
	.channel2 = IIO_MOD_##axis,				\
	.address = index,					\
	.info_mask_separate = BIT(IIO_CHAN_INFO_RAW),		\
}

static const struct iio_chan_spec ssi_gyro_channels[] = {
	SSI_RAW_AXIS(ANGL_VEL, X, 0),
	SSI_RAW_AXIS(ANGL_VEL, Y, 1),
	SSI_RAW_AXIS(ANGL_VEL, Z, 2),
};

static const struct iio_chan_spec ssi_magn_channels[] = {
	SSI_RAW_AXIS(MAGN, X, 0),
	SSI_RAW_AXIS(MAGN, Y, 1),
	SSI_RAW_AXIS(MAGN, Z, 2),
};

static const struct iio_chan_spec ssi_pressure_channels[] = {
	{
		.type = IIO_PRESSURE,
		.info_mask_separate = BIT(IIO_CHAN_INFO_RAW) | BIT(IIO_CHAN_INFO_SCALE),
	},
	{
		.type = IIO_TEMP,
		.address = 1,
		.info_mask_separate = BIT(IIO_CHAN_INFO_RAW) | BIT(IIO_CHAN_INFO_SCALE),
	},
};

static const struct iio_chan_spec ssi_steps_channels[] = {
	{
		.type = IIO_STEPS,
		.info_mask_separate = BIT(IIO_CHAN_INFO_PROCESSED),
	},
};

static const struct iio_chan_spec ssi_heading_channels[] = {
	{
		.type = IIO_ROT,
		.modified = 1,
		.channel2 = IIO_MOD_NORTH_MAGN_TILT_COMP,
		.info_mask_separate = BIT(IIO_CHAN_INFO_RAW) | BIT(IIO_CHAN_INFO_SCALE),
		SSI_SCAN_CHANNEL(0)
	},
};

#if IS_ENABLED(CONFIG_IIO_TRIGGERED_BUFFER)
static int ssi_sensor_trigger_state(struct iio_trigger *trigger, bool enabled)
{
	struct ssi_iio_priv *priv = iio_priv(iio_trigger_get_drvdata(trigger));
	struct g955n_ssi *ssi = priv->ssi;
	struct ssi_sensor_slot *slot = &ssi->slots[priv->kind];

	mutex_lock(&ssi->lock);
	slot->buffered = enabled;
	slot->requested = enabled;
	if (!enabled)
		WRITE_ONCE(slot->valid, false);
	ssi_sensor_update(ssi);
	ssi_sensor_schedule_idle(ssi);
	mutex_unlock(&ssi->lock);
	return 0;
}

static int ssi_sensor_trigger_validate(struct iio_trigger *trigger, struct iio_dev *indio)
{
	return iio_trigger_get_drvdata(trigger) == indio ? 0 : -EINVAL;
}

static const struct iio_trigger_ops ssi_sensor_trigger_ops = {
	.set_trigger_state = ssi_sensor_trigger_state,
	.validate_device = ssi_sensor_trigger_validate,
};

static irqreturn_t ssi_sensor_push(int irq, void *data)
{
	struct iio_poll_func *poll = data;
	struct iio_dev *indio = poll->indio_dev;
	struct ssi_iio_priv *priv = iio_priv(indio);
	struct ssi_sensor_slot *slot = &priv->ssi->slots[priv->kind];
	__le32 scan[ARRAY_SIZE(slot->sample)];
	unsigned int channel, index = 0;

	/* The nested trigger runs under ssi->lock, with all axes from one report. */
	for_each_set_bit(channel, indio->active_scan_mask, indio->masklength)
		scan[index++] = cpu_to_le32(slot->sample[channel]);

	iio_push_to_buffers(indio, scan);
	iio_trigger_notify_done(indio->trig);
	return IRQ_HANDLED;
}

static const char * const ssi_sensor_trigger_names[SSI_IIO_COUNT] = {
	[SSI_ACCEL] = "accel_3d",
	[SSI_LIGHT] = "als",
	[SSI_HEADING] = "magn_3d",
};

static int ssi_sensor_buffer_init(struct g955n_ssi *ssi, struct iio_dev *indio,
				  enum ssi_iio_kind kind)
{
	struct device *dev = &ssi->spi->dev;
	struct iio_trigger *trigger;
	int ret;

	trigger = devm_iio_trigger_alloc(dev, "%s-dev%d",
					 ssi_sensor_trigger_names[kind], iio_device_id(indio));
	if (!trigger)
		return -ENOMEM;
	trigger->ops = &ssi_sensor_trigger_ops;
	iio_trigger_set_drvdata(trigger, indio);
	ret = devm_iio_triggered_buffer_setup(dev, indio, NULL, ssi_sensor_push, NULL);
	if (ret)
		return ret;

	ssi->slots[kind].trigger = trigger;
	return devm_iio_trigger_register(dev, trigger);
}
#endif

static const struct iio_info ssi_sensor_info = {
	.read_raw = ssi_iio_read_raw,
};

static const struct {
	const char *name;
	const struct iio_chan_spec *channels;
	unsigned int count;
} ssi_iio_layout[] = {
	[SSI_ACCEL] = { "g955n-bcm4773-accel", ssi_accel_channels, ARRAY_SIZE(ssi_accel_channels) },
	[SSI_LIGHT] = { "g955n-bcm4773-light", ssi_light_channels, ARRAY_SIZE(ssi_light_channels) },
	[SSI_PROX] = { "g955n-bcm4773-proximity", ssi_prox_channels, ARRAY_SIZE(ssi_prox_channels) },
	[SSI_GYRO] = { "g955n-bcm4773-gyro", ssi_gyro_channels, ARRAY_SIZE(ssi_gyro_channels) },
	[SSI_MAGN] = { "g955n-bcm4773-magnetometer", ssi_magn_channels, ARRAY_SIZE(ssi_magn_channels) },
	[SSI_PRESS] = { "g955n-bcm4773-pressure", ssi_pressure_channels, ARRAY_SIZE(ssi_pressure_channels) },
	[SSI_STEPS] = { "g955n-bcm4773-steps", ssi_steps_channels, ARRAY_SIZE(ssi_steps_channels) },
	[SSI_HEADING] = { "g955n-bcm4773-heading", ssi_heading_channels, ARRAY_SIZE(ssi_heading_channels) },
};

static int ssi_register_sensor(struct g955n_ssi *ssi, enum ssi_iio_kind kind)
{
	struct ssi_iio_priv *priv;
	struct iio_dev *indio;
	int ret;

	indio = devm_iio_device_alloc(&ssi->spi->dev, sizeof(*priv));
	if (!indio)
		return -ENOMEM;
	priv = iio_priv(indio);
	priv->ssi = ssi;
	priv->kind = kind;
	indio->name = ssi_iio_layout[kind].name;
	indio->modes = INDIO_DIRECT_MODE;
	indio->info = &ssi_sensor_info;
	indio->channels = ssi_iio_layout[kind].channels;
	indio->num_channels = ssi_iio_layout[kind].count;
#if IS_ENABLED(CONFIG_IIO_TRIGGERED_BUFFER)
	if (ssi_sensor_trigger_names[kind]) {
		ret = ssi_sensor_buffer_init(ssi, indio, kind);
		if (ret)
			return ret;
	}
#endif
	ssi->slots[kind].iio = indio;
	ret = iio_device_register(indio);
	if (ret)
		ssi->slots[kind].iio = NULL;
	return ret;
}

static void ssi_unregister_sensors(struct g955n_ssi *ssi)
{
	int i;

	for (i = SSI_IIO_COUNT - 1; i >= 0; i--) {
		if (ssi->slots[i].iio)
			iio_device_unregister(ssi->slots[i].iio);
	}
}

/* With the lock held, a file operation owns the GPIO handshake and SPI. */
static int ssi_wake(struct g955n_ssi *ssi)
{
	int level, ret, attempt;

	for (attempt = 0; attempt < 4; attempt++) {
		gpiod_set_value_cansleep(ssi->request, 1);
		ret = read_poll_timeout(gpiod_get_value_cansleep, level, level != 0,
				       1000, 22000, false, ssi->response);
		if (!ret && level > 0)
			return 0;
		gpiod_set_value_cansleep(ssi->request, 0);
		if (!ret)
			return level;
		usleep_range(1000, 2000);
	}
	return ret;
}

static int ssi_transfer(struct g955n_ssi *ssi, size_t len)
{
	struct spi_transfer xfer = {
		.tx_buf = ssi->tx,
		.rx_buf = ssi->rx,
		.len = len,
		.bits_per_word = 8,
	};
	struct spi_message msg;
	int ret;

	spi_message_init_with_transfers(&msg, &xfer, 1);
	ret = spi_sync(ssi->spi, &msg);
	if (ret)
		return ret;
	return msg.actual_length == len ? 0 : -EIO;
}

static int ssi_receive_awake(struct g955n_ssi *ssi)
{
	size_t length;
	int ret;

	memset(ssi->tx, 0, SSI_HEADER + SSI_PAYLOAD);
	ssi->tx[0] = SSI_READ;
	ret = ssi_transfer(ssi, SSI_HEADER);
	if (ret)
		return ret;
	if (ssi->rx[0])
		return -EPROTO;

	length = min_t(size_t, ssi->rx[1] ?: SSI_PAYLOAD, SSI_PAYLOAD);
	ret = ssi_transfer(ssi, SSI_HEADER + length);
	if (ret)
		return ret;
	if (ssi->rx[0])
		return -EPROTO;
	return min_t(size_t, ssi->rx[1], length);
}

static int ssi_receive(struct g955n_ssi *ssi)
{
	int ret = ssi_wake(ssi);

	if (ret)
		return ret;
	ret = ssi_receive_awake(ssi);
	gpiod_set_value_cansleep(ssi->request, 0);
	if (ret <= 0)
		return ret ?: -ENODATA;
	ssi->pending = ret;
	return 0;
}

static int ssi_save_gpio(struct gpio_desc *gpio, struct ssi_saved_gpio *saved)
{
	int ret;

	if (!gpio || saved->saved)
		return 0;
	ret = gpiod_get_direction(gpio);
	if (ret < 0)
		return ret;
	saved->direction = ret;
	if (!saved->direction) {
		ret = gpiod_get_value_cansleep(gpio);
		if (ret < 0)
			return ret;
		saved->value = ret;
	}
	saved->saved = true;
	return 0;
}

static int ssi_restore_gpio(struct gpio_desc *gpio, struct ssi_saved_gpio *saved)
{
	int ret;

	if (!saved->saved)
		return 0;
	if (saved->direction)
		ret = gpiod_direction_input(gpio);
	else
		ret = gpiod_direction_output(gpio, saved->value);
	if (!ret)
		saved->saved = false;
	return ret;
}

static int ssi_drive_gpio(struct gpio_desc *gpio, bool enable)
{
	int ret = gpiod_direction_output(gpio, enable);

	if (ret)
		return ret;
	ret = gpiod_get_value_cansleep(gpio);
	if (ret < 0)
		return ret;
	return ret == enable ? 0 : -EIO;
}

static int ssi_power_on(struct g955n_ssi *ssi)
{
	int ret, restore;

	ret = ssi_save_gpio(ssi->enable, &ssi->enable_original);
	if (ret)
		return ret;
	ret = regulator_enable(ssi->supply);
	if (ret) {
		ssi->enable_original.saved = false;
		return ret;
	}
	ssi->powered = true;
	if (!ssi->enable)
		return 0;

	ret = ssi_drive_gpio(ssi->enable, true);
	if (!ret)
		return 0;
	restore = ssi_restore_gpio(ssi->enable, &ssi->enable_original);
	if (restore)
		dev_err(&ssi->spi->dev, "cannot restore hub enable: %d\n", restore);
	if (!regulator_disable(ssi->supply))
		ssi->powered = false;
	return ret;
}

static int ssi_power_off(struct g955n_ssi *ssi)
{
	int restore = ssi_restore_gpio(ssi->enable, &ssi->enable_original);
	int ret = regulator_disable(ssi->supply);

	if (!ret)
		ssi->powered = false;
	return restore ?: ret;
}

static int ssi_open_link(struct file *file, struct g955n_ssi *ssi, bool stream)
{
	int ret;

	mutex_lock(&ssi->lock);
	if (ssi->removed) {
		ret = -ENODEV;
		goto out;
	}
	if (ssi->opened) {
		ret = -EBUSY;
		goto out;
	}
	if (expose_legacy_power) {
		if (!stream) {
			ret = -EBUSY;
			goto out;
		}
	} else {
		if (ssi->powered) {
			ret = -EIO;
			goto out;
		}
		ret = ssi_power_on(ssi);
		if (ret)
			goto out;
		msleep(200);
	}
	ssi->opened = true;
	ssi->pending = 0;
	if (stream) {
		kfifo_reset(&ssi->stream_tx);
		kfifo_reset(&ssi->stream_rx);
		ssi->stream_tx_bytes = 0;
		ssi->stream_rx_bytes = 0;
		ssi->stream_error = 0;
		ssi->empty_receives = 0;
	}
	WRITE_ONCE(ssi->stream_open, stream);
	kref_get(&ssi->refs);
	file->private_data = ssi;
	enable_irq(ssi->irq);
	if (stream)
		queue_delayed_work(system_freezable_wq, &ssi->stream_work, 0);
out:
	mutex_unlock(&ssi->lock);
	return ret;
}

static int ssi_open(struct inode *inode, struct file *file)
{
	struct g955n_ssi *ssi = container_of(file->private_data,
					   struct g955n_ssi, misc);

	return ssi_open_link(file, ssi, false);
}

static int ssi_release(struct inode *inode, struct file *file)
{
	struct g955n_ssi *ssi = file->private_data;
	int ret = 0;

	mutex_lock(&ssi->lock);
	if (!ssi->removed) {
		disable_irq(ssi->irq);
		if (!expose_legacy_power)
			ret = ssi_power_off(ssi);
	}
	WRITE_ONCE(ssi->stream_open, false);
	ssi->opened = false;
	mutex_unlock(&ssi->lock);
	kref_put(&ssi->refs, ssi_free);
	return ret;
}

static ssize_t ssi_read(struct file *file, char __user *buffer,
			size_t length, loff_t *position)
{
	struct g955n_ssi *ssi = file->private_data;
	ssize_t ret;

	if (!length)
		return 0;
	ret = mutex_lock_interruptible(&ssi->lock);
	if (ret)
		return ret;
	if (ssi->removed) {
		ret = -ENODEV;
		goto out;
	}
	if (!ssi->pending) {
		ret = gpiod_get_value_cansleep(ssi->host);
		if (ret <= 0) {
			ret = ret ?: -EAGAIN;
			goto out;
		}
		ret = ssi_receive(ssi);
		if (ret)
			goto out;
	}

	length = min(length, ssi->pending);
	if (copy_to_user(buffer, ssi->rx + SSI_HEADER, length)) {
		ret = -EFAULT;
		goto out;
	}
	ssi->pending -= length;
	memmove(ssi->rx + SSI_HEADER, ssi->rx + SSI_HEADER + length,
		ssi->pending);
	ret = length;
	if (!ssi->pending)
		wake_up_interruptible(&ssi->wait);
out:
	mutex_unlock(&ssi->lock);
	return ret;
}

static ssize_t ssi_write(struct file *file, const char __user *buffer,
			 size_t length, loff_t *position)
{
	struct g955n_ssi *ssi = file->private_data;
	ssize_t ret;

	if (!length)
		return 0;
	length = min_t(size_t, length, SSI_PAYLOAD);
	ret = mutex_lock_interruptible(&ssi->lock);
	if (ret)
		return ret;
	if (ssi->removed) {
		ret = -ENODEV;
		goto out;
	}
	/* Inbound data takes priority and must survive a TX transfer. */
	ret = gpiod_get_value_cansleep(ssi->host);
	if (ret || ssi->pending) {
		ret = ret < 0 ? ret : -EAGAIN;
		goto out;
	}
	ssi->tx[0] = SSI_WRITE;
	if (copy_from_user(ssi->tx + 1, buffer, length)) {
		ret = -EFAULT;
		goto out;
	}
	ret = ssi_wake(ssi);
	if (!ret) {
		ret = ssi_transfer(ssi, length + 1);
		gpiod_set_value_cansleep(ssi->request, 0);
		if (!ret)
			ret = length;
	}
out:
	mutex_unlock(&ssi->lock);
	return ret;
}

static __poll_t ssi_poll(struct file *file, poll_table *wait)
{
	struct g955n_ssi *ssi = file->private_data;
	__poll_t flags;
	int host;

	poll_wait(file, &ssi->wait, wait);
	mutex_lock(&ssi->lock);
	if (ssi->removed) {
		flags = EPOLLHUP | EPOLLERR;
	} else {
		host = gpiod_get_value_cansleep(ssi->host);
		flags = !ssi->pending && !host ? EPOLLOUT | EPOLLWRNORM : 0;
		if (ssi->pending || host > 0)
			flags |= EPOLLIN | EPOLLRDNORM;
		if (host < 0)
			flags |= EPOLLERR;
	}
	mutex_unlock(&ssi->lock);
	return flags;
}

static const struct file_operations ssi_ops = {
	.owner = THIS_MODULE,
	.open = ssi_open,
	.release = ssi_release,
	.read = ssi_read,
	.write = ssi_write,
	.poll = ssi_poll,
	.llseek = noop_llseek,
};

/*
 * The legacy daemon queues complete byte ranges independently of the hub's
 * SSI handshake. Port the stream transport first; BBD RPC routing is separate.
 */
static void ssi_stream_worker(struct work_struct *work)
{
	struct g955n_ssi *ssi = container_of(to_delayed_work(work),
					   struct g955n_ssi, stream_work);
	unsigned long delay = 0;
	bool awake = false;
	int host, ret = 0, frame;

	mutex_lock(&ssi->lock);
	if (ssi->removed || !ssi->stream_open || !ssi->powered || ssi->stream_error)
		goto out;

	for (frame = 0; frame < SSI_WORK_BUDGET; frame++) {
		unsigned int count;

		host = gpiod_get_value_cansleep(ssi->host);
		if (host < 0) {
			ret = host;
			break;
		}
		if (host && kfifo_avail(&ssi->stream_rx) < SSI_PAYLOAD)
			break;
		if (!host && kfifo_is_empty(&ssi->stream_tx))
			break;
		if (!awake) {
			ret = ssi_wake(ssi);
			if (ret)
				break;
			awake = true;
		}

		/* Leave room for the whole inbound SSI frame before clocking it. */
		if (host) {
			ret = ssi_receive_awake(ssi);
			if (ret < 0)
				break;
			count = kfifo_in(&ssi->stream_rx, ssi->rx + SSI_HEADER, ret);
			ssi->stream_rx_bytes += count;
			if ((expose_legacy_accel || expose_legacy_environment || expose_legacy_motion) &&
			    ssi->firmware_state == BBD_FIRMWARE_READY)
				ssi_bbd_feed(ssi, ssi->rx + SSI_HEADER, count);
			if (!count && ++ssi->empty_receives == 4) {
				ret = -EPROTO;
				break;
			}
			if (count)
				ssi->empty_receives = 0;
		} else {
			ssi->empty_receives = 0;
		}

		ssi->tx[0] = SSI_WRITE;
		count = kfifo_out_peek(&ssi->stream_tx, ssi->tx + 1, SSI_PAYLOAD);
		if (count) {
			ret = ssi_transfer(ssi, count + 1);
			if (ret)
				break;
			kfifo_skip_count(&ssi->stream_tx, count);
			ssi->stream_tx_bytes += count;
		} else if (!ret) {
			/* HOST_REQ may stay asserted after an empty length report. */
			delay = msecs_to_jiffies(10);
			break;
		}
	}
	if (awake)
		gpiod_set_value_cansleep(ssi->request, 0);
	if (ret < 0)
		ssi->stream_error = ret;
	if (frame == SSI_WORK_BUDGET || delay)
		queue_delayed_work(system_freezable_wq, &ssi->stream_work, delay);
	wake_up_interruptible(&ssi->wait);
out:
	mutex_unlock(&ssi->lock);
}

static int ssi_stream_open(struct inode *inode, struct file *file)
{
	struct g955n_ssi *ssi = container_of(file->private_data,
					   struct g955n_ssi, stream);
	int ret = stream_open(inode, file);

	return ret ?: ssi_open_link(file, ssi, true);
}

static ssize_t ssi_stream_read(struct file *file, char __user *buffer,
			       size_t length, loff_t *position)
{
	struct g955n_ssi *ssi = file->private_data;
	unsigned int copied = 0;
	int ret;

	if (!length)
		return 0;
	ret = mutex_lock_interruptible(&ssi->lock);
	if (ret)
		return ret;
	if (ssi->removed) {
		ret = -ENODEV;
	} else if (kfifo_is_empty(&ssi->stream_rx)) {
		ret = ssi->stream_error;
	} else {
		ret = kfifo_to_user(&ssi->stream_rx, buffer,
				   min_t(size_t, length, SSI_STREAM_SIZE), &copied);
		if (copied && !ssi->stream_error)
			queue_delayed_work(system_freezable_wq, &ssi->stream_work, 0);
	}
	mutex_unlock(&ssi->lock);
	return copied ? (ssize_t)copied : ret;
}

static ssize_t ssi_stream_write(struct file *file, const char __user *buffer,
				size_t length, loff_t *position)
{
	struct g955n_ssi *ssi = file->private_data;
	unsigned int copied = 0;
	int ret;

	if (!length)
		return 0;
	ret = mutex_lock_interruptible(&ssi->lock);
	if (ret)
		return ret;
	if (ssi->removed) {
		ret = -ENODEV;
	} else if (!ssi->powered) {
		ret = -EHOSTDOWN;
	} else if (ssi->stream_error) {
		ret = ssi->stream_error;
	} else {
		ret = kfifo_from_user(&ssi->stream_tx, buffer,
				     min_t(size_t, length, SSI_STREAM_SIZE), &copied);
		if (copied)
			queue_delayed_work(system_freezable_wq, &ssi->stream_work, 0);
	}
	mutex_unlock(&ssi->lock);
	return copied ? (ssize_t)copied : ret;
}

static __poll_t ssi_stream_poll(struct file *file, poll_table *wait)
{
	struct g955n_ssi *ssi = file->private_data;
	__poll_t flags = 0;

	poll_wait(file, &ssi->wait, wait);
	mutex_lock(&ssi->lock);
	if (ssi->removed) {
		flags = EPOLLHUP | EPOLLERR;
	} else {
		if (!kfifo_is_empty(&ssi->stream_rx))
			flags |= EPOLLIN | EPOLLRDNORM;
		if (ssi->stream_error)
			flags |= EPOLLERR;
		else if (ssi->powered && !kfifo_is_full(&ssi->stream_tx))
			flags |= EPOLLOUT | EPOLLWRNORM;
	}
	mutex_unlock(&ssi->lock);
	return flags;
}

static const struct file_operations ssi_stream_ops = {
	.owner = THIS_MODULE,
	.open = ssi_stream_open,
	.release = ssi_release,
	.read = ssi_stream_read,
	.write = ssi_stream_write,
	.poll = ssi_stream_poll,
};

static ssize_t transport_status_show(struct device *dev,
				     struct device_attribute *attr, char *buf)
{
	struct miscdevice *stream = dev_get_drvdata(dev);
	struct g955n_ssi *ssi = container_of(stream, struct g955n_ssi, stream);
	ssize_t count;

	mutex_lock(&ssi->lock);
	count = sysfs_emit(buf, "tx_bytes=%llu rx_bytes=%llu tx_pending=%u error=%d\n",
			   ssi->stream_tx_bytes, ssi->stream_rx_bytes,
			   kfifo_len(&ssi->stream_tx), ssi->stream_error);
	mutex_unlock(&ssi->lock);
	return count;
}
static DEVICE_ATTR_RO(transport_status);

static struct attribute *ssi_stream_attrs[] = {
	&dev_attr_transport_status.attr,
	NULL,
};
ATTRIBUTE_GROUPS(ssi_stream);

/*
 * The verified Korean-board patch comes from the owner's Samsung boot.
 * Do not accept a differently sized or identified image on this endpoint.
 */
static int ssi_patch_open(struct inode *inode, struct file *file)
{
	static const u8 expected[SHA256_DIGEST_SIZE] = {
		0x66, 0x9c, 0x53, 0x69, 0x90, 0xa0, 0xd5, 0xf5,
		0x79, 0x46, 0xd3, 0xd9, 0x44, 0x5c, 0xd6, 0xbc,
		0x71, 0xec, 0xd4, 0x4e, 0x87, 0x15, 0xe5, 0xb5,
		0x02, 0xdc, 0x9f, 0xe5, 0xbc, 0xab, 0xc3, 0x84,
	};
	struct g955n_ssi *ssi = container_of(file->private_data,
					   struct g955n_ssi, patch);
	const struct firmware *firmware;
	u8 digest[SHA256_DIGEST_SIZE];
	int ret;

	if (file->f_mode & FMODE_WRITE)
		return -EACCES;
	mutex_lock(&ssi->lock);
	ret = ssi->removed ? -ENODEV :
		request_firmware_direct(&firmware, BBD_PATCH_NAME, &ssi->spi->dev);
	mutex_unlock(&ssi->lock);
	if (ret)
		return ret;
	if (firmware->size != BBD_PATCH_SIZE)
		goto reject;
	sha256(firmware->data, firmware->size, digest);
	if (memcmp(digest, expected, sizeof(digest)))
		goto reject;
	file->private_data = (void *)firmware;
	return 0;

reject:
	release_firmware(firmware);
	return -EBADMSG;
}

static ssize_t ssi_patch_read(struct file *file, char __user *buffer,
			      size_t length, loff_t *position)
{
	const struct firmware *firmware = file->private_data;

	return simple_read_from_buffer(buffer, length, position,
				       firmware->data, firmware->size);
}

static int ssi_patch_release(struct inode *inode, struct file *file)
{
	release_firmware(file->private_data);
	return 0;
}

static loff_t ssi_patch_seek(struct file *file, loff_t offset, int whence)
{
	const struct firmware *firmware = file->private_data;

	return fixed_size_llseek(file, offset, whence, firmware->size);
}

static const struct file_operations ssi_patch_ops = {
	.owner = THIS_MODULE,
	.open = ssi_patch_open,
	.release = ssi_patch_release,
	.read = ssi_patch_read,
	.llseek = ssi_patch_seek,
};

static int ssi_control_open(struct inode *inode, struct file *file)
{
	struct g955n_ssi *ssi = container_of(file->private_data,
					   struct g955n_ssi, control);
	int ret = stream_open(inode, file);

	if (ret)
		return ret;

	kref_get(&ssi->refs);
	file->private_data = ssi;
	return 0;
}

static int ssi_control_release(struct inode *inode, struct file *file)
{
	struct g955n_ssi *ssi = file->private_data;

	kref_put(&ssi->refs, ssi_free);
	return 0;
}

static ssize_t ssi_control_read(struct file *file, char __user *buffer,
				size_t length, loff_t *position)
{
	struct g955n_ssi *ssi = file->private_data;

	/* No kernel-originated messages are produced yet. */
	return READ_ONCE(ssi->removed) ? -ENODEV : 0;
}

static int ssi_sensor_open(struct inode *inode, struct file *file)
{
	struct g955n_ssi *ssi = container_of(file->private_data,
					   struct g955n_ssi, sensor);
	int ret = stream_open(inode, file);

	if (ret)
		return ret;
	mutex_lock(&ssi->lock);
	if (ssi->removed) {
		ret = -ENODEV;
	} else if (ssi->sensor_open) {
		ret = -EBUSY;
	} else {
		ssi->sensor_open = true;
		kref_get(&ssi->refs);
		file->private_data = ssi;
	}
	mutex_unlock(&ssi->lock);
	return ret;
}

static int ssi_sensor_release(struct inode *inode, struct file *file)
{
	struct g955n_ssi *ssi = file->private_data;

	mutex_lock(&ssi->lock);
	ssi->sensor_open = false;
	ssi_sensor_reset(ssi);
	mutex_unlock(&ssi->lock);
	kref_put(&ssi->refs, ssi_free);
	return 0;
}

static ssize_t ssi_sensor_read(struct file *file, char __user *buffer,
			       size_t length, loff_t *position)
{
	struct g955n_ssi *ssi = file->private_data;
	ssize_t ret = 0;

	if (!length)
		return 0;
	mutex_lock(&ssi->lock);
	if (ssi->removed) {
		ret = -ENODEV;
	} else if (ssi->sensor_size) {
		length = min(length, ssi->sensor_size - ssi->sensor_offset);
		length -= copy_to_user(buffer, ssi->sensor_request + ssi->sensor_offset,
				       length);
		ssi->sensor_offset += length;
		if (ssi->sensor_offset == ssi->sensor_size) {
			ssi->sensor_size = 0;
			ssi_sensor_update(ssi);
		}
		ret = length ? (ssize_t)length : -EFAULT;
	}
	mutex_unlock(&ssi->lock);
	return ret;
}

static __poll_t ssi_sensor_poll(struct file *file, poll_table *wait)
{
	struct g955n_ssi *ssi = file->private_data;
	__poll_t flags = 0;

	poll_wait(file, &ssi->wait, wait);
	mutex_lock(&ssi->lock);
	if (ssi->removed)
		flags = EPOLLHUP | EPOLLERR;
	else if (ssi->sensor_size)
		flags = EPOLLIN | EPOLLRDNORM;
	mutex_unlock(&ssi->lock);
	return flags;
}

static const struct file_operations ssi_sensor_ops = {
	.owner = THIS_MODULE,
	.open = ssi_sensor_open,
	.release = ssi_sensor_release,
	.read = ssi_sensor_read,
	.poll = ssi_sensor_poll,
};

static ssize_t ssi_control_write(struct file *file, const char __user *buffer,
				 size_t length, loff_t *position)
{
	struct g955n_ssi *ssi = file->private_data;
	char command[BBD_CONTROL_MAX + 1];
	size_t end = length;
	ssize_t ret = length;

	if (!length)
		return 0;
	if (length > BBD_CONTROL_MAX)
		return -EMSGSIZE;
	if (copy_from_user(command, buffer, length))
		return -EFAULT;
	if (command[end - 1] == '\0')
		end--;
	if (end && command[end - 1] == '\n')
		end--;
	if (!end || memchr(command, '\0', end))
		return -EINVAL;
	command[end] = '\0';

	mutex_lock(&ssi->lock);
	if (ssi->removed) {
		ret = -ENODEV;
	} else if (!strcmp(command, "ESW:NOTREADY")) {
		ssi->firmware_state = BBD_FIRMWARE_NOT_READY;
		ssi_sensor_reset(ssi);
	} else if (!strcmp(command, "ESW:READY")) {
		if (probe_legacy_ssp && ssi->firmware_state != BBD_FIRMWARE_READY) {
			ssi_sensor_queue(ssi, ssi_ssp_whoami, sizeof(ssi_ssp_whoami));
		}
		ssi->firmware_state = BBD_FIRMWARE_READY;
		ssi_sensor_update(ssi);
	} else if (!strcmp(command, "ESW:CRASHED")) {
		ssi->firmware_state = BBD_FIRMWARE_CRASHED;
		ssi_sensor_reset(ssi);
		ssi->patch_transfer = false;
	} else if (!strcmp(command, "BBD:PassThru=1") ||
		   !strcmp(command, "SSI:PassThru=1")) {
		ssi->patch_transfer = true;
	} else if (!strcmp(command, "BBD:PassThru=0") ||
		   !strcmp(command, "SSI:PassThru=0")) {
		ssi->patch_transfer = false;
	} else if (strcmp(command, "BBD:DEBUG=0") &&
		   strcmp(command, "SSP:DEBUG=0") &&
		   strcmp(command, "SSI:DEBUG=0")) {
		ret = -EOPNOTSUPP;
	}
	mutex_unlock(&ssi->lock);
	return ret;
}

static __poll_t ssi_control_poll(struct file *file, poll_table *wait)
{
	struct g955n_ssi *ssi = file->private_data;

	poll_wait(file, &ssi->wait, wait);
	return READ_ONCE(ssi->removed) ? EPOLLERR | EPOLLHUP :
					EPOLLOUT | EPOLLWRNORM;
}

static const struct file_operations ssi_control_ops = {
	.owner = THIS_MODULE,
	.open = ssi_control_open,
	.release = ssi_control_release,
	.read = ssi_control_read,
	.write = ssi_control_write,
	.poll = ssi_control_poll,
};

static ssize_t daemon_status_show(struct device *dev,
				  struct device_attribute *attr, char *buf)
{
	static const char * const states[] = {
		[BBD_FIRMWARE_UNKNOWN] = "unknown",
		[BBD_FIRMWARE_NOT_READY] = "not-ready",
		[BBD_FIRMWARE_READY] = "ready",
		[BBD_FIRMWARE_CRASHED] = "crashed",
	};
	struct miscdevice *control = dev_get_drvdata(dev);
	struct g955n_ssi *ssi = container_of(control, struct g955n_ssi, control);
	ssize_t count;

	mutex_lock(&ssi->lock);
	count = sysfs_emit(buf, "firmware_state=%s patch_transfer=%u\n",
			   states[ssi->firmware_state], ssi->patch_transfer);
	mutex_unlock(&ssi->lock);
	return count;
}
static DEVICE_ATTR_RO(daemon_status);

static struct attribute *ssi_control_attrs[] = {
	&dev_attr_daemon_status.attr,
	NULL,
};
ATTRIBUTE_GROUPS(ssi_control);

/* On Korean rev10, the gate stays asserted while lhd cycles the 1.8 V rail. */
static int ssi_manual_rail(struct g955n_ssi *ssi, bool on)
{
	int ret;

	if (ssi->powered == on)
		return 0;
	if (on) {
		ret = ssi_save_gpio(ssi->enable, &ssi->enable_original);
		if (ret)
			return ret;
		ret = ssi_drive_gpio(ssi->enable, true);
		if (!ret)
			ret = regulator_enable(ssi->supply);
		if (ret && ssi_restore_gpio(ssi->enable, &ssi->enable_original))
			dev_err(&ssi->spi->dev, "cannot restore manual hub gate\n");
	} else {
		ret = regulator_disable(ssi->supply);
	}
	if (ret)
		return ret;
	ssi->powered = on;
	if (!on) {
		kfifo_reset(&ssi->stream_rx);
		kfifo_reset(&ssi->stream_tx);
		ssi->empty_receives = 0;
		ssi->stream_error = 0;
		ssi->firmware_state = BBD_FIRMWARE_UNKNOWN;
		ssi->patch_transfer = false;
		ssi_sensor_reset(ssi);
	}
	msleep(20);
	if (on && ssi->stream_open)
		queue_delayed_work(system_freezable_wq, &ssi->stream_work, 0);
	wake_up_interruptible(&ssi->wait);
	return 0;
}

static ssize_t mcu_power_show(struct device *dev, struct device_attribute *attr,
			      char *buf)
{
	struct g955n_ssi *ssi = dev_get_drvdata(dev);
	int ret;

	mutex_lock(&ssi->lock);
	ret = regulator_is_enabled(ssi->supply);
	mutex_unlock(&ssi->lock);
	return ret < 0 ? ret : sysfs_emit(buf, "%d\n", ret);
}

static ssize_t mcu_power_store(struct device *dev, struct device_attribute *attr,
			       const char *buf, size_t count)
{
	struct g955n_ssi *ssi = dev_get_drvdata(dev);
	u8 on;
	int ret;

	ret = kstrtou8(buf, 10, &on);
	if (ret)
		return ret;
	if (on > 1)
		return -EINVAL;
	mutex_lock(&ssi->lock);
	ret = ssi_manual_rail(ssi, on);
	mutex_unlock(&ssi->lock);
	return ret ? ret : (ssize_t)count;
}
static DEVICE_ATTR(mcu_power, 0600, mcu_power_show, mcu_power_store);

static struct attribute *ssi_power_attrs[] = {
	&dev_attr_mcu_power.attr,
	NULL,
};
ATTRIBUTE_GROUPS(ssi_power);

static ssize_t value_show(struct device *dev, struct device_attribute *attr,
			  char *buf)
{
	struct g955n_ssi *ssi = dev_get_drvdata(dev);
	int ret;

	mutex_lock(&ssi->lock);
	ret = gpiod_get_value_cansleep(ssi->gnss_enable);
	mutex_unlock(&ssi->lock);
	return ret < 0 ? ret : sysfs_emit(buf, "%d\n", ret);
}

static ssize_t value_store(struct device *dev, struct device_attribute *attr,
			   const char *buf, size_t count)
{
	struct g955n_ssi *ssi = dev_get_drvdata(dev);
	u8 on;
	int ret;

	ret = kstrtou8(buf, 10, &on);
	if (ret)
		return ret;
	if (on > 1)
		return -EINVAL;
	mutex_lock(&ssi->lock);
	ret = ssi_save_gpio(ssi->gnss_enable, &ssi->gnss_original);
	if (!ret)
		ret = ssi_drive_gpio(ssi->gnss_enable, on);
	mutex_unlock(&ssi->lock);
	return ret ? ret : (ssize_t)count;
}
static DEVICE_ATTR(value, 0600, value_show, value_store);

static struct attribute *ssi_gnss_attrs[] = {
	&dev_attr_value.attr,
	NULL,
};
static const struct attribute_group ssi_gnss_group = {
	.name = "GPS_PWR_EN",
	.attrs = ssi_gnss_attrs,
};
static const struct attribute_group *ssi_gnss_groups[] = {
	&ssi_gnss_group,
	NULL,
};

static int ssi_register_power(struct g955n_ssi *ssi)
{
	struct device *parent = &ssi->spi->dev;
	int ret;

	ssi->sec_class = class_create("sec");
	if (IS_ERR(ssi->sec_class))
		return PTR_ERR(ssi->sec_class);
	ssi->power_device = device_create_with_groups(ssi->sec_class, parent,
						      0, ssi, ssi_power_groups,
						      "sensorhub");
	if (IS_ERR(ssi->power_device)) {
		ret = PTR_ERR(ssi->power_device);
		goto destroy_class;
	}
	ssi->gnss_device = device_create_with_groups(ssi->sec_class, parent,
						     0, ssi, ssi_gnss_groups,
						     "gps");
	if (IS_ERR(ssi->gnss_device)) {
		ret = PTR_ERR(ssi->gnss_device);
		device_unregister(ssi->power_device);
		goto destroy_class;
	}
	return 0;

destroy_class:
	class_destroy(ssi->sec_class);
	return ret;
}

static void ssi_disconnect(struct g955n_ssi *ssi)
{
	mutex_lock(&ssi->lock);
	if (ssi->removed) {
		mutex_unlock(&ssi->lock);
		return;
	}
	WRITE_ONCE(ssi->removed, true);
	if (ssi->opened)
		disable_irq(ssi->irq);
	if (ssi->powered && ssi_power_off(ssi))
		dev_err(&ssi->spi->dev, "cannot restore hub power on removal\n");
	if (ssi_restore_gpio(ssi->enable, &ssi->enable_original))
		dev_err(&ssi->spi->dev, "cannot restore hub enable on removal\n");
	if (ssi_restore_gpio(ssi->gnss_enable, &ssi->gnss_original))
		dev_err(&ssi->spi->dev, "cannot restore GNSS enable on removal\n");
	mutex_unlock(&ssi->lock);
	cancel_delayed_work_sync(&ssi->stream_work);
	cancel_delayed_work_sync(&ssi->sensor_idle);
	wake_up_interruptible(&ssi->wait);
}

static int g955n_ssi_probe(struct spi_device *spi)
{
	struct device *dev = &spi->dev;
	struct g955n_ssi *ssi;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks") ||
	    (spi->mode & (SPI_CPOL | SPI_CPHA)) != SPI_MODE_3)
		return -ENODEV;

	if (expose_legacy_power && !expose_legacy_stream)
		return dev_err_probe(dev, -EINVAL, "daemon power requires the queued SSI stream\n");

	if (probe_legacy_ssp && !expose_legacy_control)
		return dev_err_probe(dev, -EINVAL, "SSP probe requires BBD control\n");

	if ((expose_legacy_accel || expose_legacy_environment || expose_legacy_motion) &&
	    (!probe_legacy_ssp || !expose_legacy_stream))
		return dev_err_probe(dev, -EINVAL, "sensor IIO requires the legacy SSI bridge\n");

	ssi = kzalloc(sizeof(*ssi), GFP_KERNEL);
	if (!ssi)
		return -ENOMEM;
	kref_init(&ssi->refs);
	mutex_init(&ssi->lock);
	init_waitqueue_head(&ssi->wait);
	INIT_DELAYED_WORK(&ssi->stream_work, ssi_stream_worker);
	INIT_DELAYED_WORK(&ssi->sensor_idle, ssi_sensor_idle);
	ssi->spi = spi;
	ssi->tx = devm_kzalloc(dev, SSI_HEADER + SSI_PAYLOAD, GFP_KERNEL);
	ssi->rx = devm_kzalloc(dev, SSI_HEADER + SSI_PAYLOAD, GFP_KERNEL);
	ret = -ENOMEM;
	if (!ssi->tx || !ssi->rx)
		goto free;
	if (expose_legacy_stream) {
		void *tx = devm_kmalloc(dev, SSI_STREAM_SIZE, GFP_KERNEL);
		void *rx = devm_kmalloc(dev, SSI_STREAM_SIZE, GFP_KERNEL);

		if (!tx || !rx)
			goto free;
		kfifo_init(&ssi->stream_tx, tx, SSI_STREAM_SIZE);
		kfifo_init(&ssi->stream_rx, rx, SSI_STREAM_SIZE);
	}

	ssi->supply = devm_regulator_get(dev, "vddio");
	ret = PTR_ERR_OR_ZERO(ssi->supply);
	if (ret)
		goto free;
	ssi->request = devm_gpiod_get(dev, "wake-request", GPIOD_OUT_LOW);
	ret = PTR_ERR_OR_ZERO(ssi->request);
	if (ret)
		goto free;
	ssi->response = devm_gpiod_get(dev, "wake-response", GPIOD_IN);
	ret = PTR_ERR_OR_ZERO(ssi->response);
	if (ret)
		goto free;
	ssi->host = devm_gpiod_get(dev, "host-request", GPIOD_IN);
	ret = PTR_ERR_OR_ZERO(ssi->host);
	if (ret)
		goto free;

	ssi->enable = devm_gpiod_get_optional(dev, "rev10-enable", GPIOD_ASIS);
	ret = PTR_ERR_OR_ZERO(ssi->enable);
	if (ret)
		goto free;

	if (expose_legacy_power) {
		if (!ssi->enable) {
			ret = -ENODEV;
			goto free;
		}
		ssi->gnss_enable = devm_gpiod_get(dev, "gnss-enable", GPIOD_ASIS);
		if (IS_ERR(ssi->gnss_enable)) {
			ret = PTR_ERR(ssi->gnss_enable);
			goto free;
		}
	}

	ssi->irq = gpiod_to_irq(ssi->host);
	if (ssi->irq < 0) {
		ret = ssi->irq;
		goto free;
	}
	ret = request_irq(ssi->irq, ssi_host_irq,
			  IRQF_TRIGGER_RISING | IRQF_NO_AUTOEN, dev_name(dev), ssi);
	if (ret)
		goto free;

	ssi->misc = (struct miscdevice) {
		.minor = MISC_DYNAMIC_MINOR,
		.name = "g955n-bcm4773-ssi",
		.mode = 0600,
		.parent = dev,
		.fops = &ssi_ops,
	};
	ret = misc_register(&ssi->misc);
	if (ret)
		goto free_irq;
	if (expose_legacy_patch) {
		ssi->patch = (struct miscdevice) {
			.minor = MISC_DYNAMIC_MINOR,
			.name = "bbd_patch",
			.mode = 0400,
			.parent = dev,
			.fops = &ssi_patch_ops,
		};
		ret = misc_register(&ssi->patch);
		if (ret)
			goto deregister_misc;
	}
	if (expose_legacy_control) {
		ssi->control = (struct miscdevice) {
			.minor = MISC_DYNAMIC_MINOR,
			.name = "bbd_control",
			.mode = 0600,
			.parent = dev,
			.fops = &ssi_control_ops,
			.groups = ssi_control_groups,
		};
		ret = misc_register(&ssi->control);
		if (ret)
			goto deregister_patch;
	}
	if (expose_legacy_stream) {
		ssi->stream = (struct miscdevice) {
			.minor = MISC_DYNAMIC_MINOR,
			.name = "ttyBCM",
			.mode = 0600,
			.parent = dev,
			.fops = &ssi_stream_ops,
			.groups = ssi_stream_groups,
		};
		ret = misc_register(&ssi->stream);
		if (ret)
			goto deregister_control;
	}
	if (expose_legacy_power) {
		ret = ssi_register_power(ssi);
		if (ret)
			goto deregister_stream;
	}
	if (probe_legacy_ssp) {
		ssi->sensor = (struct miscdevice) {
			.minor = MISC_DYNAMIC_MINOR,
			.name = "bbd_sensor",
			.mode = 0600,
			.parent = dev,
			.fops = &ssi_sensor_ops,
		};
		ret = misc_register(&ssi->sensor);
		if (ret)
			goto deregister_power;
	}
	if (expose_legacy_accel) {
		ret = ssi_register_sensor(ssi, SSI_ACCEL);
		if (ret)
			goto deregister_sensor;
	}
	if (expose_legacy_environment) {
		ret = ssi_register_sensor(ssi, SSI_LIGHT);
		if (ret)
			goto deregister_sensor;
		ret = ssi_register_sensor(ssi, SSI_PROX);
		if (ret)
			goto deregister_sensor;
	}
	if (expose_legacy_motion) {
		enum ssi_iio_kind kind;

		for (kind = SSI_GYRO; kind <= SSI_HEADING; kind++) {
			ret = ssi_register_sensor(ssi, kind);
			if (ret)
				goto deregister_sensor;
		}
	}
	spi_set_drvdata(spi, ssi);
	return 0;

deregister_sensor:
	ssi_disconnect(ssi);
	ssi_unregister_sensors(ssi);
	misc_deregister(&ssi->sensor);
deregister_power:
	if (expose_legacy_power) {
		device_unregister(ssi->gnss_device);
		device_unregister(ssi->power_device);
		class_destroy(ssi->sec_class);
	}
deregister_stream:
	misc_deregister(&ssi->stream);
deregister_control:
	if (expose_legacy_control)
		misc_deregister(&ssi->control);
deregister_patch:
	if (expose_legacy_patch)
		misc_deregister(&ssi->patch);
deregister_misc:
	misc_deregister(&ssi->misc);
	/* An open could have raced registration of a later endpoint. */
	ssi_disconnect(ssi);
free_irq:
	free_irq(ssi->irq, ssi);
free:
	kref_put(&ssi->refs, ssi_free);
	return dev_err_probe(dev, ret, "cannot register SSI transport\n");
}

static void g955n_ssi_remove(struct spi_device *spi)
{
	struct g955n_ssi *ssi = spi_get_drvdata(spi);

	if (probe_legacy_ssp)
		misc_deregister(&ssi->sensor);
	if (expose_legacy_power) {
		device_unregister(ssi->gnss_device);
		device_unregister(ssi->power_device);
		class_destroy(ssi->sec_class);
	}
	if (expose_legacy_stream)
		misc_deregister(&ssi->stream);
	if (expose_legacy_control)
		misc_deregister(&ssi->control);
	if (expose_legacy_patch)
		misc_deregister(&ssi->patch);
	misc_deregister(&ssi->misc);
	ssi_disconnect(ssi);
	ssi_unregister_sensors(ssi);
	free_irq(ssi->irq, ssi);
	kref_put(&ssi->refs, ssi_free);
}

static const struct of_device_id g955n_ssi_of_match[] = {
	{ .compatible = "samsung,g955n-bcm4773-test" },
	{}
};

static const struct spi_device_id g955n_ssi_ids[] = {
	{ "g955n-bcm4773-test" },
	{}
};

static struct spi_driver g955n_ssi_driver = {
	.driver = {
		.name = "g955n-bcm4773-ssi",
		.of_match_table = g955n_ssi_of_match,
	},
	.id_table = g955n_ssi_ids,
	.probe = g955n_ssi_probe,
	.remove = g955n_ssi_remove,
};
module_spi_driver(g955n_ssi_driver);
MODULE_DESCRIPTION("SM-G955N BCM4773 SSI transport");
MODULE_LICENSE("GPL");
