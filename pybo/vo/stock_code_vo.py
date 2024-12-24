class StockInfoVO:
    def __init__(self, stockcode, secondcode, stockname, stdprice):
        self.stockcode = stockcode
        self.secondcode = secondcode
        self.stockname = stockname
        self.stdprice = stdprice


class ChartinfoVO:
    def __init__(self, no, stockcode, date, beginval, highval, lowval, endval, changeval, tradeval, tradesum, changesum, changesign, chagevol):
        self.no = no            # 번호
        self.stockcode = stockcode  # 주식코드
        self.date = date        # 날짜
        self.beginval = beginval    # 시가
        self.highval = highval    # 고가
        self.lowval = lowval    # 저가
        self.endval = endval    # 종가
        self.changeval = changeval  # 전일비
        self.tradeval = tradeval    # 거래량
        self.tradesum = tradesum    # 거래대금
        self.changesum = changesum  # 누적체결수량
        self.changesign = changesign  # 등락구분
        self.chagevol = chagevol    # 거래회전율

class KeyToken:
    static_key = ""
    static_token = ""
    def __init__(self,value):
        self.value = value #인스턴스 변수 
