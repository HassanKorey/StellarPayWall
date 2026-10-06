#![cfg(test)]
extern crate std;

use super::*;
use soroban_sdk::{
    testutils::{Address as _, Events},
    token::{Client as TokenClient, StellarAssetClient},
    TryFromVal,
};

fn create_token_contract<'a>(env: &Env, admin: &Address) -> (TokenClient<'a>, StellarAssetClient<'a>) {
    let token_contract_id = env.register_stellar_asset_contract_v2(admin.clone());
    (
        TokenClient::new(env, &token_contract_id.address()),
        StellarAssetClient::new(env, &token_contract_id.address()),
    )
}

#[test]
fn test_full_paywall_vault_lifecycle() {
    let env = Env::default();
    env.mock_all_auths();

    let admin = Address::generate(&env);
    let token_admin = Address::generate(&env);
    let payer = Address::generate(&env);
    let merchant = Address::generate(&env);

    let (token_client, token_asset_client) = create_token_contract(&env, &token_admin);

    // Mint tokens to payer
    token_asset_client.mint(&payer, &1000);
    assert_eq!(token_client.balance(&payer), 1000);

    // Register PaywallVault
    let contract_id = env.register_contract(None, PaywallVault);
    let vault_client = PaywallVaultClient::new(&env, &contract_id);

    // Initialize vault
    vault_client.initialize(&admin, &token_client.address);

    // Request ID for HTTP 402 challenge
    let request_id = Symbol::new(&env, "req_a1b2c3d4");
    let payment_amount: i128 = 50; // e.g. 0.05 XLM or USDC in scaled units

    // Pay for resource
    let record = vault_client.pay_for_resource(&payer, &request_id, &payment_amount);
    assert!(record.paid);
    assert_eq!(record.amount, payment_amount);
    assert_eq!(record.payer, payer);

    // Balances check
    assert_eq!(token_client.balance(&payer), 950);
    assert_eq!(token_client.balance(&contract_id), 50);

    // Query payment status
    let status = vault_client.get_payment_status(&request_id).expect("Payment record must exist");
    assert!(status.paid);
    assert_eq!(status.amount, payment_amount);
    assert_eq!(status.payer, payer);

    // Verify PaymentVerified event was emitted
    let events = env.events().all();
    assert!(!events.is_empty(), "Events should be emitted");
    let last_event = events.last().unwrap();
    let event_amount = i128::try_from_val(&env, &last_event.2).unwrap();
    assert_eq!(event_amount, payment_amount);

    // Merchant claim balance
    vault_client.claim_merchant_balance(&merchant, &50);
    assert_eq!(token_client.balance(&contract_id), 0);
    assert_eq!(token_client.balance(&merchant), 50);
}

#[test]
fn test_duplicate_payment_rejection() {
    let env = Env::default();
    env.mock_all_auths();

    let admin = Address::generate(&env);
    let token_admin = Address::generate(&env);
    let payer = Address::generate(&env);

    let (token_client, token_asset_client) = create_token_contract(&env, &token_admin);
    token_asset_client.mint(&payer, &1000);

    let contract_id = env.register_contract(None, PaywallVault);
    let vault_client = PaywallVaultClient::new(&env, &contract_id);
    vault_client.initialize(&admin, &token_client.address);

    let request_id = Symbol::new(&env, "req_test_dup");
    vault_client.pay_for_resource(&payer, &request_id, &100);

    // Attempting same request_id payment must fail
    let res = vault_client.try_pay_for_resource(&payer, &request_id, &100);
    assert_eq!(res.err(), Some(Ok(Error::PaymentAlreadyExists)));
}

#[test]
fn test_invalid_amount_rejection() {
    let env = Env::default();
    env.mock_all_auths();

    let admin = Address::generate(&env);
    let token_admin = Address::generate(&env);
    let payer = Address::generate(&env);

    let (token_client, _) = create_token_contract(&env, &token_admin);

    let contract_id = env.register_contract(None, PaywallVault);
    let vault_client = PaywallVaultClient::new(&env, &contract_id);
    vault_client.initialize(&admin, &token_client.address);

    let request_id = Symbol::new(&env, "req_zero");
    let res = vault_client.try_pay_for_resource(&payer, &request_id, &0);
    assert_eq!(res.err(), Some(Ok(Error::InvalidAmount)));

    let res_neg = vault_client.try_pay_for_resource(&payer, &request_id, &-10);
    assert_eq!(res_neg.err(), Some(Ok(Error::InvalidAmount)));
}
