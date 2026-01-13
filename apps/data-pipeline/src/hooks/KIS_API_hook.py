# -*- coding: utf-8 -*-
"""한국투자증권(KIS) API 연동을 위한 훅(Hook) 모듈.

이 모듈은 FinSignt 프로젝트에서 KIS REST API와의 모든 상호작용을 중앙에서 관리합니다.
주요 기능은 다음과 같습니다:
  - API 인증 토큰의 발급 및 캐싱(메모리, 파일)을 통한 효율적인 관리
  - API 요청을 위한 공통 인터페이스 제공 및 재시도 로직 내장
  - API의 다양한 응답 형태(output, output1, output2 등)를 동적으로 파싱하여
    일관된 형식의 데이터로 변환
"""

from datetime import datetime
import os
from pathlib import Path
import time
import requests
import json
from typing import Dict, Any, List

# 프로젝트의 중앙 에러 관리 패키지에서 커스텀 예외 클래스들을 가져옵니다.
from src.errors.KIS_API_errors import KISAPIError, KISAuthenticationError, KISDataError

class KISAPIHook:
  """한국투자증권(KIS) REST API와의 상호작용을 관리하는 훅(Hook) 클래스.

  이 클래스는 API 인증(접근 토큰 관리) 및 데이터 조회를 위한 메서드를 캡슐화하여
  Airflow DAG이나 다른 스크립트에서 간편하게 사용할 수 있도록 설계되었습니다.

  Attributes:
    app_key (str): KIS API의 앱 키.
    app_secret (str): KIS API의 앱 시크릿.
    base_url (str): KIS API의 기본 URL (실전 투자 환경).
    token_filepath (Path): API 접근 토큰을 저장하는 로컬 파일 경로.
    _access_token (str | None): 발급받은 접근 토큰을 저장하는 내부 변수 (메모리 캐시).
  """

  def __init__(self):
    """KISHook 인스턴스를 초기화합니다.

    .env 파일에 저장된 환경 변수로부터 API 키를 로드하며, 키가 없을 경우
    프로그램이 즉시 종료되도록 예외를 발생시킵니다.
    """
    # 환경 변수로부터 API 키를 불러옵니다.
    self.app_key = os.getenv("KIS_APP_KEY")
    self.app_secret = os.getenv("KIS_APP_SECRET")
    self.base_url = "https://openapi.koreainvestment.com:9443"
    self._access_token = None

    # 토큰을 저장할 파일 경로를 지정합니다. (프로젝트 루트 기준)
    self.token_filepath = Path("kis_token.json")

    # 필수적인 API 키가 환경변수에 설정되지 않았다면, 에러를 발생시켜 문제를 즉시 알립니다.
    if not self.app_key or not self.app_secret:
      raise KISAPIError("환경변수 KIS_APP_KEY와 KIS_APP_SECRET가 설정되지 않았습니다.")

  def _get_new_access_token(self) -> str:
    """KIS API 서버로부터 새로운 접근 토큰을 발급받고 파일에 저장합니다.

    이 메서드는 외부에서 직접 호출하기보다는 get_access_token을 통해 호출됩니다.
    발급 성공 시, 토큰 값과 만료 시각을 JSON 파일에 저장하여 다른 프로세스나
    다음 실행에서 재사용할 수 있도록 합니다.

    Returns:
      str: 새로 발급받은 접근 토큰 문자열 (예: "Bearer ...").

    Raises:
      KISAuthenticationError: 네트워크 문제나 API 서버의 응답 오류로 토큰 발급에
        실패한 경우 발생합니다.
    """
    headers = {"content-type": "application/json"}
    body = {"grant_type": "client_credentials", "appkey": self.app_key, "appsecret": self.app_secret}
    path = "/oauth2/tokenP"
    url = f"{self.base_url}{path}"

    try:
      response = requests.post(url, headers=headers, data=json.dumps(body), timeout=10)
      response.raise_for_status()  # HTTP 200 OK가 아닐 경우 예외 발생
      token_data = response.json()

      # 발급받은 토큰을 Bearer 형식으로 가공하여 self 변수에 저장 (메모리 캐시)
      self._access_token = f"Bearer {token_data['access_token']}"

      # 파일에 저장할 정보(토큰 값, 만료 시각)를 딕셔너리로 구성
      token_info = {
        "access_token": self._access_token,
        "expired_at": token_data['access_token_token_expired']
      }
      
      # JSON 파일에 토큰 정보를 기록하여 영속성을 부여합니다.
      with open(self.token_filepath, 'w') as f:
        json.dump(token_info, f)

      return self._access_token

    except requests.exceptions.RequestException as e:
      raise KISAuthenticationError(f"API 서버 접속 실패: 접근 토큰을 발급받을 수 없습니다. 원인: {e}")

  def get_access_token(self) -> str:
    """유효한 접근 토큰을 반환합니다.

    토큰의 효율적인 사용을 위해 3단계 캐싱 전략을 사용합니다.
    1. 메모리 캐시: 현재 실행 중인 스크립트 내에서 가장 빠른 접근을 제공합니다.
    2. 파일 캐시: 스크립트가 재시작되어도 유효기간 내의 토큰을 재사용합니다.
    3. 신규 발급: 위 두 캐시가 모두 유효하지 않을 때만 새로 토큰을 발급받습니다.

    Returns:
      str: "Bearer ..." 형식의 유효한 접근 토큰 문자열.
    """
    # 1. 메모리 캐시 확인: 가장 먼저 확인하여 불필요한 I/O를 줄입니다.
    if self._access_token:
      return self._access_token

    # 2. 로컬 파일 캐시 확인: 토큰 파일이 존재하고, 내용이 유효하며, 만료되지 않았는지 검사합니다.
    try:
      if self.token_filepath.exists():
        with open(self.token_filepath, 'r') as f:
          token_info = json.load(f)
        
        # 저장된 만료 시각을 datetime 객체로 변환
        expired_at = datetime.strptime(token_info['expired_at'], '%Y-%m-%d %H:%M:%S')

        # 토큰이 만료되지 않았고, 값이 존재한다면 이를 사용합니다.
        if datetime.now() < expired_at and token_info.get('access_token'):
          self._access_token = token_info['access_token'] # 메모리에 캐싱
          return self._access_token
    except (json.JSONDecodeError, KeyError):
      # 파일 내용이 손상되었거나(JSON 형식 오류), 필요한 키가 없는 경우,
      # 오류를 무시하고 새로 발급받도록 로직을 진행시킵니다.
      pass
    
    # 3. 모든 캐시가 유효하지 않으면 새로 발급 받습니다.
    return self._get_new_access_token()
  
  def _send_request(self, path: str, tr_id: str, params: Dict[str, Any], error_prefix: str) -> List[Dict]:
    """KIS API에 GET 요청을 보내고 응답을 처리하는 공통 메서드.

    이 메서드는 API 요청의 전 과정을 추상화하며, 다음과 같은 기능을 내장합니다.
    - 유효한 토큰을 자동으로 헤더에 포함
    - 요청 실패 시 지정된 횟수만큼 재시도
    - API 응답의 `rt_cd`를 확인하여 비즈니스 레벨 오류 처리
    - `output`, `output1` 등 다양한 형태의 응답을 하나의 리스트로 통합 및 정규화

    Args:
      path (str): 요청할 API의 세부 경로 (예: /uapi/domestic-stock/v1/quotations/inquire-price).
      tr_id (str): API별 고유 거래 ID.
      params (Dict[str, Any]): API 요청에 필요한 쿼리 파라미터.
      error_prefix (str): 로깅 및 예외 발생 시, 어떤 작업에서 오류가 발생했는지
        식별하기 위한 접두사 문자열.

    Returns:
      List[Dict]: API 응답의 output 블록들을 통합한 딕셔너리의 리스트.
                   각 딕셔너리에는 'data_source' 키를 통해 원본 output 블록 이름이 추가됩니다.
                   최종 실패 시 빈 리스트를 반환합니다.
    Raises:
      KISDataError: API가 비즈니스 오류(`rt_cd` != '0')를 반환하거나,
                    모든 재시도 후에도 서버 접속에 실패한 경우 발생합니다.
    """
    token = self.get_access_token()
    headers = {
      "Content-Type": "application/json",
      "authorization": token,
      "appKey": self.app_key,
      "appSecret": self.app_secret,
      "tr_id": tr_id,
    }
    url = f"{self.base_url}{path}"
    
    max_retries = 3 # 최대 재시도 횟수
    for attempt in range(max_retries):
      try:
        response = requests.get(url, headers=headers, params=params, timeout=10)
        response.raise_for_status() # HTTP 오류 발생 시 예외 throw
        data = response.json()

        # KIS API 비즈니스 로직 상의 오류 처리
        if data['rt_cd'] != "0":
          raise KISDataError(f"{error_prefix} 실패: {data['msg1']}")
        
        # 모든 'output' 블록을 담을 빈 리스트 생성
        merged_list = []
        
        # API 응답의 모든 키를 순회하며 'output'으로 시작하는 키를 동적으로 찾습니다.
        for key, value in data.items():
          if key.startswith('output') and value:
            # API 응답에서 value는 대부분 리스트 형태([{}, {}])이지만,
            # 간혹 단일 딕셔너리 형태({})일 수 있어 처리를 통일하기 위해 리스트로 감쌉니다.
            item_list = value if isinstance(value, list) else [value]
            
            for item in item_list:
              # 각 항목(딕셔너리)에 데이터 출처(원본 키 이름)를 기록하여 추적성을 높입니다.
              item['data_source'] = key
              merged_list.append(item)
              
        return merged_list

      except requests.exceptions.RequestException as e:
        # 요청 실패 시, 마지막 시도라면 예외를 발생시키고, 아니라면 잠시 대기 후 재시도합니다.
        if attempt == max_retries - 1:
          raise KISDataError(f"API 서버 접속 실패 (재시도 {max_retries}회 모두 실패): {e}")
        time.sleep(attempt + 1) # 1, 2초 간격으로 대기

    return [] # 모든 재시도 실패 시, 빈 리스트를 반환하여 후속 처리의 안정성을 높입니다.
  
  def get_kr_stock_basic_info(self, stock_code: str) -> Dict[str, Any]:
    """[국내 주식 정보] 국내 주식 기본 정보를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드 (예: "005930").

    Returns:
      List[Dict[str, Any]]: 조회된 주식 기본 정보 딕셔너리를 담은 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/search-stock-info",
      tr_id="CTPF1002R",
      params={
        "PDNO": stock_code,   # 상품번호 (종목코드)
        "PRDT_TYPE_CD": "300" # 상품타입코드 (300: 주식)
      },
      error_prefix="주식 기본 정보 조회"
    )

  def get_kr_stock_balance_sheet(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 국내 주식 대차대조표를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 분기별 대차대조표 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/finance/balance-sheet",
      tr_id="FHKST66430100",
      params={
        "FID_DIV_CLS_CODE": "1",       # 분류 구분 코드 (0:년, 1:분기)
        "fid_cond_mrkt_div_code": "J", # 조건 시장 분류 코드 (J: 주식)
        "fid_input_iscd": stock_code   # 입력 종목코드
      },
      error_prefix="주식 대차대조표 조회"
    )

  def get_kr_stock_income_statement(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 국내 주식 손익계산서를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 분기별 손익계산서 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/finance/income-statement",
      tr_id="FHKST66430200",
      params={
        "FID_DIV_CLS_CODE": "1",       # 분류 구분 코드 (0:년, 1:분기)
        "fid_cond_mrkt_div_code": "J", # 조건 시장 분류 코드 (J: 주식)
        "fid_input_iscd": stock_code   # 입력 종목코드
      },
      error_prefix="국내 주식 손익계산서 조회"
    )
  
  def get_kr_stock_financial_ratio(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 국내 주식 재무비율을 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 분기별 재무비율 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/finance/financial-ratio",
      tr_id="FHKST66430300",
      params={
        "FID_DIV_CLS_CODE": "1",       # 분류 구분 코드 (0:년, 1:분기)
        "fid_cond_mrkt_div_code": "J", # 조건 시장 분류 코드 (J:주식)
        "fid_input_iscd": stock_code   # 입력 종목코드
      },
      error_prefix="국내 주식 재무비율 조회"
    )
  
  def get_kr_stock_profit_ratio(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 국내 주식 수익성비율을 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 분기별 수익성비율 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/finance/profit-ratio",
      tr_id="FHKST66430400",
      params={
        "fid_input_iscd": stock_code, # 입력 종목코드
        "FID_DIV_CLS_CODE": "1",      # 분류 구분 코드 (0:년, 1:분기)
        "fid_cond_mrkt_div_code": "J" # 조건 시장 분류 코드 (J:주식)
      },
      error_prefix="국내 주식 수익성비율 조회"
    )

  def get_kr_stock_other_major_ratio(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 국내 주식 기타주요비율을 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 분기별 기타주요비율 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/finance/other-major-ratios",
      tr_id="FHKST66430500",
      params={
        "fid_input_iscd": stock_code, # 입력 종목코드
        "fid_div_cls_code": "1",      # 분류 구분 코드(0:년, 1:분기)
        "fid_cond_mrkt_div_code": "J" # 조건 시장 분류 코드 (J:주식)
      },
      error_prefix="국내 주식 기타주요비율 조회"
    )

  def get_kr_stock_stability_ratio(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 국내 주식 안정성비율을 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 분기별 안정성비율 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/finance/stability-ratio",
      tr_id="FHKST66430600",
      params={
        "fid_input_iscd": stock_code, # 입력 종목코드
        "fid_div_cls_code": "1",      # 분류 구분 코드 (0:년, 1:분기)
        "fid_cond_mrkt_div_code": "J" # 조건 시장 분류 코드 (J:주식)
      },
      error_prefix="국내 주식 안정성비율 조회"
    )

  def get_kr_stock_growth_ratio(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 국내 주식 성장성비율을 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 분기별 성장성비율 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/finance/growth-ratio",
      tr_id="FHKST66430800",
      params={
        "fid_input_iscd": stock_code, # 입력 종목코드
        "fid_div_cls_code": "1",      # 분류 구분 코드 (0:년, 1:분기)
        "fid_cond_mrkt_div_code": "J" # 조건 시장 분류 코드 (J:주식)
      },
      error_prefix="국내 주식 성장성비율 조회"
    )
  
  def get_kr_stock_inquire_price_basic(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 현재가] 국내 주식 현재가를 조회합니다.
    
    Note:
        현재 이 함수의 `path`와 `tr_id`가 '성장성비율' 조회와 동일하게
        설정되어 있습니다. 올바른 현재가 조회(예: FHKST01010100)로 수정이 필요합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 현재가 정보 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/finance/growth-ratio",
      tr_id="FHKST66430800",
      params={
        "fid_input_iscd": stock_code, # 입력 종목코드
        "fid_div_cls_code": "1",      # 분류 구분 코드 (0:년, 1:분기)
        "fid_cond_mrkt_div_code": "J" # 조건 시장 분류 코드 (J:주식)
      },
      error_prefix="국내 주식 성장성비율 조회"
    )
  
  def get_kr_stock_dividend(self, stock_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 기간별 배당금 정보를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.
      start_date (str): 조회 시작일 (YYYYMMDD 형식).
      end_date (str): 조회 종료일 (YYYYMMDD 형식).

    Returns:
      List[Dict[str, Any]]: 조회된 기간 내 배당금 정보 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/ksdinfo/dividend",
      tr_id="HHKDB669102C0",
      params={
        "CTS": "",            # 연속 조회 검증값 (첫 조회 시 빈칸)
        "GB1": "0",           # 조회구분 (0:배당전체, 1:결산배당, 2:중간배당)
        "F_DT": start_date,   # 시작일
        "T_DT": end_date,     # 종료일
        "SHT_CD": stock_code, # 입력 종목코드
        "HIGH_GB": "",        # 고배당여부 (빈칸)
      },
      error_prefix="국내 주식 예탁원 정보(배당일정) 조회"
    )
  
  def get_kr_stock_estimate_perform(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 국내 주식 종목추정실적을 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 종목추정실적 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/estimate-perform",
      tr_id="HHKST668300C0",
      params={
        "SHT_CD": stock_code # 종목코드
      },
      error_prefix="국내 주식 종목추정실적 조회"
    )
  
  def get_kr_stock_invest_opinion(self, stock_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 기간별 종목 투자 의견을 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.
      start_date (str): 조회 시작일 (YYYYMMDD 형식).
      end_date (str): 조회 종료일 (YYYYMMDD 형식).

    Returns:
      List[Dict[str, Any]]: 조회된 기간 내 투자 의견 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/invest-opinion",
      tr_id="FHKST663300C0",
      params={
        "FID_COND_MRKT_DIV_CODE": "J",    # 조건 시장 분류 코드(J:주식)
        "FID_COND_SCR_DIV_CODE": "16633", # 조건 화면 분류 코드 (Primary Key)
        "FID_INPUT_ISCD": stock_code,     # 입력 종목코드
        "FID_INPUT_DATE_1": start_date,   # 시작일
        "FID_INPUT_DATE_2": end_date,     # 종료일
      },
      error_prefix="국내 주식 종목투자의견 조회"
    )
  
  def get_kr_stock_invest_opbysec(self, stock_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """[국내 주식 정보] 기간별 증권사별 투자의견을 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.
      start_date (str): 조회 시작일 (YYYYMMDD 형식).
      end_date (str): 조회 종료일 (YYYYMMDD 형식).

    Returns:
      List[Dict[str, Any]]: 조회된 기간 내 증권사별 투자의견 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/invest-opbysec",
      tr_id="FHKST663400C0",
      params={
        "FID_COND_MRKT_DIV_CODE": "J",    # 조건 시장 분류 코드(J:주식)
        "FID_COND_SCR_DIV_CODE": "16633", # 조건 화면 분류 코드 (Primary Key)
        "FID_INPUT_ISCD": stock_code,     # 입력 종목코드
        "FID_DIV_CLS_CODE": "0",          # 분류구분코드 (0: 전체, 1: 매수, 2: 중립, 3: 매도)
        "FID_INPUT_DATE_1": start_date,   # 시작일
        "FID_INPUT_DATE_2": end_date,     # 종료일
      },
      error_prefix="국내 주식 증권사별 투자의견 조회"
    )
  
  def get_kr_stock_price_basic(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 시세] 국내 주식의 기본 시세를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 국내 주식 기본 시세 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/inquire-price",
      tr_id="FHKST01010100",
      params={
        "FID_COND_MRKT_DIV_CODE": "J", # 조건 시장 분류 코드 (J:KRX, NX:NXT, UN:통합)
        "FID_INPUT_ISCD": stock_code   # 입력 종목코드
      },
      error_prefix="국내 주식 현재가 기본 시세 조회"
    )
  
  def get_kr_stock_price_detail(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 시세] 국내 주식의 세부 시세를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 국내 주식 세부 시세 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/inquire-price-2",
      tr_id="FHPST01010000",
      params={
        "FID_COND_MRKT_DIV_CODE": "J", # 조건 시장 분류 코드 (J:KRX, NX:NXT, UN:통합)
        "FID_INPUT_ISCD": stock_code   # 입력 종목코드
      },
      error_prefix="국내 주식 현재가 세부 시세 조회"
    )
  
  def get_kr_stock_asking_price(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 시세] 국내 주식의 호가/예상체결 정보를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 국내 주식 세부 시세 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/inquire-asking-price-exp-ccn",
      tr_id="FHKST01010200",
      params={
        "FID_COND_MRKT_DIV_CODE": "J", # 조건 시장 분류 코드 (J:KRX, NX:NXT, UN:통합)
        "FID_INPUT_ISCD": stock_code   # 입력 종목코드
      },
      error_prefix="국내 주식 호가/예상체결 정보 조회"
    )
  
  def get_kr_stock_investor(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 시세] 국내 주식의 투자자 정보를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 국내 주식 세부 시세 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/inquire-investor",
      tr_id="FHKST01010900",
      params={
        "FID_COND_MRKT_DIV_CODE": "J", # 조건 시장 분류 코드 (J:KRX, NX:NXT, UN:통합)
        "FID_INPUT_ISCD": stock_code   # 입력 종목코드
      },
      error_prefix="국내 주식 투자자 정보 조회"
    )
  
  def get_kr_stock_member(self, stock_code: str) -> List[Dict[str, Any]]:
    """[국내 주식 시세] 국내 주식의 회원사 정보를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.

    Returns:
      List[Dict[str, Any]]: 조회된 국내 주식 세부 시세 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/inquire-member",
      tr_id="FHKST01010600",
      params={
        "FID_COND_MRKT_DIV_CODE": "J", # 조건 시장 분류 코드 (J:KRX, NX:NXT, UN:통합)
        "FID_INPUT_ISCD": stock_code   # 입력 종목코드
      },
      error_prefix="국내 주식 회원사 정보 조회"
    )
  
  def get_kr_stock_daily_itemchartprice(self, stock_code: str, start_date: str, end_date: str) -> List[Dict[str, Any]]:
    """[국내 주식 시세] 국내 주식의 기간별 시세를 조회합니다.
    
    Args:
      stock_code (str): 조회할 종목의 표준 코드.
      start_date (str): 조회 시작일 (YYYYMMDD 형식).
      end_date (str): 조회 종료일 (YYYYMMDD 형식).

    Returns:
      List[Dict[str, Any]]: 조회된 국내 주식 세부 시세 딕셔너리의 리스트.
    """
    return self._send_request(
      path="/uapi/domestic-stock/v1/quotations/inquire-daily-itemchartprice",
      tr_id="FHKST03010100",
      params={
        "FID_COND_MRKT_DIV_CODE": "J",  # 조건 시장 분류 코드 (J:KRX, NX:NXT, UN:통합)
        "FID_INPUT_ISCD": stock_code,   # 입력 종목코드
        "FID_INPUT_DATE_1": start_date, # 시작일
        "FID_INPUT_DATE_2": end_date,   # 종료일
        "FID_PERIOD_DIV_CODE": "D",     # 기간분류코드 (D:일봉, W:주봉, M:월봉, Y:년봉)
        "FID_ORG_ADJ_PRC": "0"          # 수정주가 원주가 가격 여부 (0:수정주가, 1:원주가)
      },
      error_prefix="국내 주식 기간별 시세 조회"
    )