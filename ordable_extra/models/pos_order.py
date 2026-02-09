from odoo import api, models, fields
import logging
import requests

_logger = logging.getLogger(__name__)

class PosOrder(models.Model):
    _inherit = "pos.order"

    concept_id = fields.Many2one("res.concept", string="Concept")
    order_stage_id = fields.Many2one(
        'order.stage',
        string='Order Stage',
        default=lambda self: self.env.ref('ordable_extra.order_stage_new', raise_if_not_found=False),
        ondelete='restrict',
        tracking=True,
        help="Current stage of the order in the workflow"
    )

