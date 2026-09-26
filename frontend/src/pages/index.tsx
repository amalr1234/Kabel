import { useEffect } from "react";
import { useRouter } from "next/router";

export default function Home() {
  const router = useRouter();

  useEffect(() => {
    router.replace("/search");
  }, [router]);

  return (
    <div className="min-h-screen bg-surface-900 flex items-center justify-center">
      <div className="animate-pulse text-surface-400 text-sm">Loading SOLVIA...</div>
    </div>
  );
}
