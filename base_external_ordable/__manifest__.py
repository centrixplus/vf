# -*- coding: utf-8 -*-
{
    'name': "Base-External-Ordable",
    'summary': "Ordable-Centrixplus Integration",
    'icon': '/base_external_ordable/static/description/icon.png',
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
    'depends': ['mail', 'base'],

    # always loaded
    'data': [
        # security
        # Wizard
        # Views
        # data
        # Menu
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
