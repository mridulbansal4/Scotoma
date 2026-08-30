"""CES to ISO 20022 pacs.008 element names, for the SEPA Instant and ACH rails."""

CES_TO_PACS008: dict[str, str] = {
    "uetr": "GrpHdr/MsgId + PmtId/UETR",
    "amount": "CdtTrfTxInf/IntrBkSttlmAmt",
    "currency": "CdtTrfTxInf/IntrBkSttlmAmt@Ccy",
    "settlement_ts": "GrpHdr/IntrBkSttlmDt",
    "debtor_agent_bic": "DbtrAgt/FinInstnId/BICFI",
    "creditor_agent_bic": "CdtrAgt/FinInstnId/BICFI",
    "payer_entity_id": "Dbtr/Id/OrgId/Othr/Id",
    "payee_entity_id": "Cdtr/Id/OrgId/Othr/Id",
    "remittance_ref": "RmtInf/Ustrd",
    "return_code": "pacs.004 TxInfAndSts/StsRsnInf/Rsn/Cd",
}
