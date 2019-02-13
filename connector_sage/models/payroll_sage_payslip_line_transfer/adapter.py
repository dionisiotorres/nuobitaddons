# Copyright NuoBiT Solutions, S.L. (<https://www.nuobit.com>)
# Eric Antones <eantones@nuobit.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import models, fields

from odoo.addons.component.core import Component


class PayslipLineTransferAdapter(Component):
    _name = 'sage.payroll.sage.payslip.line.transfer.adapter'
    _inherit = 'sage.payroll.sage.payslip.line.adapter'

    _apply_on = 'sage.payroll.sage.payslip.line.transfer'

    _id = ('CodigoEmpresa', 'Año', 'MesD', 'CodigoEmpleado', 'CodigoConceptoNom',
           'CodigoConvenio', 'FechaRegistroCV', 'FechaCobro')