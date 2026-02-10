import { useState } from 'react';
import Prism from 'prismjs';
import 'prismjs/themes/prism-tomorrow.css';
import 'prismjs/components/prism-typescript';
import 'prismjs/components/prism-jsx';
import 'prismjs/components/prism-tsx';
import 'prismjs/components/prism-css';
import 'prismjs/components/prism-bash';
import 'prismjs/components/prism-json';
import { cn } from '../../lib/utils';

export type CodeLanguage = 
  | 'javascript'
  | 'typescript'
  | 'jsx'
  | 'tsx'
  | 'css'
  | 'html'
  | 'bash'
  | 'json';

interface CodeSnippetProps {
  code: string;
  language?: CodeLanguage;
  showLineNumbers?: boolean;
  className?: string;
  /**
   * 제목 (선택사항)
   */
  title?: string;
}

export const CodeSnippet = ({
  code,
  language = 'typescript',
  showLineNumbers = true,
  className,
  title,
}: CodeSnippetProps) => {
  const [isCopied, setIsCopied] = useState(false);

  // Syntax Highlighting
  const highlightedCode = Prism.highlight(
    code,
    Prism.languages[language] || Prism.languages.javascript,
    language
  );

  // Copy to Clipboard
  const handleCopy = async () => {
    try {
      await navigator.clipboard.writeText(code);
      setIsCopied(true);
      setTimeout(() => setIsCopied(false), 2000);
    } catch (err) {
      console.error('복사 실패:', err);
    }
  };

  const lines = code.split('\n');

  return (
    <div className={cn('rounded-xl overflow-hidden bg-[#1C1D21] border border-[#2E2F33]', className)}>
      {/* Header */}
      <div className="flex items-center justify-between px-4 py-3 bg-[#16171A] border-b border-[#2E2F33]">
        <div className="flex items-center gap-2">
          {title && (
            <span className="text-[14px] font-medium text-white">{title}</span>
          )}
          <span className="text-[12px] text-[#7C7E87] uppercase">{language}</span>
        </div>

        {/* Copy Button */}
        <button
          onClick={handleCopy}
          className={cn(
            'flex items-center gap-2 px-3 py-1.5 rounded-md text-[13px] font-medium transition-all',
            isCopied
              ? 'bg-[#0D59F2] text-white'
              : 'bg-[#2E2F33] text-[#E5E5E5] hover:bg-[#3E3F43]'
          )}
          aria-label={isCopied ? '복사 완료' : '코드 복사'}
        >
          {isCopied ? (
            <>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <path
                  d="M13.3333 4L6 11.3333L2.66667 8"
                  stroke="currentColor"
                  strokeWidth="2"
                  strokeLinecap="round"
                  strokeLinejoin="round"
                />
              </svg>
              Copied!
            </>
          ) : (
            <>
              <svg width="16" height="16" viewBox="0 0 16 16" fill="none">
                <rect
                  x="5.33333"
                  y="5.33333"
                  width="8"
                  height="8"
                  rx="1"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
                <path
                  d="M10.6667 5.33333V3.33333C10.6667 2.96514 10.3682 2.66667 10 2.66667H3.33333C2.96514 2.66667 2.66667 2.96514 2.66667 3.33333V10C2.66667 10.3682 2.96514 10.6667 3.33333 10.6667H5.33333"
                  stroke="currentColor"
                  strokeWidth="1.5"
                />
              </svg>
              Copy
            </>
          )}
        </button>
      </div>

      {/* Code Content */}
      <div className="relative overflow-x-auto">
        <pre className="p-4 text-[14px] leading-[1.6] font-mono">
          {showLineNumbers ? (
            <div className="flex">
              {/* Line Numbers */}
              <div className="select-none pr-4 text-[#5F616B] text-right border-r border-[#2E2F33] mr-4">
                {lines.map((_, index) => (
                  <div key={index}>{index + 1}</div>
                ))}
              </div>
              {/* Code */}
              <code
                className={`language-${language}`}
                dangerouslySetInnerHTML={{ __html: highlightedCode }}
              />
            </div>
          ) : (
            <code
              className={`language-${language}`}
              dangerouslySetInnerHTML={{ __html: highlightedCode }}
            />
          )}
        </pre>
      </div>
    </div>
  );
};