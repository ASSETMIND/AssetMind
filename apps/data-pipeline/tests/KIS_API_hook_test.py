# tests/hooks/test_KIS_API_hook.py

import pytest
import requests
import json
from unittest.mock import patch, MagicMock
from datetime import datetime, timedelta

# 테스트 대상 모듈 및 클래스 임포트
from src.hooks.KIS_API_hook import KISAPIHook
from src.errors.KIS_API_errors import KISAPIError, KISAuthenticationError, KISDataError

# --- Pytest Fixtures: 테스트 환경 설정 ---

@pytest.fixture
def mock_env_vars(monkeypatch):
  """테스트를 위한 KIS API 환경 변수를 모의(mock) 설정합니다."""
  monkeypatch.setenv("KIS_APP_KEY", "test_app_key")
  monkeypatch.setenv("KIS_APP_SECRET", "test_app_secret")

@pytest.fixture
def api_hook(mock_env_vars, tmp_path):
  """테스트에 사용될 KISAPIHook 인스턴스를 생성하고 임시 파일 경로를 설정합니다."""
  hook = KISAPIHook()
  hook.token_filepath = tmp_path / "kis_token.json"
  return hook

# --- 테스트 케이스 ---

class TestKISAPIHookInitialization:
  """KISAPIHook 클래스의 초기화 로직을 테스트합니다."""

  def test_initialization_success(self, mock_env_vars):
    """환경 변수가 정상일 때, KISAPIHook 인스턴스 생성 성공 테스트"""
    hook = KISAPIHook()
    assert hook.app_key == "test_app_key"
    assert hook.app_secret == "test_app_secret"

  def test_initialization_fail_without_env_vars(self):
    """환경 변수가 없을 때, KISAPIError 예외 발생 테스트"""
    with pytest.raises(KISAPIError):
      KISAPIHook()

