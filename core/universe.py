"""Initial stock universe adapted from PyTerm."""

STOCK_GROUPS = {
    "tsx": [
        "SHOP.TO", "RY.TO", "TD.TO", "ENB.TO", "BNS.TO",
        "CNQ.TO", "BMO.TO", "CNR.TO", "TRP.TO", "CM.TO",
        "MFC.TO", "SU.TO", "BCE.TO", "NTR.TO", "SLF.TO",
        "ATD.TO", "POW.TO", "FTS.TO", "QSR.TO", "FNV.TO",
        "WCN.TO", "BAM.TO", "GWO.TO", "IMO.TO", "CP.TO",
        "GIB-A.TO", "CVE.TO", "NA.TO", "AEM.TO", "MG.TO",
        "TIH.TO", "EMA.TO", "L.TO", "IFC.TO", "AP-UN.TO",
        "WN.TO", "CTC-A.TO", "DOL.TO", "AQN.TO",
        "BIP-UN.TO", "TRI.TO", "CGX.TO", "NFI.TO",
        "CSU.TO", "BIR.TO", "TOU.TO", "CAR-UN.TO",
        "ENGH.TO", "BHC.TO", "H.TO", "ZEB.TO",
        "XFN.TO", "HEWB.TO", "TBNK.TO", "HCAL.TO",
        "HBNK.TO", "ZWB.TO", "CIC.TO", "RBNK.TO",
        "HCA.TO"
    ],

    "nyse": [
        "AAPL", "MSFT", "AMZN", "JNJ", "JPM", "V",
        "PG", "XOM", "UNH", "HD", "MA", "KO", "PEP",
        "PFE", "CVX", "MRK", "BAC", "DIS", "NVDA",
        "VZ", "ADBE", "NFLX", "ABT", "CMCSA",
        "INTC", "WMT", "T", "CSCO", "NKE", "ORCL",
        "PYPL", "TMO", "CRM", "COST", "DHR", "ACN",
        "MCD", "WFC", "C", "LIN", "MDT", "PM", "TXN",
        "UPS", "QCOM", "NEE", "HON", "IBM", "BMY",
        "LOW", "LLY", "RTX", "UNP", "GS", "CAT",
        "AMGN", "BA", "AMT", "SPGI", "LMT", "NOW",
        "INTU", "CVS", "MDLZ", "ADI", "ZTS",
        "SBUX", "BLK", "BKNG", "ADP", "ISRG",
        "DE", "EL", "MMM", "PLD", "TGT", "GE",
        "CL", "MMC", "SYK", "AXP", "MO", "CI",
        "CB", "CME", "PNC", "USB", "DUK", "SO",
        "CCI", "APD", "EQIX", "NSC", "ITW",
        "BDX", "SHW", "TFC", "REGN", "GM",
        "FDX", "EW", "COF", "COP", "BK", "STT",
        "MTB", "FITB", "RF", "HBAN", "KEY",
        "CFG", "CMA", "VLY", "WAL", "ZION",
        "AIG", "MET", "PRU", "AFL", "ALL",
        "TRV", "HIG", "GNW", "LNC", "PGR",
        "CINF", "WRB", "RNR", "AXS"
    ],

    "nas": [
        "GOOG", "META", "NFLX", "TSLA", "NVDA",
        "AMD", "INTC", "AAPL", "AMZN", "MSFT",
        "ADBE", "CSCO", "PEP", "COST", "QCOM",
        "TXN", "AVGO", "SBUX", "AMAT", "PYPL",
        "HON", "INTU", "BKNG", "ADI", "LRCX",
        "MDLZ", "MU", "VRTX", "GILD", "MNST",
        "ISRG", "MELI", "REGN", "PANW", "KDP",
        "CTAS", "ADSK", "FTNT", "NXPI", "KHC",
        "MAR", "SNPS", "PDD", "KLAC", "ORLY",
        "ROST", "MRNA", "ODFL", "EXC", "PAYX",
        "EA", "PCAR", "WBD", "WDAY", "BIDU",
        "CSX", "IDXX", "TEAM", "ILMN", "CRWD",
        "ABNB", "CHTR", "XEL", "DLTR", "FAST",
        "ALGN", "VRSK", "CDNS", "AZN", "EBAY",
        "BIIB", "SIRI", "SWKS", "TTWO", "TTD",
        "FANG", "ZS", "RIVN", "ON", "OKTA",
        "DDOG", "DOCU", "ZM", "LULU", "NTES",
        "SGEN", "CEG", "MRVL", "EXPE", "ANSS",
        "WBA", "SWAV", "MTCH", "CERN", "CHKP",
        "LCID", "CPRT", "RBLX"
    ]
}


def get_universe(exchange="All"):
    if exchange == "All":
        groups = STOCK_GROUPS
    else:
        key = exchange.lower()
        groups = {
            key: STOCK_GROUPS.get(key, [])
        }

    seen = set()
    output = []

    for group, tickers in groups.items():
        for ticker in tickers:
            if ticker not in seen:
                seen.add(ticker)
                output.append(
                    (ticker, group.upper())
                )

    return output