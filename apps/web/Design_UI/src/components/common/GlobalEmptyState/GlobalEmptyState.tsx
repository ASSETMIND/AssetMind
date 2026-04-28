import { BoxIcon } from "../../icons/BoxIcon";
import { MoonIcon } from "../../icons/MoonIcon";

type EmptyStateVariant =
  | "no-data"       // Stock Chart Empty — 박스 아이콘, "조회된 종목이 없습니다."
  | "market-closed"; // 호가창/차트/AI패널 Empty — 달 아이콘, 시장 휴장 안내

type EmptyStateBadge = "inline" | "badge";

interface GlobalEmptyStateProps {
  variant?: EmptyStateVariant;
  display?: EmptyStateBadge;
  message?: string;
  subMessage?: string;
  className?: string;
}

/**
 * GlobalEmptyState 컴포넌트
 *
 * 데이터 없음 / 시장 휴장 상태 UI
 *
 * @variant no-data       — 박스 아이콘, 조회 결과 없음 (Stock Chart)
 * @variant market-closed — 달 아이콘, 시장 휴장 안내 (호가창, 차트, AI 패널)
 *
 * @display inline — 영역 중앙에 아이콘 + 텍스트 (이미지 1, 2)
 * @display badge  — 우측 상단 소형 뱃지 (이미지 3, 4, 5)
 */
export const GlobalEmptyState = ({
  variant = "market-closed",
  display = "inline",
  message,
  subMessage,
  className,
}: GlobalEmptyStateProps) => {
  const defaultMessage =
    variant === "no-data"
      ? "조회된 종목이 없습니다."
      : "지금은 시장 휴장 시간입니다.";

  const defaultSubMessage =
    variant === "market-closed"
      ? "정규장 개장 시간에 실시간 데이터가 업데이트됩니다."
      : undefined;

  const resolvedMessage = message ?? defaultMessage;
  const resolvedSubMessage = subMessage ?? defaultSubMessage;

  // ─── Badge variant ───────────────────────────────────────
  if (display === "badge") {
    return (
      <div
        style={{
          display: "inline-flex",
          alignItems: "center",
          gap: "5px",
          padding: "5px",
          backgroundColor: "#2C2C30",
          borderRadius: "4px",
          width: "64px",
          height: "25px",
          boxSizing: "border-box",
        }}
        className={className}
      >
        <MoonIcon color="#FFFFFF" width={12} height={12} />
        <span
          style={{
            fontSize: "10px",
            fontWeight: 500,
            color: "#FFFFFF",
            whiteSpace: "nowrap",
          }}
        >
          휴장 시간
        </span>
      </div>
    );
  }

  // ─── Inline variant ───────────────────────────────────────
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
      className={className}
    >
      {variant === "no-data" ? (
        <BoxIcon color="#9F9F9F" />
      ) : (
        <MoonIcon color="#9F9F9F" />
      )}

      <div
        style={{
          display: "flex",
          flexDirection: "column",
          alignItems: "center",
          gap: "6px",
        }}
      >
        <p
          style={{
            fontSize: "14px",
            fontWeight: 400,
            color: "#9F9F9F",
            textAlign: "center",
            margin: 0,
          }}
        >
          {resolvedMessage}
        </p>
        {resolvedSubMessage && (
          <p
            style={{
              fontSize: "14px",
              fontWeight: 400,
              color: "#9F9F9F",
              textAlign: "center",
              margin: 0,
            }}
          >
            {resolvedSubMessage}
          </p>
        )}
      </div>
    </div>
  );
};