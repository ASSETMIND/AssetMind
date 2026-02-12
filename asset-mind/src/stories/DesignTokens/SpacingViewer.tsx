import React from 'react';

interface SpacingToken {
  name: string;
  value: string;
  pixels: number;
}

interface SpacingViewerProps {
  title?: string;
}

export const SpacingViewer: React.FC<SpacingViewerProps> = ({ 
  title = 'Spacing System'
}) => {
  // Tailwind default spacing scale
  const spacingTokens: SpacingToken[] = [
    { name: '0', value: '0px', pixels: 0 },
    { name: '1', value: '0.25rem', pixels: 4 },
    { name: '2', value: '0.5rem', pixels: 8 },
    { name: '3', value: '0.75rem', pixels: 12 },
    { name: '4', value: '1rem', pixels: 16 },
    { name: '5', value: '1.25rem', pixels: 20 },
    { name: '6', value: '1.5rem', pixels: 24 },
    { name: '8', value: '2rem', pixels: 32 },
    { name: '10', value: '2.5rem', pixels: 40 },
    { name: '12', value: '3rem', pixels: 48 },
    { name: '16', value: '4rem', pixels: 64 },
    { name: '20', value: '5rem', pixels: 80 },
    { name: '24', value: '6rem', pixels: 96 },
    { name: '32', value: '8rem', pixels: 128 },
  ];

  return (
    <div className="w-full max-w-7xl mx-auto p-8 bg-background-primary">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">
          {title}
        </h1>
        <p className="text-text-secondary">
          Tailwind spacing scale visualization
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
                  <code className="inline-block mt-2 text-xs text-text-secondary font-mono bg-background-elevated px-2 py-1 rounded">
                    p-{token.name} / m-{token.name}
                  </code>
                </div>
              </div>

              {/* Visual Box */}
              <div className="flex-1 flex items-center gap-4">
                {/* Padding Example */}
                <div className="flex-1">
                  <div className="text-xs text-text-secondary mb-2">Padding (p-{token.name})</div>
                  <div className="bg-background-elevated border-2 border-dashed border-border-divider">
                    <div 
                      style={{ padding: token.value }}
                      className="bg-brand-primary/20 border border-brand-primary"
                    >
                      <div className="h-8 bg-brand-primary rounded"></div>
                    </div>
                  </div>
                </div>

                {/* Margin Example */}
                <div className="flex-1">
                  <div className="text-xs text-text-secondary mb-2">Margin (m-{token.name})</div>
                  <div className="bg-background-elevated border-2 border-dashed border-border-divider p-2">
                    <div 
                      style={{ margin: token.value }}
                      className="h-8 bg-brand-primary rounded"
                    ></div>
                  </div>
                </div>

                {/* Width/Height Example */}
                <div className="flex-1">
                  <div className="text-xs text-text-secondary mb-2">Size (w-{token.name})</div>
                  <div className="bg-background-elevated border-2 border-dashed border-border-divider p-4 flex items-center justify-center">
                    <div 
                      style={{ width: token.value, height: token.value }}
                      className="bg-brand-primary rounded"
                    ></div>
                  </div>
                </div>
              </div>
            </div>
          </div>
        ))}
      </div>

      {/* Usage Guide */}
      <div className="mt-12 p-6 bg-background-surface rounded-lg border border-border-divider">
        <h3 className="text-lg font-semibold text-text-primary mb-3">
          Usage Examples
        </h3>
        <div className="space-y-4 text-sm">
          <div className="grid grid-cols-2 gap-4">
            <div>
              <strong className="text-text-primary">Padding:</strong>
              <code className="block mt-1 p-2 bg-background-elevated rounded text-xs font-mono">
                p-4, px-6, py-2, pt-8
              </code>
            </div>
            <div>
              <strong className="text-text-primary">Margin:</strong>
              <code className="block mt-1 p-2 bg-background-elevated rounded text-xs font-mono">
                m-4, mx-6, my-2, mt-8
              </code>
            </div>
            <div>
              <strong className="text-text-primary">Gap:</strong>
              <code className="block mt-1 p-2 bg-background-elevated rounded text-xs font-mono">
                gap-4, gap-x-6, gap-y-2
              </code>
            </div>
            <div>
              <strong className="text-text-primary">Space:</strong>
              <code className="block mt-1 p-2 bg-background-elevated rounded text-xs font-mono">
                space-x-4, space-y-6
              </code>
            </div>
          </div>
        </div>
      </div>
    </div>
  );
};