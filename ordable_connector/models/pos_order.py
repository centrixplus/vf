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

        # Check if sync is enabled for this brand
        if not brand.sync_ordable_info:
            _logger.info(f"Skipping brand {brand.name}, sync_ordable_info is disabled")
            return

        # Check if order already has ordable_id (already synced)
        if self.ordable_id:
            _logger.info(f"Skipping order {self.id}, already synced to Ordable with ordable_id: {self.ordable_id}")
            return

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

    # ============================================
    # ORDABLE STATUS MAPPING - API INTEGRATION
    # Added: 2026-02-09
    # Purpose: Update Ordable status when POS order stage changes
    # Can be safely removed if reverting
    # ============================================

    def write(self, vals):
        """Override to trigger Ordable status update when stage changes"""
        result = super(PosOrder, self).write(vals)

        # Only proceed if order_stage_id was changed
        if 'order_stage_id' in vals:
            for order in self:
                # Update Ordable status via API
                order._update_ordable_status()

        return result

    def _update_ordable_status(self):
        """
        Update order status in Ordable API when stage changes.
        Only calls API if all conditions are met.
        """
        # STEP 1: Check if order is synced with Ordable
        if not (self.ordable_id or self.ordable_tracking_id):
            _logger.debug(f"Order {self.name}: Not synced with Ordable (no ordable_id or ordable_tracking_id)")
            return

        # STEP 2: Check if order has a stage
        if not self.order_stage_id:
            _logger.debug(f"Order {self.name}: No order stage set")
            return

        # STEP 3: Get Ordable status from mapping
        ordable_status = self._get_ordable_status_for_stage(self.order_stage_id.id)
        if not ordable_status:
            _logger.info(
                f"Order {self.name}: Stage '{self.order_stage_id.name}' has no Ordable mapping. Skipping API call."
            )
            return  # No mapping = No API call

        # STEP 4: Check if order has concept
        if not self.concept_id:
            _logger.debug(f"Order {self.name}: No concept assigned")
            return

        # STEP 5: Get brand configuration from concept
        brand = self.env['ordable.brand'].search([
            ('concept', '=', self.concept_id.id),
            ('sync_ordable_info', '=', True)
        ], limit=1)

        if not brand:
            _logger.info(f"Order {self.name}: No active Ordable brand for concept '{self.concept_id.name}'")
            return

        if not brand.ordable_api_token or not brand.ordable_base_url:
            _logger.warning(f"Order {self.name}: Missing API credentials for brand '{brand.name}'")
            return

        # STEP 6: All checks passed - Call API
        _logger.info(
            f"Order {self.name}: Updating Ordable status to '{ordable_status}' for stage '{self.order_stage_id.name}'"
        )
        self._call_ordable_status_api(ordable_status, brand)

    def _get_ordable_status_for_stage(self, stage_id):
        """
        Get mapped Ordable status for given POS stage.
        Returns False if no mapping exists or mapping is inactive.
        """
        if not stage_id:
            return False

        mapping = self.env['ordable.status.map'].search([
            ('pos_stage_id', '=', stage_id),
            ('active', '=', True)
        ], limit=1)

        if mapping:
            _logger.debug(f"Found mapping: Stage '{mapping.pos_stage_id.name}' → Ordable '{mapping.ordable_status}'")
            return mapping.ordable_status
        else:
            return False

    def _build_ordable_status_payload(self, ordable_status):
        """
        Build API payload for status update.
        Determines reference type (enable_id or tracking_id) based on available data.
        """
        if self.ordable_id:
            order_id = str(self.ordable_id)
            reference_by = 'order_id'
        else:
            order_id = self.ordable_tracking_id
            reference_by = 'tracking_id'

        payload = {
            "order_id": order_id,
            "reference_by": reference_by,
            "status": ordable_status
        }

        _logger.debug(f"Built Ordable payload: {payload}")
        return payload

    def _call_ordable_status_api(self, ordable_status, brand):
        """
        Call Ordable API to update order status.
        Handles request/response and logs results.
        """
        # Build payload
        payload = self._build_ordable_status_payload(ordable_status)

        # Prepare API call
        url = f"{brand.ordable_base_url.rstrip('/')}/order_status/"
        headers = {
            'Authorization': brand.ordable_api_token,
            'Content-Type': 'application/json',
            'Accept': 'application/json'
        }

        try:
            _logger.info(f"Calling Ordable API: {url}")
            _logger.debug(f"Payload: {payload}")

            response = requests.patch(url, json=payload, headers=headers, timeout=10)
            if response.status_code in [200, 201]:
                _logger.info(
                    f"Order {self.name}: Ordable status updated successfully. "
                    f"Response: {response.text}"
                )
            else:
                error_msg = f"API returned {response.status_code}: {response.text}"
                _logger.error(f"Order {self.name}: Ordable API error - {error_msg}")

        except requests.exceptions.Timeout:
            error_msg = "API request timeout (10s)"
            _logger.error(f"Order {self.name}: {error_msg}")

        except requests.exceptions.ConnectionError as e:
            error_msg = f"Connection error: {str(e)}"
            _logger.error(f"Order {self.name}: {error_msg}")

        except Exception as e:
            error_msg = f"Unexpected error: {str(e)}"
            _logger.error(f"Order {self.name}: {error_msg}")

    # END ORDABLE STATUS MAPPING - API INTEGRATION
    # ============================================
