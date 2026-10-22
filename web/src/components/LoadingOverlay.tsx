interface LoadingOverlayProps {
  visible: boolean;
  message?: string;
}

/** Non-blocking status pill: the rest of the dashboard stays usable while data loads. */
export function LoadingOverlay({ visible, message = 'Loading...' }: LoadingOverlayProps) {
  if (!visible) return null;

  return (
    <div role="status" className="absolute top-3 left-1/2 -translate-x-1/2 z-20 flex items-center gap-2 bg-white border border-gray-200 rounded-full px-4 py-2 shadow">
      <span className="w-4 h-4 border-2 border-flood-200 border-t-flood-700 rounded-full animate-spin" aria-hidden="true" />
      <span className="text-sm text-gray-800">{message}</span>
    </div>
  );
}
