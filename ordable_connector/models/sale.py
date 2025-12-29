from odoo import models, fields, api
import requests
import json
import logging

_logger = logging.getLogger(__name__)


class ProductTemplate(models.Model):
    _inherit = 'sale.order'

    ordable_id = fields.Char(string="Ordable Order ID")
    ordable_tracking_id = fields.Char(string="Ordable Traking ID")
    concept_id = fields.Many2one("res.concept", string="Concept")