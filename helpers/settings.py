from .fedex.config import FedexConfig

FEDEX_CONFIG = FedexConfig(
    'key', 'password',
    account_number="your account number",
    meter_number="your meter number",
    integrator_id="your integrator ID",
    use_test_server=True
)