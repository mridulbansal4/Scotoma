"""CES field to ISO 8583 data element. DE41 is the terminal id (8 chars), DE42 the
card-acceptor / merchant id (15 chars), DE43 the card-acceptor name and location."""

CES_TO_DE: dict[str, str] = {
    "pan_token": "DE2",
    "processing_code": "DE3",
    "amount": "DE4",
    "mcc": "DE18",
    "pos_entry_mode": "DE22",
    "acquirer_id": "DE32",
    "response_code": "DE39",
    "terminal_id": "DE41",
    "merchant_id": "DE42",
    "merchant_country": "DE43",
}

DE39_CODES: dict[str, str] = {
    "00": "Approved",
    "05": "Do not honor",
    "14": "Invalid card number",
    "51": "Insufficient funds",
    "54": "Expired card",
    "57": "Transaction not permitted",
    "59": "Suspected fraud",
    "61": "Exceeds withdrawal limit",
    "65": "Exceeds activity count limit",
    "82": "CVV failure",
    "91": "Issuer unavailable",
}

DE39_RETRY_CLASS: dict[str, str] = {
    "05": "soft",
    "14": "hard",
    "51": "soft",
    "54": "hard",
    "57": "hard",
    "59": "hard",
    "61": "soft",
    "65": "soft",
    "82": "hard",
    "91": "soft",
}

POS_ENTRY_MODES: dict[str, str] = {
    "812": "e-commerce",
    "051": "chip and PIN",
    "071": "contactless, no PIN",
    "901": "magnetic stripe fallback",
}

MTI_CODES: frozenset[str] = frozenset({"0100", "0110", "0120", "0200", "0210", "0400", "0420"})
