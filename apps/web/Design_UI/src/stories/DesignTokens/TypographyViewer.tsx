import React from 'react';
import type { TypographyToken } from '../../lib/design-tokens';

interface TypographyViewerProps {
  tokens: TypographyToken[];
  title?: string;
  sampleText?: string;
}

export const TypographyViewer: React.FC<TypographyViewerProps> = ({ 
  tokens,
  title = 'Typography System',
  sampleText = 'The quick brown fox jumps over the lazy dog'
}) => {
  return (
    <div className="w-full max-w-7xl mx-auto p-8 bg-background-primary">
      {/* Header */}
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">
          {title}
        </h1>
        <p className="text-text-secondary">
          Tailwind Config font styles visualization
        </p>
      </div>

      {/* Typography Grid */}
      <div className="space-y-8">
        {tokens.map((token) => (
          <div 
            key={token.name}
            className="p-6 bg-background-surface rounded-lg border border-border-divider"
          >
            {/* Token Info Header */}
            <div className="flex items-start justify-between mb-4 pb-4 border-b border-border-divider">
              <div className="space-y-2">
                <h3 className="text-lg font-semibold text-text-primary">
                  {token.name.toUpperCase()}
                </h3>
                <code className="text-xs text-text-secondary font-mono bg-background-elevated px-3 py-1 rounded">
                  text-{token.name}
                </code>
              </div>
              
              {/* Specs */}
              <div className="grid grid-cols-2 gap-4 text-sm">
                <div>
                  <span className="text-text-secondary">Size:</span>
                  <span className="text-text-primary ml-2 font-mono">{token.fontSize}</span>
                </div>
                <div>
                  <span className="text-text-secondary">Weight:</span>
                  <span className="text-text-primary ml-2 font-mono">{token.fontWeight}</span>
                </div>
                <div>
                  <span className="text-text-secondary">Line Height:</span>
                  <span className="text-text-primary ml-2 font-mono">{token.lineHeight}</span>
                </div>
                <div>
                  <span className="text-text-secondary">Letter Spacing:</span>
                  <span className="text-text-primary ml-2 font-mono">{token.letterSpacing}</span>
                </div>
              </div>
            </div>

            {/* Sample Text */}
            <div
              style={{
                fontSize: token.fontSize,
                lineHeight: token.lineHeight,
                letterSpacing: token.letterSpacing,
                fontWeight: token.fontWeight,
              }}
              className="text-text-primary"
            >
              {sampleText}
            </div>

            {/* Copy Button */}
            <button
              onClick={() => {
                navigator.clipboard.writeText(`text-${token.name}`);
              }}
              className="mt-4 text-xs text-brand-primary hover:text-brand-primaryHover transition-colors"
            >
              Copy Tailwind Class
            </button>
          </div>
        ))}
      </div>

      {/* Usage Guide */}
      <div className="mt-12 p-6 bg-background-surface rounded-lg border border-border-divider">
        <h3 className="text-lg font-semibold text-text-primary mb-3">
          Usage Guide
        </h3>
        <div className="space-y-3 text-sm text-text-secondary">
          <div>
            <strong className="text-text-primary">Body Styles (B):</strong> For body text and paragraphs
          </div>
          <div>
            <strong className="text-text-primary">Label Styles (L):</strong> For labels, buttons, and UI elements
          </div>
          <div className="mt-4 p-3 bg-background-elevated rounded font-mono text-xs">
            {'<p className="text-b1">Your text here</p>'}
          </div>
        </div>
      </div>
    </div>
  );
};