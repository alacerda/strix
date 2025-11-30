'use client';

import { useState, useEffect } from 'react';
import Link from 'next/link';
import type { Scan } from '@/types';
import { DeleteScanModal } from './DeleteScanModal';

interface ScanCardProps {
  scan: Scan;
  onDelete: (scanId: string) => void;
}

export function ScanCard({ scan, onDelete }: ScanCardProps) {
  const [showDeleteModal, setShowDeleteModal] = useState(false);
  const [isDeleting, setIsDeleting] = useState(false);

  useEffect(() => {
    return () => {
      if (isDeleting) {
        setIsDeleting(false);
      }
    };
  }, [isDeleting]);

  const handleDeleteClick = (e: React.MouseEvent) => {
    e.preventDefault();
    e.stopPropagation();
    setShowDeleteModal(true);
  };

  const handleConfirmDelete = async () => {
    setIsDeleting(true);
    setShowDeleteModal(false);
    try {
      await onDelete(scan.scan_id);
    } catch (error) {
      setIsDeleting(false);
    }
  };

  const handleCancelDelete = () => {
    if (!isDeleting) {
      setShowDeleteModal(false);
    }
  };

  const getStatusBadgeClass = (status: string) => {
    switch (status) {
      case 'running':
        return 'bg-success text-white';
      case 'completed':
        return 'bg-info text-white';
      case 'stopped':
        return 'bg-warning text-white';
      case 'failed':
        return 'bg-error text-white';
      default:
        return 'bg-text-muted text-white';
    }
  };

  const getContainerStatusClass = (status?: string) => {
    if (!status) return '';
    switch (status) {
      case 'running':
        return 'bg-success text-white';
      case 'exited':
      case 'stopped':
        return 'bg-warning text-white';
      case 'created':
      case 'restarting':
        return 'bg-info text-white';
      case 'paused':
        return 'bg-text-muted text-white';
      default:
        return 'bg-text-muted text-white';
    }
  };

  const targetDisplay = scan.targets.length > 0
    ? scan.targets.map((t) => t.original || (t.details as { target_url?: string; target_repo?: string })?.target_url || (t.details as { target_url?: string; target_repo?: string })?.target_repo || 'Unknown').join(', ')
    : 'No targets';

  const cardContent = (
    <div className={`bg-bg-secondary border ${isDeleting ? 'border-error' : 'border-border-color'} rounded-lg p-6 transition-all relative ${isDeleting ? 'opacity-50 cursor-not-allowed' : 'cursor-pointer hover:-translate-y-0.5 hover:shadow-lg hover:border-primary-green'}`}>
      {isDeleting && (
        <div className="absolute inset-0 bg-error/20 rounded-lg flex items-center justify-center z-10">
          <div className="flex flex-col items-center gap-3">
            <svg
              className="animate-spin h-8 w-8 text-error"
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
            <span className="text-error font-semibold text-sm">Deleting...</span>
          </div>
        </div>
      )}
        <div className="flex justify-between items-start mb-4">
          <div className="text-lg font-semibold text-text-primary flex-1">
            {scan.run_name || scan.scan_id}
          </div>
          <div className="flex items-center gap-2">
            <span className={`px-3 py-1 rounded-full text-xs font-semibold ${getStatusBadgeClass(scan.status)}`}>
              {scan.status}
            </span>
            <button
              onClick={handleDeleteClick}
              disabled={isDeleting}
              className="bg-transparent border-none text-text-muted cursor-pointer p-1 rounded transition-colors hover:text-error hover:bg-error/10 disabled:opacity-50 disabled:cursor-not-allowed"
              title="Delete scan"
            >
              🗑️
            </button>
          </div>
        </div>

        <div className="space-y-2 text-sm">
          <div className="flex items-center gap-2 flex-wrap">
            <span className="text-text-muted font-medium text-xs">Scan ID:</span>
            <span className="font-mono text-xs bg-bg-tertiary px-1.5 py-0.5 rounded text-primary-green">
              {scan.scan_id}
            </span>
          </div>

          {scan.container_status && (
            <div className="flex items-center gap-2 flex-wrap">
              <span className="text-text-muted font-medium text-xs">Container:</span>
              <span className={`px-2 py-0.5 rounded text-xs font-semibold capitalize ${getContainerStatusClass(scan.container_status)}`}>
                {scan.container_status}
              </span>
            </div>
          )}

          {scan.created_at && (
            <div className="text-text-secondary text-xs">
              Created: {new Date(scan.created_at).toLocaleString()}
            </div>
          )}

          <div className="mt-4 pt-4 border-t border-border-color">
            <div className="text-text-secondary text-xs">
              <div className="font-medium mb-1">Targets:</div>
              <div className="text-text-muted text-xs">{targetDisplay}</div>
            </div>
          </div>
        </div>
      </div>
    );

  return (
    <>
      {isDeleting ? (
        <div className="relative">
          {cardContent}
        </div>
      ) : (
        <Link href={`/scan/${scan.scan_id}`}>
          {cardContent}
        </Link>
      )}
      {showDeleteModal && (
        <DeleteScanModal
          scanId={scan.scan_id}
          scanName={scan.run_name || scan.scan_id}
          isDeleting={isDeleting}
          onConfirm={handleConfirmDelete}
          onCancel={handleCancelDelete}
        />
      )}
    </>
  );
}

