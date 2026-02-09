# -*- coding: utf-8 -*-

from odoo import api, fields, models


class OrderStage(models.Model):
    _name = 'order.stage'
    _description = 'Order Stage'
    _order = 'sequence, id'

    name = fields.Char(string='Stage Name', required=True, translate=True)
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True)

    _sql_constraints = [
        ('name_uniq', 'unique (name)', 'Stage name must be unique!'),
    ]
