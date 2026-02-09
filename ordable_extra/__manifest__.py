# -*- coding: utf-8 -*-
{
    'name': "Ordable Extra",
    'summary': "Ordable-Extra-Centrixplus Integration",
    'description': """
        Ordable-Extra-Ordable-Centrixplus Integration
    """,

    'author': "Centrixplus",
    'website': "https://centrixplus.com",

    # Categories can be used to filter modules in modules listing
    # Check https://github.com/odoo/odoo/blob/16.0/odoo/addons/base/data/ir_module_category_data.xml
    # for the full list
    'category': 'Connector',
    'version': '16.0.0.0.1',
    'license': 'LGPL-3',
    # any module necessary for this one to work correctly
    'depends': ['mail', 'base', 'point_of_sale'],

    # always loaded
    'data': [
        # security
        'security/ir.model.access.csv',
        # Data (must load before views that reference them)
        'data/order_stage_data.xml',
        # Wizard
        # Views
        'views/res_concept.xml',
        'views/product.xml',
        'views/category.xml',
        'views/order_stage_views.xml',
        'views/pos_order_views.xml',
        # data
        'data/action.xml',
        # Menu
        'data/menu.xml',
        # Report

    ],
    'installable': True,
    'application': False,
    'assets': {
        'web.assets_frontend': [
        ],
        'web.assets_backend': [
        ]
    },

}
