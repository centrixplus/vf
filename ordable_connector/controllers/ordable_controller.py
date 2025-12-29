from odoo import http
from odoo.http import request
import logging

_logger = logging.getLogger(__name__)

class OrdableController(http.Controller):

    @http.route('/ordable/sync_products', type='http', auth='user', methods=['GET'], csrf=False)
    def sync_ordable_products(self, **kwargs):
        """
        Trigger the sync_products_from_ordable function manually via GET request.
        """
        try:
            request.env['ordable.product'].sudo().sync_products_from_ordable()
            return "✅ Ordable products sync executed successfully."
        except Exception as e:
            _logger.error(f"❌ Error syncing Ordable products: {str(e)}")
            return f"❌ Error: {str(e)}"

    @http.route('/ordable/sync_options', type='http', auth='user', methods=['GET'], csrf=False)
    def sync_ordable_options(self, **kwargs):
        """
        Trigger the sync_products_from_ordable function manually via GET request.
        """
        try:
            request.env['ordable.product'].sudo().sync_products_from_ordable()
            return "✅ Ordable products sync executed successfully."
        except Exception as e:
            _logger.error(f"❌ Error syncing Ordable products: {str(e)}")
            return f"❌ Error: {str(e)}"

    @http.route('/ordable/sync_orders', type='http', auth='user', methods=['GET'], csrf=False)
    def sync_ordable_orders(self, **kwargs):
        try:
            request.env['pos.order'].sudo().send_orders_to_ordable()
            return "✅ Ordable order sync executed successfully."
        except Exception as e:
            _logger.error(f"❌ Error syncing Ordable order: {str(e)}")
            return f"❌ Error: {str(e)}"


