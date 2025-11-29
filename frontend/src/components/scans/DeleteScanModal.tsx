'use client';

import { useEffect } from 'react';

interface DeleteScanModalProps {
  scanId: string;
  scanName?: string;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteScanModal({ scanId, scanName, onConfirm, onCancel }: DeleteScanModalProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape') {
        onCancel();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onCancel]);

  return (
    <div
      className="fixed inset-0 bg-black/70 z-[1000] flex items-center justify-center"
      onClick={onCancel}
      aria-label="Delete scan confirmation modal"
    >
      <div
        className="bg-bg-secondary rounded-lg p-6 max-w-md w-[90%] shadow-2xl"
        onClick={(e) => e.stopPropagation()}
      >
        <div className="mb-4">
          <h2 className="text-xl font-semibold text-text-primary mb-2">
            Delete Scan
          </h2>
          <p className="text-text-secondary text-sm mb-4">
            Are you sure you want to delete scan "{scanName || scanId}"?
          </p>
          <div className="text-text-secondary text-sm mb-4">
            <p className="mb-2">This will permanently delete:</p>
            <ul className="list-disc list-inside space-y-1 ml-2">
              <li>All scan data and files</li>
              <li>Associated Docker containers</li>
            </ul>
            <p className="mt-3 text-error font-medium">This action cannot be undone.</p>
          </div>
        </div>
        <div className="flex gap-3 justify-end">
          <button
            onClick={onCancel}
            className="px-6 py-2 bg-bg-tertiary text-text-primary rounded font-semibold hover:bg-bg-tertiary/80 transition-colors"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            className="px-6 py-2 bg-error text-white rounded font-semibold hover:bg-error/80 transition-colors"
          >
            Delete
          </button>
        </div>
      </div>
    </div>
  );
}

