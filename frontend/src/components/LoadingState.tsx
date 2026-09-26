import React from "react";

export default function LoadingState({ message = "Working on it..." }: { message?: string }) {
  return (
    <div className="flex flex-col items-center justify-center py-24 gap-4">
      <div className="w-10 h-10 rounded-full border-2 border-accent border-t-transparent animate-spin" />
      <div className="text-sm text-surface-400 font-medium">{message}</div>
    </div>
  );
}
