{
    "name": "Purchase Vendor Rating Report",
    "version": "16.0.1.0.0",
    "category": "Purchases",
    "author": "Abdurrachman Basurroh",
    "summary": "Penilaian vendor berdasarkan pengiriman dan harga pembelian",
    "license": "LGPL-3",
    "images": ["static/description/cover.png"],
    "depends": ["purchase_stock"],
    "data": [
        "security/ir.model.access.csv",
        "security/vendor_rating_security.xml",
        "views/vendor_rating_report_views.xml",
    ],
    "price": 10.00,
    "currency": "USD",
    "installable": True,
    "application": False,
}
