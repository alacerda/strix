'use client';

import { useEffect } from 'react';

interface DeleteScanModalProps {
  scanId: string;
  scanName?: string;
  isDeleting?: boolean;
  onConfirm: () => void;
  onCancel: () => void;
}

export function DeleteScanModal({ scanId, scanName, isDeleting = false, onConfirm, onCancel }: DeleteScanModalProps) {
  useEffect(() => {
    const handleEscape = (e: KeyboardEvent) => {
      if (e.key === 'Escape' && !isDeleting) {
        onCancel();
      }
    };

    document.addEventListener('keydown', handleEscape);
    return () => document.removeEventListener('keydown', handleEscape);
  }, [onCancel, isDeleting]);

  return (
    <div
      className="fixed inset-0 bg-black/70 z-[1000] flex items-center justify-center"
      onClick={isDeleting ? undefined : onCancel}
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
            disabled={isDeleting}
            className="px-6 py-2 bg-bg-tertiary text-text-primary rounded font-semibold hover:bg-bg-tertiary/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed"
          >
            Cancel
          </button>
          <button
            onClick={onConfirm}
            disabled={isDeleting}
            className="px-6 py-2 bg-error text-white rounded font-semibold hover:bg-error/80 transition-colors disabled:opacity-50 disabled:cursor-not-allowed flex items-center gap-2"
          >
            {isDeleting && (
              <svg
                className="animate-spin h-4 w-4 text-white"
                xmlns="http://www.w3.org/2000/svg"
                fill="none"
                viewBox="0 0 24 24"
              >
                <circle
                  className="opacity-25"
                  cx="12"
                  cy="12"
                  r="10"
                  stroke="currentColor"
                  strokeWidth="4"
                />
                <path
                  className="opacity-75"
                  fill="currentColor"
                  d="M4 12a8 8 0 018-8V0C5.373 0 0 5.373 0 12h4zm2 5.291A7.962 7.962 0 014 12H0c0 3.042 1.135 5.824 3 7.938l3-2.647z"
                />
              </svg>
            )}
            {isDeleting ? 'Deleting...' : 'Delete'}
          </button>
        </div>
      </div>
    </div>
  );
}

