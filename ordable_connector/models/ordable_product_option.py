import logging
import requests
from odoo import api, models, fields, _

_logger = logging.getLogger(__name__)

class OrdableProductOption(models.Model):
    _name = "ordable.product.option"

    name = fields.Char(string="Name")
    concept = fields.Many2one("res.concept", string="Concept")
    ordable_id = fields.Integer(string="ordable_id")