import React from "react";

interface ErrorAlertProps {
  message: string;
  onRetry?: () => void;
}

export default function ErrorAlert({ message, onRetry }: ErrorAlertProps) {
  return (
    <div className="rounded-xl border border-danger/40 bg-danger/10 px-5 py-4 mb-6">
      <div className="flex items-start gap-3">
        <div className="mt-0.5 w-6 h-6 rounded-full bg-danger/20 flex items-center justify-center shrink-0">
          <svg width="12" height="12" viewBox="0 0 24 24" fill="none" stroke="#f85149" strokeWidth="3">
            <path d="M12 9v4M12 17h.01M12 3l9 16H3L12 3z" />
          </svg>
        </div>
        <div className="flex-1 min-w-0">
          <div className="text-sm font-semibold text-danger mb-1">Something went wrong</div>
          <p className="text-sm text-danger/80 leading-relaxed">{message}</p>
          {onRetry && (
            <button
              onClick={onRetry}
              className="mt-3 inline-flex items-center gap-2 rounded-lg px-4 py-2 text-sm font-medium bg-transparent border border-danger/40 text-danger hover:bg-danger/10 transition-colors"
            >
              <svg width="14" height="14" viewBox="0 0 24 24" fill="none" stroke="currentColor" strokeWidth="2">
                <path d="M1 4v6h6M23 20v-6h-6" />
                <path d="M20.49 9A9 9 0 005.64 5.64L1 10m22 4l-4.64 4.36A9 9 0 013.51 15" />
              </svg>
              Try again
            </button>
          )}
        </div>
      </div>
    </div>
  );
}
