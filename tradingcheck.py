import os
import jwt
import uuid
import hashlib
from urllib.parse import urlencode, unquote
import requests
import json

class UpbitAPI:
    def __init__(self, access_key, secret_key):
        """
        업비트 API 클라이언트 초기화
        
        Args:
            access_key (str): 업비트에서 발급받은 Access Key
            secret_key (str): 업비트에서 발급받은 Secret Key
        """
        self.access_key = access_key
        self.secret_key = secret_key
        self.server_url = "https://api.upbit.com"
    
    def _get_headers(self, query_string=None):
        """JWT 토큰을 생성하여 헤더에 포함"""
        payload = {
            'access_key': self.access_key,
            'nonce': str(uuid.uuid4()),
        }
        
        if query_string:
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

def load_api_keys_from_file():
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

def main():
    """메인 함수"""
    # API 키 설정 우선순위:
    # 1. 환경 변수
    # 2. Key.txt 파일
    # 3. 사용자 직접 입력
    
    access_key = os.getenv('UPBIT_ACCESS_KEY')
    secret_key = os.getenv('UPBIT_SECRET_KEY')
    
    # 환경 변수가 설정되지 않은 경우 파일에서 읽기
    if not access_key or not secret_key:
        print("환경 변수에서 API 키를 찾을 수 없습니다. Key.txt 파일에서 읽어옵니다...")
        file_access_key, file_secret_key = load_api_keys_from_file()
        
        if file_access_key and file_secret_key:
            access_key = file_access_key
            secret_key = file_secret_key
            print("Key.txt 파일에서 API 키를 성공적으로 읽어왔습니다.")
        else:
            print("Key.txt 파일에서 API 키를 읽을 수 없습니다.")
    
    # 여전히 API 키가 없는 경우 사용자 입력 받기
    if not access_key or not secret_key:
        print("\n업비트 API 키가 필요합니다.")
        print("1. 환경 변수로 설정: UPBIT_ACCESS_KEY, UPBIT_SECRET_KEY")
        print("2. APIKey/Key.txt 파일에 저장")
        print("3. 또는 아래에 직접 입력하세요:")
        print()
        
        access_key = input("Access Key를 입력하세요: ").strip()
        secret_key = input("Secret Key를 입력하세요: ").strip()
        
        if not access_key or not secret_key:
            print("API 키가 입력되지 않았습니다.")
            return
    
    # UpbitAPI 인스턴스 생성
    upbit = UpbitAPI(access_key, secret_key)
    
    # 자산 정보 출력
    upbit.display_assets()

if __name__ == "__main__":
    main()
