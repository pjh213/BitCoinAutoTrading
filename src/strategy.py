"""
트레이딩 전략을 담당하는 모듈
"""
import time
from datetime import datetime
from .utils import (
  calculate_moving_average,
  calculate_ema,
  calculate_rsi,
  calculate_volume_ma
)
from .trader import TradeExecutor


class GridTradingStrategy:
  """그리드 트레이딩 전략"""

  def __init__(self, api, target_coin, grid_count=10, grid_range=0.05,
      order_amount=5000, base_price=None, check_interval=10):
    """
    그리드 트레이딩 봇 초기화

    Args:
        api: UpbitAPI 인스턴스
        target_coin (str): 매매할 코인 (예: BTC)
        grid_count (int): 그리드 개수
        grid_range (float): 그리드 범위 (예: 0.05 = ±5%)
        order_amount (float): 각 그리드당 주문 금액
        base_price (float): 기준 가격 (None이면 현재가)
        check_interval (int): 체크 주기 (초)
    """
    self.api = api
    self.target_coin = target_coin
    self.market = f"KRW-{target_coin}"
    self.is_running = False

    # 그리드 설정
    self.grid_count = grid_count
    self.grid_range = grid_range
    self.order_amount = order_amount
    self.base_price = base_price
    self.check_interval = check_interval

    # 그리드 데이터
    self.buy_grids = []  # 매수 그리드 가격 리스트
    self.sell_grids = []  # 매도 그리드 가격 리스트
    self.executed_buys = set()  # 실행된 매수 그리드 추적
    self.executed_sells = set()  # 실행된 매도 그리드 추적

    # 그리드 초기화
    self._initialize_grids()

  def _initialize_grids(self):
    """그리드 가격대 초기화"""
    # 기준 가격 설정
    if self.base_price is None:
      current_price = self.api.get_ticker_price(self.market)
      if current_price == 0:
        raise ValueError("현재 가격을 가져올 수 없습니다.")
      self.base_price = current_price

    print(f"그리드 기준 가격: {self.base_price:,.0f}원")

    # 그리드 간격 계산
    grid_step = (self.base_price * self.grid_range) / (self.grid_count / 2)

    # 매수 그리드 생성 (기준가보다 낮은 가격대)
    self.buy_grids = []
    for i in range(1, (self.grid_count // 2) + 1):
      buy_price = self.base_price - (grid_step * i)
      self.buy_grids.append(buy_price)

    # 매도 그리드 생성 (기준가보다 높은 가격대)
    self.sell_grids = []
    for i in range(1, (self.grid_count // 2) + 1):
      sell_price = self.base_price + (grid_step * i)
      self.sell_grids.append(sell_price)

    # 그리드 정렬
    self.buy_grids.sort(reverse=True)  # 높은 가격부터 (기준가에 가까운 순)
    self.sell_grids.sort()  # 낮은 가격부터 (기준가에 가까운 순)

    print(f"\n=== 그리드 설정 완료 ===")
    print(f"매수 그리드 ({len(self.buy_grids)}개):")
    for i, price in enumerate(self.buy_grids):
      print(
        f"  {i + 1}. {price:,.0f}원 ({((price / self.base_price - 1) * 100):+.2f}%)")

    print(f"매도 그리드 ({len(self.sell_grids)}개):")
    for i, price in enumerate(self.sell_grids):
      print(
        f"  {i + 1}. {price:,.0f}원 ({((price / self.base_price - 1) * 100):+.2f}%)")
    print("=" * 30)

  def _check_buy_signals(self, current_price):
    """매수 신호 체크"""
    buy_signals = []

    for grid_price in self.buy_grids:
      if (current_price <= grid_price and
          grid_price not in self.executed_buys):
        buy_signals.append(grid_price)

    return buy_signals

  def _check_sell_signals(self, current_price):
    """매도 신호 체크"""
    sell_signals = []

    # 코인 보유량 확인
    coin_balance = self.api.get_balance(self.target_coin)
    if coin_balance <= 0:
      return sell_signals

    for grid_price in self.sell_grids:
      if (current_price >= grid_price and
          grid_price not in self.executed_sells):
        sell_signals.append(grid_price)

    return sell_signals

  def _execute_grid_buy(self, grid_price):
    """그리드 매수 실행"""
    # 원화 잔고 확인
    krw_balance = self.api.get_balance('KRW')

    if krw_balance < self.order_amount:
      print(
        f"매수 실패: 원화 잔고 부족 (보유: {krw_balance:,.0f}원, 필요: {self.order_amount:,.0f}원)")
      return False

    print(f"그리드 매수 실행: {self.order_amount:,.0f}원 어치 @ {grid_price:,.0f}원")

    result = self.api.place_buy_order(self.market, self.order_amount)

    if result:
      self.executed_buys.add(grid_price)
      print(f"그리드 매수 성공: {grid_price:,.0f}원")
      return True
    else:
      print(f"그리드 매수 실패: {grid_price:,.0f}원")
      return False

  def _execute_grid_sell(self, grid_price):
    """그리드 매도 실행"""
    # 코인 잔고 확인
    coin_balance = self.api.get_balance(self.target_coin)

    if coin_balance <= 0:
      print(f"매도 실패: {self.target_coin} 보유량 없음")
      return False

    # 매도할 수량 계산 (총 보유량을 그리드 개수로 나눈 만큼)
    sell_volume = coin_balance / len(self.sell_grids)

    # 최소 주문 수량 체크 (대략적으로 1000원 이상)
    current_price = self.api.get_ticker_price(self.market)
    if sell_volume * current_price < 1000:
      print(f"매도 실패: 주문 금액이 너무 작음 ({sell_volume * current_price:,.0f}원)")
      return False

    print(
      f"그리드 매도 실행: {sell_volume:.8f} {self.target_coin} @ {grid_price:,.0f}원")

    result = self.api.place_sell_order(self.market, sell_volume)

    if result:
      self.executed_sells.add(grid_price)
      print(f"그리드 매도 성공: {grid_price:,.0f}원")
      return True
    else:
      print(f"그리드 매도 실패: {grid_price:,.0f}원")
      return False

  def _reset_executed_grids(self, current_price):
    """실행된 그리드 초기화 (가격이 그리드를 역방향으로 지날 때)"""
    # 매수 그리드 초기화 (현재가가 그리드 위로 올라가면)
    reset_buys = set()
    for grid_price in self.executed_buys:
      if current_price > grid_price:
        reset_buys.add(grid_price)

    if reset_buys:
      self.executed_buys -= reset_buys
      print(f"매수 그리드 {len(reset_buys)}개 초기화됨")

    # 매도 그리드 초기화 (현재가가 그리드 아래로 내려가면)
    reset_sells = set()
    for grid_price in self.executed_sells:
      if current_price < grid_price:
        reset_sells.add(grid_price)

    if reset_sells:
      self.executed_sells -= reset_sells
      print(f"매도 그리드 {len(reset_sells)}개 초기화됨")

  def run_once(self):
    """한 번의 그리드 트레이딩 사이클 실행"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_price = self.api.get_ticker_price(self.market)

    if current_price == 0:
      print("현재 가격을 가져올 수 없습니다.")
      return

    print(f"\n[{current_time}] {self.market} 현재가: {current_price:,.0f}원")
    print(f"기준가 대비: {((current_price / self.base_price - 1) * 100):+.2f}%")

    # 실행된 그리드 초기화 체크
    self._reset_executed_grids(current_price)

    # 매수 신호 체크 및 실행
    buy_signals = self._check_buy_signals(current_price)
    for grid_price in buy_signals:
      self._execute_grid_buy(grid_price)

    # 매도 신호 체크 및 실행
    sell_signals = self._check_sell_signals(current_price)
    for grid_price in sell_signals:
      self._execute_grid_sell(grid_price)

    if not buy_signals and not sell_signals:
      print("그리드 신호 없음 (대기 중)")

    # 현재 상태 출력
    print(f"실행된 매수 그리드: {len(self.executed_buys)}개")
    print(f"실행된 매도 그리드: {len(self.executed_sells)}개")

  def start(self):
    """그리드 트레이딩 시작"""
    self.is_running = True
    print(f"=== {self.target_coin} 그리드 트레이딩 시작 ===")
    print(f"그리드 개수: {self.grid_count}개")
    print(f"그리드 범위: ±{self.grid_range * 100}%")
    print(f"주문 금액: {self.order_amount:,.0f}원")
    print(f"체크 주기: {self.check_interval}초")
    print("Ctrl+C로 중지할 수 있습니다.\n")

    try:
      while self.is_running:
        self.run_once()

        # 다음 체크까지 대기
        print(f"{self.check_interval}초 후 다시 체크...")
        time.sleep(self.check_interval)

    except KeyboardInterrupt:
      print("\n그리드 트레이딩을 중지합니다.")
      self.is_running = False
    except Exception as e:
      print(f"예상치 못한 오류 발생: {e}")
      self.is_running = False


class MovingAverageStrategy:
  """이동평균 교차 전략"""

  def __init__(self, api, target_coin, buy_amount=10000, sell_ratio=1.0,
      check_interval=60):
    """
    이동평균 전략 봇 초기화

    Args:
        api: UpbitAPI 인스턴스
        target_coin (str): 매매할 코인 (예: BTC)
        buy_amount (float): 매수 금액
        sell_ratio (float): 매도 비율
        check_interval (int): 체크 주기 (초)
    """
    self.api = api
    self.target_coin = target_coin
    self.market = f"KRW-{target_coin}"
    self.is_running = False
    self.check_interval = check_interval

    # 거래 실행기
    self.executor = TradeExecutor(api, target_coin, buy_amount, sell_ratio)

  def analyze_market(self):
    """
    고급 이동평균선 교차 전략을 사용한 시장 분석

    Returns:
        str: 'BUY', 'SELL', 'HOLD'
    """
    # 캔들 데이터 조회
    candles = self.api.get_candles(self.market, 'minutes', 100)
    if len(candles) < 60:
      print("충분한 캔들 데이터가 없습니다.")
      return 'HOLD'

    # 최신 데이터가 앞에 오므로 뒤집기
    candles = list(reversed(candles))

    # 가격 데이터 추출
    close_prices = [float(candle['trade_price']) for candle in candles]
    volumes = [float(candle['candle_acc_trade_volume']) for candle in candles]

    current_price = close_prices[-1]
    current_volume = volumes[-1]

    # === 1. 이동평균선 계산 ===
    sma_5 = calculate_moving_average(close_prices, 5)  # 단기
    sma_20 = calculate_moving_average(close_prices, 20)  # 중기
    sma_60 = calculate_moving_average(close_prices, 60)  # 장기
    ema_12 = calculate_ema(close_prices, 12)  # 단기 EMA
    ema_26 = calculate_ema(close_prices, 26)  # 장기 EMA

    # === 2. 이전 이동평균선 계산 (교차 확인용) ===
    prev_sma_5 = calculate_moving_average(close_prices[:-1], 5)
    prev_sma_20 = calculate_moving_average(close_prices[:-1], 20)

    if len(close_prices) >= 13:
      prev_ema_12 = calculate_ema(close_prices[:-1], 12)
    else:
      prev_ema_12 = None
    if len(close_prices) >= 27:
      prev_ema_26 = calculate_ema(close_prices[:-1], 26)
    else:
      prev_ema_26 = None

    # === 3. RSI 계산 ===
    rsi = calculate_rsi(close_prices, 14)

    # === 4. 거래량 분석 ===
    volume_ma = calculate_volume_ma(candles, 20)
    if volume_ma and volume_ma > 0:
      volume_ratio = current_volume / volume_ma
    else:
      volume_ratio = 1

    # 필수 지표들이 없으면 HOLD
    if None in [sma_5, sma_20, sma_60, ema_12, ema_26, prev_sma_5, prev_sma_20]:
      print("기술적 지표 계산 불가")
      return 'HOLD'

    print(f"\n=== 기술적 분석 결과 ===")
    print(f"현재가: {current_price:,.0f}원")
    print(f"SMA5: {sma_5:,.0f}원, SMA20: {sma_20:,.0f}원, SMA60: {sma_60:,.0f}원")
    print(f"EMA12: {ema_12:,.0f}원, EMA26: {ema_26:,.0f}원")
    print(f"RSI: {rsi:.1f}" if rsi else "RSI: N/A")
    print(f"거래량 비율: {volume_ratio:.2f}x")

    # === 5. 매수 신호 조건들 ===
    buy_signals = []

    # 골든크로스 (단기 이평이 중기 이평을 상향 돌파)
    if prev_sma_5 <= prev_sma_20 and sma_5 > sma_20:
      buy_signals.append("골든크로스(SMA5/20)")

    # EMA 골든크로스
    if (prev_ema_12 is not None and prev_ema_26 is not None and
        ema_12 is not None and ema_26 is not None and
        prev_ema_12 <= prev_ema_26 and ema_12 > ema_26):
      buy_signals.append("EMA골든크로스(12/26)")

    # 상승 추세 확인
    trend_bullish = current_price > sma_60

    # RSI 과매도 반등
    rsi_oversold_bounce = rsi and rsi > 35 and rsi < 70

    # 거래량 증가
    volume_surge = volume_ratio >= 1.2

    # 단기 이평이 모두 상승 배열
    ma_alignment_bullish = sma_5 > sma_20 > sma_60

    # === 6. 매도 신호 조건들 ===
    sell_signals = []

    # 데드크로스
    if prev_sma_5 >= prev_sma_20 and sma_5 < sma_20:
      sell_signals.append("데드크로스(SMA5/20)")

    # EMA 데드크로스
    if (prev_ema_12 is not None and prev_ema_26 is not None and
        ema_12 is not None and ema_26 is not None and
        prev_ema_12 >= prev_ema_26 and ema_12 < ema_26):
      sell_signals.append("EMA데드크로스(12/26)")

    # 하락 추세 확인
    trend_bearish = current_price < sma_60

    # RSI 과매수
    rsi_overbought = rsi and rsi > 70

    # 단기 이평이 모두 하락 배열
    ma_alignment_bearish = sma_5 < sma_20 < sma_60

    # === 7. 신호 강도 계산 ===
    buy_score = 0
    sell_score = 0

    # 매수 점수
    if buy_signals:
      buy_score += len(buy_signals) * 2
    if trend_bullish:
      buy_score += 1
    if rsi_oversold_bounce:
      buy_score += 1
    if volume_surge:
      buy_score += 1
    if ma_alignment_bullish:
      buy_score += 1

    # 매도 점수
    if sell_signals:
      sell_score += len(sell_signals) * 2
    if trend_bearish:
      sell_score += 1
    if rsi_overbought:
      sell_score += 2
    if ma_alignment_bearish:
      sell_score += 1

    # === 8. 최종 판단 ===
    print(f"매수 신호: {buy_signals}")
    print(f"매도 신호: {sell_signals}")
    print(f"매수 점수: {buy_score}, 매도 점수: {sell_score}")
    print(f"추가 조건 - 상승추세: {trend_bullish}, 거래량증가: {volume_surge}")

    # 강한 매수 신호
    if buy_score >= 4 and buy_signals and trend_bullish:
      return 'BUY'

    # 강한 매도 신호
    elif sell_score >= 3 and sell_signals:
      return 'SELL'

    # 약한 매수 신호
    elif buy_signals and trend_bullish and buy_score >= 3:
      return 'BUY'

    # 보유
    else:
      return 'HOLD'

  def run_once(self):
    """한 번의 매매 사이클 실행"""
    current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
    current_price = self.api.get_ticker_price(self.market)

    if current_price == 0:
      print("현재 가격을 가져올 수 없습니다.")
      return

    print(f"\n{'=' * 60}")
    print(f"[{current_time}] {self.market} 이동평균 전략 분석")
    print(f"{'=' * 60}")

    # 현재 자산 상황 요약
    krw_balance = self.api.get_balance('KRW')
    coin_balance = self.api.get_balance(self.target_coin)

    print(f"현재가: {current_price:,.0f}원")
    print(
      f"보유 자산: {krw_balance:,.0f}원 KRW, {coin_balance:.8f} {self.target_coin}")

    if coin_balance > 0:
      coin_value = coin_balance * current_price
      total_value = krw_balance + coin_value
      print(f"코인 평가액: {coin_value:,.0f}원")
      print(f"총 자산: {total_value:,.0f}원")

    # 시장 분석 실행
    signal = self.analyze_market()

    print(f"\n최종 매매 신호: {signal}")
    print("-" * 60)

    # 신호에 따른 매매 실행
    if signal == 'BUY':
      print("매수 신호 발생!")
      success = self.executor.execute_buy()
      if success:
        print("매수 주문이 성공적으로 실행되었습니다.")
      else:
        print("매수 주문 실행에 실패했습니다.")

    elif signal == 'SELL':
      print("매도 신호 발생!")
      success = self.executor.execute_sell()
      if success:
        print("매도 주문이 성공적으로 실행되었습니다.")
      else:
        print("매도 주문 실행에 실패했습니다.")

    else:
      print("보유 (매매 조건 미충족)")

    print(f"{'=' * 60}")
    print(f"다음 분석: {self.check_interval}초 후")

  def start(self):
    """이동평균 전략 자동매매 시작"""
    self.is_running = True
    print(f"\n=== {self.target_coin} 고급 이동평균 전략 자동매매 시작 ===")
    print(f"전략: 다중 이동평균선 교차 + RSI + 거래량 분석")
    print(f"매수 금액: {self.executor.buy_amount:,.0f}원")
    print(f"매도 비율: {self.executor.sell_ratio * 100}%")
    print(f"체크 주기: {self.check_interval}초")
    print(f"분석 지표:")
    print(f"   - SMA (5, 20, 60일)")
    print(f"   - EMA (12, 26일)")
    print(f"   - RSI (14일)")
    print(f"   - 거래량 분석")
    print(f"   - 추세 분석")
    print(f"중지: Ctrl+C")
    print("=" * 60)

    try:
      while self.is_running:
        self.run_once()

        # 다음 체크까지 대기
        time.sleep(self.check_interval)

    except KeyboardInterrupt:
      print(f"\n{self.target_coin} 자동매매를 중지합니다.")
      print("최종 자산 현황을 확인하세요.")
      self.is_running = False
    except Exception as e:
      print(f"예상치 못한 오류 발생: {e}")
      print("프로그램을 안전하게 종료합니다.")
      self.is_running = False