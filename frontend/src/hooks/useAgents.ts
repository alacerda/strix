import { useState, useEffect, useCallback } from 'react';
import { api } from '@/lib/api';
import type { Agent, ChatMessage, ToolExecution } from '@/types';

export function useAgents(scanId: string) {
  const [agents, setAgents] = useState<Record<string, Agent>>({});
  const [messages, setMessages] = useState<Record<string, ChatMessage[]>>({});
  const [toolExecutions, setToolExecutions] = useState<Record<string, ToolExecution[]>>({});
  const [loading, setLoading] = useState(true);
  const [error, setError] = useState<Error | null>(null);

  const loadAgents = useCallback(async () => {
    try {
      setLoading(true);
      setError(null);
      const data = await api.agents.list(scanId);
      setAgents(data.agents);
    } catch (err) {
      setError(err instanceof Error ? err : new Error('Failed to load agents'));
    } finally {
      setLoading(false);
    }
  }, [scanId]);

  useEffect(() => {
    loadAgents();
  }, [loadAgents]);

  const loadAgentData = useCallback(
    async (agentId: string) => {
      try {
        const [messagesData, toolsData] = await Promise.all([
          api.agents.messages(scanId, agentId),
          api.agents.tools(scanId, agentId),
        ]);

        setMessages((prev) => ({
          ...prev,
          [agentId]: messagesData.messages.map((msg) => ({
            ...msg,
            timestamp: new Date(msg.timestamp).toISOString(),
          })),
        }));

        setToolExecutions((prev) => ({
          ...prev,
          [agentId]: toolsData.tools.map((tool) => ({
            ...tool,
            timestamp: tool.timestamp || tool.started_at || new Date().toISOString(),
          })),
        }));
      } catch (err) {
        console.error(`Error loading data for agent ${agentId}:`, err);
      }
    },
    [scanId]
  );

  const sendMessage = useCallback(
    async (agentId: string, content: string) => {
      try {
        await api.agents.sendMessage(scanId, agentId, { content });
      } catch (err) {
        throw err instanceof Error ? err : new Error('Failed to send message');
      }
    },
    [scanId]
  );

  const stopAgent = useCallback(
    async (agentId: string) => {
      try {
        await api.agents.stop(scanId, agentId);
        await loadAgents();
      } catch (err) {
        throw err instanceof Error ? err : new Error('Failed to stop agent');
      }
    },
    [scanId, loadAgents]
  );

  return {
    agents,
    messages,
    toolExecutions,
    loading,
    error,
    loadAgents,
    loadAgentData,
    sendMessage,
    stopAgent,
  };
}

