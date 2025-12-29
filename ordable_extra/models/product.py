from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)
class ProductTemplate(models.Model):
    _inherit = 'product.template'

    concept_ids = fields.Many2many("res.concept", string="Concept")
    name_secondary = fields.Char("Arabic Name")

class ProductMain(models.Model):
    _inherit = 'product.product'

    concept_ids = fields.Many2many("res.concept", string="Concept", related='product_tmpl_id.concept_ids')
    name_secondary = fields.Char("Arabic Name")