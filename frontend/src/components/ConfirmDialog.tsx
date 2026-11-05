type ConfirmDialogProps = {
  title: string;
  description: string;
  confirmLabel: string;
  busy: boolean;
  onConfirm: () => void;
  onCancel: () => void;
};

export function ConfirmDialog({
  title,
  description,
  confirmLabel,
  busy,
  onConfirm,
  onCancel,
}: ConfirmDialogProps) {
  return (
    <div className="fixed inset-0 z-20 flex items-end justify-center bg-overlay p-4 sm:items-center">
      <div
        role="dialog"
        aria-modal="true"
        aria-labelledby="confirm-title"
        className="w-full max-w-md rounded-3xl bg-surface p-6 shadow-xl"
      >
        <h2 id="confirm-title" className="text-xl font-semibold tracking-tight">
          {title}
        </h2>
        <p className="mt-3 text-sm leading-6 text-muted">{description}</p>
        <div className="mt-6 flex flex-wrap justify-end gap-3">
          <button
            type="button"
            onClick={onCancel}
            disabled={busy}
            className="rounded-full border border-line px-4 py-2 text-sm font-medium text-muted"
          >
            取消
          </button>
          <button
            type="button"
            onClick={onConfirm}
            disabled={busy}
            className="rounded-full bg-rose-700 px-4 py-2 text-sm font-medium text-white disabled:opacity-60"
          >
            {busy ? "正在删除…" : confirmLabel}
          </button>
        </div>
      </div>
    </div>
  );
}
