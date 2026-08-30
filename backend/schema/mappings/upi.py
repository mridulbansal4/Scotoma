"""CES to NPCI UPI ReqPay / RespPay fields."""

CES_TO_UPI: dict[str, str] = {
    "vpa_payer": "Payer/@addr",
    "vpa_payee": "Payee/@addr",
    "amount": "Payer/Amount/@value",
    "upi_txn_type": "Txn/@type",
    "mandate_id": "Mandate/@umn",
    "payee_name_match": "Payee/@name verification result",
    "device_binding_id": "DeviceTag/@id",
    "response_code": "Resp/@respCode",
}

UPI_PER_TXN_LIMIT_INR: float = 100_000.0
