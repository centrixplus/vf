from odoo import http
from odoo.http import request, Response
from datetime import datetime
import requests
import json
import logging
from odoo.exceptions import AccessError
import re
_logger = logging.getLogger(__name__)


class OrdermainController(http.Controller):

    def create_sale_order(self, order_data, partner, brand):
        # Validate required data
        if not order_data.get('items'):
            raise ValueError("Order must contain at least one item")

        # Check if sale order already exists with the same ordable_id and ordable_tracking_id
        existing_order = request.env['sale.order'].sudo().search([
            ('ordable_id', '=', order_data['id']),
            ('ordable_tracking_id', '=', order_data['tracking_id'])
        ], limit=1)

        if existing_order:
            _logger.info(
                f"Sale Order already exists with ordable_id: {order_data['id']} and ordable_tracking_id: {order_data['tracking_id']}. Skipping creation.")
            return {'success': True, 'sale_order_id': existing_order.id, 'already_exists': True}

        # Prepare sale order values
        sale_order_vals = {
            'partner_id': partner.id,
            'ordable_id': order_data['id'],
            'ordable_tracking_id': order_data['tracking_id'],
            'user_id': 1,
            'company_id': brand.company_id.id,
            'note': order_data.get('special_remarks', ''),
            'client_order_ref': order_data.get('tracking_id'),
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

        # Add delivery charge if applicable
        is_delivery = order_data.get('is_delivery', False)
        delivery_rate = order_data.get('delivery_rate', 0.0)

        if is_delivery and delivery_rate > 0:
            # Search for Delivery Charge product
            delivery_product = request.env['product.product'].sudo().search([
                ('name', '=', 'Delivery Charge'),
                ('type', '=', 'service')
            ], limit=1)

            # Create Delivery Charge product if it doesn't exist
            if not delivery_product:
                delivery_template = request.env['product.template'].sudo().create({
                    'name': 'Delivery Charge',
                    'type': 'service',
                    'list_price': delivery_rate,
                    'categ_id': 1
                })
                delivery_product = delivery_template.product_variant_id
                _logger.info(f"Created new Delivery Charge product with ID: {delivery_product.id}")

            # Add delivery charge as a sale order line
            request.env['sale.order.line'].sudo().create({
                'order_id': sale_order.id,
                'product_id': delivery_product.id,
                'product_uom_qty': 1,
                'price_unit': delivery_rate,
            })
            _logger.info(f"Added delivery charge of {delivery_rate} to Sale Order {sale_order.id}")

        _logger.info(f"Sale Order created with ID: {sale_order.id}")
        # Confirm the Sale Order
        try:
            sale_order.action_confirm()
            _logger.info("Sale Order Confirmed with ID: %s", sale_order.id)

            # Check if payment is complete and create invoice
            if order_data.get('payment_complete'):
                self.sale_order_invoice_payment(sale_order)
        except Exception as e:
            _logger.exception("Failed to confirm Sale Order ID %s: %s", sale_order.id, e)

        return {'success': True, 'sale_order_id': sale_order.id}

    def sale_order_invoice_payment(self, sale_order):
        """
        Create invoice for the sale order when payment is complete
        """
        try:
            # Create invoice from the sale order
            invoice = sale_order._create_invoices()

            if invoice:
                _logger.info(f"Invoice created with ID: {invoice.id} for Sale Order: {sale_order.id}")

                # Post the invoice
                invoice.action_post()
                _logger.info(f"Invoice {invoice.id} posted successfully")

                # Register payment after invoice is posted
                payment = self.register_invoice_payment(invoice)
                if payment:
                    _logger.info(f"Payment registered with ID: {payment.id} for Invoice: {invoice.id}")

                return {'success': True, 'invoice_id': invoice.id, 'payment_id': payment.id if payment else None}
            else:
                _logger.warning(f"Failed to create invoice for Sale Order: {sale_order.id}")
                return {'success': False, 'message': 'Invoice creation failed'}

        except Exception as e:
            _logger.exception(f"Error creating invoice for Sale Order {sale_order.id}: {e}")
            return {'success': False, 'message': str(e)}

    def register_invoice_payment(self, invoice):
        """
        Register payment for the posted invoice
        """
        try:
            # Get default payment method (cash/bank journal)
            payment_journal = request.env['account.journal'].sudo().search([
                ('type', 'in', ['cash', 'bank']),
                ('company_id', '=', invoice.company_id.id)
            ], limit=1)

            if not payment_journal:
                _logger.warning(f"No payment journal found for company: {invoice.company_id.name}")
                return None

            # Prepare payment values
            payment_vals = {
                'payment_type': 'inbound',
                'partner_type': 'customer',
                'partner_id': invoice.partner_id.id,
                'amount': invoice.amount_total,
                'journal_id': payment_journal.id,
                'date': datetime.now().date(),
                'ref': f"Payment for {invoice.name}",
                'currency_id': invoice.currency_id.id,
            }

            # Create payment
            payment = request.env['account.payment'].sudo().create(payment_vals)
            _logger.info(f"Payment created with ID: {payment.id}")

            # Post the payment
            payment.action_post()
            _logger.info(f"Payment {payment.id} posted successfully")

            # Reconcile payment with invoice
            # invoice_lines = invoice.line_ids.filtered(lambda line: line.account_id.account_type in ['asset_receivable', 'liability_payable'])
            # payment_lines = payment.line_ids.filtered(lambda line: line.account_id.account_type in ['asset_receivable', 'liability_payable'])
            #
            # if invoice_lines and payment_lines:
            #     (invoice_lines + payment_lines).reconcile()
            #     _logger.info(f"Payment {payment.id} reconciled with Invoice {invoice.id}")

            return payment

        except Exception as e:
            _logger.exception(f"Error registering payment for Invoice {invoice.id}: {e}")
            return None

    def create_pos_order(self, order_data, partner, brand):
        """
        Create POS order in the Call Center POS
        """
        # 1. SESSION, COMPANY, AND TAX ACQUISITION
        pos_session = request.env['pos.session'].sudo().search([
            ('state', '=', 'opened'),
            ('config_id.name', '=', 'Call Center')
        ], limit=1)

        if not pos_session:
            _logger.error("No active POS session found for Call Center")
            return {'success': False, 'error': 'No active POS session found for Call Center'}

        company_id = pos_session.config_id.company_id.id

        # Find the 0% Sales Tax Record (mandatory for Kuwait)
        zero_tax = request.env['account.tax'].sudo().search([
            ('company_id', '=', company_id),
            ('type_tax_use', '=', 'sale'),
            ('amount', '=', 0.0)
        ], limit=1)

        tax_ids_to_use = zero_tax.ids if zero_tax else []

        if not zero_tax:
            _logger.warning(f"No 0% Sales Tax record found for company ID {company_id}")

        # 2. CHECK FOR DUPLICATE POS ORDER
        existing_pos_order = request.env['pos.order'].sudo().search([
            ('ordable_id', '=', order_data.get('id')),
            ('ordable_tracking_id', '=', order_data.get('tracking_id'))
        ], limit=1)

        if existing_pos_order:
            _logger.info(f"POS Order already exists with ordable_id: {order_data.get('id')} and ordable_tracking_id: {order_data.get('tracking_id')}. Skipping creation.")
            return {'success': True, 'pos_order_id': existing_pos_order.id, 'already_exists': True}

        # 3. POS ORDER CREATION
        pos_order_vals = {
            'partner_id': partner.id,
            'session_id': pos_session.id,
            'user_id': pos_session.user_id.id,
            'company_id': company_id,
            'pricelist_id': pos_session.config_id.pricelist_id.id,
            'fiscal_position_id': partner.property_account_position_id.id or False,
            'ordable_id': order_data.get('id'),
            'ordable_tracking_id': order_data.get('tracking_id'),
            'concept_id': brand.concept.id if hasattr(brand, 'concept') else False,
            'amount_tax': 0.0,
            'amount_total': order_data.get('total', 0.0),
            'amount_paid': order_data.get('total', 0.0),
            'amount_return': 0.0
        }

        pos_order = request.env['pos.order'].sudo().create(pos_order_vals)
        _logger.info(f"POS Order created with reference: {pos_order.pos_reference}")

        # 4. ORDER LINE CREATION - Items
        for item in order_data.get('items', []):
            # Search for product with concept filter
            product = request.env['product.product'].sudo().search([
                ('name', '=', item['name']),
                ('product_tmpl_id.concept_ids', 'in', brand.concept.id)
            ], limit=1)

            # Create product if doesn't exist
            if not product:
                product_template = request.env['product.template'].sudo().create({
                    'name': item['name'],
                    'list_price': item.get('price', 0),
                    'categ_id': 1,
                    'concept_ids': [(6, 0, [brand.concept.id])],
                    'taxes_id': [(6, 0, tax_ids_to_use)],
                })
                product = product_template.product_variant_id
                _logger.info(f"Created new product: {product.name} with ID: {product.id}")

            unit_price = item.get('price', 0)
            quantity = item.get('quantity', 1)
            subtotal = unit_price * quantity

            # Create POS order line
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

            # Create separate lines for item options
            for option in item.get('options', []):
                option_product = request.env['product.product'].sudo().search([
                    ('name', '=', option['name']),
                    ('product_tmpl_id.concept_ids', 'in', brand.concept.id)
                ], limit=1)

                if not option_product:
                    option_template = request.env['product.template'].sudo().create({
                        'name': option['name'],
                        'list_price': option.get('price', 0),
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

        # 5. ADD DELIVERY CHARGE IF APPLICABLE
        is_delivery = order_data.get('is_delivery', False)
        delivery_rate = order_data.get('delivery_rate', 0.0)

        if is_delivery and delivery_rate > 0:
            delivery_product = request.env['product.product'].sudo().search([
                ('name', '=', 'Delivery Charge'),
                ('type', '=', 'service')
            ], limit=1)

            if not delivery_product:
                delivery_template = request.env['product.template'].sudo().create({
                    'name': 'Delivery Charge',
                    'type': 'service',
                    'list_price': delivery_rate,
                    'categ_id': 1,
                    'taxes_id': [(6, 0, tax_ids_to_use)],
                })
                delivery_product = delivery_template.product_variant_id
                _logger.info(f"Created Delivery Charge product with ID: {delivery_product.id}")

            request.env['pos.order.line'].sudo().create({
                'order_id': pos_order.id,
                'product_id': delivery_product.id,
                'qty': 1,
                'price_unit': delivery_rate,
                'price_subtotal': delivery_rate,
                'price_subtotal_incl': delivery_rate,
                'tax_ids': [(6, 0, tax_ids_to_use)],
                'full_product_name': 'Delivery Charge',
            })
            _logger.info(f"Added delivery charge of {delivery_rate} to POS Order {pos_order.id}")

        # 6. PAYMENT CREATION
        payments = order_data.get('payments', [])
        for payment in payments:
            payment_method_name = payment.get('payment_method')
            payment_amount = payment.get('amount')

            if not payment_method_name or payment_amount is None:
                _logger.warning("Payment entry is missing method or amount. Skipping.")
                continue

            # Find POS payment method
            payment_method = request.env['pos.payment.method'].sudo().search([
                ('name', 'ilike', payment_method_name)
            ], limit=1)

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
                _logger.info(f"Payment added to POS order with method: {payment_method_name}")
            except Exception as e:
                _logger.exception(f"Failed to add payment to POS order ID {pos_order.id}: {e}")

        # 7. VALIDATE AND MARK ORDER AS PAID
        try:
            pos_order.action_pos_order_paid()
            _logger.info(f"POS Order validated and paid with ID: {pos_order.id}")
        except Exception as e:
            _logger.exception(f"Failed to validate POS order ID {pos_order.id}: {e}")
            return {'success': False, 'error': f"Order validation failed: {e}"}

        return {'success': True, 'pos_order_id': pos_order.id}
    @http.route('/ordable/order/create', type='http', auth='public', website=True, cors="*", methods=["POST"], csrf=False)
    def ordable_order_create(self, **kwargs):
        try:
            _logger.info(f'========= Data received from ordable payment webhook {kwargs} {request.get_json_data()} {request.params}===============')
            data = request.get_json_data()
            brand_id = kwargs.get('brand')
            brand = request.env['ordable.brand'].sudo().search([('branch', '=', brand_id)], limit=1)
            if not brand:
                _logger.warning("Brand not available")
                return request.make_json_response({
                    'status': 'error',
                    'message': 'Brand ID missing'
                }, status=400)
            partner = request.env['res.partner'].sudo().search([
                ('phone', '=', data.get('phone'))
            ], limit=1)

            if not partner:
                partner = request.env['res.partner'].sudo().create({
                    'name': data.get('customer_name'),
                    'phone': data.get('phone'),
                    'country_id': request.env.ref('base.kw').id,
                })

            if brand.ordable_brand == "pos":
                self.create_pos_order(data, partner, brand)
            else:
                self.create_sale_order(data, partner, brand)

            return request.make_json_response({
                'status': 'success',
                'message': 'Data successfully submitted!'
            })
        except Exception as e:
            return request.make_json_response({
                'status': 'error',
                'message': str(e)
            })