# -*- coding: utf-8 -*-
# from odoo import http


# class OrdableConnector(http.Controller):
#     @http.route('/ordable_connector/ordable_connector', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ordable_connector/ordable_connector/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('ordable_connector.listing', {
#             'root': '/ordable_connector/ordable_connector',
#             'objects': http.request.env['ordable_connector.ordable_connector'].search([]),
#         })

#     @http.route('/ordable_connector/ordable_connector/objects/<model("ordable_connector.ordable_connector"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ordable_connector.object', {
#             'object': obj
#         })
