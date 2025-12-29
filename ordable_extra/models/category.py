from odoo import models, fields, api
import json
import logging

_logger = logging.getLogger(__name__)
class ProductCategory(models.Model):
    _inherit = 'pos.category'

    concept_ids = fields.Many2many("res.concept", string="Concept")


