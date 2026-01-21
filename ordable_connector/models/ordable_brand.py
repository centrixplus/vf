import logging
from odoo import api, models, fields, _

class OrdableBrand(models.Model):
    _name = "ordable.brand"

    name = fields.Char(string="Name", required=True)
    ordable_api_token = fields.Char(string="Ordable API Token", required=True)
    ordable_base_url = fields.Char(string="Ordable Base URL", required=True)
    branch = fields.Char(string="Branch", required=True)
    concept = fields.Many2one("res.concept", string="Concept")
    sync_ordable_info = fields.Boolean("Is Sync Ordable")
    ordable_brand = fields.Selection([('pos', 'POS Order'), ('sale', 'Sale Order')], string="Ordable Brand", default="pos")
    company_id = fields.Many2one(
        'res.company',
        string='Company',
        default=lambda self: self.env.company,
        required=True
    )