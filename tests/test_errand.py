from sendrelay import Errand

BANK = {"latitude": 6.4281, "longitude": 3.4219, "address": "GTBank, Adeola Odeku"}
SHOP = {"latitude": 6.4433, "longitude": 3.4796, "address": "Shoprite, Lekki"}
HOME = {"latitude": 6.4474, "longitude": 3.4723, "address": "22 Admiralty Way"}


def test_builders_make_the_stages_you_could_write_by_hand() -> None:
    assert Errand.queue(BANK, instructions="Collect the token", expectedMinutes=30, maxMinutes=90) == {
        "type": "QUEUE",
        "location": BANK,
        "instructions": "Collect the token",
        "expectedMinutes": 30,
        "maxMinutes": 90,
    }
    assert Errand.purchase(
        SHOP, [{"name": "Peak milk 400g", "quantity": 2, "maxUnitPrice": 350_000}], spendLimit=2_500_000
    ) == {
        "type": "PURCHASE",
        "location": SHOP,
        "instructions": "",
        "spendLimit": 2_500_000,
        "items": [{"name": "Peak milk 400g", "quantity": 2, "maxUnitPrice": 350_000}],
    }
    assert Errand.dropoff(HOME, contact={"name": "Ada", "phone": "+2348030000000"}) == {
        "type": "DROPOFF",
        "location": HOME,
        "instructions": "",
        "contact": {"name": "Ada", "phone": "+2348030000000"},
    }


def test_builders_put_required_fields_where_the_api_reads_them() -> None:
    payment = Errand.payment(BANK, "Eko Electricity", 1_500_000, billReference="0123456789")
    assert (payment["type"], payment["payee"], payment["amount"], payment["billReference"]) == (
        "PAYMENT",
        "Eko Electricity",
        1_500_000,
        "0123456789",
    )
    assert Errand.inspection(SHOP, [{"type": "PHOTO", "text": "The shelf"}])["questions"] == [
        {"type": "PHOTO", "text": "The shelf"}
    ]
    assert Errand.custom(HOME, "Hand the keys to the gateman", "S") == {
        "type": "CUSTOM",
        "location": HOME,
        "instructions": "Hand the keys to the gateman",
        "effort": "S",
    }
