import logging
import requests
from odoo import api, models, fields, _

_logger = logging.getLogger(__name__)

class OrdableProduct(models.Model):
    _name = "ordable.product"

    name = fields.Char(string="Name")
    concept = fields.Many2one("res.concept", string="Concept")
    ordable_id = fields.Integer(string="ordable_id")

    @api.model
    def sync_products_from_ordable(self):
        brands = self.env["ordable.brand"].search([("sync_ordable_info", "=", True)])

        for brand in brands:
            try:
                _logger.info(f"🔄 Syncing products for brand: {brand.name}")
                headers = {
                    "Authorization": brand.ordable_api_token,
                    "Content-Type": "application/json"
                }
                url = f"{brand.ordable_base_url.rstrip('/')}/products/"
                response = requests.get(url, headers=headers, timeout=60)
                if response.status_code != 200:
                    _logger.warning(f"Failed for {brand.name} - Status {response.status_code}")
                    continue
                data = response.json()
                if not data.get("success"):
                    _logger.warning(f"Invalid response for {brand.name}: {data}")
                    continue
                products = data.get("data", [])
                for prod in products:
                    ordable_id = prod.get("id")
                    name = prod.get("name")
                    existing = self.search([
                        ("concept", "=", brand.concept.id),
                        ("ordable_id", "=", ordable_id)
                    ], limit=1)
                    vals = {
                        "name": name,
                        "concept": brand.concept.id,
                        "ordable_id": ordable_id,
                    }

                    if existing:
                        existing.write(vals)
                        _logger.info(f"✅ Updated product {name} ({ordable_id}) for {brand.name}")
                    else:
                        self.create(vals)
                        _logger.info(f"🆕 Created product {name} ({ordable_id}) for {brand.name}")
            except Exception as e:
                _logger.error(f"❌ Error syncing brand {brand.name}: {str(e)}")