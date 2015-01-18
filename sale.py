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

class sale_order(osv.osv):
    _inherit = "sale.order"

    def action_ship_create(self, cr, uid, ids, context=None):
        pick_obj = self.pool.get('stock.picking')
        result = super(sale_order, self).action_ship_create(cr, uid, ids, context=context)
        if result:
            for sale in self.browse(cr, uid, ids):
                if sale.ship_company_code == 'fedex':
                    pick_ids = pick_obj.search(cr, uid, [('sale_id', '=', sale.id), ('type', '=', 'out')], context=context)
                    if pick_ids:
                        vals = {
                            'ship_company_code': 'fedex',
                            'logis_company': sale.logis_company and sale.logis_company.id or False,
                            'shipper': sale.fedex_shipper_id and sale.fedex_shipper_id.id or False,
                            'fedex_service': sale.fedex_service_id and sale.fedex_service_id.id or False,
                            'fedex_pickup_type': sale.fedex_pickup_type,
                            'fedex_packaging_type': sale.fedex_packaging_type and sale.fedex_packaging_type.id or False,
                            'ship_from_address':sale.fedex_shipper_id and sale.fedex_shipper_id.address and sale.fedex_shipper_id.address.id or False,
                            'shipcharge':sale.shipcharge or False
                        }
                        pick_obj.write(cr, uid, pick_ids, vals)
                else:
                    pick_ids = pick_obj.search(cr, uid, [('sale_id', '=', sale.id), ('type', '=', 'out')])
                    if pick_ids:
                        pick_obj.write(cr, uid, pick_ids, {'shipper': False}, context=context)
        return result

    def _get_company_code(self, cr, user, context=None):
        res = super(sale_order, self)._get_company_code(cr, user, context=context)
        res.append(('fedex', 'FedEx'))
        return list(set(res))
    
    def onchange_service(self, cr, uid, ids, fedex_shipper_id=False, context=None):
         service_type_ids = []
         if fedex_shipper_id:
             shipper_obj = self.pool.get('fedex.account.shipping').browse(cr, uid, fedex_shipper_id)
             for shipper in shipper_obj.fedex_shipping_service_ids:
                 service_type_ids.append(shipper.id)
         domain = [('id', 'in', service_type_ids)]
         return {'domain': {'fedex_service_id': domain}}
    
    _columns = {
        'ship_company_code': fields.selection(_get_company_code, 'Logistic Company', method=True, size=64),
        'fedex_shipper_id': fields.many2one('fedex.account.shipping', 'Shipper'),
        'fedex_service_id': fields.many2one('fedex.shipping.service.type', 'Service Type'),
        'fedex_pickup_type': fields.selection([
            ('REGULAR_PICKUP', 'Daily Pickup'),
            ('REQUEST_COURIER', 'Courier Pickup'),
            ('STATION', 'Station'),
            ('DROP_BOX', 'FedEx Drop Box'),
            ('BUSINESS_SERVICE_CENTER', 'Business Service Center Dropoff')
        ], 'Pickup Type'),
        'fedex_packaging_type': fields.many2one('shipping.package.type', 'Packaging Type')
    }

    def _get_sale_account(self, cr, uid, context=None):
        if context is None:
            context = {}
        logisitic_obj = self.pool.get('logistic.company')
        logis_company = logisitic_obj.search(cr, uid, [])

        if not logis_company:
            return False

        return logisitic_obj.browse(cr, uid, logis_company[0], context).ship_account_id.id

    _defaults = {
        'sale_account_id': _get_sale_account,
        'fedex_pickup_type': 'REQUEST_COURIER'
    }

sale_order()

# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4:
