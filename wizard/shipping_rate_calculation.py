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
from openerp.osv import orm, fields, osv
from tools.translate import _
import math
from ..helpers.fedex_wrapper import FedEx, PACKAGES, SERVICES
from ..helpers.shipping import Address, Package
from ..helpers import settings
from ..api import v1 as fedex_api

class shipping_rate_wizard(orm.TransientModel):
    _inherit = 'shipping.rate.wizard'

    def _get_company_code(self, cr, user, context=None):
        res =  super(shipping_rate_wizard, self)._get_company_code(cr, user, context=context)
        res.append(('fedex', 'FedEx'))
        return list(set(res))

    def default_get(self, cr, uid, fields, context={}):
        res = super(shipping_rate_wizard, self).default_get(cr, uid, fields, context=context)
        if context.get('active_model',False) == 'sale.order':
            sale_id = context.get('active_id',False)
            if sale_id:
                sale = self.pool.get('sale.order').browse(cr, uid, sale_id, context=context)
                if 'fedex_service_type' in fields and  sale.fedex_service_type:
                    res['fedex_service_type'] = sale.fedex_service_type
                
                if 'fedex_container' in fields and  sale.fedex_container:
                    res['fedex_container'] = sale.fedex_container
                    
                if 'fedex_length' in fields and  sale.fedex_length:
                    res['fedex_length'] = sale.fedex_length
                    
                if 'fedex_width' in fields and  sale.fedex_width:
                    res['fedex_width'] = sale.fedex_width
                    
                if 'fedex_height' in fields and  sale.fedex_height:
                    res['fedex_height'] = sale.fedex_height
                    
        return res

    def update_sale_order(self, cr, uid, ids, context={}):
        data = self.browse(cr, uid, ids[0], context=context)
        if not (data['rate_selection'] == 'rate_request' and data['ship_company_code']=='fedex'):
            return super(shipping_rate_wizard, self).update_sale_order(cr, uid, ids, context)
        if context.get('active_model',False) == 'sale.order':
            ship_method_ids = self.pool.get('shipping.rate.config').search(
                cr, uid, [('name','=',data.fedex_service_type)], context=context
            )
            ship_method_id = (ship_method_ids and ship_method_ids[0]) or None
            sale_id = context.get('active_id',False)
            sale_id and self.pool.get('sale.order').write(cr,uid,[sale_id],{'shipcharge':data.shipping_cost,
                                                                            'ship_method_id':ship_method_id,
                                                                            'sale_account_id':data.logis_company and data.logis_company.ship_account_id and data.logis_company.ship_account_id.id or False,
                                                                            'ship_company_code' :data.ship_company_code,
                                                                            'logis_company' : data.logis_company and data.logis_company.id or False,
                                                                            'fedex_service_type' : data.fedex_service_type,
                                                                            'fedex_container' : data.fedex_container ,
                                                                            'fedex_length' : data.fedex_length ,
                                                                            'fedex_width' : data.fedex_width ,
                                                                            'fedex_height' : data.fedex_height ,
                                                                            'rate_selection' : data.rate_selection
                                                                            })
            self.pool.get('sale.order').button_dummy(cr, uid, [sale_id], context=context)
            return {'nodestroy':False,'type': 'ir.actions.act_window_close'}
        
        return True

    def get_rate(self, cr, uid, ids, context={}):
        """Calculates the cost of shipping for USPS."""

        data = self.browse(cr, uid, ids[0], context=context)

        if not ( data['rate_selection'] == 'rate_request' and data['ship_company_code']=='fedex'):
            return super(shipping_rate_wizard, self).get_rate(cr, uid, ids, context)

        if context.get('active_model',False) == 'sale.order':
            # Are we running in test mode?
            test = data.logis_company.test_mode or False

            # Find the order we're calculating shipping costs on.
            sale_id = context.get('active_id',False)
            sale = self.pool.get('sale.order').browse(cr, uid, sale_id, context=context)

            # Get the shipper and recipient addresses for this order.
            address_from = sale.company_id.partner_id
            address_to = sale.partner_shipping_id or ''

            shipper = Address(address_from.name, address_from.street, address_from.city, address_from.state_id.code,
                              address_from.zip, address_from.country_id.name, address2=address_from.street2
            )
            recipient = Address(address_to.name, address_to.street, address_to.city, address_to.state_id.code,
                                address_to.zip, address_to.country_id.name, address2=address_to.street2
            )

            # Get the package's weight in ounces.
            weight = math.modf(sale.total_weight_net)
            ounces = (weight[1] * 16) + round(weight[0] * 16, 2)

            # Create the Package we are going to send.
            package = Package(str(ounces), data.fedex_container, data.fedex_length,
                              data.fedex_width, data.fedex_height, mail_class=data.fedex_service_type
            )

            # Connect to the Endicia API.
            api = FedEx(fedex_api.get_config(cr, uid, sale, None))

            # Ask Endicia what the cost of shipping for this package is.
            response = {'status': -1}
            try:
                response = api.rate([package], shipper, recipient)
            except Exception, e:
                self.write(cr, uid, [data.id], {'status_message': str(e)}, context=context)

            # Extract the shipping cost from the response, if successful.
            if response['status'] == 0:
                ship_method_ids = self.pool.get('shipping.rate.config').search(
                    cr, uid, [('name', '=', data.fedex_service_type)], context=context
                )
                ship_method_id = (ship_method_ids and ship_method_ids[0]) or None
                for item in response['info']:
                    if 'cost' in item:
                        self.write(cr, uid, [data.id], {
                                'status_message': '',
                                'shipping_cost': item['cost']
                        }, context=context)
                        sale.write({
                            'shipcharge': float(item['cost']) or 0.00,
                            'ship_method_id':ship_method_id,
                            'status_message': ''
                        })
                        return True

        # Get the view for this particular function.
        mod, modid = self.pool.get('ir.model.data').get_object_reference(
            cr, uid, 'shipping_api_fedex', 'view_for_shipping_rate_wizard_fedex'
        )

        return {
            'name':_("Get Rate"),
            'view_mode': 'form',
            'view_id': modid,
            'view_type': 'form',
            'res_model': 'shipping.rate.wizard',
            'type': 'ir.actions.act_window',
            'target':'new',
            'nodestroy': True,
            'domain': '[]',
            'res_id': ids[0],
            'context':context,
        }

    _columns= {
                    'ship_company_code': fields.selection(_get_company_code, 'Ship Company', method=True, size=64),
                    'fedex_service_type': fields.selection(SERVICES, 'Service Type', size=100),
                    'fedex_container': fields.selection(PACKAGES,'Container', size=100),
                    'fedex_length': fields.float('Length'),
                    'fedex_width':  fields.float('Width'),
                    'fedex_height':  fields.float('Height'),
            }
shipping_rate_wizard()
# vim:expandtab:smartindent:tabstop=4:softtabstop=4:shiftwidth=4: