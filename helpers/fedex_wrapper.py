import base64, logging
logger = logging.getLogger(__name__)
logging.basicConfig(level=logging.INFO)

from collections import namedtuple
from shipping import Package, get_country_code
from .fedex.services.rate_service import FedexRateServiceRequest
from .fedex.services.ship_service import FedexDeleteShipmentRequest, FedexProcessShipmentRequest

PACKAGES = [
    ('FEDEX_BOX', 'FedEx Box'),
    ('FEDEX_PAK', 'FedEx Pak'),
    ('FEDEX_TUBE', 'FedEx Tube'),
    ('YOUR_PACKAGING', 'Custom')
]

SERVICES = [
    ('STANDARD_OVERNIGHT', 'FedEx Standard Overnight'),
    ('PRIORITY_OVERNIGHT', 'FedEx Priority Overnight'),
    ('FEDEX_GROUND', 'FedEx Ground'),
    ('FEDEX_EXPRESS_SAVER', 'FedEx Express Saver')
]

Label = namedtuple("Label", ["tracking", "postage", "label", "format"])

class FedExError(Exception):
    pass
        
class FedEx(object):
    def __init__(self, config):
        self.config = config

    def _prepare_request(self, request, shipper, recipient, package):
        request.RequestedShipment.DropoffType = 'REQUEST_COURIER'
        request.RequestedShipment.PackagingType = 'YOUR_PACKAGING'#package.shape.code

        # Shipper contact info.
        #request.RequestedShipment.Shipper.Contact.PersonName = shipper.name or shipper.company_name
        request.RequestedShipment.Shipper.Contact.CompanyName = shipper.company_name or shipper.name
        request.RequestedShipment.Shipper.Contact.PhoneNumber = shipper.phone

        # Shipper address.
        request.RequestedShipment.Shipper.Address.StreetLines = [shipper.address1, shipper.address2]
        request.RequestedShipment.Shipper.Address.City = shipper.city
        request.RequestedShipment.Shipper.Address.StateOrProvinceCode = shipper.state
        request.RequestedShipment.Shipper.Address.PostalCode = shipper.zip
        request.RequestedShipment.Shipper.Address.CountryCode = shipper.country_code
        request.RequestedShipment.Shipper.Address.Residential = False

        # Recipient contact info.
        request.RequestedShipment.Recipient.Contact.PersonName = recipient.name or recipient.company_name
        request.RequestedShipment.Recipient.Contact.CompanyName = recipient.company_name or ''
        request.RequestedShipment.Recipient.Contact.PhoneNumber = recipient.phone

        # Recipient address
        request.RequestedShipment.Recipient.Address.StreetLines = [recipient.address1, recipient.address2]
        request.RequestedShipment.Recipient.Address.City = recipient.city
        request.RequestedShipment.Recipient.Address.StateOrProvinceCode = recipient.state
        request.RequestedShipment.Recipient.Address.PostalCode = recipient.zip
        request.RequestedShipment.Recipient.Address.CountryCode = recipient.country_code

        # This is needed to ensure an accurate rate quote with the response.
        request.RequestedShipment.Recipient.Address.Residential = recipient.is_residence
        request.RequestedShipment.EdtRequestType = 'NONE'

        # Who pays for the shipment?
        # RECIPIENT, SENDER or THIRD_PARTY
        request.RequestedShipment.ShippingChargesPayment.PaymentType = 'SENDER'

        wsdl_package = request.create_wsdl_object_of_type('RequestedPackageLineItem')
        wsdl_package.PhysicalPackaging = 'BOX'

        wsdl_package.Weight = request.create_wsdl_object_of_type('Weight')
        wsdl_package.Weight.Value = round(package.weight_in_lbs, 2)
        wsdl_package.Weight.Units = 'LB'

        #wsdl_package.Dimensions = request.create_wsdl_object_of_type('Dimensions')
        #wsdl_package.Dimensions.Length = package.length
        #wsdl_package.Dimensions.Width = package.width
        #wsdl_package.Dimensions.Height = package.height
        #wsdl_package.Dimensions.Units = 'IN'

        request.add_package(wsdl_package)

        return request

    def rate(self, package, shipper, recipient, insurance='OFF', insurance_amount=0, delivery_confirmation=False, signature_confirmation=False):
        response = {'info': []}

        # Play nice with the other function signatures, which expect to take lists of packages.
        if not isinstance(package, Package):

            # But not too nice.
            if len(package) > 1:
                raise Exception("Can only take one Package at a time!")

            package = package[0]

        shipper.country_code = get_country_code(shipper.country)
        recipient.country_code = get_country_code(recipient.country)

        rate_request = FedexRateServiceRequest(self.config)
        rate_request = self._prepare_request(rate_request, shipper, recipient, package)
        rate_request.RequestedShipment.ServiceType = None
        rate_request.RequestedShipment.EdtRequestType = 'NONE'
        rate_request.RequestedShipment.PackageDetail = 'INDIVIDUAL_PACKAGES'
        rate_request.RequestedShipment.ShippingChargesPayment.Payor.AccountNumber = self.config.account_number

        seen_quotes = []

        try:
            rate_request.send_request()

            for service in rate_request.response.RateReplyDetails:
                for detail in service.RatedShipmentDetails:
                    response['info'].append({
                        'service': service.ServiceType,
                        'package': service.PackagingType,
                        'delivery_day': '',
                        'cost': float(detail.ShipmentRateDetail.TotalNetFedExCharge.Amount)
                    })

        except Exception as e:
            raise FedExError(e)

        return response

    def label(self, package, shipper, recipient, customs=None, image_format="PNG"):
        shipper.country_code = get_country_code(shipper.country)
        recipient.country_code = get_country_code(recipient.country)
        shipment = self._prepare_request(FedexProcessShipmentRequest(self.config), shipper, recipient, package)
        shipment.RequestedShipment.ServiceType = package.mail_class

        shipment.RequestedShipment.ShippingChargesPayment.Payor.ResponsibleParty.AccountNumber = self.config.account_number

        # Specifies the label type to be returned.
        # LABEL_DATA_ONLY or COMMON2D
        shipment.RequestedShipment.LabelSpecification.LabelFormatType = 'COMMON2D'

        # Specifies which format the label file will be sent to you in.
        # DPL, EPL2, PDF, PNG, ZPLII
        shipment.RequestedShipment.LabelSpecification.ImageType = image_format
        shipment.RequestedShipment.LabelSpecification.LabelStockType = 'STOCK_4X6' if image_format == 'EPL2' else 'PAPER_4X6'
        shipment.RequestedShipment.LabelSpecification.LabelPrintingOrientation = 'BOTTOM_EDGE_OF_TEXT_FIRST'

        if customs:
            customs_label = shipment.create_wsdl_object_of_type('AdditionalLabelsDetail')
            customs_label.Type = 'CUSTOMS'
            customs_label.Count = 1
            shipment.AdditionalLabels.append(customs_label)

            wsdl_customs = shipment.create_wsdl_object_of_type('CustomsClearanceDetail')
            wsdl_customs.CustomsValue = shipment.create_wsdl_object_of_type('Money')
            wsdl_customs.CustomsValue.Currency = 'USD'
            wsdl_customs.CustomsValue.Amount = package.value

            for item in sorted(customs.items, key=lambda i: i.value, reverse=True):
                wsdl_item = shipment.create_wsdl_object_of_type('Commodity')
                wsdl_item.CustomsValue = shipment.create_wsdl_object_of_type('Money')
                wsdl_item.CustomsValue.Amount = item.value
                wsdl_item.CustomsValue.Currency = 'USD'
                wsdl_item.NumberOfPieces = item.quantity
                wsdl_item.CountryOfManufacture = item.country_of_origin
                wsdl_item.Description = item.description
                wsdl_item.Weight = round(item.weight, 2)
                wsdl_customs.Commodities.append(wsdl_item)

            shipment.CustomsClearanceDetail = wsdl_customs

        try:
            shipment.send_request()

        except Exception as e:
            return {"error": str(e)}

        tracking = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].TrackingIds[0].TrackingNumber
        net_cost = shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].PackageRating.PackageRateDetails[0].NetCharge.Amount

        return Label(
            postage=net_cost, tracking=tracking, format=[image_format],
            label=[base64.b64decode(shipment.response.CompletedShipmentDetail.CompletedPackageDetails[0].Label.Parts[0].Image)]
        )

    def cancel(self, tracking_no, **kwargs):
        delete = FedexDeleteShipmentRequest(self.config)
        delete.DeletionControlType = "DELETE_ALL_PACKAGES"
        delete.TrackingId.TrackingNumber = tracking_no

        try:
            delete.send_request()
            return delete.response

        except Exception as e:
            raise FedExError(e)