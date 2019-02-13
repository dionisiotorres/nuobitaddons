# Copyright NuoBiT Solutions, S.L. (<https://www.nuobit.com>)
# Eric Antones <eantones@nuobit.com>
# License AGPL-3.0 or later (http://www.gnu.org/licenses/agpl)

from odoo import api, fields, models, _
from odoo.exceptions import UserError, ValidationError

from datetime import datetime


class Payslip(models.Model):
    _name = 'payroll.sage.payslip'
    _description = 'Payslip'

    name = fields.Char(string='Name', required=True)
    date = fields.Date(string='Date', required=True)

    labour_agreement_id = fields.Many2one('payroll.sage.labour.agreement', string='Labour agreement',
                                          # domain=[('registration_date_cv', '>=')]
                                          required=True)

    company_id = fields.Many2one('res.company', string='Company', required=True, readonly=True,
                                 default=lambda self: self.env['res.company']._company_default_get())

    journal_id = fields.Many2one('account.journal', string='Journal', required=True)

    type = fields.Selection([('transfer', _('Transfer')), ('payroll', _('Payroll'))], string='Type', required=True)

    ss_cost = fields.Float('S.S. cost')

    payment_date = fields.Date('Payment date')

    note = fields.Text(string='Note')

    payslip_line_ids = fields.One2many('payroll.sage.payslip.line',
                                       'payslip_id', string='Wage type lines', copy=True)

    payslip_check_ids = fields.One2many('payroll.sage.payslip.check',
                                        'payslip_id', string='Checks', copy=True)

    payslip_wage_type_ids = fields.One2many('payroll.sage.payslip.wage.type',
                                            'payslip_id', string='Wage types', copy=True, readonly=True)

    move_id = fields.Many2one('account.move', string='Journal Entry',
                              readonly=True, index=True, ondelete='restrict', copy=False,
                              help="Link to the automatically generated Journal Items.")
    move_name = fields.Char(string='Journal Entry Name', readonly=False,
                            default=False, copy=False,
                            help="Technical field holding the number given to the invoice, automatically set when the invoice is validated then stored to set the same number again if the invoice is cancelled, set to draft and re-validated.")

    state = fields.Selection([
        ('draft', _('Draft')),
        ('validated', _('Validated')),
        ('posted', _('Posted')),
    ], string='Status', default='draft', readonly=True, required=True, copy=False)

    @api.multi
    def action_paysplip_set_to_draft(self):
        for rec in self:
            rec.payslip_wage_type_ids.unlink()
            rec.write({
                'state': 'draft'
            })

    @api.multi
    def action_paysplip_validate(self):
        for rec in self:
            ### agrupem i acumulem iomports per wage type
            items_d = {}
            for line in rec.payslip_line_ids:
                wage_type_line = line.wage_type_line_id
                amount = line.amount * (-1 if not wage_type_line.positive else 1)
                amount = amount * (-1 if wage_type_line.total_historical_record == 'withholding' else 1)
                key = (wage_type_line.id,)
                if key not in items_d:
                    items_d[key] = {'wage_line_type': wage_type_line,
                                    'amount': 0, }
                items_d[key]['amount'] += amount

            ### muntem el valors
            values_l = []
            for wage_type in sorted(items_d.values(), key=lambda x: x['wage_line_type'].code):
                values_l.append({
                    'wage_type_line_id': wage_type['wage_line_type'].id,
                    'amount': wage_type['amount'],
                })

            ## inserim
            rec.write({'payslip_wage_type_ids': [(0, False, v) for v in values_l],
                       'state': 'validated',
                       })

    @api.multi
    def action_paysplip_post(self):
        def add2dict(items_d, tag, employee, amount):
            if tag.aggregate:
                employee = None
                description = None
                key = (tag.id, employee)
            else:
                description = set()
                key = (tag.id, employee.id)

            if key not in items_d:
                items_d[key] = {'tag': tag,
                                'employee': employee,
                                'amount': 0,
                                'description': description}

            items_d[key]['amount'] += amount
            if not tag.aggregate:
                items_d[key]['description'].add(line.name.strip())

        for rec in self:
            ### agrupem i acumulem iomports per tag
            items_d = {}
            for line in rec.payslip_line_ids:
                wage_type_line = line.wage_type_line_id
                if wage_type_line.total_historical_record in ('accrural', 'withholding'):
                    amount = line.amount * (-1 if not wage_type_line.positive else 1)
                    amount = amount * (-1 if wage_type_line.total_historical_record == 'withholding' else 1)
                    for tag in wage_type_line.wage_tag_ids.filtered(lambda x: x.type == rec.type):
                        amount_tag = amount
                        if tag.negative_withholding and wage_type_line.total_historical_record == 'withholding':
                            amount_tag *= -1
                        add2dict(items_d, tag, line.employee_id, amount_tag)

            ### afegim ls S.S si es payroll
            if rec.type == 'payroll':
                for tag in rec.labour_agreement_id.ss_tag_ids:
                    if not tag.aggregate:
                        raise UserError(_("S.S. Tags must be aggregated!"))
                    add2dict(items_d, tag, None, round(rec.ss_cost, 2))
            else:
                ## afegm els talons si es transfer (sempre han de restar)
                for check in rec.payslip_check_ids:
                    for tag in rec.labour_agreement_id.check_tag_ids:
                        add2dict(items_d, tag, check.employee_id, round(-check.amount,2))

            #### generem lassentament
            ## apunts
            line_values_l = []
            for item_d in items_d.values():
                tag = item_d['tag']

                ## compte
                values = {
                    'account_id': tag.account_id.id,
                }

                # partner
                if not tag.aggregate:
                    values.update({'partner_id': item_d['employee'].address_home_id.id})

                ## descripcio
                from_string = fields.Date.from_string
                date_str = '%s/%s' % (from_string(rec.date).strftime("%m"),
                                      from_string(rec.date).strftime("%Y"))
                description_l = [date_str]
                if tag.description and tag.description.strip():
                    description_l.append(tag.description.strip())
                else:
                    if item_d['description']:
                        if len(item_d['description']) == 1:
                            description_l.append(list(item_d['description'])[0])
                if description_l:
                    values.update({'name': ' '.join(description_l)})

                # import
                credit_debit = tag.credit_debit
                if item_d['amount'] < 0:
                    if credit_debit == 'debit':
                        credit_debit = 'credit'
                    else:
                        credit_debit = 'debit'
                values.update({
                    credit_debit: abs(round(item_d['amount'], 2)),
                })

                line_values_l.append(values)

            ## assentament
            values = {
                'date': self.date,
                'ref': self.name,
                'company_id': self.company_id.id,
                'journal_id': self.journal_id.id,
                'line_ids': [(0, False, values) for values in line_values_l]
            }
            if rec.move_name:
                values.update({
                    'name': rec.move_name,
                })

            move = self.env['account.move'].create(values)
            move.post()

            rec.write({
                'move_id': move.id,
                'move_name': move.name,
                'state': 'posted'
            })

    @api.multi
    def action_paysplip_unpost(self):
        for rec in self:
            move = rec.move_id
            rec.move_id = False

            move.button_cancel()
            move.unlink()
            rec.write({'state': 'validated'})

    @api.multi
    def unlink(self):
        for rec in self:
            if rec.state not in ('draft',):
                raise UserError(_('You cannot delete a payslip which is not draft,'))
            elif rec.move_name:
                raise UserError(_(
                    'You cannot delete a payslip after it has been posted (and received a number). You can set it back to "Draft" state and modify its content, then re-confirm it.'))
        return super().unlink()


