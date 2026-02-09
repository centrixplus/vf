# -*- coding: utf-8 -*-
# ============================================
# ORDABLE STATUS MAPPING IMPLEMENTATION
# Created: 2026-02-09
# Purpose: Map POS order stages to Ordable API statuses
# Can be safely removed if reverting
# ============================================

from odoo import api, fields, models, _
from odoo.exceptions import ValidationError
import logging

_logger = logging.getLogger(__name__)


class OrdableStatusMap(models.Model):
    _name = 'ordable.status.map'
    _description = 'Ordable Status Mapping'
    _order = 'sequence, id'

    name = fields.Char(string='Name', compute='_compute_name', store=True)
    pos_stage_id = fields.Many2one(
        'order.stage',
        string='POS Stage',
        required=True,
        ondelete='cascade',
        help="The POS order stage that triggers status update"
    )
    ordable_status = fields.Selection([
        ('New', 'New'),
        ('Received', 'Received'),
        ('Out For Delivery', 'Out For Delivery'),
        ('Complete', 'Complete'),
        ('Cancelled', 'Cancelled'),
    ], string='Ordable Status', required=True,
       help="The status that will be sent to Ordable API")
    sequence = fields.Integer(string='Sequence', default=10)
    active = fields.Boolean(string='Active', default=True,
                           help="Uncheck to disable this mapping without deleting it")

    _sql_constraints = [
        ('pos_stage_uniq', 'unique(pos_stage_id)',
         'Each POS stage can only have one Ordable status mapping!'),
    ]

    @api.depends('pos_stage_id', 'ordable_status')
    def _compute_name(self):
        """Compute display name from stage and status"""
        for record in self:
            if record.pos_stage_id and record.ordable_status:
                record.name = f"{record.pos_stage_id.name} → {record.ordable_status}"
            else:
                record.name = "New Mapping"

    @api.constrains('pos_stage_id')
    def _check_pos_stage(self):
        """Ensure POS stage exists"""
        for record in self:
            if not record.pos_stage_id:
                raise ValidationError(_("POS Stage is required for mapping."))

# ============================================
# END ORDABLE STATUS MAPPING
# ============================================
