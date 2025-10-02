import os
import jwt
import uuid
import hashlib
from urllib.parse import urlencode, unquote
import requests
import json
import time
from datetime import datetime

# ================== 설정 구간 ==================
# 매매할 코인 종목 설정 (KRW- 제외하고 입력)
TARGET_COIN = "ETH"  # 예: BTC, ETH, ADA, DOGE 등

# 그리드 트레이딩 설정
# 25000원으로 테스트 할 설정 
GRID_COUNT = 10         # 그리드 개수 (매수/매도 구간 개수)
GRID_RANGE = 0.001       # 그리드 범위 (5% = 0.05, 기준가 ±5%) 테스트로 좁은 범위 설정
ORDER_AMOUNT = 5000    # 각 그리드당 주문 금액 (원화) 5000원 *(10개/2)= 25000원
BASE_PRICE = None       # 기준 가격 (None이면 현재가 기준으로 자동 설정)

# 체크 주기 (초)
CHECK_INTERVAL = 10     # 10초마다 가격 체크

# 이동평균선 트레이딩 설정
BUY_AMOUNT = 10000      # 한 번에 매수할 금액 (원화) - 기존 호환성용
SELL_RATIO = 1.0        # 매도 비율 (1.0 = 100%, 0.5 = 50%) - 기존 호환성용
# ==============================================

