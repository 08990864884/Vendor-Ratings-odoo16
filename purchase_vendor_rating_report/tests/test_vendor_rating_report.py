from odoo.tests.common import TransactionCase


class TestPurchaseVendorRatingReport(TransactionCase):

    @classmethod
    def setUpClass(cls):
        super().setUpClass()
        cls.vendor = cls.env["res.partner"].create(
            {"name": "Vendor Rating Test", "supplier_rank": 1}
        )
        cls.product = cls.env["product.product"].search(
            [
                ("purchase_ok", "=", True),
                ("detailed_type", "=", "product"),
            ],
            limit=1,
        )
        if not cls.product:
            cls.product = cls.env.ref("product.product_product_8")

    def _create_purchase(self, price):
        order = self.env["purchase.order"].create(
            {
                "partner_id": self.vendor.id,
                "order_line": [
                    (
                        0,
                        0,
                        {
                            "product_id": self.product.id,
                            "name": self.product.display_name,
                            "product_qty": 1,
                            "product_uom": self.product.uom_po_id.id,
                            "price_unit": price,
                            "date_planned": "2026-06-20 00:00:00",
                        },
                    )
                ],
            }
        )
        order.button_confirm()
        return order

    def test_rating_uses_latest_and_previous_price(self):
        self._create_purchase(100)
        latest = self._create_purchase(90)
        latest.write({"date_order": "2026-06-10 00:00:00"})
        self.env.flush_all()

        rating = self.env["purchase.vendor.rating.report"].search(
            [
                ("partner_id", "=", self.vendor.id),
                ("product_id", "=", self.product.id),
            ]
        )

        self.assertEqual(len(rating), 1)
        self.assertEqual(rating.purchase_count, 2)
        self.assertAlmostEqual(rating.last_purchase_price, 90)
        self.assertAlmostEqual(rating.previous_purchase_price, 100)
        self.assertAlmostEqual(rating.price_change_percent, -10)
        self.assertEqual(rating.price_score, 100)