class TestAccessTokenManagement:
  """접근 토큰 발급 및 캐싱 전략을 테스트합니다."""

  @patch('src.hooks.KIS_API_hook.requests.post')
  def test_get_new_access_token_success(self, mock_post, api_hook):
    """새로운 접근 토큰 발급 성공 및 파일 저장 테스트"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
      "access_token": "new_dummy_token",
      "access_token_token_expired": (datetime.now() + timedelta(hours=6)).strftime('%Y-%m-%d %H:%M:%S')
    }
    mock_post.return_value = mock_response

    token = api_hook._get_new_access_token()

    assert token == "Bearer new_dummy_token"
    assert api_hook.token_filepath.exists()

  @patch('src.hooks.KIS_API_hook.requests.post', side_effect=requests.exceptions.RequestException)
  def test_get_new_access_token_fail(self, mock_post, api_hook):
    """네트워크 오류로 인한 토큰 발급 실패 시 KISAuthenticationError 발생 테스트"""
    with pytest.raises(KISAuthenticationError):
      api_hook._get_new_access_token()

  def test_get_access_token_from_valid_file_cache(self, api_hook):
    """유효한 파일 캐시로부터 토큰을 성공적으로 읽어오는지 테스트"""
    valid_token = "Bearer file_cached_token"
    expired_at = (datetime.now() + timedelta(hours=1)).strftime('%Y-%m-%d %H:%M:%S')
    token_info = {"access_token": valid_token, "expired_at": expired_at}
    with open(api_hook.token_filepath, 'w') as f:
      json.dump(token_info, f)

    with patch.object(api_hook, '_get_new_access_token') as mock_get_new:
      token = api_hook.get_access_token()
      assert token == valid_token
      mock_get_new.assert_not_called()

class TestRequestSending:
  """_send_request 메서드의 요청 및 응답 처리 로직을 테스트합니다."""

  @patch('src.hooks.KIS_API_hook.requests.get')
  def test_send_request_success_parsing(self, mock_get, api_hook):
    """API 성공 응답을 올바르게 파싱하는지 테스트"""
    mock_response = MagicMock()
    mock_response.json.return_value = {
      'rt_cd': '0', 'msg1': 'Success',
      'output1': [{'key1': 'value1'}],
      'output2': [{'key2': 'value2'}]
    }
    mock_get.return_value = mock_response
    api_hook._access_token = "dummy_token"
    
    result = api_hook._send_request("path", "tr_id", {}, "prefix")

    assert len(result) == 2
    assert result[0]['data_source'] == 'output1'
    assert result[1]['data_source'] == 'output2'

  @patch('src.hooks.KIS_API_hook.requests.get')
  def test_send_request_api_business_error(self, mock_get, api_hook):
    """API 비즈니스 오류(rt_cd != '0') 시 KISDataError 발생 테스트"""
    mock_response = MagicMock()
    mock_response.json.return_value = {'rt_cd': '1', 'msg1': 'Error Message'}
    mock_get.return_value = mock_response
    api_hook._access_token = "dummy_token"
    
    with pytest.raises(KISDataError, match="prefix 실패: Error Message"):
      api_hook._send_request("path", "tr_id", {}, "prefix")

  @patch('src.hooks.KIS_API_hook.time.sleep')
  @patch('src.hooks.KIS_API_hook.requests.get', side_effect=requests.exceptions.RequestException)
  def test_send_request_retry_and_fail(self, mock_get, mock_sleep, api_hook):
    """네트워크 오류 시, 3회 재시도 후 최종 실패하는지 테스트"""
    api_hook._access_token = "dummy_token"
    
    with pytest.raises(KISDataError, match="API 서버 접속 실패"):
      api_hook._send_request("path", "tr_id", {}, "prefix")
    assert mock_get.call_count == 3

class TestAPIWrapperMethods:
  """각 API 엔드포인트를 감싸는 래퍼(wrapper) 메서드들의 정확성 테스트 그룹."""

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_basic_info_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_basic_info가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_basic_info(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/quotations/search-stock-info",
      tr_id="CTPF1002R",
      params={"PDNO": stock_code, "PRDT_TYPE_CD": "300"},
      error_prefix="주식 기본 정보 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_balance_sheet_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_balance_sheet가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_balance_sheet(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/finance/balance-sheet",
      tr_id="FHKST66430100",
      params={"FID_DIV_CLS_CODE": "1", "fid_cond_mrkt_div_code": "J", "fid_input_iscd": stock_code},
      error_prefix="주식 대차대조표 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_income_statement_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_income_statement가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_income_statement(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/finance/income-statement",
      tr_id="FHKST66430200",
      params={"FID_DIV_CLS_CODE": "1", "fid_cond_mrkt_div_code": "J", "fid_input_iscd": stock_code},
      error_prefix="국내 주식 손익계산서 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_financial_ratio_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_financial_ratio가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_financial_ratio(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/finance/financial-ratio",
      tr_id="FHKST66430300",
      params={"FID_DIV_CLS_CODE": "1", "fid_cond_mrkt_div_code": "J", "fid_input_iscd": stock_code},
      error_prefix="국내 주식 재무비율 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_profit_ratio_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_profit_ratio가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_profit_ratio(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/finance/profit-ratio",
      tr_id="FHKST66430400",
      params={"fid_input_iscd": stock_code, "FID_DIV_CLS_CODE": "1", "fid_cond_mrkt_div_code": "J"},
      error_prefix="국내 주식 수익성비율 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_other_major_ratio_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_other_major_ratio가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_other_major_ratio(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/finance/other-major-ratios",
      tr_id="FHKST66430500",
      params={"fid_input_iscd": stock_code, "fid_div_cls_code": "1", "fid_cond_mrkt_div_code": "J"},
      error_prefix="국내 주식 기타주요비율 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_stability_ratio_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_stability_ratio가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_stability_ratio(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/finance/stability-ratio",
      tr_id="FHKST66430600",
      params={"fid_input_iscd": stock_code, "fid_div_cls_code": "1", "fid_cond_mrkt_div_code": "J"},
      error_prefix="국내 주식 안정성비율 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_growth_ratio_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_growth_ratio가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_growth_ratio(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/finance/growth-ratio",
      tr_id="FHKST66430800",
      params={"fid_input_iscd": stock_code, "fid_div_cls_code": "1", "fid_cond_mrkt_div_code": "J"},
      error_prefix="국내 주식 성장성비율 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_inquire_price_basic_calls_incorrectly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_inquire_price_basic가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_inquire_price_basic(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/finance/growth-ratio",
      tr_id="FHKST66430800",
      params={"fid_input_iscd": stock_code, "fid_div_cls_code": "1", "fid_cond_mrkt_div_code": "J"},
      error_prefix="국내 주식 성장성비율 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_dividend_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_dividend가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code, start_date, end_date = "005930", "20240101", "20241231"
    api_hook.get_kr_stock_dividend(stock_code, start_date, end_date)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/ksdinfo/dividend",
      tr_id="HHKDB669102C0",
      params={"CTS": "", "GB1": "0", "F_DT": start_date, "T_DT": end_date, "SHT_CD": stock_code, "HIGH_GB": ""},
      error_prefix="국내 주식 예탁원 정보(배당일정) 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_estimate_perform_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_estimate_perform가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code = "005930"
    api_hook.get_kr_stock_estimate_perform(stock_code)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/quotations/estimate-perform",
      tr_id="HHKST668300C0",
      params={"SHT_CD": stock_code},
      error_prefix="국내 주식 종목추정실적 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_invest_opinion_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_invest_opinion가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code, start_date, end_date = "005930", "20240101", "20241231"
    api_hook.get_kr_stock_invest_opinion(stock_code, start_date, end_date)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/quotations/invest-opinion",
      tr_id="FHKST663300C0",
      params={
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "16633",
        "FID_INPUT_ISCD": stock_code,
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
      },
      error_prefix="국내 주식 종목투자의견 조회"
    )

  @patch('src.hooks.KIS_API_hook.KISAPIHook._send_request')
  def test_get_kr_stock_invest_opbysec_calls_correctly(self, mock_send_request, api_hook):
    """[정상] get_kr_stock_invest_opbysec가 올바른 인자로 _send_request를 호출하는지 검증합니다."""
    stock_code, start_date, end_date = "005930", "20240101", "20241231"
    api_hook.get_kr_stock_invest_opbysec(stock_code, start_date, end_date)
    mock_send_request.assert_called_once_with(
      path="/uapi/domestic-stock/v1/quotations/invest-opbysec",
      tr_id="FHKST663400C0",
      params={
        "FID_COND_MRKT_DIV_CODE": "J",
        "FID_COND_SCR_DIV_CODE": "16633",
        "FID_INPUT_ISCD": stock_code,
        "FID_DIV_CLS_CODE": "0",
        "FID_INPUT_DATE_1": start_date,
        "FID_INPUT_DATE_2": end_date,
      },
      error_prefix="국내 주식 증권사별 투자의견 조회"
    )

if __name__ == "__main__":
  """
  이 스크립트를 직접 실행할 경우, pytest를 통해 모든 테스트를 수행하고
  상세한 결과를 터미널에 출력합니다.
  """
  print("FinSignt: `KIS_API_hook.py` 모듈에 대한 단위 테스트를 시작합니다.")
  
  # pytest.main()에 인자를 전달하여 실행 방식을 제어합니다.
  # '-v': 상세한 결과 출력
  # __file__: 현재 파일에 대해서만 테스트 실행
  pytest.main(['-v', __file__])