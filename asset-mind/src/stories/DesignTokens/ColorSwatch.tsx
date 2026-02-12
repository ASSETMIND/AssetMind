import React, { useState } from 'react';
import type { ColorToken } from '../../lib/design-tokens';
import { needsLightText } from '../../lib/design-tokens/extractTokens';

interface ColorSwatchProps {
  token: ColorToken;
  showCode?: boolean;
}

export const ColorSwatch: React.FC<ColorSwatchProps> = ({ 
  token, 
  showCode = true 
}) => {
  const [copied, setCopied] = useState(false);
  const isLight = needsLightText(token.value);

  const handleCopy = () => {
    navigator.clipboard.writeText(token.value);
    setCopied(true);
    setTimeout(() => setCopied(false), 2000);
  };

  const getTailwindClass = () => {
    if (token.subcategory) {
      return `${token.category}-${token.subcategory}-${token.name.split('.')[1]}`;
    }
    return `${token.category}-${token.name}`;
  };

  return (
    <div className="flex flex-col gap-2 min-w-[200px]">
      <button
        onClick={handleCopy}
        className="relative h-24 rounded-lg transition-all hover:scale-105 hover:shadow-lg cursor-pointer group"
        style={{ backgroundColor: token.value }}
        title="Click to copy"
      >
        {copied && (
          <div className="absolute inset-0 flex items-center justify-center bg-black/50 rounded-lg">
            <span className="text-white text-sm font-medium">Copied!</span>
          </div>
        )}
        
        <div className={`absolute inset-0 flex items-center justify-center opacity-0 group-hover:opacity-100 transition-opacity ${isLight ? 'text-white' : 'text-black'}`}>
          <span className="text-xs font-mono font-medium">{token.value}</span>
        </div>
      </button>

      <div className="flex flex-col gap-1">
        <div className="flex items-center justify-between">
          <span className="text-sm font-medium text-text-primary">
            {token.name}
          </span>
        </div>

        {showCode && (
          <code className="text-xs text-text-secondary font-mono bg-background-surface px-2 py-1 rounded">
            {getTailwindClass()}
          </code>
        )}

        <button
          onClick={handleCopy}
          className="text-xs text-text-secondary font-mono hover:text-brand-primary transition-colors text-left"
        >
          {token.value}
        </button>
      </div>
    </div>
  );
};