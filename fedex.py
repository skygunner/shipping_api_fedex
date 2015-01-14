# -*- coding: utf-8 -*-
##############################################################################
#
#    OpenERP, Open Source Management Solution
#    Copyright (C) 2011 NovaPoint Group LLC (<http://www.novapointgroup.com>)
#    Copyright (C) 2004-2010 OpenERP SA (<http://www.openerp.com>)
#
#    This program is free software: you can redistribute it and/or modify
#    it under the terms of the GNU General Public License as published by
#    the Free Software Foundation, either version 3 of the License, or
#    (at your option) any later version.
#
#    This program is distributed in the hope that it will be useful,
#    but WITHOUT ANY WARRANTY; without even the implied warranty of
#    MERCHANTABILITY or FITNESS FOR A PARTICULAR PURPOSE.  See the
#    GNU General Public License for more details.
#
#    You should have received a copy of the GNU General Public License
#    along with this program.  If not, see <http://www.gnu.org/licenses/>
#
##############################################################################

from openerp.osv import fields, osv

class fedex_account_shipping(osv.osv):
    _name = "fedex.account.shipping"
    _columns = {
        'name': fields.char('Name', size=64, required=True),
        'fedex_account_id': fields.many2one('fedex.account', 'FedEx Account', required=True),
        'integrator_id': fields.related('fedex_account_id', 'fedex_integrator_id', type='char', size=64, string='IntegratorID', required=True),
        'password': fields.related('fedex_account_id', 'fedex_password', type='char', size=64, string='Password', required=True),
        'active': fields.boolean('Active'),
        'key': fields.related('fedex_account_id', 'fedex_key', type='char', size=64, string='Key', required=True),
        'account_number': fields.related('fedex_account_id', 'fedex_account_number', type='char', size=64, string='Account Number', required=True),
        'meter_number': fields.related('fedex_account_id', 'fedex_meter_number', type='char', size=64, string='Meter Number', required=True),
        'tax_id_no': fields.char('Tax Identification Number', size=64 , select=1, help="Shipper's Tax Identification Number."),
        'logistic_company_id': fields.many2one('logistic.company', 'Parent Logistic Company'),
        'company_id': fields.dummy(string='Company ID', relation='res.company', type='many2one'), # For playing nice with the global domain.
        'address': fields.property(
           'res.partner',
           type='many2one',
           relation='res.partner',
           string="Shipper Address",
           view_load=True),
        'sandbox': fields.boolean('Sandbox mode')
    }
    _defaults = {
        'active': True,
        'sandbox': False
    }

    def onchange_fedex_account(self, cr, uid, ids, fedex_account_id=False, context=None):
        res = {
            'key': '',
            'integrator_id': '',
            'password': '',
            'account_number': '',
            'meter_number': '',
            'sandbox': True
        }

        if fedex_account_id:
            fedex_account = self.pool.get('fedex.account').browse(cr, uid, fedex_account_id, context=context)
            res = {
                'key': fedex_account.fedex_key,
                'integrator_id': fedex_account.fedex_integrator_id,
                'password': fedex_account.fedex_password,
                'account_number': fedex_account.fedex_account_number,
                'meter_number': fedex_account.fedex_meter_number,
                'sandbox': fedex_account.test_mode
            }
        return {'value': res}

fedex_account_shipping()

class fedex_account_shipping_service(osv.osv):
    
    _name = "fedex.shipping.service.type"
    _rec_name = "description"
    
    _columns = {
        'description': fields.char('Description', size=32, required=True, select=1),
        'category': fields.char('Category', size=32, select=1),
        'shipping_service_code': fields.char('Shipping Service Code', size=8, select=1),
        'rating_service_code': fields.char('Rating Service Code', size=8, select=1),
        'fedex_account_id': fields.many2one('fedex.account.shipping', 'Parent Shipping Account'),
    }
    
fedex_account_shipping_service()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
