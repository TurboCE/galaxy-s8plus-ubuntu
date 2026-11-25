// SPDX-License-Identifier: GPL-2.0-only
/* Normal-mode NCI I2C transport for the SM-G955N S3NRN82. */
#include <linux/interrupt.h>
#include <linux/module.h>
#include <linux/of.h>
#include <net/nfc/nci_core.h>

#include "g955n-nfc-hw.h"

struct g955n_nci {
	struct g955n_nfc hw;
	struct nci_dev *ndev;
	bool irq_enabled;
	int irq;
};

static int g955n_nci_open(struct nci_dev *ndev)
{
	struct g955n_nci *nfc = nci_get_drvdata(ndev);

	/* The IRQ remains masked until the controller accepts a command. */
	return g955n_nfc_power_on(&nfc->hw, true);
}

static int g955n_nci_close(struct nci_dev *ndev)
{
	struct g955n_nci *nfc = nci_get_drvdata(ndev);

	mutex_lock(&nfc->hw.lock);
	if (nfc->irq_enabled) {
		nfc->irq_enabled = false;
		disable_irq_nosync(nfc->irq);
	}
	mutex_unlock(&nfc->hw.lock);
	synchronize_irq(nfc->irq);
	return g955n_nfc_power_off(&nfc->hw);
}

static int g955n_nci_send(struct nci_dev *ndev, struct sk_buff *skb)
{
	struct g955n_nci *nfc = nci_get_drvdata(ndev);
	unsigned int bytes = skb->len;
	int ret;

	mutex_lock(&nfc->hw.lock);
	ret = i2c_master_send(nfc->hw.client, skb->data, bytes);
	if (ret == bytes && !nfc->irq_enabled) {
		nfc->irq_enabled = true;
		enable_irq(nfc->irq);
	}
	mutex_unlock(&nfc->hw.lock);
	consume_skb(skb);

	if (ret != bytes) {
		dev_err_ratelimited(&nfc->hw.client->dev,
				    "NCI write returned %d for %u bytes\n", ret, bytes);
		return ret < 0 ? ret : -EIO;
	}
	return 0;
}

static irqreturn_t g955n_nci_irq(int irq, void *data)
{
	struct g955n_nci *nfc = data;
	u8 header[NCI_HEADER_BYTES], payload[U8_MAX];
	struct sk_buff *skb;
	int ret;

	mutex_lock(&nfc->hw.lock);
	if (!nfc->irq_enabled) {
		mutex_unlock(&nfc->hw.lock);
		return IRQ_HANDLED;
	}

	ret = gpiod_get_value_cansleep(nfc->hw.ready);
	if (ret > 0)
		ret = g955n_read_nci_frame(&nfc->hw, header, payload);
	else if (!ret) {
		mutex_unlock(&nfc->hw.lock);
		return IRQ_HANDLED;
	}
	if (ret) {
		nfc->irq_enabled = false;
		disable_irq_nosync(irq);
	}
	mutex_unlock(&nfc->hw.lock);
	if (ret) {
		dev_err_ratelimited(&nfc->hw.client->dev, "NCI receive failed: %d\n", ret);
		return IRQ_HANDLED;
	}

	skb = alloc_skb(sizeof(header) + header[2], GFP_KERNEL);
	if (!skb)
		return IRQ_HANDLED;
	skb_put_data(skb, header, sizeof(header));
	skb_put_data(skb, payload, header[2]);
	nci_recv_frame(nfc->ndev, skb);
	return IRQ_HANDLED;
}

static const struct nci_ops g955n_nci_ops = {
	.open = g955n_nci_open,
	.close = g955n_nci_close,
	.send = g955n_nci_send,
};

static int g955n_nci_probe(struct i2c_client *client)
{
	const u32 protocols = NFC_PROTO_JEWEL_MASK | NFC_PROTO_MIFARE_MASK |
		NFC_PROTO_FELICA_MASK | NFC_PROTO_ISO14443_MASK | NFC_PROTO_ISO14443_B_MASK |
		NFC_PROTO_NFC_DEP_MASK | NFC_PROTO_ISO15693_MASK;
	struct device *dev = &client->dev;
	struct g955n_nci *nfc;
	int ret;

	if (!of_machine_is_compatible("samsung,dream2lteks") || client->addr != 0x27)
		return -ENODEV;
	if (!i2c_check_functionality(client->adapter, I2C_FUNC_I2C))
		return -EOPNOTSUPP;

	nfc = devm_kzalloc(dev, sizeof(*nfc), GFP_KERNEL);
	if (!nfc)
		return -ENOMEM;
	ret = g955n_nfc_get_resources(client, &nfc->hw);
	if (ret)
		return ret;

	nfc->irq = gpiod_to_irq(nfc->hw.ready);
	if (nfc->irq < 0)
		return dev_err_probe(dev, nfc->irq, "NFC IRQ unavailable\n");

	/* READY stays high when another frame is pending. */
	ret = devm_request_threaded_irq(dev, nfc->irq, NULL, g955n_nci_irq,
					IRQF_TRIGGER_HIGH | IRQF_ONESHOT | IRQF_NO_AUTOEN,
					dev_name(dev), nfc);
	if (ret)
		return dev_err_probe(dev, ret, "cannot request NFC IRQ\n");

	nfc->ndev = nci_allocate_device(&g955n_nci_ops, protocols, 0, 0);
	if (!nfc->ndev)
		return -ENOMEM;
	nci_set_parent_dev(nfc->ndev, dev);
	nci_set_drvdata(nfc->ndev, nfc);
	i2c_set_clientdata(client, nfc);

	ret = nci_register_device(nfc->ndev);
	if (ret)
		nci_free_device(nfc->ndev);
	return ret;
}

static void g955n_nci_remove(struct i2c_client *client)
{
	struct g955n_nci *nfc = i2c_get_clientdata(client);

	nci_unregister_device(nfc->ndev);
	nci_free_device(nfc->ndev);
}

static const struct of_device_id g955n_nci_match[] = {
	{ .compatible = "samsung,sm-g955n-s3nrn82" },
	{ }
};
MODULE_DEVICE_TABLE(of, g955n_nci_match);

static struct i2c_driver g955n_nci_driver = {
	.driver = {
		.name = "g955n-s3nrn82",
		.of_match_table = g955n_nci_match,
	},
	.probe = g955n_nci_probe,
	.remove = g955n_nci_remove,
};
module_i2c_driver(g955n_nci_driver);

MODULE_DESCRIPTION("SM-G955N S3NRN82 NCI transport");
MODULE_LICENSE("GPL");