class UpbitAPI:
    def __init__(self):
        """
        업비트 API 클라이언트 초기화
        Key.txt 파일에서 자동으로 API 키를 읽어옴
        """
        self.access_key, self.secret_key = self._load_api_keys()
        if not self.access_key or not self.secret_key:
            raise ValueError("API 키를 읽을 수 없습니다. APIKey/Key.txt 파일을 확인해주세요.")
        self.server_url = "https://api.upbit.com"
    
    def _load_api_keys(self):
        """
        Key.txt 파일에서 API 키를 읽어오는 함수
        
        Returns:
            tuple: (access_key, secret_key) 또는 (None, None)
        """
        key_file_path = os.path.join(os.path.dirname(__file__), "APIKey", "Key.txt")
        
        try:
            with open(key_file_path, 'r', encoding='utf-8') as file:
                lines = file.readlines()
                
            access_key = None
            secret_key = None
            
            for line in lines:
                line = line.strip()
                if line.startswith("Access Key:"):
                    access_key = line.split("Access Key:", 1)[1].strip()
                elif line.startswith("Secret Key:"):
                    secret_key = line.split("Secret Key:", 1)[1].strip()
            
            return access_key, secret_key
        
        except FileNotFoundError:
            print(f"API 키 파일을 찾을 수 없습니다: {key_file_path}")
            return None, None
        except Exception as e:
            print(f"API 키 파일 읽기 오류: {e}")
            return None, None
    
    def _get_headers(self, query_string=None):
        """JWT 토큰을 생성하여 헤더에 포함"""
        payload = {
            'access_key': self.access_key,
            'nonce': str(uuid.uuid4()),
        }
        
        if query_string:
            # query_string이 bytes인지 문자열인지 확인
            if isinstance(query_string, bytes):
                query_hash = hashlib.sha512(query_string).hexdigest()
            else:
                query_hash = hashlib.sha512(query_string.encode()).hexdigest()
            payload['query_hash'] = query_hash
            payload['query_hash_alg'] = 'SHA512'
        
        jwt_token = jwt.encode(payload, self.secret_key, algorithm='HS256')
        
        headers = {
            'Authorization': f'Bearer {jwt_token}',
            'Content-Type': 'application/json'
        }
        
        return headers
    
    def get_accounts(self):
        """
        현재 보유 자산 조회
        
        Returns:
            list: 보유 중인 자산 정보 리스트
        """
        url = f"{self.server_url}/v1/accounts"
        headers = self._get_headers()
        
        try:
            response = requests.get(url, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"API 요청 오류: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"응답 상태 코드: {e.response.status_code}")
                print(f"응답 내용: {e.response.text}")
            return None
        except json.JSONDecodeError as e:
            print(f"JSON 디코딩 오류: {e}")
            return None
    
    def get_ticker_price(self, market):
        """
        특정 마켓의 현재 가격 조회 (공개 API)
        
        Args:
            market (str): 마켓 코드 (예: KRW-BTC)
        
        Returns:
            float: 현재 가격
        """
        url = f"{self.server_url}/v1/ticker"
        params = {'markets': market}
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            data = response.json()
            if data:
                return data[0]['trade_price']
            return 0
        except requests.exceptions.RequestException as e:
            print(f"가격 조회 오류: {e}")
            return 0
    
    def get_candles(self, market, interval='minutes', count=200):
        """
        캔들 데이터 조회 (기술적 분석용)
        
        Args:
            market (str): 마켓 코드 (예: KRW-BTC)
            interval (str): 시간 간격 (minutes, days, weeks, months)
            count (int): 조회할 캔들 개수
        
        Returns:
            list: 캔들 데이터 리스트
        """
        if interval == 'minutes':
            url = f"{self.server_url}/v1/candles/minutes/5"  # 5분봉
        elif interval == 'days':
            url = f"{self.server_url}/v1/candles/days"
        else:
            url = f"{self.server_url}/v1/candles/minutes/5"
        
        params = {'market': market, 'count': count}
        
        try:
            response = requests.get(url, params=params)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"캔들 데이터 조회 오류: {e}")
            return []
    
    def place_buy_order(self, market, price):
        """
        지정가 매수 주문
        
        Args:
            market (str): 마켓 코드 (예: KRW-BTC)
            price (float): 매수할 금액 (원화)
        
        Returns:
            dict: 주문 결과
        """
        url = f"{self.server_url}/v1/orders"
        
        params = {
            'market': market,
            'side': 'bid',  # 매수
            'price': str(price),
            'ord_type': 'price'  # 시장가 매수 (금액 지정)
        }
        
        query_string = urlencode(params).encode()
        headers = self._get_headers(query_string)
        
        try:
            response = requests.post(url, json=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"매수 주문 오류: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"응답 내용: {e.response.text}")
            return None
    
    def place_sell_order(self, market, volume):
        """
        시장가 매도 주문
        
        Args:
            market (str): 마켓 코드 (예: KRW-BTC)
            volume (float): 매도할 수량
        
        Returns:
            dict: 주문 결과
        """
        url = f"{self.server_url}/v1/orders"
        
        params = {
            'market': market,
            'side': 'ask',  # 매도
            'volume': str(volume),
            'ord_type': 'market'  # 시장가 매도
        }
        
        query_string = urlencode(params).encode()
        headers = self._get_headers(query_string)
        
        try:
            response = requests.post(url, json=params, headers=headers)
            response.raise_for_status()
            return response.json()
        except requests.exceptions.RequestException as e:
            print(f"매도 주문 오류: {e}")
            if hasattr(e, 'response') and e.response is not None:
                print(f"응답 내용: {e.response.text}")
            return None
    
    def get_balance(self, currency):
        """
        특정 통화의 잔고 조회
        
        Args:
            currency (str): 통화 코드 (예: KRW, BTC)
        
        Returns:
            float: 사용 가능한 잔고
        """
        accounts = self.get_accounts()
        if not accounts:
            return 0
        
        for account in accounts:
            if account['currency'] == currency:
                return float(account['balance'])
        return 0
    
    def display_assets(self):
        """현재 보유 자산을 보기 좋게 출력"""
        accounts = self.get_accounts()
        
        if accounts is None:
            print("자산 정보를 가져올 수 없습니다.")
            return
        
        if len(accounts) == 0:
            print("현재 보유 중인 자산이 없습니다.")
            return
        
        print("=" * 60)
        print("업비트 현재 보유 자산")
        print("=" * 60)
        
        total_krw_value = 0
        
        for account in accounts:
            currency = account['currency']
            balance = float(account['balance'])
            locked = float(account['locked'])
            avg_buy_price = float(account['avg_buy_price'])
            
            if balance + locked > 0:  # 보유량이 있는 자산만 표시
                if currency == 'KRW':
                    # 원화의 경우
                    total_balance = balance + locked
                    total_krw_value += total_balance
                    
                    print(f"통화: {currency}")
                    print(f"  사용가능: {balance:,.0f} KRW")
                    print(f"  사용중: {locked:,.0f} KRW")
                    print(f"  총 보유: {total_balance:,.0f} KRW")
                    print("-" * 40)
                else:
                    # 암호화폐의 경우
                    market = f"KRW-{currency}"
                    current_price = self.get_ticker_price(market)
                    
                    total_balance = balance + locked
                    current_value = total_balance * current_price
                    
                    if avg_buy_price > 0:
                        profit_loss = current_value - (total_balance * avg_buy_price)
                        profit_rate = (profit_loss / (total_balance * avg_buy_price)) * 100
                    else:
                        profit_loss = 0
                        profit_rate = 0
                    
                    total_krw_value += current_value
                    
                    print(f"통화: {currency}")
                    print(f"  사용가능: {balance:.8f}")
                    print(f"  사용중: {locked:.8f}")
                    print(f"  총 보유: {total_balance:.8f}")
                    print(f"  평균매수가: {avg_buy_price:,.0f} KRW")
                    print(f"  현재가: {current_price:,.0f} KRW")
                    print(f"  평가금액: {current_value:,.0f} KRW")
                    if avg_buy_price > 0:
                        print(f"  손익: {profit_loss:,.0f} KRW ({profit_rate:+.2f}%)")
                    print("-" * 40)
        
        print(f"총 자산 평가액: {total_krw_value:,.0f} KRW")
        print("=" * 60)

class GridTradingBot:
    def __init__(self, upbit_api, target_coin):
        """
        그리드 트레이딩 봇 초기화
        
        Args:
            upbit_api (UpbitAPI): 업비트 API 인스턴스
            target_coin (str): 매매할 코인 (예: BTC)
        """
        self.api = upbit_api
        self.target_coin = target_coin
        self.market = f"KRW-{target_coin}"
        self.is_running = False
        
        # 그리드 설정
        self.grid_count = GRID_COUNT
        self.grid_range = GRID_RANGE
        self.order_amount = ORDER_AMOUNT
        self.base_price = BASE_PRICE
        
        # 그리드 데이터
        self.buy_grids = []   # 매수 그리드 가격 리스트
        self.sell_grids = []  # 매도 그리드 가격 리스트
        self.executed_buys = set()   # 실행된 매수 그리드 추적
        self.executed_sells = set()  # 실행된 매도 그리드 추적
        
        # 그리드 초기화
        self._initialize_grids()
    
    def _initialize_grids(self):
        """
        그리드 가격대 초기화
        """
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
        self.buy_grids.sort(reverse=True)   # 높은 가격부터 (기준가에 가까운 순)
        self.sell_grids.sort()              # 낮은 가격부터 (기준가에 가까운 순)
        
        print(f"\n=== 그리드 설정 완료 ===")
        print(f"매수 그리드 ({len(self.buy_grids)}개):")
        for i, price in enumerate(self.buy_grids):
            print(f"  {i+1}. {price:,.0f}원 ({((price/self.base_price-1)*100):+.2f}%)")
        
        print(f"매도 그리드 ({len(self.sell_grids)}개):")
        for i, price in enumerate(self.sell_grids):
            print(f"  {i+1}. {price:,.0f}원 ({((price/self.base_price-1)*100):+.2f}%)")
        print("=" * 30)
    
    def _check_buy_signals(self, current_price):
        """
        매수 신호 체크
        
        Args:
            current_price (float): 현재 가격
            
        Returns:
            list: 실행할 매수 그리드 가격 리스트
        """
        buy_signals = []
        
        for grid_price in self.buy_grids:
            if (current_price <= grid_price and 
                grid_price not in self.executed_buys):
                buy_signals.append(grid_price)
        
        return buy_signals
    
    def _check_sell_signals(self, current_price):
        """
        매도 신호 체크
        
        Args:
            current_price (float): 현재 가격
            
        Returns:
            list: 실행할 매도 그리드 가격 리스트
        """
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
        """
        그리드 매수 실행
        
        Args:
            grid_price (float): 그리드 가격
            
        Returns:
            bool: 성공 여부
        """
        # 원화 잔고 확인
        krw_balance = self.api.get_balance('KRW')
        
        if krw_balance < self.order_amount:
            print(f"매수 실패: 원화 잔고 부족 (보유: {krw_balance:,.0f}원, 필요: {self.order_amount:,.0f}원)")
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
        """
        그리드 매도 실행
        
        Args:
            grid_price (float): 그리드 가격
            
        Returns:
            bool: 성공 여부
        """
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
        
        print(f"그리드 매도 실행: {sell_volume:.8f} {self.target_coin} @ {grid_price:,.0f}원")
        
        result = self.api.place_sell_order(self.market, sell_volume)
        
        if result:
            self.executed_sells.add(grid_price)
            print(f"그리드 매도 성공: {grid_price:,.0f}원")
            return True
        else:
            print(f"그리드 매도 실패: {grid_price:,.0f}원")
            return False
    
    def _reset_executed_grids(self, current_price):
        """
        실행된 그리드 초기화 (가격이 그리드를 역방향으로 지날 때)
        
        Args:
            current_price (float): 현재 가격
        """
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
        """
        한 번의 그리드 트레이딩 사이클 실행
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_price = self.api.get_ticker_price(self.market)
        
        if current_price == 0:
            print("현재 가격을 가져올 수 없습니다.")
            return
        
        print(f"\n[{current_time}] {self.market} 현재가: {current_price:,.0f}원")
        print(f"기준가 대비: {((current_price/self.base_price-1)*100):+.2f}%")
        
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
    
    def start_trading(self):
        """
        그리드 트레이딩 시작
        """
        self.is_running = True
        print(f"=== {self.target_coin} 그리드 트레이딩 시작 ===")
        print(f"그리드 개수: {self.grid_count}개")
        print(f"그리드 범위: ±{self.grid_range*100}%")
        print(f"주문 금액: {self.order_amount:,.0f}원")
        print(f"체크 주기: {CHECK_INTERVAL}초")
        print("Ctrl+C로 중지할 수 있습니다.\n")
        
        try:
            while self.is_running:
                self.run_once()
                
                # 다음 체크까지 대기
                print(f"{CHECK_INTERVAL}초 후 다시 체크...")
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            print("\n그리드 트레이딩을 중지합니다.")
            self.is_running = False
        except Exception as e:
            print(f"예상치 못한 오류 발생: {e}")
            self.is_running = False

class TradingBot:
    def __init__(self, upbit_api, target_coin):
        """
        자동매매 봇 초기화
        
        Args:
            upbit_api (UpbitAPI): 업비트 API 인스턴스
            target_coin (str): 매매할 코인 (예: BTC)
        """
        self.api = upbit_api
        self.target_coin = target_coin
        self.market = f"KRW-{target_coin}"
        self.is_running = False
        
    def calculate_moving_average(self, prices, period):
        """
        이동평균 계산
        
        Args:
            prices (list): 가격 리스트
            period (int): 이동평균 기간
        
        Returns:
            float: 이동평균값
        """
        if len(prices) < period:
            return None
        return sum(prices[-period:]) / period
    
    def calculate_ema(self, prices, period):
        """
        지수 이동평균(EMA) 계산
        
        Args:
            prices (list): 가격 리스트
            period (int): EMA 기간
        
        Returns:
            float: EMA 값
        """
        if len(prices) < period:
            return None
        
        # 승수 계산
        multiplier = 2 / (period + 1)
        
        # 첫 번째 EMA는 단순 이동평균으로 시작
        ema = sum(prices[:period]) / period
        
        # 나머지 가격들에 대해 EMA 계산
        for price in prices[period:]:
            ema = (price * multiplier) + (ema * (1 - multiplier))
        
        return ema
    
    def calculate_rsi(self, prices, period=14):
        """
        RSI(Relative Strength Index) 계산
        
        Args:
            prices (list): 가격 리스트
            period (int): RSI 기간 (기본 14)
        
        Returns:
            float: RSI 값 (0-100)
        """
        if len(prices) < period + 1:
            return None
        
        # 가격 변화 계산
        price_changes = []
        for i in range(1, len(prices)):
            price_changes.append(prices[i] - prices[i-1])
        
        if len(price_changes) < period:
            return None
        
        # 상승분과 하락분 분리
        gains = [change if change > 0 else 0 for change in price_changes[-period:]]
        losses = [-change if change < 0 else 0 for change in price_changes[-period:]]
        
        # 평균 계산
        avg_gain = sum(gains) / period
        avg_loss = sum(losses) / period
        
        if avg_loss == 0:
            return 100
        
        rs = avg_gain / avg_loss
        rsi = 100 - (100 / (1 + rs))
        
        return rsi
    
    def calculate_volume_ma(self, candles, period=20):
        """
        거래량 이동평균 계산
        
        Args:
            candles (list): 캔들 데이터
            period (int): 기간
        
        Returns:
            float: 거래량 이동평균
        """
        if len(candles) < period:
            return None
        
        volumes = [float(candle['candle_acc_trade_volume']) for candle in candles[-period:]]
        return sum(volumes) / period
    
    def analyze_market(self):
        """
        고급 이동평균선 교차 전략을 사용한 시장 분석
        
        Returns:
            str: 'BUY', 'SELL', 'HOLD'
        """
        # 캔들 데이터 조회 (더 많은 데이터 필요)
        candles = self.api.get_candles(self.market, 'minutes', 100)
        if len(candles) < 50:
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
        sma_5 = self.calculate_moving_average(close_prices, 5)    # 단기
        sma_20 = self.calculate_moving_average(close_prices, 20)  # 중기
        sma_60 = self.calculate_moving_average(close_prices, 60)  # 장기
        ema_12 = self.calculate_ema(close_prices, 12)             # 단기 EMA
        ema_26 = self.calculate_ema(close_prices, 26)             # 장기 EMA
        
        # === 2. 이전 이동평균선 계산 (교차 확인용) ===
        prev_sma_5 = self.calculate_moving_average(close_prices[:-1], 5)
        prev_sma_20 = self.calculate_moving_average(close_prices[:-1], 20)
        # EMA는 누적 계산이므로 전체 데이터에서 마지막 전 값을 사용
        if len(close_prices) >= 13:
            prev_ema_12 = self.calculate_ema(close_prices[:-1], 12)
        else:
            prev_ema_12 = None
        if len(close_prices) >= 27:
            prev_ema_26 = self.calculate_ema(close_prices[:-1], 26)
        else:
            prev_ema_26 = None
        
        # === 3. RSI 계산 ===
        rsi = self.calculate_rsi(close_prices, 14)
        
        # === 4. 거래량 분석 ===
        volume_ma = self.calculate_volume_ma(candles, 20)
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
        
        # 5-1. 골든크로스 (단기 이평이 중기 이평을 상향 돌파)
        if prev_sma_5 <= prev_sma_20 and sma_5 > sma_20:
            buy_signals.append("골든크로스(SMA5/20)")
        
        # 5-2. EMA 골든크로스
        if (prev_ema_12 is not None and prev_ema_26 is not None and 
            ema_12 is not None and ema_26 is not None and
            prev_ema_12 <= prev_ema_26 and ema_12 > ema_26):
            buy_signals.append("EMA골든크로스(12/26)")
        
        # 5-3. 상승 추세 확인 (현재가가 장기 이평 위)
        trend_bullish = current_price > sma_60
        
        # 5-4. RSI 과매도 반등 (30 이하에서 35 위로)
        rsi_oversold_bounce = rsi and rsi > 35 and rsi < 70
        
        # 5-5. 거래량 증가 (평균의 1.2배 이상)
        volume_surge = volume_ratio >= 1.2
        
        # 5-6. 단기 이평이 모두 상승 배열
        ma_alignment_bullish = sma_5 > sma_20 > sma_60
        
        # === 6. 매도 신호 조건들 ===
        sell_signals = []
        
        # 6-1. 데드크로스 (단기 이평이 중기 이평을 하향 돌파)
        if prev_sma_5 >= prev_sma_20 and sma_5 < sma_20:
            sell_signals.append("데드크로스(SMA5/20)")
        
        # 6-2. EMA 데드크로스
        if (prev_ema_12 is not None and prev_ema_26 is not None and 
            ema_12 is not None and ema_26 is not None and
            prev_ema_12 >= prev_ema_26 and ema_12 < ema_26):
            sell_signals.append("EMA데드크로스(12/26)")
        
        # 6-3. 하락 추세 확인 (현재가가 장기 이평 아래)
        trend_bearish = current_price < sma_60
        
        # 6-4. RSI 과매수 (70 이상)
        rsi_overbought = rsi and rsi > 70
        
        # 6-5. 단기 이평이 모두 하락 배열
        ma_alignment_bearish = sma_5 < sma_20 < sma_60
        
        # === 7. 신호 강도 계산 ===
        buy_score = 0
        sell_score = 0
        
        # 매수 점수 계산
        if buy_signals:
            buy_score += len(buy_signals) * 2  # 교차 신호는 강한 신호
        if trend_bullish:
            buy_score += 1
        if rsi_oversold_bounce:
            buy_score += 1
        if volume_surge:
            buy_score += 1
        if ma_alignment_bullish:
            buy_score += 1
        
        # 매도 점수 계산
        if sell_signals:
            sell_score += len(sell_signals) * 2  # 교차 신호는 강한 신호
        if trend_bearish:
            sell_score += 1
        if rsi_overbought:
            sell_score += 2  # 과매수는 강한 매도 신호
        if ma_alignment_bearish:
            sell_score += 1
        
        # === 8. 최종 판단 ===
        print(f"매수 신호: {buy_signals}")
        print(f"매도 신호: {sell_signals}")
        print(f"매수 점수: {buy_score}, 매도 점수: {sell_score}")
        print(f"추가 조건 - 상승추세: {trend_bullish}, 거래량증가: {volume_surge}")
        
        # 강한 매수 신호 (점수 4 이상 + 주요 교차 신호)
        if buy_score >= 4 and buy_signals and trend_bullish:
            return 'BUY'
        
        # 강한 매도 신호 (점수 3 이상 + 주요 교차 신호)
        elif sell_score >= 3 and sell_signals:
            return 'SELL'
        
        # 약한 매수 신호 (골든크로스만 있고 다른 조건 양호)
        elif buy_signals and trend_bullish and buy_score >= 3:
            return 'BUY'
        
        # 보유
        else:
            return 'HOLD'
    
    def execute_buy(self):
        """
        정교한 매수 실행 (리스크 관리 포함)
        
        Returns:
            bool: 성공 여부
        """
        # 원화 잔고 확인
        krw_balance = self.api.get_balance('KRW')
        
        if krw_balance < BUY_AMOUNT:
            print(f"매수 실패: 원화 잔고 부족 (보유: {krw_balance:,.0f}원, 필요: {BUY_AMOUNT:,.0f}원)")
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
            prev_candle = candles[1]    # 이전 캔들
            
            recent_price = float(recent_candle['trade_price'])
            prev_price = float(prev_candle['trade_price'])
            
            price_change_rate = abs((recent_price - prev_price) / prev_price)
            
            if price_change_rate > 0.05:  # 5% 이상 급변동
                print(f"매수 주의: 급격한 가격 변동 감지 ({price_change_rate*100:.1f}%)")
                # 급변동 시에도 매수할지는 설정에 따라 결정
                # 현재는 경고만 출력하고 진행
        
        # 최소 주문 금액 확인 (업비트 최소 주문: 5,000원)
        if BUY_AMOUNT < 5000:
            print(f"매수 실패: 최소 주문 금액 미달 (최소: 5,000원, 설정: {BUY_AMOUNT:,.0f}원)")
            return False
        
        print(f"매수 주문 실행: {BUY_AMOUNT:,.0f}원 어치 {self.target_coin} @ {current_price:,.0f}원")
        
        # 실제 주문 실행
        result = self.api.place_buy_order(self.market, BUY_AMOUNT)
        
        if result:
            # 예상 수량 계산
            expected_volume = BUY_AMOUNT / current_price
            print(f"매수 주문 성공!")
            print(f"  주문 ID: {result.get('uuid', 'N/A')}")
            print(f"  예상 수량: {expected_volume:.8f} {self.target_coin}")
            print(f"  주문 금액: {BUY_AMOUNT:,.0f}원")
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
        sell_volume = coin_balance * SELL_RATIO
        
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
        
        print(f"매도 주문 실행: {sell_volume:.8f} {self.target_coin} @ {current_price:,.0f}원")
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
    
    def run_once(self):
        """
        한 번의 고급 매매 사이클 실행
        """
        current_time = datetime.now().strftime("%Y-%m-%d %H:%M:%S")
        current_price = self.api.get_ticker_price(self.market)
        
        if current_price == 0:
            print("현재 가격을 가져올 수 없습니다.")
            return
        
        print(f"\n{'='*60}")
        print(f"[{current_time}] {self.market} 이동평균 전략 분석")
        print(f"{'='*60}")
        
        # 현재 자산 상황 요약
        krw_balance = self.api.get_balance('KRW')
        coin_balance = self.api.get_balance(self.target_coin)
        
        print(f"현재가: {current_price:,.0f}원")
        print(f"보유 자산: {krw_balance:,.0f}원 KRW, {coin_balance:.8f} {self.target_coin}")
        
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
            success = self.execute_buy()
            if success:
                print("매수 주문이 성공적으로 실행되었습니다.")
            else:
                print("매수 주문 실행에 실패했습니다.")
                
        elif signal == 'SELL':
            print("매도 신호 발생!")
            success = self.execute_sell()
            if success:
                print("매도 주문이 성공적으로 실행되었습니다.")
            else:
                print("매도 주문 실행에 실패했습니다.")
                
        else:
            print("보유 (매매 조건 미충족)")
        
        print(f"{'='*60}")
        print(f"다음 분석: {CHECK_INTERVAL}초 후")
    
    def start_trading(self):
        """
        고급 이동평균 교차 전략 자동매매 시작
        """
        self.is_running = True
        print(f"\n=== {self.target_coin} 고급 이동평균 전략 자동매매 시작 ===")
        print(f"전략: 다중 이동평균선 교차 + RSI + 거래량 분석")
        print(f"매수 금액: {BUY_AMOUNT:,.0f}원")
        print(f"매도 비율: {SELL_RATIO * 100}%")
        print(f"체크 주기: {CHECK_INTERVAL}초")
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
                time.sleep(CHECK_INTERVAL)
                
        except KeyboardInterrupt:
            print(f"\n{self.target_coin} 자동매매를 중지합니다.")
            print("최종 자산 현황을 확인하세요.")
            self.is_running = False
        except Exception as e:
            print(f"예상치 못한 오류 발생: {e}")
            print("프로그램을 안전하게 종료합니다.")
            self.is_running = False

def main():
    """메인 함수"""
    print(f"=== 업비트 자동매매 프로그램 ===")
    print(f"대상 코인: {TARGET_COIN}")
    print("=" * 50)
    
    try:
        # UpbitAPI 인스턴스 생성 (자동으로 Key.txt에서 API 키 로드)
        print("Key.txt 파일에서 API 키를 읽어옵니다...")
        upbit = UpbitAPI()
        print("Key.txt 파일에서 API 키를 성공적으로 읽어왔습니다.")
    except ValueError as e:
        print(f"오류: {e}")
        return
    except Exception as e:
        print(f"예상치 못한 오류: {e}")
        return
    
    # 현재 자산 조회
    print("\n현재 보유 자산:")
    upbit.display_assets()
    
    # 모드 선택
    print("\n실행 모드를 선택하세요:")
    print("1. 그리드 트레이딩 시작")
    print("2. 기존 자동매매 시작 (이동평균 전략)")
    print("3. 종료")
    
    choice = input("선택 (1, 2 또는 3): ").strip()
    
    if choice == "1":
        # 그리드 트레이딩 시작
        try:
            grid_bot = GridTradingBot(upbit, TARGET_COIN)
            grid_bot.start_trading()
        except ValueError as e:
            print(f"그리드 트레이딩 초기화 오류: {e}")
    elif choice == "2":
        # 기존 자동매매 시작
        bot = TradingBot(upbit, TARGET_COIN)
        bot.start_trading()
    else:
        print("종료합니다.")

if __name__ == "__main__": #내장 변수 스크립트에서 실행시 변수 main으로 초기화
    main()
