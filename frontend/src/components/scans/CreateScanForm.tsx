'use client';

import { useState } from 'react';
import type { CreateScanRequest } from '@/types';

interface CreateScanFormProps {
  onSubmit: (request: CreateScanRequest) => void;
  onCancel: () => void;
}

export function CreateScanForm({ onSubmit, onCancel }: CreateScanFormProps) {
  const [targets, setTargets] = useState<string[]>(['']);
  const [userInstructions, setUserInstructions] = useState('');
  const [runName, setRunName] = useState('');
  const [maxIterations, setMaxIterations] = useState(300);
  const [error, setError] = useState<string | null>(null);

  const handleSubmit = (e: React.FormEvent) => {
    e.preventDefault();
    setError(null);

    const validTargets = targets.filter((t) => t.trim() !== '');
    if (validTargets.length === 0) {
      setError('At least one target is required');
      return;
    }

    const request: CreateScanRequest = {
      targets: validTargets,
      user_instructions: userInstructions || undefined,
      run_name: runName || undefined,
      max_iterations: maxIterations,
    };

    onSubmit(request);
    onCancel();
  };

  const addTarget = () => {
    setTargets([...targets, '']);
  };

  const removeTarget = (index: number) => {
    if (targets.length > 1) {
      setTargets(targets.filter((_, i) => i !== index));
    }
  };

  const updateTarget = (index: number, value: string) => {
    const newTargets = [...targets];
    newTargets[index] = value;
    setTargets(newTargets);
  };

  return (
    <div className="fixed inset-0 bg-black/70 z-[1000] flex items-center justify-center">
      <div className="bg-bg-secondary rounded-lg p-8 max-w-2xl w-[90%] max-h-[90vh] overflow-y-auto">
        <div className="flex justify-between items-center mb-6">
          <h2 className="text-2xl text-primary-green">Create New Scan</h2>
          <button
            onClick={onCancel}
            className="bg-transparent border-none text-text-secondary text-2xl cursor-pointer hover:text-text-primary"
          >
            ×
          </button>
        </div>

        <form onSubmit={handleSubmit} className="space-y-4">
          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              Targets *
            </label>
            {targets.map((target, index) => (
              <div key={index} className="flex gap-2 mb-2">
                <input
                  type="text"
                  value={target}
                  onChange={(e) => updateTarget(index, e.target.value)}
                  placeholder="URL, repository, or local path"
                  className="flex-1 px-3 py-2 bg-bg-tertiary border border-border-color rounded text-text-primary text-sm focus:outline-none focus:border-primary-green"
                  required={index === 0}
                />
                {targets.length > 1 && (
                  <button
                    type="button"
                    onClick={() => removeTarget(index)}
                    className="px-3 py-2 bg-error text-white rounded text-sm hover:bg-error/80"
                  >
                    Remove
                  </button>
                )}
              </div>
            ))}
            <button
              type="button"
              onClick={addTarget}
              className="mt-2 px-4 py-2 bg-bg-tertiary text-text-primary rounded text-sm hover:bg-bg-tertiary/80 border border-border-color"
            >
              + Add Target
            </button>
          </div>

          <div>
            <label className="block text-sm font-medium text-text-secondary mb-2">
              User Instructions
            </label>
            <textarea
              value={userInstructions}
              onChange={(e) => setUserInstructions(e.target.value)}
              placeholder="Optional instructions for the scan"
              rows={4}
              className="w-full px-3 py-2 bg-bg-tertiary border border-border-color rounded text-text-primary text-sm focus:outline-none focus:border-primary-green resize-none"
            />
          </div>

          <div className="grid grid-cols-2 gap-4">
            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Run Name
              </label>
              <input
                type="text"
                value={runName}
                onChange={(e) => setRunName(e.target.value)}
                placeholder="Auto-generated if empty"
                className="w-full px-3 py-2 bg-bg-tertiary border border-border-color rounded text-text-primary text-sm focus:outline-none focus:border-primary-green"
              />
            </div>

            <div>
              <label className="block text-sm font-medium text-text-secondary mb-2">
                Max Iterations
              </label>
              <input
                type="number"
                value={maxIterations}
                onChange={(e) => setMaxIterations(parseInt(e.target.value) || 300)}
                min={1}
                max={1000}
                className="w-full px-3 py-2 bg-bg-tertiary border border-border-color rounded text-text-primary text-sm focus:outline-none focus:border-primary-green"
              />
            </div>
          </div>

          {error && (
            <div className="p-3 bg-error/20 border border-error rounded text-error text-sm">
              {error}
            </div>
          )}

          <div className="flex gap-3 justify-end pt-4">
            <button
              type="button"
              onClick={onCancel}
              className="px-6 py-2 bg-bg-tertiary text-text-primary rounded font-semibold hover:bg-bg-tertiary/80"
            >
              Cancel
            </button>
            <button
              type="submit"
              className="px-6 py-2 bg-primary-green text-white rounded font-semibold hover:bg-primary-green-dark"
            >
              Create Scan
            </button>
          </div>
        </form>
      </div>
    </div>
  );
}

