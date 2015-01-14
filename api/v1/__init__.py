u"""
Defines public methods and classes for other modules to use.
Breaking changes are never introduced within a version.

"""
from openerp import pooler
from ...helpers import fedex_wrapper, shipping, settings, label
from ...helpers.fedex.config import FedexConfig

def get_config(cr, uid, sale=None, logistic_company_id=None, context=None, config=None, test=False):
    """Returns the FedEx configuration relevant to the given object."""

    if not config and sale and sale.fedex_shipper_id:
        config = sale.fedex_shipper_id

    if not config and logistic_company_id:
        log_comp = pooler.get_pool('logistic.company').browse(cr, uid, logistic_company_id, context=context)
        config = log_comp.fedex_account_shipping_id if log_comp else None

    if not config and sale:
        config = sale.company_id.fedex_account_shipping_id

    if not config:
        # Just go by uid.
        user_pool = pooler.get_pool(cr.dbname).get("res.users")
        user = user_pool.browse(cr, uid, uid, context=context)
        config = user.company_id.fedex_account_shipping_id

    if config:

        return FedexConfig(
            config.key, config.password,
            account_number=config.account_number,
            meter_number=config.meter_number,
            integrator_id=config.integrator_id,
            use_test_server=config.sandbox or test
        )

    return settings.FEDEX_CONFIG
    
def get_quotes(config, package, sale=None, from_address=None, to_address=None, **kwargs):
    """Calculates the cost of shipping for all FedEx's services."""

    # Get the shipper and recipient addresses for this order.
    if sale:
        from_address = sale.company_id.partner_id
        to_address = sale.partner_shipping_id or ''
        from_address.state = from_address.state_id.code
        from_address.country = from_address.country_id.name
        to_address.state = to_address.state_id.code
        to_address.country = to_address.country_id.name

    shipper = shipping.Address(
        name=from_address.name, address=from_address.street,
        address2=from_address.street2, city=from_address.city,
        state=from_address.state_id.code, zip=from_address.zip,
        country=from_address.country_id.code
    )

    recipient = shipping.Address(
        name=to_address.name, address=to_address.street,
        address2=to_address.street2, city=to_address.city,
        state=to_address.state_id.code, zip=to_address.zip,
        country=to_address.country_id.code
    )

    if sale.fedex_shipper_id:
        test = sale.fedex_shipper_id.sandbox

    # Set up our API client, get our rates, and construct our return value.
    api = fedex_wrapper.FedEx(config)

    fedex_package = shipping.Package(
        package.weight, package.length, package.width, package.height
    )

    response = api.rate(fedex_package, shipper, recipient)

    return [
        {"company": "FedEx", "container": item["package"], "service": item['service'], "price": item["cost"]}
        for item in response['info']
    ]


def get_label(config, package, service, picking=None, from_address=None, to_address=None, customs=None, test=None,
              image_format="EPL2"):
    try:
        return label.Label(package, picking=picking, from_address=from_address, to_address=to_address,
                           customs=customs, config=config, test=test
        ).get(service, image_format=image_format)
    except Exception as e:
        return {"success": False, "error": str(e)}


def cancel_shipping(config, package, shipper=None, test=None):
    return fedex_wrapper.FedEx(config).cancel(package.tracking_no)