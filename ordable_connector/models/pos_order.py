from odoo import api, models, fields
import logging
import requests

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    ordable_id = fields.Integer(string="ordable_id")
    ordable_tracking_id = fields.Char(string="Ordable Traking ID")

    @api.model
    def create(self, vals):
        # If concept_id is not provided, set default to 9
        if not vals.get('concept_id'):
            vals['concept_id'] = 9
        rec = super(PosOrder, self).create(vals)
        if rec:
            rec.send_order_to_ordable()
        return rec

    def push_orders_to_ordable(self):
        for rec in self:
            rec.send_order_to_ordable()

    def send_order_to_ordable(self):
        brand = self.env['ordable.brand'].search([('concept', '=', self.concept_id.id)])
        if not brand.ordable_api_token:
            _logger.info(f"Skipping brand {brand.name}, no API token")
        else:
            order_payload = self._get_order_payload(brand)
            self._send_order_to_ordable(order_payload, brand)

    def send_orders_to_ordable(self):
        OrdableBrand = self.env['ordable.brand'].sudo()
        OrdableProduct = self.env['ordable.product'].sudo()

        brands = self.env["ordable.brand"].sudo().search([("sync_ordable_info", "=", True)])
        for brand in brands:
            if not brand.ordable_api_token:
                _logger.info(f"Skipping brand {brand.name}, no API token")
                continue
            orders = self.search([('concept_id', '=', brand.concept.id), ('state', '=', 'paid')])

            for order in orders:
                order_payload = order._get_order_payload(brand)
                self._send_order_to_ordable(order_payload, brand)

    def _get_order_payload(self, brand):
        OrdableProduct = self.env['ordable.product'].sudo()

        # Get phone or mobile
        mobile = self.partner_id.phone or self.partner_id.mobile or "12345678"
        # Keep only digits
        mobile_digits_only = ''.join(filter(str.isdigit, mobile))
        # Take last 8 digits
        last_8_mobile_digits = mobile_digits_only[-8:]
        # Add +965
        final_mobile_number = f"+965{last_8_mobile_digits}"

        order_payload = {
            "branchId": brand.branch,
            "status": "Complete",
            "expectedTime": self.date_order.strftime('%Y-%m-%dT%H:%M'),
            "source": "Odoo",
            "orderType": "delivery",
            "deliveryRate": 0,
            "IsAsap": True,
            "paymentComplete": True,
            "paymentMethod": "cash",
            "customer": {
                "name": self.partner_id.name or "Guest",
                "phoneNumber": final_mobile_number,
                "email": self.partner_id.email or ""
            },
            "deliveryAddress": {
                "area": self.partner_id.city or "Area",
                "street": self.partner_id.street or "street"
            },
            "items": [],
            "discounts": []
        }
        # Add items
        for line in self.lines:
            ordable_product = OrdableProduct.search([
                ('name', '=', line.product_id.name),
                ('concept', '=', brand.concept.id)
            ], limit=1)
            if ordable_product:
                order_payload["items"].append({
                    "id": ordable_product.ordable_id,
                    "price": line.price_unit,
                    "quantity": line.qty,
                    "options": []
                })
            else:
                _logger.warning(f"Product {line.product_id.name} not found for brand {brand.name}")

        return order_payload

    def _send_order_to_ordable(self, payload, brand):
        headers = {
            "Authorization": brand.ordable_api_token,
            "Content-Type": "application/json"
        }
        url = f"{brand.ordable_base_url.rstrip('/')}/orders/"
        try:
            response = requests.post(url, json=payload, headers=headers, timeout=30)
            if response.status_code in [200, 201]:
                self.sudo().write({
                    'ordable_id': 1
                })
                _logger.info(f"Order sent successfully for brand {brand.name}")
            else:
                _logger.error(f"Failed to send order for brand {brand.name}: {response.text}")
        except Exception as e:
            _logger.error(f"Exception sending order for brand {brand.name}: {str(e)}")
