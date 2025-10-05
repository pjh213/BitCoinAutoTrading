"""
거래 실행을 담당하는 모듈
"""


class TradeExecutor:
  """거래 실행 클래스"""

  def __init__(self, api, target_coin, buy_amount=10000, sell_ratio=1.0):
    """
    거래 실행기 초기화

    Args:
        api: UpbitAPI 인스턴스
        target_coin (str): 대상 코인 (예: BTC)
        buy_amount (float): 매수 금액
        sell_ratio (float): 매도 비율 (0.0 ~ 1.0)
    """
    self.api = api
    self.target_coin = target_coin
    self.market = f"KRW-{target_coin}"
    self.buy_amount = buy_amount
    self.sell_ratio = sell_ratio

  def execute_buy(self):
    """
    정교한 매수 실행 (리스크 관리 포함)

    Returns:
        bool: 성공 여부
    """
    # 원화 잔고 확인
    krw_balance = self.api.get_balance('KRW')

    if krw_balance < self.buy_amount:
      print(
        f"매수 실패: 원화 잔고 부족 (보유: {krw_balance:,.0f}원, 필요: {self.buy_amount:,.0f}원)")
      return False

    # 현재 가격 확인
    current_price = self.api.get_ticker_price(self.market)
    if current_price == 0:
      print("매수 실패: 현재 가격을 가져올 수 없습니다.")
      return False

    # 급격한 가격 변동 감지 (5분 전 대비 5% 이상 변동 시 주의)
    candles = self.api.get_candles(self.market, 'minutes', 5)
    if len(candles) >= 2:
      recent_candle = candles[0]  # 최신 캔들
      prev_candle = candles[1]  # 이전 캔들

      recent_price = float(recent_candle['trade_price'])
      prev_price = float(prev_candle['trade_price'])

      price_change_rate = abs((recent_price - prev_price) / prev_price)

      if price_change_rate > 0.05:  # 5% 이상 급변동
        print(f"매수 주의: 급격한 가격 변동 감지 ({price_change_rate * 100:.1f}%)")

    # 최소 주문 금액 확인 (업비트 최소 주문: 5,000원)
    if self.buy_amount < 5000:
      print(f"매수 실패: 최소 주문 금액 미달 (최소: 5,000원, 설정: {self.buy_amount:,.0f}원)")
      return False

    print(
      f"매수 주문 실행: {self.buy_amount:,.0f}원 어치 {self.target_coin} @ {current_price:,.0f}원")

    # 실제 주문 실행
    result = self.api.place_buy_order(self.market, self.buy_amount)

    if result:
      # 예상 수량 계산
      expected_volume = self.buy_amount / current_price
      print(f"매수 주문 성공!")
      print(f"  주문 ID: {result.get('uuid', 'N/A')}")
      print(f"  예상 수량: {expected_volume:.8f} {self.target_coin}")
      print(f"  주문 금액: {self.buy_amount:,.0f}원")
      return True
    else:
      print("매수 주문 실패")
      return False

  def execute_sell(self):
    """
    정교한 매도 실행 (리스크 관리 포함)

    Returns:
        bool: 성공 여부
    """
    # 코인 잔고 확인
    coin_balance = self.api.get_balance(self.target_coin)

    if coin_balance <= 0:
      print(f"매도 실패: {self.target_coin} 보유량 없음")
      return False

    # 현재 가격 확인
    current_price = self.api.get_ticker_price(self.market)
    if current_price == 0:
      print("매도 실패: 현재 가격을 가져올 수 없습니다.")
      return False

    # 매도할 수량 계산
    sell_volume = coin_balance * self.sell_ratio

    # 최소 주문 수량 체크 (최소 주문 금액: 5,000원)
    sell_amount = sell_volume * current_price
    if sell_amount < 5000:
      print(f"매도 실패: 최소 주문 금액 미달")
      print(f"  보유량: {coin_balance:.8f} {self.target_coin}")
      print(f"  매도 예정량: {sell_volume:.8f} {self.target_coin}")
      print(f"  예상 금액: {sell_amount:,.0f}원 (최소: 5,000원)")
      return False

    # 수익률 계산 (평균 매수가와 비교)
    accounts = self.api.get_accounts()
    avg_buy_price = 0
    if accounts:
      for account in accounts:
        if account['currency'] == self.target_coin:
          avg_buy_price = float(account['avg_buy_price'])
          break

    if avg_buy_price > 0:
      profit_rate = ((current_price - avg_buy_price) / avg_buy_price) * 100
      profit_amount = (current_price - avg_buy_price) * sell_volume
      print(f"수익률 분석:")
      print(f"  평균 매수가: {avg_buy_price:,.0f}원")
      print(f"  현재가: {current_price:,.0f}원")
      print(f"  수익률: {profit_rate:+.2f}%")
      print(f"  예상 손익: {profit_amount:+,.0f}원")

    print(
      f"매도 주문 실행: {sell_volume:.8f} {self.target_coin} @ {current_price:,.0f}원")
    print(f"예상 매도 금액: {sell_amount:,.0f}원")

    # 실제 주문 실행
    result = self.api.place_sell_order(self.market, sell_volume)

    if result:
      print(f"매도 주문 성공!")
      print(f"  주문 ID: {result.get('uuid', 'N/A')}")
      print(f"  매도 수량: {sell_volume:.8f} {self.target_coin}")
      print(f"  예상 금액: {sell_amount:,.0f}원")
      return True
    else:
      print("매도 주문 실패")
      return False