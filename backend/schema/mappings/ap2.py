"""CES to AP2 three-mandate concepts.

Modelling disclaimer: these field names are PayLoop's schema modelling of concepts that
exist in the AP2 and ACP specifications. They are not verbatim spec field names. The
underlying primitive is real — the cart hash is bound into the Payment Mandate, so
post-approval mutation breaks signature verification.
"""

CES_TO_AP2: dict[str, str] = {
    "intent_mandate_id": "Intent Mandate (mandate 1): what the user authorised in principle",
    "cart_mandate_id": "Cart Mandate (mandate 2): the specific basket the user approved",
    "payment_mandate_id": "Payment Mandate (mandate 3): the credential presented to the issuer",
    "cart_hash_at_intent": "digest bound into the Cart Mandate at signing time",
    "cart_hash_at_settle": "digest of the basket actually presented at settlement",
    "human_present_flag": "human-present signal the issuer risk engine ingests",
    "mandate_amount_max": "spend ceiling carried on the Intent Mandate",
    "mandate_merchant_allowlist": "merchant scope carried on the Intent Mandate",
    "mandate_nonce": "replay-protection nonce on the Payment Mandate",
    "agent_attestation_valid": "agent attestation result (Visa TAP / Web Bot Auth shape)",
}

AP2_PROTOCOLS: frozenset[str] = frozenset({"AP2", "ACP", "x402", "TAP"})
