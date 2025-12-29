from odoo import api, models, fields
import logging
import requests

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    concept_id = fields.Many2one("res.concept", string="Concept")

