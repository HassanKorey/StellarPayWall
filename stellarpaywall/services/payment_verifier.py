
from stellarpaywall.services.verifier import verify_stellar_payment


async def verify_payment(
    tx_hash: str,
    expected_amount: str,
    destination: str,
    expected_asset: str = "XLM",
    challenge_uuid: str | None = None
) -> bool:
    """
    Verify payment transaction against source accounts, trustlines, destination,
    and replay resistance.
    """
    return await verify_stellar_payment(
        tx_hash=tx_hash,
        expected_amount=expected_amount,
        destination=destination,
        expected_asset=expected_asset,
        challenge_uuid=challenge_uuid
    )
