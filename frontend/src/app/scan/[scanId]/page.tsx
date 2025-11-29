'use client';

import { useState, useEffect, useCallback } from 'react';
import { useParams, useRouter } from 'next/navigation';
import { AgentsTree } from '@/components/agents/AgentsTree';
import { ChatContainer } from '@/components/chat/ChatContainer';
import { StatsPanel } from '@/components/stats/StatsPanel';
import { SeverityBreakdown } from '@/components/stats/SeverityBreakdown';
import { VulnerabilityList } from '@/components/vulnerabilities/VulnerabilityList';
import { VulnerabilityDrawer } from '@/components/vulnerabilities/VulnerabilityDrawer';
import { useAgents } from '@/hooks/useAgents';
import { useVulnerabilities } from '@/hooks/useVulnerabilities';
import { useWebSocket } from '@/hooks/useWebSocket';
import { api } from '@/lib/api';
import type { Scan, Stats, Vulnerability, WebSocketMessage, Agent } from '@/types';

export default function ScanDetailPage() {
  const params = useParams();
  const router = useRouter();
  const scanId = params.scanId as string;

  const [scan, setScan] = useState<Scan | null>(null);
  const [selectedAgentId, setSelectedAgentId] = useState<string | null>(null);
  const [stats, setStats] = useState<Stats | null>(null);
  const [selectedVulnerability, setSelectedVulnerability] = useState<Vulnerability | null>(null);
  const [loading, setLoading] = useState(true);

  const { agents, messages, toolExecutions, loadAgentData, sendMessage, stopAgent } = useAgents(scanId);
  const { vulnerabilities, loadVulnerabilities } = useVulnerabilities(scanId);
  const { on, connected } = useWebSocket(scanId);

  useEffect(() => {
    const loadScan = async () => {
      try {
        const scanData = await api.scans.get(scanId);
        setScan(scanData);
      } catch (err) {
        console.error('Error loading scan:', err);
        router.push('/');
      } finally {
        setLoading(false);
      }
    };

    loadScan();
  }, [scanId, router]);

  useEffect(() => {
    const loadStats = async () => {
      try {
        const statsData = await api.stats.get(scanId);
        setStats(statsData);
      } catch (err) {
        console.error('Error loading stats:', err);
      }
    };

    loadStats();
    const interval = setInterval(loadStats, 2000);
    return () => clearInterval(interval);
  }, [scanId]);

  useEffect(() => {
    if (selectedAgentId) {
      loadAgentData(selectedAgentId);
    }
  }, [selectedAgentId, loadAgentData]);

  useEffect(() => {
    const unsubscribeAgentCreated = on('agent_created', (message: WebSocketMessage) => {
      if (message.scan_id === scanId && message.data && 'agent_id' in message.data) {
        const agentData = message.data as unknown as Agent;
        setSelectedAgentId((prev) => prev || agentData.agent_id);
      }
    });

    const unsubscribeAgentUpdated = on('agent_updated', (message: WebSocketMessage) => {
      if (message.scan_id === scanId) {
        window.location.reload();
      }
    });

    const unsubscribeMessage = on('message', (message: WebSocketMessage) => {
      if (message.scan_id === scanId && message.data && 'agent_id' in message.data) {
        const agentId = message.data.agent_id as string;
        if (agentId === selectedAgentId) {
          loadAgentData(agentId);
        }
      }
    });

    const unsubscribeToolExecution = on('tool_execution', (message: WebSocketMessage) => {
      if (message.scan_id === scanId && message.data && 'agent_id' in message.data) {
        const agentId = message.data.agent_id as string;
        if (agentId === selectedAgentId) {
          loadAgentData(agentId);
        }
      }
    });

    const unsubscribeVulnerability = on('vulnerability_found', (message: WebSocketMessage) => {
      if (message.scan_id === scanId) {
        loadVulnerabilities();
      }
    });

    const unsubscribeStats = on('stats_updated', (message: WebSocketMessage) => {
      if (message.scan_id === scanId && message.data) {
        setStats(message.data as Stats);
      }
    });

    return () => {
      unsubscribeAgentCreated();
      unsubscribeAgentUpdated();
      unsubscribeMessage();
      unsubscribeToolExecution();
      unsubscribeVulnerability();
      unsubscribeStats();
    };
  }, [scanId, selectedAgentId, on, loadAgentData, loadVulnerabilities]);

  const handleSelectAgent = useCallback((agentId: string) => {
    setSelectedAgentId(agentId);
    loadAgentData(agentId);
  }, [loadAgentData]);

  const handleSendMessage = useCallback(
    async (content: string) => {
      if (!selectedAgentId) return;
      try {
        await sendMessage(selectedAgentId, content);
        await loadAgentData(selectedAgentId);
      } catch (err) {
        console.error('Error sending message:', err);
        alert(`Failed to send message: ${err instanceof Error ? err.message : 'Unknown error'}`);
      }
    },
    [selectedAgentId, sendMessage, loadAgentData]
  );

  const handleStopAgent = useCallback(async () => {
    if (!selectedAgentId) return;
    try {
      await stopAgent(selectedAgentId);
    } catch (err) {
      console.error('Error stopping agent:', err);
      alert(`Failed to stop agent: ${err instanceof Error ? err.message : 'Unknown error'}`);
    }
  }, [selectedAgentId, stopAgent]);

  if (loading || !scan) {
    return (
      <div className="flex items-center justify-center h-screen text-text-muted">
        Loading scan...
      </div>
    );
  }

  const selectedAgent = selectedAgentId ? agents[selectedAgentId] : null;
  const selectedMessages = selectedAgentId ? messages[selectedAgentId] || [] : [];
  const selectedToolExecutions = selectedAgentId ? toolExecutions[selectedAgentId] || [] : [];

  return (
    <div className="flex h-screen gap-px bg-border-color">
      <div className="w-[300px] bg-bg-secondary flex flex-col border-r border-border-color">
        <div className="p-4 bg-bg-tertiary border-b border-border-color">
          <h2 className="text-xl text-primary-green flex items-center gap-2">🤖 Active Agents</h2>
        </div>
        <div className="flex-1 overflow-y-auto p-4">
          <AgentsTree
            agents={agents}
            selectedAgentId={selectedAgentId}
            onSelectAgent={handleSelectAgent}
          />
        </div>
      </div>

      <div className="flex-1 flex flex-col bg-bg-primary">
        <div className="p-4 bg-bg-secondary border-b border-border-color">
          <div className="flex items-center justify-between">
            <div className="flex items-center gap-4">
              <button
                onClick={() => router.push('/')}
                className="bg-transparent border-none text-text-secondary cursor-pointer text-xl hover:text-text-primary"
              >
                ←
              </button>
              <h1 className="text-2xl text-primary-green">🦉 Strix Cybersecurity Agent</h1>
              <span className="text-sm text-text-muted">{scanId}</span>
            </div>
            <div className="flex items-center gap-4">
              <div className="flex items-center gap-2">
                <span className="text-sm text-text-secondary">
                  {selectedAgent ? `Status: ${selectedAgent.status}` : 'Select an agent'}
                </span>
                {connected && (
                  <span className="w-2 h-2 bg-success rounded-full" title="WebSocket connected" />
                )}
              </div>
              {selectedAgent && selectedAgent.status === 'running' && (
                <button
                  onClick={handleStopAgent}
                  className="px-4 py-2 bg-error text-white rounded text-sm hover:bg-error/80"
                >
                  Stop Agent
                </button>
              )}
            </div>
          </div>
        </div>

        <div className="flex-1 flex overflow-hidden">
          <div className="flex-1 flex flex-col">
            {selectedAgentId ? (
              <ChatContainer
                messages={selectedMessages}
                toolExecutions={selectedToolExecutions}
                onSendMessage={handleSendMessage}
                disabled={selectedAgent?.status !== 'running'}
              />
            ) : (
              <div className="flex-1 flex items-center justify-center text-text-muted">
                Select an agent to start chatting
              </div>
            )}
          </div>

          <div className="w-[350px] bg-bg-secondary flex flex-col border-l border-border-color overflow-y-auto">
            {stats && <StatsPanel stats={stats} />}
            <SeverityBreakdown vulnerabilities={vulnerabilities} />
            <VulnerabilityList
              vulnerabilities={vulnerabilities}
              onVulnerabilityClick={setSelectedVulnerability}
            />
          </div>
        </div>
      </div>

      {selectedVulnerability && (
        <VulnerabilityDrawer
          vulnerability={selectedVulnerability}
          onClose={() => setSelectedVulnerability(null)}
        />
      )}
    </div>
  );
}

