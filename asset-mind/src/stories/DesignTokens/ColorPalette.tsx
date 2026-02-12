import React from 'react';
import type { ColorGroup } from '../../lib/design-tokens';
import { ColorSwatch } from './ColorSwatch';

interface ColorPaletteProps {
  groups: ColorGroup[];
  title?: string;
  showCode?: boolean;
}

export const ColorPalette: React.FC<ColorPaletteProps> = ({ 
  groups, 
  title = 'Color Palette',
  showCode = true,
}) => {
  return (
    <div className="w-full max-w-7xl mx-auto p-8 bg-background-primary">
      <div className="mb-8">
        <h1 className="text-3xl font-bold text-text-primary mb-2">
          {title}
        </h1>
        <p className="text-text-secondary">
          Tailwind Config auto-sync design token visualization
        </p>
      </div>

      <div className="space-y-12">
        {groups.map((group) => (
          <section key={group.category} className="space-y-4">
            <div className="border-b border-border-divider pb-3">
              <h2 className="text-xl font-semibold text-text-primary capitalize">
                {group.category}
              </h2>
              {group.description && (
                <p className="text-sm text-text-secondary mt-1">
                  {group.description}
                </p>
              )}
            </div>

            <div className="grid grid-cols-1 sm:grid-cols-2 md:grid-cols-3 lg:grid-cols-4 gap-6">
              {group.colors.map((color) => (
                <ColorSwatch 
                  key={`${group.category}-${color.name}`}
                  token={color}
                  showCode={showCode}
                />
              ))}
            </div>
          </section>
        ))}
      </div>

      <div className="mt-12 p-6 bg-background-surface rounded-lg border border-border-divider">
        <h3 className="text-lg font-semibold text-text-primary mb-3">
          Usage Guide
        </h3>
        <ul className="space-y-2 text-sm text-text-secondary">
          <li>Click: Copy HEX code to clipboard</li>
          <li>Hover: Preview HEX code</li>
          <li>Tailwind class: Use directly in your code</li>
        </ul>
      </div>
    </div>
  );
};