class PayslipLine(models.Model):
    _name = 'payroll.sage.payslip.line'
    _description = 'Payslip line'

    name = fields.Char('Description')

    wage_type_line_id = fields.Many2one('payroll.sage.labour.agreement.wage.type.line',
                                        string='Wage type line', required=True)
    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)

    amount = fields.Float('Amount', required=True)

    payslip_id = fields.Many2one('payroll.sage.payslip', string='Payslip', required=True, ondelete='cascade')


class PayslipCheck(models.Model):
    _name = 'payroll.sage.payslip.check'
    _description = 'Payslip check'

    name = fields.Char('Description')

    employee_id = fields.Many2one('hr.employee', string='Employee', required=True)

    amount = fields.Float('Amount', required=True)

    payslip_id = fields.Many2one('payroll.sage.payslip', string='Payslip', required=True, ondelete='cascade')


class PayslipWageType(models.Model):
    _name = 'payroll.sage.payslip.wage.type'
    _description = 'Payslip wage type'

    name = fields.Char('Description')

    wage_type_line_id = fields.Many2one('payroll.sage.labour.agreement.wage.type.line',
                                        string='Wage type line', required=True)

    amount = fields.Float('Amount', required=True)

    payslip_id = fields.Many2one('payroll.sage.payslip', string='Payslip', required=True, ondelete='cascade')