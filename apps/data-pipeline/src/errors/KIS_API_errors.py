class KISAPIError(Exception):
  """KIS API 관련 모든 예외의 기본 클래스."""
  pass

class KISAuthenticationError(KISAPIError):
  """KIS API 인증(토큰 발급) 과정에서 발생하는 예외."""
  pass

class KISDataError(KISAPIError):
  """KIS API 데이터 조회 실패 시 발생하는 예외."""
  pass