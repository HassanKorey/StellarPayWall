from stellarpaywall.services.soroban_verifier import verify_sac_transfer
from stellarpaywall.services.verifier import verify_stellar_payment


async def verify_payment(
    tx_hash: str,
    expected_amount: str,
    destination: str,
    expected_asset: str = "XLM",
    challenge_uuid: str | None = None,
) -> bool:
    """
    Verify payment transaction against source accounts, trustlines, destination,
    and replay resistance. Supports both native Stellar Horizon payments and Soroban SAC tokens.
    """
    asset_upper = expected_asset.upper() if expected_asset else "XLM"
    if asset_upper in ("SAC", "USDC") or (expected_asset and expected_asset.startswith("C")):
        return await verify_sac_transfer(
            tx_hash=tx_hash,
            expected_amount=expected_amount,
            destination=destination,
            expected_contract_id=expected_asset if expected_asset.startswith("C") else None,
            challenge_uuid=challenge_uuid,
        )

    return await verify_stellar_payment(
        tx_hash=tx_hash,
        expected_amount=expected_amount,
        destination=destination,
        expected_asset=expected_asset,
        challenge_uuid=challenge_uuid,
    )
