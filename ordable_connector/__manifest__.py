# -*- coding: utf-8 -*-
{
    'name': "Ordable",
    'summary': "Ordable-Centrixplus Integration",
    'icon': '/ordable_connector/static/description/icon.png',
    'description': """
        Base-External-Ordable-Centrixplus Integration
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
    'depends': ['mail', 'base', 'point_of_sale', 'sale','ordable_extra'],

    # always loaded
    'data': [
        # security
        'security/ir.model.access.csv',
        # Wizard
        # Views
        'views/ordable_brand_view.xml',
        'views/ordable_product.xml',
        # data
        'data/action.xml',
        'data/server_actions.xml',
        # Menu
        'data/menu.xml',
        # Report

    ],
    'installable': True,
    'application': True,
    'assets': {
        'web.assets_frontend': [
        ],
        'web.assets_backend': [
        ]
    },

}
