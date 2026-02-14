import React from 'react';

interface SpacingToken {
  name: string;
  value: string;
  pixels: number;
  usage?: string;
}

interface SpacingViewerProps {
  title?: string;
}

export const SpacingViewer: React.FC<SpacingViewerProps> = ({ 
  title = 'Spacing System'
}) => {
  // AssetMind 실제 디자인 spacing (피그마 기준)
  const spacingTokens: SpacingToken[] = [
    { name: '0', value: '0px', pixels: 0, usage: '간격 없음' },
    { name: '1', value: '4px', pixels: 4, usage: '최소 간격' },
    { name: '2', value: '8px', pixels: 8, usage: '작은 간격' },
    { name: '3', value: '12px', pixels: 12, usage: '기본 작은 간격' },
    { name: '4', value: '16px', pixels: 16, usage: '입력 필드 padding (상하)' },
    { name: '5', value: '20px', pixels: 20, usage: '입력 필드 padding (좌우)' },
    { name: '6', value: '24px', pixels: 24, usage: '요소 사이 간격' },
    { name: '7', value: '25px', pixels: 25, usage: '입력 필드 좌측 padding' },
    { name: '8', value: '32px', pixels: 32, usage: '큰 간격' },
    { name: '10', value: '40px', pixels: 40, usage: '큰 padding' },
    { name: '11', value: '45px', pixels: 45, usage: '모달 padding (좌우)' },
    { name: '12', value: '48px', pixels: 48, usage: '섹션 간격' },
    { name: '14', value: '54px', pixels: 54, usage: '버튼 높이' },
    { name: '16', value: '64px', pixels: 64, usage: '큰 섹션 간격' },
    { name: '20', value: '80px', pixels: 80, usage: '타이틀 영역' },
    { name: '31', value: '125px', pixels: 125, usage: '모달 상단 여백' },
    { name: '40', value: '160px', pixels: 160, usage: '큰 상단 여백' },
  ];

  return (
    <div className="w-full max-w-7xl mx-auto p-8 bg-background-primary">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">
          {title}
        </h1>
        <p className="text-text-secondary">
          AssetMind 디자인 시스템 spacing 스케일 (Figma 실측값 기준)
        </p>
      </div>

      {/* Spacing Grid */}
      <div className="space-y-6">
        {spacingTokens.map((token) => (
          <div 
            key={token.name}
            className="p-6 bg-background-surface rounded-lg border border-border-divider"
          >
            <div className="flex items-center gap-8">
              {/* Token Info */}
              <div className="w-48 flex-shrink-0">
                <h3 className="text-lg font-semibold text-text-primary mb-2">
                  {token.name}
                </h3>
                <div className="space-y-1 text-sm">
                  <div className="text-text-secondary">
                    Value: <span className="text-text-primary font-mono">{token.value}</span>
                  </div>
                  <div className="text-text-secondary">
                    Pixels: <span className="text-text-primary font-mono">{token.pixels}px</span>
                  </div>
                  {token.usage && (
                    <div className="text-text-secondary">
                      사용: <span className="text-text-primary">{token.usage}</span>
                    </div>
                  )}
                  <code className="inline-block mt-2 text-xs text-text-secondary font-mono bg-background-elevated px-2 py-1 rounded">
                    p-{token.name} / m-{token.name}
                  </code>
                </div>
              </div>

              {/* Visual Box */}
              <div className="flex-1 flex items-center gap-4">
                {/* Padding Example */}
                <div className="flex-1">
                  <div className="text-xs text-text-secondary mb-2">Padding</div>
                  <div className="bg-background-elevated border-2 border-dashed border-border-divider">
                    <div 
                      style={{ padding: `${token.pixels}px` }}
                      className="bg-brand-primary/20 border border-brand-primary"
                    >
                      <div className="h-8 bg-brand-primary rounded"></div>
                    </div>
                  </div>
                </div>

                {/* Margin Example */}
                <div className="flex-1">
                  <div className="text-xs text-text-secondary mb-2">Margin</div>
                  <div className="bg-background-elevated border-2 border-dashed border-border-divider p-2">
                    <div 
                      style={{ margin: `${token.pixels}px` }}
                      className="h-8 bg-brand-primary rounded"
                    ></div>
                  </div>
                </div>

                {/* Width/Height Example */}
                <div className="flex-1">
                  <div className="text-xs text-text-secondary mb-2">Size</div>
                  <div className="bg-background-elevated border-2 border-dashed border-border-divider p-4 flex items-center justify-center min-h-[100px]">
                    <div 
                      style={{ 
                        width: `${Math.min(token.pixels, 80)}px`, 
                        height: `${Math.min(token.pixels, 80)}px`
                      }}
                      className="bg-brand-primary rounded"
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* AssetMind Specific Usage */}
      <div className="mt-12 p-6 bg-background-surface rounded-lg border border-border-divider">
        <h3 className="text-lg font-semibold text-text-primary mb-3">
          📏 AssetMind 실제 Spacing 값 (Figma 실측)
        </h3>
        <div className="grid grid-cols-2 gap-6 text-sm">
          <div>
            <strong className="text-text-primary">로그인 모달 (PC):</strong>
            <ul className="mt-2 space-y-1 text-text-secondary font-mono text-xs">
              <li>• padding-left/right: <span className="text-brand-primary">45px</span></li>
              <li>• padding-top: <span className="text-brand-primary">125px</span></li>
              <li>• border-radius: 40px</li>
              <li>• 전체 크기: 539 x 741px</li>
            </ul>
          </div>
          <div>
            <strong className="text-text-primary">입력 필드:</strong>
            <ul className="mt-2 space-y-1 text-text-secondary font-mono text-xs">
              <li>• padding-top/bottom: <span className="text-brand-primary">16px</span></li>
              <li>• padding-left: <span className="text-brand-primary">25px</span></li>
              <li>• padding-right: <span className="text-brand-primary">20px</span></li>
              <li>• 필드 사이 간격: 16-24px</li>
            </ul>
          </div>
          <div>
            <strong className="text-text-primary">로그인 버튼:</strong>
            <ul className="mt-2 space-y-1 text-text-secondary font-mono text-xs">
              <li>• width: <span className="text-brand-primary">451px</span></li>
              <li>• height: <span className="text-brand-primary">54px</span></li>
              <li>• margin-top: 32px</li>
              <li>• border-radius: 8px</li>
            </ul>
          </div>
          <div>
            <strong className="text-text-primary">소셜 로그인:</strong>
            <ul className="mt-2 space-y-1 text-text-secondary font-mono text-xs">
              <li>• 버튼 사이 간격: <span className="text-brand-primary">16px</span></li>
              <li>• 상단 여백: <span className="text-brand-primary">24px</span></li>
              <li>• 구분선 margin: 32px</li>
            </ul>
          </div>
        </div>
      </div>

      {/* Usage Guide */}
      <div className="mt-8 p-6 bg-background-surface rounded-lg border border-border-divider">
        <h3 className="text-lg font-semibold text-text-primary mb-3">
          💡 Tailwind 사용 예시
        </h3>
        <div className="space-y-3">
          <div>
            <strong className="text-text-primary">모달 스타일:</strong>
            <code className="block mt-1 p-3 bg-background-elevated rounded text-xs font-mono">
              className="px-[45px] pt-[125px] pb-10 rounded-[40px]"
            </code>
          </div>
          <div>
            <strong className="text-text-primary">입력 필드:</strong>
            <code className="block mt-1 p-3 bg-background-elevated rounded text-xs font-mono">
              className="py-4 pl-[25px] pr-5 rounded-lg"
            </code>
          </div>
          <div>
            <strong className="text-text-primary">버튼:</strong>
            <code className="block mt-1 p-3 bg-background-elevated rounded text-xs font-mono">
              className="h-[54px] w-full rounded-lg"
            </code>
          </div>
        </div>
      </div>
    </div>
  );
};