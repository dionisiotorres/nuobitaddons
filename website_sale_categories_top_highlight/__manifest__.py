# -*- coding: utf-8 -*-
# Copyright NuoBiT Solutions, S.L. (<https://www.nuobit.com>)
# Eric Antones <eantones@nuobit.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

{
    'name': "Highlight active top categories",
    'description': "Show web categories on top of product page highlighted",
    'version': '10.0.0.2.0',
    'author': 'NuoBiT Solutions, S.L., Eric Antones',
    'license': 'AGPL-3',
    'category': 'Custom',
    'website': 'https://www.nuobit.com',
    'depends': ['website_sale_categories_top'],
    'data': [
        'views/templates.xml',
        ],
    'installable': True,
}
