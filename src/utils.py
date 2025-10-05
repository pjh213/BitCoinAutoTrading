"""
유틸리티 함수 모듈
"""
import os
from dotenv import load_dotenv


def load_api_keys():
  """
  API 키를 로드하는 함수
  우선순위: .env 파일 → APIKey/Key.txt → 환경 변수

  Returns:
      tuple: (access_key, secret_key)
  """
  # 플레이스홀더 값 목록
  PLACEHOLDER_VALUES = [
      'your_access_key_here',
      'your_secret_key_here',
      '<여기에 키 입력>',
      'YOUR_ACCESS_KEY',
      'YOUR_SECRET_KEY',
      '',
      None
  ]
  
  # .env 파일 로드
  load_dotenv()
  
  # 1. 환경 변수에서 시도
  access_key = os.getenv('UPBIT_ACCESS_KEY')
  secret_key = os.getenv('UPBIT_SECRET_KEY')
  
  # 플레이스홀더 체크
  if access_key and secret_key:
      if access_key not in PLACEHOLDER_VALUES and secret_key not in PLACEHOLDER_VALUES:
          return access_key, secret_key
  
  # 2. Key.txt 파일에서 읽기 (work_jonghyeok 호환)
  key_file_path = os.path.join(os.path.dirname(__file__), "..", "APIKey", "Key.txt")
  
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
      
      # 플레이스홀더 체크
      if access_key and secret_key:
          if access_key not in PLACEHOLDER_VALUES and secret_key not in PLACEHOLDER_VALUES:
              return access_key, secret_key
  
  except FileNotFoundError:
      pass
  except Exception as e:
      print(f"API 키 파일 읽기 오류: {e}")
  
  return None, None


def calculate_moving_average(prices, period):
  """
  단순 이동평균(SMA) 계산

  Args:
      prices (list): 가격 리스트
      period (int): 이동평균 기간

  Returns:
      float: 이동평균값
  """
  if len(prices) < period:
    return None
  return sum(prices[-period:]) / period


def calculate_ema(prices, period):
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


def calculate_rsi(prices, period=14):
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
    price_changes.append(prices[i] - prices[i - 1])

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


def calculate_volume_ma(candles, period=20):
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

  volumes = [float(candle['candle_acc_trade_volume']) for candle in
             candles[-period:]]
  return sum(volumes) / period