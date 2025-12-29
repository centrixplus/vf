# -*- coding: utf-8 -*-
# from odoo import http


# class OrdableExtra(http.Controller):
#     @http.route('/ordable_extra/ordable_extra', auth='public')
#     def index(self, **kw):
#         return "Hello, world"

#     @http.route('/ordable_extra/ordable_extra/objects', auth='public')
#     def list(self, **kw):
#         return http.request.render('ordable_extra.listing', {
#             'root': '/ordable_extra/ordable_extra',
#             'objects': http.request.env['ordable_extra.ordable_extra'].search([]),
#         })

#     @http.route('/ordable_extra/ordable_extra/objects/<model("ordable_extra.ordable_extra"):obj>', auth='public')
#     def object(self, obj, **kw):
#         return http.request.render('ordable_extra.object', {
#             'object': obj
#         })
