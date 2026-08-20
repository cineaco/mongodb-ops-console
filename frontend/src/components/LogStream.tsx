import { useEffect, useRef, useState } from "react";

interface Props {
  jobId: string;
  onComplete?: (success: boolean) => void;
}

type StreamStatus = "streaming" | "success" | "failed" | "timeout";

export default function LogStream({ jobId, onComplete }: Props) {
  const [lines, setLines] = useState<string[]>([]);
  const [status, setStatus] = useState<StreamStatus>("streaming");
  const preRef = useRef<HTMLPreElement>(null);

  /* Auto-scroll on new lines */
  useEffect(() => {
    if (preRef.current) {
      preRef.current.scrollTop = preRef.current.scrollHeight;
    }
  }, [lines]);

  /* SSE connection */
  useEffect(() => {
    const es = new EventSource(`/api/jobs/${jobId}/logs`);

    es.onmessage = (evt) => {
      const raw = evt.data;

      /* Try to parse as JSON for control events */
      try {
        const parsed = JSON.parse(raw);
        if (parsed.event === "done") {
          const ok = parsed.success !== false;
          setStatus(ok ? "success" : "failed");
          onComplete?.(ok);
          es.close();
          return;
        }
        if (parsed.event === "timeout") {
          setStatus("timeout");
          onComplete?.(false);
          es.close();
          return;
        }
      } catch {
        /* Not JSON — treat as a log line */
      }

      setLines((prev) => [...prev, raw]);
    };

    es.onerror = () => {
      /* EventSource will auto-reconnect, but if the stream is done the server closes it */
      if (status === "streaming") {
        setStatus("failed");
        onComplete?.(false);
      }
      es.close();
    };

    return () => {
      es.close();
    };
    // eslint-disable-next-line react-hooks/exhaustive-deps
  }, [jobId]);

  const bannerClass =
    status === "streaming"
      ? "bg-blue-600 text-white"
      : status === "success"
        ? "bg-green-600 text-white"
        : "bg-red-600 text-white";

  const bannerText =
    status === "streaming"
      ? "Deploying..."
      : status === "success"
        ? "Deployment succeeded"
        : status === "timeout"
          ? "Deployment timed out"
          : "Deployment failed";

  return (
    <div className="space-y-2">
      <div className={`rounded px-3 py-2 text-sm font-medium ${bannerClass}`}>
        {bannerText}
      </div>
      <pre
        ref={preRef}
        className="h-96 overflow-auto rounded bg-gray-900 p-4 font-mono text-sm text-green-400"
      >
        {lines.length === 0 && status === "streaming"
          ? "Waiting for output...\n"
          : lines.join("\n")}
      </pre>
    </div>
  );
}
