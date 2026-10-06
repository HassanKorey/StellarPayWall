#![no_std]

use soroban_sdk::{
    contract, contracterror, contractimpl, contracttype, symbol_short, token, Address, Env, Symbol,
};

#[contracterror]
#[derive(Copy, Clone, Debug, Eq, PartialEq, PartialOrd, Ord)]
#[repr(u32)]
pub enum Error {
    AlreadyInitialized = 1,
    NotInitialized = 2,
    InvalidAmount = 3,
    PaymentAlreadyExists = 4,
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub enum DataKey {
    Admin,
    Token,
    Payment(Symbol),
}

#[contracttype]
#[derive(Clone, Debug, Eq, PartialEq)]
pub struct PaymentRecord {
    pub paid: bool,
    pub amount: i128,
    pub payer: Address,
    pub timestamp: u64,
}

#[contract]
pub struct PaywallVault;

#[contractimpl]
impl PaywallVault {
    /// Initialize the vault with an admin and the accepted token address (e.g. SAC USDC or XLM).
    pub fn initialize(env: Env, admin: Address, token: Address) -> Result<(), Error> {
        if env.storage().instance().has(&DataKey::Admin) {
            return Err(Error::AlreadyInitialized);
        }

        env.storage().instance().set(&DataKey::Admin, &admin);
        env.storage().instance().set(&DataKey::Token, &token);

        Ok(())
    }

    /// Process payment for an HTTP 402 resource challenge.
    /// Emits `PaymentVerified` event containing the request UUID (`request_id`) and amount.
    pub fn pay_for_resource(
        env: Env,
        payer: Address,
        request_id: Symbol,
        amount: i128,
    ) -> Result<PaymentRecord, Error> {
        if amount <= 0 {
            return Err(Error::InvalidAmount);
        }

        payer.require_auth();

        if !env.storage().instance().has(&DataKey::Admin) {
            return Err(Error::NotInitialized);
        }

        let payment_key = DataKey::Payment(request_id.clone());
        if env.storage().persistent().has(&payment_key) {
            return Err(Error::PaymentAlreadyExists);
        }

        let token_address: Address = env.storage().instance().get(&DataKey::Token).unwrap();
        let token_client = token::Client::new(&env, &token_address);

        // Transfer funds from payer to vault contract
        token_client.transfer(&payer, &env.current_contract_address(), &amount);

        let record = PaymentRecord {
            paid: true,
            amount,
            payer: payer.clone(),
            timestamp: env.ledger().timestamp(),
        };

        env.storage().persistent().set(&payment_key, &record);

        // Emit PaymentVerified event: topics = ("PaymentVerified", request_id), data = amount
        env.events().publish(
            (Symbol::new(&env, "PaymentVerified"), request_id),
            amount,
        );

        Ok(record)
    }

    /// Allows the merchant admin to withdraw accumulated balance from the vault.
    pub fn claim_merchant_balance(
        env: Env,
        merchant: Address,
        amount: i128,
    ) -> Result<(), Error> {
        if amount <= 0 {
            return Err(Error::InvalidAmount);
        }

        let admin: Address = env
            .storage()
            .instance()
            .get(&DataKey::Admin)
            .ok_or(Error::NotInitialized)?;

        admin.require_auth();

        let token_address: Address = env
            .storage()
            .instance()
            .get(&DataKey::Token)
            .ok_or(Error::NotInitialized)?;

        let token_client = token::Client::new(&env, &token_address);
        token_client.transfer(&env.current_contract_address(), &merchant, &amount);

        // Emit MerchantClaimed event
        env.events().publish(
            (symbol_short!("claimed"), merchant),
            amount,
        );

        Ok(())
    }

    /// Query verification and payment status for a specific request UUID.
    pub fn get_payment_status(env: Env, request_id: Symbol) -> Option<PaymentRecord> {
        let payment_key = DataKey::Payment(request_id);
        env.storage().persistent().get(&payment_key)
    }
}

#[cfg(test)]
mod test;
