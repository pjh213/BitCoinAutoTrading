"""
업비트 API 통신을 담당하는 핵심 모듈
"""
import os
import jwt
import uuid
import hashlib
from urllib.parse import urlencode
import requests
import json


class UpbitAPI:
  """업비트 API 클라이언트"""

  def __init__(self, access_key=None, secret_key=None):
    """
    업비트 API 클라이언트 초기화

    Args:
        access_key (str, optional): 업비트 Access Key
        secret_key (str, optional): 업비트 Secret Key
    """
    if access_key and secret_key:
      self.access_key = access_key
      self.secret_key = secret_key
    else:
      # utils에서 키 로드
      from .utils import load_api_keys
      self.access_key, self.secret_key = load_api_keys()

    if not self.access_key or not self.secret_key:
      raise ValueError(
        "API 키를 읽을 수 없습니다. .env 파일 또는 APIKey/Key.txt 파일을 확인해주세요.")

    self.server_url = "https://api.upbit.com"

  def _get_headers(self, query_string=None):
    """
    JWT 토큰을 생성하여 헤더에 포함

    Args:
        query_string (str or bytes, optional): 쿼리 문자열

    Returns:
        dict: 인증 헤더
    """
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
    시장가 매수 주문

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