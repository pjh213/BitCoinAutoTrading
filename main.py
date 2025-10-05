"""
업비트 자동매매 프로그램 메인 진입점
"""
from src.core import UpbitAPI
from src.strategy import GridTradingStrategy, MovingAverageStrategy

# ================== 설정 구간 ==================
# 매매할 코인 종목 설정 (KRW- 제외하고 입력)
TARGET_COIN = "ETH"  # 예: BTC, ETH, ADA, DOGE 등

# 그리드 트레이딩 설정
GRID_COUNT = 10  # 그리드 개수
GRID_RANGE = 0.05  # 그리드 범위 (5% = 0.05)
ORDER_AMOUNT = 5000  # 각 그리드당 주문 금액 (원화)
BASE_PRICE = None  # 기준 가격 (None이면 현재가 기준)

# 이동평균선 트레이딩 설정
BUY_AMOUNT = 10000  # 한 번에 매수할 금액 (원화)
SELL_RATIO = 1.0  # 매도 비율 (1.0 = 100%)

# 체크 주기 (초)
CHECK_INTERVAL = 60  # 60초마다 가격 체크


# ==============================================


def main():
  """메인 함수"""
  print(f"=== 업비트 자동매매 프로그램 ===")
  print(f"대상 코인: {TARGET_COIN}")
  print("=" * 50)

  try:
    # UpbitAPI 인스턴스 생성
    print("API 키를 로드합니다...")
    upbit = UpbitAPI()
    print("API 키를 성공적으로 로드했습니다.\n")
  except ValueError as e:
    print(f"오류: {e}")
    return
  except Exception as e:
    print(f"예상치 못한 오류: {e}")
    return

  # 현재 자산 조회
  print("현재 보유 자산:")
  upbit.display_assets()

  # 모드 선택
  print("\n실행 모드를 선택하세요:")
  print("1. 그리드 트레이딩 시작")
  print("2. 이동평균 전략 자동매매 시작")
  print("3. 자산 조회만")
  print("4. 종료")

  choice = input("\n선택 (1, 2, 3 또는 4): ").strip()

  if choice == "1":
    # 그리드 트레이딩 시작
    try:
      strategy = GridTradingStrategy(
          api=upbit,
          target_coin=TARGET_COIN,
          grid_count=GRID_COUNT,
          grid_range=GRID_RANGE,
          order_amount=ORDER_AMOUNT,
          base_price=BASE_PRICE,
          check_interval=CHECK_INTERVAL
      )
      strategy.start()
    except ValueError as e:
      print(f"그리드 트레이딩 초기화 오류: {e}")
    except Exception as e:
      print(f"예상치 못한 오류: {e}")

  elif choice == "2":
    # 이동평균 전략 시작
    try:
      strategy = MovingAverageStrategy(
          api=upbit,
          target_coin=TARGET_COIN,
          buy_amount=BUY_AMOUNT,
          sell_ratio=SELL_RATIO,
          check_interval=CHECK_INTERVAL
      )
      strategy.start()
    except Exception as e:
      print(f"예상치 못한 오류: {e}")

  elif choice == "3":
    # 자산 조회만
    print("\n현재 보유 자산 조회:")
    upbit.display_assets()
    print("\n프로그램을 종료합니다.")

  else:
    print("프로그램을 종료합니다.")


if __name__ == "__main__":
  main()