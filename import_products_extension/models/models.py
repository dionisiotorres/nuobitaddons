# -*- coding: utf-8 -*-
#/#############################################################################
#
#   Odoo, Open Source Management Solution
#   Copyright (C) 2015 NuoBiT Solutions, S.L. (<http://www.nuobit.com>).
#
#   This program is free software: you can redistribute it and/or modify
#   it under the terms of the GNU Affero General Public License as
#   published by the Free Software Foundation, either version 3 of the
#   License, or (at your option) any later version.
#
#   This program is distributed in the hope that it will be useful,
#   but WITHOUT ANY WARRANTY; without even the implied warranty of
#   MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#   GNU Affero General Public License for more details.
#
#   You should have received a copy of the GNU Affero General Public License
#   along with this program.  If not, see <http://www.gnu.org/licenses/>.
#
#/#############################################################################



from datetime import timedelta

import pytz

import base64
import StringIO
import re
import csv
import unicodedata
import string

from openerp import models, fields, api, _
from openerp.exceptions import AccessError, Warning



import logging

_logger = logging.getLogger(__name__)


class import_header(models.Model):
    """Session"""
    _name = 'epe.header'
    _description = 'Header'

    name = fields.Char(string='Import name', required=True,
        readonly=False)

    date_import = fields.Datetime('Date', required=True, default=fields.datetime.now())

    supplier_id = fields.Many2one('res.partner', domain=[('supplier','=', True)])

    delimiter = fields.Char(string='Delimitar', required=True,
        readonly=False, default=',')
    quotechar = fields.Char(string='Quotechar', required=True,
        readonly=False, default='"')

    strip_fields = fields.Boolean(string='Strip values', required=True,
        readonly=False, default=True)

    update_name = fields.Boolean(string='Update Name', required=True,
        readonly=False, default=False)

    update_category = fields.Boolean(string='Update Category', required=True,
        readonly=False, default=False)

    update_ean = fields.Boolean(string='Update EAN', required=True,
        readonly=False, default=False)

    update_saleprice = fields.Boolean(string='Update Sale Price', required=True,
        readonly=False, default=False)

    update_purchaseprice = fields.Boolean(string='Update Puechase Price', required=True,
        readonly=False, default=True)

    description = fields.Text(string='Description',
        readonly=False)

    datas = fields.Binary('File Content')
    datas_fname = fields.Char(string='File Name')

    line_ids = fields.One2many('epe.line','header_id')

    def _split_line(self, line):
        line9 = []
        for line in csv.reader([line],delimiter=self.delimiter.encode(), quotechar=self.quotechar.encode()):
            line9.append(line)
        return line9[0]




    @api.multi
    def import_file(self):
        txt = base64.decodestring(self.datas)
        # remove lasts newlines
        txt = re.sub(r'\n*$','' ,txt,flags=re.DOTALL)

        for i, line in enumerate(txt.split('\n')):
            field_values = self._split_line(line)
            if i==0:
                header = [x.strip() if self.strip_fields else x for x in field_values]
            else:
                if len(header)!=len(field_values):
                    raise Warning("Differnet field number i line %i" % i+1)
                fields = dict(zip(header, field_values))
                fields.update(header_id=self.id)
                self.env['epe.line'].create(fields)


    def _check_float_format(self, r):
        v = None
        if re.search('^[0-9]+$', r) is not None:
            v = r
        if re.search('^[0-9]+,[0-9]+$', r) is not None:
            v = r.replace(',','.')
        elif re.search('^[0-9]+\.[0-9]+$', r) is not None:
            v = r
        elif re.search('^[0-9]+\.[0-9]+,[0-9]+$', r) is not None:
            v = r.replace('.','').replace(',','.')
        elif re.search('^[0-9]+,[0-9]+\.[0-9]+$', r) is not None:
            v = r.replace(',','')

        return v

    def _slugify(self, r):
        return ''.join(x for x in unicodedata.normalize('NFKD', r) if x in string.ascii_letters).lower()


    @api.multi
    def update(self):
        for line in self.line_ids:
            upd = {}
            # test if arady exists another product with the same internal refernee
            pp = self.env['product.product'].search([('default_code','=', line.default_code)])
            if len(pp)>1:
                line.status='error'
                line.observations="There's more than one product with th same internart refencce"
                continue
            elif len(pp)==1:
                line.status='updated'
            else:
                line.status='created'

            # test if category exists
            if self.update_category:
                nc = []
                for cat in self.env['product.category'].search([]):
                    if self._slugify(cat.name)==self._slugify(line.category):
                        nc.append(cat)
                if len(nc)==0:
                    line.observations='Category did not exists, it was created'

                elif len(nc)==1:
                    if self._slugify(nc[0].name)!=self._slugify(line.category):
                        line.observations = "Used category %s instead of %s" % (nc[0].name, line.category)
                    line.category = nc[0].name
                    upd.update({'categ_id': nc[0].id})
                else:
                    line.status='error'
                    line.observations="There's more than one category wity the same slug %s" % nc
                    continue

            pl = self._check_float_format(line.pricelist_sale)
            if pl is None:
                line.status='error'
                line.observations='Unknown float format'
                continue
            else:
               line.pricelist_sale = pl

            pl = self._check_float_format(line.pricelist_purchase)
            if pl is None:
                line.status='error'
                line.observations='Unknown float format'
                continue
            else:
               line.pricelist_purchase = pl




    '''
    def import_file(self, cr, uid, ids, context=None):
    fileobj = TemporaryFile('w+')
    fileobj.write(base64.decodestring(data))

    # your treatment
    return
    '''
    '''
        if context is None:
            context = {}
        result = {}
        bin_size = context.get('bin_size')
        for attach in self.browse(cr, uid, ids, context=context):
            if attach.store_fname:
                result[attach.id] = self._file_read(cr, uid, attach.store_fname, bin_size)
            else:
                result[attach.id] = attach.db_datas
        return result

    def _file_read(self, cr, uid, fname, bin_size=False):
        full_path = self._full_path(cr, uid, fname)
        r = ''
        try:
            if bin_size:
                r = os.path.getsize(full_path)
            else:
                r = open(full_path,'rb').read().encode('base64')
        except IOError:
            _logger.exception("_read_file reading %s", full_path)
        return r

    def _data_set(self, cr, uid, id, name, value, arg, context=None):
        # We dont handle setting data to null
        if not value:
            return True
        if context is None:
            context = {}
        location = self._storage(cr, uid, context)
        file_size = len(value.decode('base64'))
        attach = self.browse(cr, uid, id, context=context)
        fname_to_delete = attach.store_fname
        if location != 'db':
            fname = self._file_write(cr, uid, value)
            # SUPERUSER_ID as probably don't have write access, trigger during create
            super(ir_attachment, self).write(cr, SUPERUSER_ID, [id], {'store_fname': fname, 'file_size': file_size, 'db_datas': False}, context=context)
        else:
            super(ir_attachment, self).write(cr, SUPERUSER_ID, [id], {'db_datas': value, 'file_size': file_size, 'store_fname': False}, context=context)

        # After de-referencing the file in the database, check whether we need
        # to garbage-collect it on the filesystem
        if fname_to_delete:
            self._file_delete(cr, uid, fname_to_delete)
        return True
    '''



class import_lines(models.Model):
    """Session"""
    _name = 'epe.line'
    _description = 'Import Lines'

    default_code = fields.Char(string='Internal reference', required=True)

    name = fields.Char(string='Name', required=False,
        readonly=False)

    category = fields.Char(string='Category Name', required=False,
        readonly=False)

    ean13 = fields.Char(string='EAN', required=False,
        readonly=False)

    pricelist_sale = fields.Char(string="Sale Pricelist", required=False)
    pricelist_purchase = fields.Char(string="Purchase Pricelist", required=False)

    header_id = fields.Many2one('epe.header', required=True, ondelete="cascade")

    status = fields.Char("Status")
    observations = fields.Text(string='Description',
        readonly=False)

