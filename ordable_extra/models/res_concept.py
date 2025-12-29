import logging
from odoo import api, models, fields, _

class Concepts(models.Model):
    _name = "res.concept"

    name = fields.Char(string="Name", required=True)