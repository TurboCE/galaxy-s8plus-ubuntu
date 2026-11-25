// SPDX-License-Identifier: GPL-2.0-only
/* BCM4773 half-duplex SSI transport for the SM-G955N. */
#include <linux/delay.h>
#include <linux/fs.h>
#include <linux/gpio/consumer.h>
#include <linux/interrupt.h>
#include <linux/iopoll.h>
#include <linux/kref.h>
#include <linux/miscdevice.h>
#include <linux/module.h>
#include <linux/of.h>
#include <linux/poll.h>
#include <linux/regulator/consumer.h>
#include <linux/slab.h>
#include <linux/spi/spi.h>
#include <linux/uaccess.h>

#define SSI_WRITE	0x00
#define SSI_READ	0x20
#define SSI_HEADER	2
#define SSI_PAYLOAD	254

struct g955n_ssi {
	struct kref refs;
	struct mutex lock;
	wait_queue_head_t wait;
	struct miscdevice misc;
	struct spi_device *spi;
	struct regulator *supply;
	struct gpio_desc *request;
	struct gpio_desc *response;
	struct gpio_desc *host;
	struct gpio_desc *enable;
	int enable_direction, enable_value;
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

	wake_up_interruptible(&ssi->wait);
	return IRQ_HANDLED;
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

static int ssi_receive(struct g955n_ssi *ssi)
{
	size_t length;
	int ret;

	ret = ssi_wake(ssi);
	if (ret)
		return ret;
	memset(ssi->tx, 0, SSI_HEADER + SSI_PAYLOAD);
	ssi->tx[0] = SSI_READ;
	ret = ssi_transfer(ssi, SSI_HEADER);
	if (ret)
		goto sleep;
	if (ssi->rx[0]) {
		ret = -EPROTO;
		goto sleep;
	}

	length = min_t(size_t, ssi->rx[1] ?: SSI_PAYLOAD, SSI_PAYLOAD);
	ret = ssi_transfer(ssi, SSI_HEADER + length);
	if (ret)
		goto sleep;
	if (ssi->rx[0]) {
		ret = -EPROTO;
		goto sleep;
	}
	ssi->pending = min_t(size_t, ssi->rx[1], length);
	if (!ssi->pending)
		ret = -ENODATA;

sleep:
	gpiod_set_value_cansleep(ssi->request, 0);
	return ret;
}

static int ssi_restore_enable(struct g955n_ssi *ssi)
{
	if (!ssi->enable)
		return 0;
	if (ssi->enable_direction)
		return gpiod_direction_input(ssi->enable);
	return gpiod_direction_output(ssi->enable, ssi->enable_value);
}

static int ssi_power_on(struct g955n_ssi *ssi)
{
	int ret, restore;

	if (ssi->enable) {
		ret = gpiod_get_direction(ssi->enable);
		if (ret < 0)
			return ret;
		ssi->enable_direction = ret;
		if (!ret) {
			ret = gpiod_get_value_cansleep(ssi->enable);
			if (ret < 0)
				return ret;
			ssi->enable_value = ret;
		}
	}
	ret = regulator_enable(ssi->supply);
	if (ret)
		return ret;
	ssi->powered = true;
	if (!ssi->enable)
		return 0;

	ret = gpiod_direction_output(ssi->enable, 1);
	if (!ret) {
		restore = gpiod_get_value_cansleep(ssi->enable);
		if (restore == 1)
			return 0;
		ret = restore < 0 ? restore : -EIO;
	}
	restore = ssi_restore_enable(ssi);
	if (restore)
		dev_err(&ssi->spi->dev, "cannot restore hub enable: %d\n", restore);
	if (!regulator_disable(ssi->supply))
		ssi->powered = false;
	return ret;
}

static int ssi_power_off(struct g955n_ssi *ssi)
{
	int restore = ssi_restore_enable(ssi);
	int ret = regulator_disable(ssi->supply);

	if (!ret)
		ssi->powered = false;
	return restore ?: ret;
}

static int ssi_open(struct inode *inode, struct file *file)
{
	struct g955n_ssi *ssi = container_of(file->private_data,
					   struct g955n_ssi, misc);
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
	if (ssi->powered) {
		ret = -EIO;
		goto out;
	}
	ret = ssi_power_on(ssi);
	if (ret)
		goto out;

	msleep(200);
	ssi->opened = true;
	ssi->pending = 0;
	kref_get(&ssi->refs);
	file->private_data = ssi;
	enable_irq(ssi->irq);
out:
	mutex_unlock(&ssi->lock);
	return ret;
}

static int ssi_release(struct inode *inode, struct file *file)
{
	struct g955n_ssi *ssi = file->private_data;
	int ret = 0;

	mutex_lock(&ssi->lock);
	if (!ssi->removed) {
		disable_irq(ssi->irq);
		ret = ssi_power_off(ssi);
	}
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

static int g955n_ssi_probe(struct spi_device *spi)
{
	struct device *dev = &spi->dev;
	struct g955n_ssi *ssi;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks") ||
	    (spi->mode & (SPI_CPOL | SPI_CPHA)) != SPI_MODE_3)
		return -ENODEV;

	ssi = kzalloc(sizeof(*ssi), GFP_KERNEL);
	if (!ssi)
		return -ENOMEM;
	kref_init(&ssi->refs);
	mutex_init(&ssi->lock);
	init_waitqueue_head(&ssi->wait);
	ssi->spi = spi;
	ssi->tx = devm_kzalloc(dev, SSI_HEADER + SSI_PAYLOAD, GFP_KERNEL);
	ssi->rx = devm_kzalloc(dev, SSI_HEADER + SSI_PAYLOAD, GFP_KERNEL);
	ret = -ENOMEM;
	if (!ssi->tx || !ssi->rx)
		goto free;

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
	if (!ret) {
		spi_set_drvdata(spi, ssi);
		return 0;
	}
	free_irq(ssi->irq, ssi);
free:
	kref_put(&ssi->refs, ssi_free);
	return dev_err_probe(dev, ret, "cannot register SSI transport\n");
}

static void g955n_ssi_remove(struct spi_device *spi)
{
	struct g955n_ssi *ssi = spi_get_drvdata(spi);

	misc_deregister(&ssi->misc);
	mutex_lock(&ssi->lock);
	ssi->removed = true;
	if (ssi->opened)
		disable_irq(ssi->irq);
	if (ssi->powered && ssi_power_off(ssi))
		dev_err(&spi->dev, "cannot restore hub power on removal\n");
	mutex_unlock(&ssi->lock);
	free_irq(ssi->irq, ssi);
	wake_up_interruptible(&ssi->wait);
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
