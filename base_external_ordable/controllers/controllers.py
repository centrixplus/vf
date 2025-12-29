# -*- coding: utf-8 -*-
# from odoo import http


# class BaseExternalOrdable(http.Controller):
#     @http.route('/base_external_ordable/base_external_ordable', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/base_external_ordable/base_external_ordable/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('base_external_ordable.listing', {
#             'root': '/base_external_ordable/base_external_ordable',
#             'objects': http.request.env['base_external_ordable.base_external_ordable'].search([]),
#         })

#     @http.route('/base_external_ordable/base_external_ordable/objects/<model("base_external_ordable.base_external_ordable"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('base_external_ordable.object', {
#             'object': obj
#         })
