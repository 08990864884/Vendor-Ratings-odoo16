from odoo import fields, models


class PurchaseVendorRatingReport(models.Model):
    _name = "purchase.vendor.rating.report"
    _description = "Purchase Vendor Rating"
    _auto = False
    _rec_name = "partner_id"
    _order = "score desc, partner_id, product_id"

    partner_id = fields.Many2one("res.partner", string="Vendor", readonly=True)
    product_id = fields.Many2one("product.product", string="Product", readonly=True)
    product_tmpl_id = fields.Many2one(
        "product.template", string="Product Template", readonly=True
    )
    category_id = fields.Many2one(
        "product.category", string="Product Category", readonly=True
    )
    company_id = fields.Many2one("res.company", string="Company", readonly=True)
    currency_id = fields.Many2one("res.currency", string="Currency", readonly=True)
    purchase_count = fields.Integer(string="Purchases", readonly=True)
    received_count = fields.Integer(string="Received Purchases", readonly=True)
    last_purchase_date = fields.Datetime(string="Last Purchase", readonly=True)
    last_order_id = fields.Many2one(
        "purchase.order", string="Last Purchase Order", readonly=True
    )
    average_delivery_days = fields.Float(
        string="Average Delivery Days",
        digits=(16, 2),
        readonly=True,
        group_operator="avg",
        help="Average days from PO confirmation to the completed receipt.",
    )
    average_delay_days = fields.Float(
        string="Average Delay Days",
        digits=(16, 2),
        readonly=True,
        group_operator="avg",
        help="Average late days against the scheduled delivery date.",
    )
    on_time_rate = fields.Float(
        string="On-Time Rate (%)",
        digits=(16, 2),
        readonly=True,
        group_operator="avg",
    )
    last_purchase_price = fields.Monetary(
        string="Last Purchase Price", currency_field="currency_id", readonly=True
    )
    previous_purchase_price = fields.Monetary(
        string="Previous Purchase Price", currency_field="currency_id", readonly=True
    )
    price_change_percent = fields.Float(
        string="Price Change (%)",
        digits=(16, 2),
        readonly=True,
        group_operator="avg",
    )
    delivery_score = fields.Float(
        string="Delivery Score", digits=(16, 2), readonly=True, group_operator="avg"
    )
    price_score = fields.Float(
        string="Price Score", digits=(16, 2), readonly=True, group_operator="avg"
    )
    score = fields.Float(
        string="Total Score", digits=(16, 2), readonly=True, group_operator="avg"
    )
    grade = fields.Selection(
        [
            ("a_plus", "A+"),
            ("a", "A"),
            ("b_plus", "B+"),
            ("b", "B"),
            ("c_plus", "C+"),
            ("c", "C"),
            ("d", "D"),
            ("f", "F"),
        ],
        string="Grade",
        readonly=True,
    )

    @property
    def _table_query(self):
        return """
            WITH receipt_data AS (
                SELECT
                    sm.purchase_line_id,
                    MAX(sp.date_done) AS receipt_date
                FROM stock_move sm
                JOIN stock_picking sp ON sp.id = sm.picking_id
                JOIN stock_picking_type spt ON spt.id = sp.picking_type_id
                WHERE
                    sm.purchase_line_id IS NOT NULL
                    AND sm.state = 'done'
                    AND sp.state = 'done'
                    AND spt.code = 'incoming'
                GROUP BY sm.purchase_line_id
            ),
            purchase_lines AS (
                SELECT
                    pol.id,
                    po.partner_id,
                    pol.product_id,
                    pp.product_tmpl_id,
                    pt.categ_id AS category_id,
                    po.company_id,
                    company.currency_id,
                    po.id AS order_id,
                    po.date_order,
                    COALESCE(po.date_approve, po.date_order) AS confirmation_date,
                    pol.date_planned,
                    receipt.receipt_date,
                    pol.price_unit / NULLIF(COALESCE(po.currency_rate, 1.0), 0.0)
                        AS company_price,
                    ROW_NUMBER() OVER (
                        PARTITION BY po.partner_id, pol.product_id, po.company_id
                        ORDER BY po.date_order DESC, pol.id DESC
                    ) AS purchase_rank
                FROM purchase_order_line pol
                JOIN purchase_order po ON po.id = pol.order_id
                JOIN product_product pp ON pp.id = pol.product_id
                JOIN product_template pt ON pt.id = pp.product_tmpl_id
                JOIN res_company company ON company.id = po.company_id
                LEFT JOIN receipt_data receipt ON receipt.purchase_line_id = pol.id
                WHERE
                    pol.display_type IS NULL
                    AND pol.product_id IS NOT NULL
                    AND po.state IN ('purchase', 'done')
            ),
            vendor_product_stats AS (
                SELECT
                    MIN(id) AS id,
                    partner_id,
                    product_id,
                    product_tmpl_id,
                    category_id,
                    company_id,
                    currency_id,
                    COUNT(*) AS purchase_count,
                    COUNT(receipt_date) AS received_count,
                    MAX(date_order) AS last_purchase_date,
                    MAX(order_id) FILTER (WHERE purchase_rank = 1) AS last_order_id,
                    AVG(
                        EXTRACT(EPOCH FROM (receipt_date - confirmation_date))
                        / 86400.0
                    ) FILTER (WHERE receipt_date IS NOT NULL)
                        AS average_delivery_days,
                    AVG(
                        GREATEST(
                            EXTRACT(EPOCH FROM (receipt_date - date_planned))
                            / 86400.0,
                            0.0
                        )
                    ) FILTER (WHERE receipt_date IS NOT NULL)
                        AS average_delay_days,
                    100.0 * COUNT(*) FILTER (
                        WHERE receipt_date IS NOT NULL
                        AND receipt_date <= date_planned
                    ) / NULLIF(COUNT(receipt_date), 0) AS on_time_rate,
                    MAX(company_price) FILTER (WHERE purchase_rank = 1)
                        AS last_purchase_price,
                    MAX(company_price) FILTER (WHERE purchase_rank = 2)
                        AS previous_purchase_price
                FROM purchase_lines
                GROUP BY
                    partner_id,
                    product_id,
                    product_tmpl_id,
                    category_id,
                    company_id,
                    currency_id
            ),
            calculated AS (
                SELECT
                    stats.*,
                    CASE
                        WHEN previous_purchase_price IS NULL
                            OR previous_purchase_price = 0 THEN 0.0
                        ELSE
                            100.0
                            * (last_purchase_price - previous_purchase_price)
                            / previous_purchase_price
                    END AS price_change_percent,
                    CASE
                        WHEN received_count = 0 THEN 0.0
                        WHEN COALESCE(average_delay_days, 0.0) <= 0 THEN 100.0
                        WHEN average_delay_days <= 1 THEN 90.0
                        WHEN average_delay_days <= 3 THEN 75.0
                        WHEN average_delay_days <= 7 THEN 55.0
                        WHEN average_delay_days <= 14 THEN 35.0
                        ELSE 10.0
                    END AS delivery_score,
                    CASE
                        WHEN previous_purchase_price IS NULL
                            OR previous_purchase_price = 0 THEN 75.0
                        WHEN last_purchase_price <= previous_purchase_price * 0.95
                            THEN 100.0
                        WHEN last_purchase_price <= previous_purchase_price
                            THEN 90.0
                        WHEN last_purchase_price <= previous_purchase_price * 1.05
                            THEN 75.0
                        WHEN last_purchase_price <= previous_purchase_price * 1.10
                            THEN 55.0
                        WHEN last_purchase_price <= previous_purchase_price * 1.20
                            THEN 35.0
                        ELSE 10.0
                    END AS price_score
                FROM vendor_product_stats stats
            ),
            scored AS (
                SELECT
                    calculated.*,
                    delivery_score * 0.60 + price_score * 0.40 AS score
                FROM calculated
            )
            SELECT
                scored.*,
                CASE
                    WHEN score >= 95 THEN 'a_plus'
                    WHEN score >= 90 THEN 'a'
                    WHEN score >= 85 THEN 'b_plus'
                    WHEN score >= 80 THEN 'b'
                    WHEN score >= 75 THEN 'c_plus'
                    WHEN score >= 70 THEN 'c'
                    WHEN score >= 60 THEN 'd'
                    ELSE 'f'
                END AS grade
            FROM scored
        """
