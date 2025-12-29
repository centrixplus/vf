from odoo import http
from odoo.http import request, Response
from datetime import datetime
import requests
import json
import logging
from odoo.exceptions import AccessError
import re
_logger = logging.getLogger(__name__)


class OrderController(http.Controller):

    def create_order(self, payment_data, brand):
        tracking_id = payment_data.get('tracking_id')
        api_token = brand.ordable_api_token
        base_url = brand.ordable_base_url
        url = f"{base_url}/orders?tracking_id={tracking_id}"
        headers = {
            'Authorization': api_token
        }
        try:
            response = requests.request("GET", url, headers=headers)
            response_data = response.json()
            if (response_data.get('success')):
                orders_data = response_data.get('data')
                _logger.info(f"Order data retrieved successfully from Ordable with ID {tracking_id}.")
                self.create_odoo_order(orders_data, payment_data, brand)
            else:
                _logger.error(f"Failed to retrieve Order data '{tracking_id}' from Ordable.")
        except requests.exceptions.RequestException as e:
            _logger.error(f"Failed to retrieve Order data '{tracking_id}' from Ordable: {e}")

    def create_odoo_order(self, orders_data, payments_data, brand):
        try:
            for order_data in orders_data:
                phone = order_data.get('phone', '').strip()
                normalized_phone = re.sub(r'^\+965', '', phone)
                partner = request.env['res.partner'].sudo().search([
                    '|', '|', '|',
                    ('phone', '=', phone),
                    ('mobile', '=', phone),
                    ('phone', '=', normalized_phone),
                    ('mobile', '=', normalized_phone)
                ], limit=1)
                if not partner:
                    partner = request.env['res.partner'].sudo().create({
                        'name': order_data['customer_name'],
                        'phone': order_data['phone'],
                    })
                    _logger.info(f"Created new partner: {partner.name} with phone {partner.phone}")
                if brand.ordable_brand == "pos":
                    self.create_pos_order(order_data, payments_data, partner, brand)
                else:
                    self.create_sale_order(order_data, payments_data, partner, brand)
            return {'success': True, 'message': "Order Created Successfully."}

        except Exception as e:
            _logger.error(f"Error in creating sale orders: {str(e)}")
            return {'success': False, 'message': str(e)}

    def create_sale_order(self, order_data, payments_data, partner, brand):
        sale_order_vals = {
            'partner_id': partner.id,
            'ordable_id': order_data['id'],
            'ordable_tracking_id': order_data['tracking_id'],
            'user_id': 1,
            'company_id': 1,
        }
        sale_order = request.env['sale.order'].sudo().create(sale_order_vals)
        for item in order_data.get('items', []):
            product = request.env['product.product'].sudo().search([
                ('name', '=', item['name'])
            ], limit=1)
            if not product:
                product_template = request.env['product.template'].sudo().create({
                    'name': item['name'],
                    'list_price': item['price'],
                    'categ_id': 1
                })
                product = product_template.product_variant_id

            request.env['sale.order.line'].sudo().create({
                'order_id': sale_order.id,
                'product_id': product.id,
                'product_uom_qty': item['quantity'],
                'price_unit': item['price'],
            })

            # Optionally, create a separate line for each option (if each adds to total)
            for option in item.get('options', []):
                option_product = request.env['product.product'].sudo().search([
                    ('name', '=', option['name'])
                ], limit=1)
                if not option_product:
                    option_template = request.env['product.template'].sudo().create({
                        'name': option['name'],
                        'list_price': option['price'],
                        'categ_id': 1
                    })
                    option_product = option_template.product_variant_id

                request.env['sale.order.line'].sudo().create({
                    'order_id': sale_order.id,
                    'product_id': option_product.id,
                    'product_uom_qty': option['quantity'],
                    'price_unit': option['price'],
                })
        _logger.info(f"Sale Order created with ID: {sale_order.id}")

        # Confirm the Sale Order
        try:
            sale_order.action_confirm()
            _logger.info("Sale Order Confirmed with ID: %s", sale_order.id)
        except Exception as e:
            _logger.exception("Failed to confirm Sale Order ID %s: %s", sale_order.id, e)

        return {'success': True, 'sale_order_id': sale_order.id}


    def create_pos_order(self, order_data, payments_data, partner, brand):
        # 1. SESSION, COMPANY, AND TAX ACQUISITION
        pos_session = request.env['pos.session'].sudo().search([
            ('state', '=', 'opened'),
            ('config_id.name', '=', 'Call Center')
        ], limit=1)

        if not pos_session:
            _logger.error("No active POS session found.")
            return {'success': False, 'error': 'No active POS session found.'}

        company_id = pos_session.config_id.company_id.id

        # CRITICAL FIX 1: Find the 0% Sales Tax Record
        # This record is mandatory for Odoo's calculation logic to run, even if tax amount is 0.
        zero_tax = request.env['account.tax'].sudo().search([
            ('company_id', '=', company_id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 0.0)
        ], limit=1)

        tax_ids_to_use = zero_tax.ids if zero_tax else []

        if not zero_tax:
            _logger.warning(f"No 0% Sales Tax record found for company ID {company_id}.")

        # 2. POS ORDER CREATION
        pos_order_vals = {
            'partner_id': partner.id,
            'session_id': pos_session.id,
            'user_id': pos_session.user_id.id,
            'company_id': company_id,
            'pricelist_id': pos_session.config_id.pricelist_id.id,
            'fiscal_position_id': partner.property_account_position_id.id or False,
            'ordable_id': order_data.get('id'),
            'ordable_tracking_id': order_data.get('tracking_id'),
            'concept_id': brand.concept.id,
            'amount_tax': 0.0,
            'amount_total': order_data.get('total'),
            'amount_paid': order_data.get('total'),
            'amount_return': 0.0
        }
        pos_order = request.env['pos.order'].sudo().create(pos_order_vals)
        _logger.info(f"Order reference: {pos_order.pos_reference}")
        # 3. ORDER LINE CREATION (Finalized with all manual computed fields)
        for item in order_data.get('items', []):
            product = request.env['product.product'].sudo().search([
                ('name', '=', item['name']),
                ('product_tmpl_id.concept_ids', 'in', brand.concept.id)
            ], limit=1)

            # Product Creation Logic (Ensures product exists)
            if not product:
                product_template = request.env['product.template'].sudo().create({
                    'name': item['name'],
                    'list_price': item['price'],
                    'categ_id': 1,
                    'concept_ids': [(6, 0, [brand.concept.id])],
                    'taxes_id': [(6, 0, tax_ids_to_use)],  # Link 0% tax to new product
                })
                product = product_template.product_variant_id

            unit_price = item.get('price', 0)
            quantity = item.get('quantity', 1)

            # Manually calculate subtotal (since tax is 0% in Kuwait)
            subtotal = unit_price * quantity

            request.env['pos.order.line'].sudo().create({
                'order_id': pos_order.id,
                'product_id': product.id,
                'qty': quantity,
                'price_unit': unit_price,
                'price_subtotal': subtotal,
                'price_subtotal_incl': subtotal,
                'tax_ids': [(6, 0, tax_ids_to_use)],
                'full_product_name': product.display_name,
            })

            # Optional: create separate lines for each option
            for option in item.get('options', []):
                option_product = request.env['product.product'].sudo().search([
                    ('name', '=', option['name']),
                    ('product_tmpl_id.concept_ids', 'in', brand.concept.id)
                ], limit=1)

                if not option_product:
                    option_template = request.env['product.template'].sudo().create({
                        'name': option['name'],
                        'list_price': option['price'],
                        'categ_id': 1,
                        'concept_ids': [(6, 0, [brand.concept.id])],
                        'taxes_id': [(6, 0, tax_ids_to_use)],
                    })
                    option_product = option_template.product_variant_id

                option_qty = option.get('quantity', 1)
                option_price = option.get('price', 0)
                option_subtotal = option_qty * option_price

                request.env['pos.order.line'].sudo().create({
                    'order_id': pos_order.id,
                    'product_id': option_product.id,
                    'qty': option_qty,
                    'price_unit': option_price,
                    'price_subtotal': option_subtotal,
                    'price_subtotal_incl': option_subtotal,
                    'tax_ids': [(6, 0, tax_ids_to_use)],
                    'full_product_name': f"{product.display_name} - {option['name']}",
                })
        # 4. PAYMENT CREATION AND VALIDATION
        for payment in payments_data.get('payments', []):
            payment_method_name = payment.get('payment_method')
            payment_amount = payment.get('amount')

            if not payment_method_name or payment_amount is None:
                _logger.warning("Payment entry is missing method or amount. Skipping.")
                continue

            payment_method = request.env['pos.payment.method'].sudo().search([
                ('name', 'ilike', payment_method_name)
            ], limit=1)

            if not payment_method:
                _logger.warning(f"Payment method '{payment_method_name}' not found. Skipping payment.")
                continue

            if not payment_method:
                _logger.warning(f"Payment method '{payment_method_name}' not found. Skipping payment.")
                continue
            try:

                payment_vals = {
                    'amount': payment_amount,
                    'payment_method_id': payment_method.id,
                    'pos_order_id': pos_order.id,
                    'name': f"{payment_method_name} Ref: {payment.get('payment_reference', '')}",
                }

                request.env['pos.payment'].sudo().create(payment_vals)
            except Exception as e:
                _logger.exception(f"Failed to add payment to POS order ID {pos_order.id}: {e}")
        # Final validation
        try:
            pos_order.action_pos_order_paid()
            _logger.info(f"POS Order created and validated with ID: {pos_order.id}")
        except Exception as e:
            _logger.exception(f"Failed to confirm POS order ID {pos_order.id}: {e}")
            return {'success': False, 'error': f"Order validation failed: {e}"}

        return {'success': True, 'pos_order_id': pos_order.id}

    @http.route('/ordable/payment', type='http', auth='public', website=True, cors="*", methods=["GET"], csrf=False)
    def ordable_payment(self, **kwargs):
        try:
            _logger.info(
                f'========= Data received from ordable payment webhook {kwargs} {request.get_json_data()} {request.params}===============')
            payment_data = request.get_json_data()
            brand_id = kwargs.get('brand')
            brand = request.env['ordable.brand'].sudo().search([('branch', '=', brand_id)], limit=1)
            if not brand:
                _logger.warning("Brand not available")
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Brand ID missing'
                }, status=400)

            self.create_order(payment_data, brand)

            return request.make_json_response({
                'status': 'success',
                'message': 'Data successfully submitted!'
            })

        except Exception as e:
            return request.make_json_response({
                'status': 'error',
                'message': str(e)
            })

