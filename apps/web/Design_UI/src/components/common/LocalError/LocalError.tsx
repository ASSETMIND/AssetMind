import { Button } from "../Button";
import { WarningIcon } from "../../icons/WarningIcon";

interface LocalErrorProps {
  message?: string;
  onRetry?: () => void;
}

/**
 * LocalError 컴포넌트
 *
 * 특정 API 실패 시 해당 영역에 인라인으로 노출되는 부분 오류 UI
 *
 * 디자인 스펙:
 * - 컨테이너: 채우기 x 허그 (width: 100%, height: fit-content)
 * - 아이콘: 30x28, #9F9F9F
 * - 텍스트: 14px regular, #9F9F9F, 컨테이너 너비에 맞게 채우기
 * - 버튼: Button small variant, 텍스트 "다시 시도"
 */
export const LocalError = ({
  message = "데이터를 불러오는 데 실패했습니다.",
  onRetry,
}: LocalErrorProps) => {
  return (
    <div
      style={{
        width: "100%",
        display: "flex",
        flexDirection: "column",
        alignItems: "center",
        justifyContent: "center",
        gap: "16px",
        padding: "40px 0",
      }}
    >
      {/* 경고 아이콘 — 30x28, #9F9F9F */}
      <WarningIcon color="#9F9F9F" />

      {/* 텍스트 — 14px regular, #9F9F9F */}
      <p
        style={{
          fontSize: "14px",
          fontWeight: 400,
          color: "#9F9F9F",
          textAlign: "center",
          margin: 0,
          width: "100%",
        }}
      >
        {message}
      </p>

      {/* 다시 시도 버튼 — 보라색 small 버튼 */}
      <Button
        className="bg-[#6D4AE6] hover:bg-[#5b3dc2] text-white text-[14px] font-normal rounded-[9px] px-4 h-[38px] whitespace-nowrap"
        onClick={onRetry}
      >
        다시 시도
      </Button>
    </div>
  );
};