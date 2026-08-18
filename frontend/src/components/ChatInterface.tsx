'use client';

import React, { useState, useRef, useEffect, useMemo } from 'react';
import MessageComponent from './Message';
import CommandPalette from './CommandPalette';
import LiveLogsPanel from './LiveLogsPanel';
import { WorkflowEngine } from '@/services/WorkflowEngine';
import type { ConsensusStatusResult, Intent } from '../lib/api';
import { getConsensusPresentation, shouldPollConsensus } from '../lib/consensusLifecycle.mjs';
import {
  MessageData,
  sendMessage,
  confirmAction,
  getConsensusStatus,
  getConsensusReadiness,
  getWorkflowState,
  getNotaryRecord,
  buildTransferTx,
  buildDeployTx,
  buildWorkflowDeployTx,
  buildContractCallTx,
  buildNotaryDeployTx,
  buildNotaryCallTx,
  validateContractFile,
  getChatHistory,
  saveChatHistory,
  getStoredAuthToken,
  generateContract,
  reviewWorkflowContract,
  reviewNotaryBlueprint,
  type WorkflowContractArtifact,
} from '../lib/api';
import type { NotaryBlueprintArtifact } from '@/types/Notary';
import { Bot, X } from 'lucide-react';
import ChatHeader from './ChatHeader';
import ChatInput from './ChatInput';
import { motion, AnimatePresence } from 'framer-motion';
import { useWallet } from '@/context/WalletContext';
import { useChainId } from 'wagmi';
import { DEFAULT_NETWORK, NETWORK_CONFIG, type NetworkKey } from '@/config';
import { formatEther, parseEther } from 'viem';

import ChatSidebar, { type ChatSession } from './ChatSidebar';

const STORAGE_KEY_PREFIX = 'genlayer-chat-history';
const WELCOME_MESSAGE = "Hi! I'm your GenLayer AI assistant. You can check balances, send tokens, deploy reviewed contracts, use deterministic escrow or subscription workflows, or notarize a public claim against web evidence. What would you like to do?";
const HELP_MESSAGE = `Available commands:

help - Show this command list.
check balance - Check the connected wallet balance on the selected GenLayer network.
send tokens - Prepare a wallet-side GEN transfer. Example: Send 10 GEN to 0x...
deploy contract - Start contract deployment. I will ask you to upload a .py GenLayer Intelligent Contract file.
generate contract - Describe a contract in plain English and the AI will write and deploy it for you.
notarize claim - Review a public claim against one to three HTTPS sources. Example: "Notarize whether GenLayer published docs using https://docs.genlayer.com/"

WORKFLOW COMMANDS (require wallet addresses, not names):
escrow - Deterministic participant-controlled custody. Example: "Create escrow for 500 GEN between 0x... and 0x..."
subscription - Deterministic recurring payment schedule. Example: "Send 50 GEN weekly to 0x..."

UNAVAILABLE PENDING REBUILD:
conditional payment - Evidence adjudication and settlement are disabled.
bounty - Validator-based completion judgment and payout are disabled.
appeal submission - Appealability can be inspected, but wallet preparation and submission are disabled.

NOTE: All wallet transfers require Ethereum addresses (0x followed by 40 hex characters). Names are not supported.

new chat - Start a clean chat session from the left sidebar.
switch network - Use the network selector to switch between Studionet and Bradbury.`;
const HELP_COMMANDS: NonNullable<MessageData['helpCommands']> = [
  {
    label: 'Check Balance',
    command: 'What is my balance?',
    description: 'Check the connected wallet balance on the selected network.',
  },
  {
    label: 'Send Tokens',
    command: 'Send 10 GEN to ',
    description: 'Start a GEN transfer. Add the recipient address before sending.',
  },
  {
    label: 'Deploy Contract',
    command: 'Deploy contract',
    description: 'Upload a .py contract file and review deployment parameters.',
  },
  {
    label: 'Generate Contract',
    command: 'Generate contract: ',
    description: 'Describe a contract and the AI will write, validate, and deploy it for you.',
  },
  {
    label: 'AI Notary',
    command: 'Notarize whether GenLayer published Intelligent Contracts documentation using https://docs.genlayer.com/',
    description: 'Create a validator-reviewed public evidence record from one to three HTTPS sources.',
  },
  {
    label: 'Escrow',
    command: 'Create escrow for 500 GEN between 0x',
    description: 'Secure payment between two parties with dispute resolution. Requires buyer and seller addresses.',
  },
  {
    label: 'Subscription',
    command: 'Send 50 GEN weekly to 0x',
    description: 'Set up recurring payments at specified intervals. Requires recipient wallet address.',
  },
  {
    label: 'New Chat',
    command: '__new_chat__',
    description: 'Start a clean chat session for this wallet.',
  },
  {
    label: 'Switch Network',
    command: '__switch_network__',
    description: 'Show where to switch between Studionet and Bradbury.',
  },
  {
    label: 'Help',
    command: 'help',
    description: 'Show this command menu again.',
  },
];

function createWelcomeMessage(seed: number = Date.now()): MessageData {
  return {
    id: seed.toString(),
    role: 'bot',
    content: WELCOME_MESSAGE,
  };
}

function createChatSession(seed: number = Date.now()): ChatSession {
  return {
    id: `chat-${seed}`,
    title: 'New chat',
    updatedAt: seed,
    messages: [createWelcomeMessage(seed)],
  };
}

function getWalletStorageKey(walletAddress: string) {
  return `${STORAGE_KEY_PREFIX}:${walletAddress.toLowerCase()}`;
}

function deriveChatTitle(content: string) {
  const normalized = content.replace(/\s+/g, ' ').trim();
  if (!normalized) {
    return 'New chat';
  }
  return normalized.length > 40 ? `${normalized.slice(0, 40)}...` : normalized;
}

function sanitizeMessages(messages: MessageData[]): MessageData[] {
  return messages.map((message) => {
    if (message.status === 'executing') {
      return {
        ...message,
        status: 'error',
        content: 'This action was interrupted. Please retry if you still want to execute it.',
      };
    }
    return message;
  });
}

function sanitizeChatSession(chat: ChatSession): ChatSession {
  return {
    ...chat,
    messages: sanitizeMessages(chat.messages),
  };
}

function normalizeChatHistoryPayload(payload?: { chats?: ChatSession[]; currentChatId?: string | null }) {
  const storedChats = Array.isArray(payload?.chats)
    ? payload.chats
        .map(sanitizeChatSession)
        .filter((chat) => Array.isArray(chat.messages) && chat.messages.length > 0)
    : [];

  if (storedChats.length === 0) {
    const nextChat = createChatSession();
    return {
      chats: [nextChat],
      currentChatId: nextChat.id,
    };
  }

  return {
    chats: storedChats,
    currentChatId: storedChats.some((chat) => chat.id === payload?.currentChatId)
      ? payload!.currentChatId!
      : storedChats[0].id,
  };
}

function normalizeDeployIntentForUi(intent: Intent, fileName?: string): Intent {
  const contractName = intent.contract_name || fileName?.replace(/\.py$/i, '') || 'IntelligentContract';
  return {
    ...intent,
    action: 'deploy_contract',
    contract_name: contractName,
    source_file_name: fileName || intent.source_file_name,
    constructor_args_text: intent.constructor_args_text || JSON.stringify(intent.constructor_args || [], null, 2),
    constructor_kwargs_text: intent.constructor_kwargs_text || JSON.stringify(intent.constructor_kwargs || {}, null, 2),
    deploy_value_text: intent.deploy_value_text || String(intent.deploy_value ?? 0),
    gas_limit_text: intent.gas_limit_text || (intent.gas_limit ? String(intent.gas_limit) : ''),
    consensus_max_rotations_text:
      intent.consensus_max_rotations_text || (intent.consensus_max_rotations ? String(intent.consensus_max_rotations) : ''),
  };
}

function buildWorkflowGeneratedContract(
  workflowConfig: NonNullable<MessageData['workflowConfig']>,
  artifact: WorkflowContractArtifact,
): NonNullable<MessageData['generatedContract']> {
  return {
    contractName: artifact.contract_name,
    contractType: artifact.contract_type,
    explanation: artifact.explanation,
    code: artifact.code,
    fileName: artifact.file_name,
    specification: workflowConfig as unknown as Record<string, unknown>,
    validation: artifact.validation,
    sourceHash: artifact.source_hash,
    sourceOrigin: artifact.source_origin,
    pyGenlayerDependency: artifact.py_genlayer_dependency,
    genlayerSdkVersion: artifact.genlayer_sdk_version,
    generatorVersion: artifact.generator_version,
    validatorVersion: artifact.validator_version,
    compilerVersion: artifact.compiler_version,
    artifactVersion: artifact.artifact_version,
  };
}

function buildNotaryDeployIntent(
  artifact: NotaryBlueprintArtifact,
  claimantAddress: string,
): Intent {
  return {
    action: 'deploy_contract',
    code: artifact.code,
    contract_name: artifact.contract_name,
    contract_type: artifact.contract_type,
    constructor_args: artifact.constructor_args,
    constructor_kwargs: artifact.constructor_kwargs,
    constructor_args_text: JSON.stringify(artifact.constructor_args, null, 2),
    constructor_kwargs_text: '{}',
    deploy_value: 0,
    deploy_value_text: '0',
    deploy_value_wei: '0',
    gas_limit: null,
    gas_limit_text: '',
    consensus_max_rotations: null,
    consensus_max_rotations_text: '',
    leader_only: false,
    source_file_name: artifact.file_name,
    source_hash: artifact.source_hash,
    source_origin: artifact.source_origin,
    py_genlayer_dependency: artifact.py_genlayer_dependency,
    genlayer_sdk_version: artifact.genlayer_sdk_version,
    generator_version: artifact.generator_version,
    validator_version: artifact.validator_version,
    compiler_version: artifact.compiler_version,
    artifact_version: artifact.artifact_version,
    notary_operation: 'deploy_registry',
    notary_spec: artifact.notary_spec,
    claim_id: artifact.notary_spec.claim_id,
    claimant_address: claimantAddress,
  };
}

function getWorkflowFundingFields(workflowConfig: NonNullable<MessageData['workflowConfig']>): Pick<Intent, 'deploy_value_text' | 'deploy_value_wei'> {
  const valueWei = workflowConfig.workflowType === 'bounty'
    ? workflowConfig.rewardWei
    : workflowConfig.workflowType === 'subscription'
      ? '0'
      : workflowConfig.amountWei;
  const normalizedWei = valueWei || '0';
  return {
    deploy_value_text: formatEther(BigInt(normalizedWei)),
    deploy_value_wei: normalizedWei,
  };
}

function parseDeployIntent(intent: Intent) {
  const constructorArgs = JSON.parse((intent.constructor_args_text || '[]').trim() || '[]');
  if (!Array.isArray(constructorArgs)) {
    throw new Error('Constructor args must be a JSON array.');
  }

  const constructorKwargs = JSON.parse((intent.constructor_kwargs_text || '{}').trim() || '{}');
  if (constructorKwargs === null || Array.isArray(constructorKwargs) || typeof constructorKwargs !== 'object') {
    throw new Error('Constructor kwargs must be a JSON object.');
  }

  const deployValueText = (intent.deploy_value_text || '0').trim();
  const deployValueWei = parseEther(deployValueText || '0').toString();
  const gasLimit = intent.gas_limit_text?.trim() ? Number(intent.gas_limit_text) : null;
  if (gasLimit !== null && (!Number.isInteger(gasLimit) || gasLimit < 21000)) {
    throw new Error('Gas limit must be an integer greater than or equal to 21000.');
  }

  const consensusMaxRotations = intent.consensus_max_rotations_text?.trim()
    ? Number(intent.consensus_max_rotations_text)
    : null;
  if (consensusMaxRotations !== null && (!Number.isInteger(consensusMaxRotations) || consensusMaxRotations < 1)) {
    throw new Error('Consensus rotations must be a positive integer.');
  }

  return {
    ...intent,
    constructor_args: constructorArgs,
    constructor_kwargs: constructorKwargs as Record<string, unknown>,
    deploy_value: Number(deployValueText || '0'),
    gas_limit: gasLimit,
    consensus_max_rotations: consensusMaxRotations,
    leader_only: Boolean(intent.leader_only),
    deploy_value_text: deployValueText || '0',
    deploy_value_wei: deployValueWei,
  };
}

function isDeployContractCommand(content: string) {
  const normalized = content.trim().toLowerCase();
  return /^(deploy|upload|submit)\s+(an?\s+)?(intelligent\s+)?contract\b/.test(normalized);
}

function isHelpCommand(content: string) {
  const normalized = content.trim().toLowerCase();
  return /^(help|\/help|\?|commands|show commands|what can you do)$/.test(normalized);
}

function isGenerateContractCommand(content: string) {
  const normalized = content.trim().toLowerCase();
  return (
    normalized === '/generate-contract'
    || normalized === '/generate-contract advanced'
    || /^(create|generate|build|write|make|draft)\s+(an?\s+)?(intelligent\s+)?contract\b/.test(normalized)
  );
}

function createGenerateContractPrompt(advanced = false): MessageData {
  return {
    id: (Date.now() + 1).toString(),
    role: 'bot',
    content: advanced
      ? 'Describe the custom Intelligent Contract you want to generate. I will convert it into a structured specification, generate template-based Python, validate it, and return deploy-ready code.'
      : 'Tell me what Intelligent Contract you want to generate. Example: /generate-contract Create an escrow contract that releases funds when both parties approve.',
    intent: { action: 'generate_contract', advanced },
    status: 'awaiting_input',
  };
}

function createDeployUploadPrompt(): MessageData {
  return {
    id: (Date.now() + 1).toString(),
    role: 'bot',
    content: 'Please upload a .py GenLayer Intelligent Contract file for deployment. Use the file upload button beside the chat input, then I will validate it and ask for the deployment parameters.',
    intent: { action: 'deploy_contract' },
    status: 'awaiting_input',
  };
}

function createHelpMessage(): MessageData {
  return {
    id: (Date.now() + 1).toString(),
    role: 'bot',
    content: HELP_MESSAGE,
    helpCommands: HELP_COMMANDS,
  };
}

export default function ChatInterface() {
  const [chats, setChats] = useState<ChatSession[]>(() => [createChatSession()]);
  const [currentChatId, setCurrentChatId] = useState<string>('');
  const [input, setInput] = useState('');
  const [isLoading, setIsLoading] = useState(false);
  const [isMounted, setIsMounted] = useState(false);
  const { account: connectedWallet, sendTransaction, switchNetwork, refreshBalance } = useWallet();
  const [selectedNetwork, setSelectedNetwork] = useState<NetworkKey>(DEFAULT_NETWORK);
  const [commandPaletteOpen, setCommandPaletteOpen] = useState(false);
  const [recentCommands, setRecentCommands] = useState<string[]>([]);
  const [uploadError, setUploadError] = useState<string | null>(null);
  const [activePanel, setActivePanel] = useState<'history' | 'chat' | 'logs'>('chat');
  const messagesEndRef = useRef<HTMLDivElement>(null);
  const fileInputRef = useRef<HTMLInputElement>(null);
  const isHydratingHistoryRef = useRef(false);
  const chainId = useChainId();

  const currentChat = useMemo(
    () => chats.find((chat) => chat.id === currentChatId) ?? chats[0],
    [chats, currentChatId]
  );
  const messages = useMemo(() => currentChat?.messages ?? [], [currentChat]);

  useEffect(() => {
    const timer = window.setTimeout(() => setIsMounted(true), 0);
    return () => window.clearTimeout(timer);
  }, []);

  useEffect(() => {
    if (!isMounted) {
      return;
    }

    let cancelled = false;

    const applyHistory = (payload?: { chats?: ChatSession[]; currentChatId?: string | null }) => {
      const normalized = normalizeChatHistoryPayload(payload);
      if (cancelled) {
        return normalized;
      }
      setChats(normalized.chats);
      setCurrentChatId(normalized.currentChatId);
      return normalized;
    };

    const waitForAuthToken = async () => {
      for (let attempt = 0; attempt < 4; attempt += 1) {
        if (!connectedWallet || getStoredAuthToken(connectedWallet)) {
          return Boolean(connectedWallet && getStoredAuthToken(connectedWallet));
        }
        await new Promise((resolve) => window.setTimeout(resolve, 500));
      }
      return Boolean(connectedWallet && getStoredAuthToken(connectedWallet));
    };

    const syncWalletChats = async () => {
      isHydratingHistoryRef.current = true;
      if (!connectedWallet) {
        const fallbackChat = createChatSession();
        setChats([fallbackChat]);
        setCurrentChatId(fallbackChat.id);
        isHydratingHistoryRef.current = false;
        return;
      }

      const stored = window.localStorage.getItem(getWalletStorageKey(connectedWallet));
      let localHistory: ReturnType<typeof normalizeChatHistoryPayload>;
      if (!stored) {
        localHistory = applyHistory();
      } else {
        try {
          const parsed = JSON.parse(stored) as { chats?: ChatSession[]; currentChatId?: string };
          localHistory = applyHistory(parsed);
        } catch {
          localHistory = applyHistory();
        }
      }

      try {
        const hasAuthToken = await waitForAuthToken();
        if (!hasAuthToken || cancelled) {
          return;
        }

        const remoteHistory = await getChatHistory(connectedWallet);
        if (remoteHistory && remoteHistory.chats.length > 0) {
          const normalized = applyHistory(remoteHistory);
          window.localStorage.setItem(getWalletStorageKey(connectedWallet), JSON.stringify(normalized));
        } else {
          await saveChatHistory(connectedWallet, localHistory);
        }
      } catch (error) {
        console.warn('Unable to load remote chat history:', error);
      } finally {
        if (!cancelled) {
          isHydratingHistoryRef.current = false;
        }
      }
    };

    const syncId = window.setTimeout(() => {
      void syncWalletChats();
    }, 0);
    return () => {
      cancelled = true;
      window.clearTimeout(syncId);
      isHydratingHistoryRef.current = false;
    };
  }, [connectedWallet, isMounted]);

  useEffect(() => {
    if (!isMounted || !connectedWallet) {
      return;
    }

    window.localStorage.setItem(
      getWalletStorageKey(connectedWallet),
      JSON.stringify({ chats, currentChatId })
    );
  }, [chats, currentChatId, connectedWallet, isMounted]);

  useEffect(() => {
    if (!isMounted || !connectedWallet || isHydratingHistoryRef.current || !getStoredAuthToken(connectedWallet)) {
      return;
    }

    const saveId = window.setTimeout(() => {
      saveChatHistory(connectedWallet, { chats, currentChatId }).catch((error) => {
        console.warn('Unable to save remote chat history:', error);
      });
    }, 700);

    return () => window.clearTimeout(saveId);
  }, [chats, currentChatId, connectedWallet, isMounted]);

  const scrollToBottom = () => {
    messagesEndRef.current?.scrollIntoView({ behavior: 'smooth' });
  };

  useEffect(() => {
    scrollToBottom();
  }, [messages, isLoading]);

  const isNetworkMismatch = Boolean(
    connectedWallet && chainId && chainId !== NETWORK_CONFIG[selectedNetwork].chainId
  );

  const updateCurrentChatMessages = (updater: (messages: MessageData[]) => MessageData[]) => {
    setChats((prevChats) => {
      const activeChatId = currentChatId || prevChats[0]?.id;
      if (!activeChatId) {
        return prevChats;
      }

      const nextChats = prevChats.map((chat) => {
        if (chat.id !== activeChatId) {
          return chat;
        }

        const nextMessages = updater(chat.messages);
        const firstUserMessage = nextMessages.find((message) => message.role === 'user');
        return {
          ...chat,
          messages: nextMessages,
          title: firstUserMessage ? deriveChatTitle(firstUserMessage.content) : chat.title,
          updatedAt: Date.now(),
        };
      });

      nextChats.sort((a, b) => b.updatedAt - a.updatedAt);
      return nextChats;
    });
  };

  const appendMessagesToCurrentChat = (...newMessages: MessageData[]) => {
    updateCurrentChatMessages((prevMessages) => [...prevMessages, ...newMessages]);
  };

  const replaceMessageInCurrentChat = (messageId: string, updater: (message: MessageData) => MessageData) => {
    updateCurrentChatMessages((prevMessages) =>
      prevMessages.map((message) => (message.id === messageId ? updater(message) : message))
    );
  };

  const consensusPollTargets = useMemo(
    () => messages
      .filter((message) => (
        message.role === 'bot'
        && shouldPollConsensus(message)
      ))
      .map((message) => ({
        id: message.id,
        consensusTxId: (message.consensusTxId || message.txHash) as string,
        txHash: message.txHash,
        intent: message.intent,
        network: message.consensusNetwork || selectedNetwork,
        preparedTransactionId: message.preparedTransactionId,
        intentHash: message.intentHash,
      })),
    [messages, selectedNetwork]
  );

  useEffect(() => {
    if (
      !isMounted
      || !connectedWallet
      || !getStoredAuthToken(connectedWallet)
      || consensusPollTargets.length === 0
    ) {
      return;
    }

    let cancelled = false;
    let pollDelay = 2500;
    let pollTimer: number | undefined;

    const updateConsensusMessage = (
      messageId: string,
      result?: ConsensusStatusResult,
      requestError?: string
    ) => {
      setChats((prevChats) => {
        let changed = false;
        const nextChats = prevChats.map((chat) => ({
          ...chat,
          messages: chat.messages.map((message) => {
            if (message.id !== messageId) {
              return message;
            }

            if (requestError) {
              if (message.consensusError === requestError) {
                return message;
              }
              changed = true;
              return { ...message, consensusError: requestError };
            }

            if (!result) {
              return message;
            }

            const presentation = getConsensusPresentation(message.intent, result);
            const nextContractAddress = presentation.exposeDeploymentAddresses
              ? (result.contractAddress || message.contractAddress)
              : message.intent?.notary_operation
                ? (message.contractAddress || message.intent.contract_address)
                : undefined;
            const nextDerivedAddresses = presentation.exposeDeploymentAddresses
              ? result.derivedAddresses
              : undefined;
            const currentDerivedAddresses = message.derivedAddresses || [];
            const normalizedNextDerivedAddresses = nextDerivedAddresses || [];
            const derivedAddressesUnchanged = (
              currentDerivedAddresses.length === normalizedNextDerivedAddresses.length
              && currentDerivedAddresses.every(
                (address, index) => address === normalizedNextDerivedAddresses[index]
              )
            );
            const isUnchanged = (
              message.status === presentation.messageStatus
              && message.consensusTxId === result.consensusTxId
              && message.consensusStatus === result.status
              && message.consensusStatusCode === result.statusCode
              && message.executionStatus === result.executionStatus
              && message.lifecycleStatus === result.lifecycleStatus
              && message.evmStatus === (result.evmStatus || undefined)
              && message.consensusFinal === result.final
              && message.consensusAppealable === result.appealable
              && message.consensusTerminal === result.terminal
              && message.protocolResult === result.protocolResult
              && message.consensusRounds === result.numRounds
              && message.validatorCount === result.validatorCount
              && message.voteCount === result.voteCount
              && message.zeroRoundNoMajority === result.zeroRoundNoMajority
              && message.contractAddress === nextContractAddress
              && derivedAddressesUnchanged
              && message.consensusError === undefined
            );
            if (isUnchanged) {
              return message;
            }

            changed = true;
            return {
              ...message,
              status: presentation.messageStatus,
              consensusTxId: result.consensusTxId,
              consensusStatus: result.status,
              consensusStatusCode: result.statusCode,
              executionStatus: result.executionStatus,
              lifecycleStatus: result.lifecycleStatus,
              evmStatus: result.evmStatus || undefined,
              consensusFinal: result.final,
              consensusAppealable: result.appealable,
              consensusTerminal: result.terminal,
              protocolResult: result.protocolResult,
              consensusRounds: result.numRounds,
              validatorCount: result.validatorCount,
              voteCount: result.voteCount,
              zeroRoundNoMajority: result.zeroRoundNoMajority,
              consensusError: undefined,
              contractAddress: nextContractAddress,
              derivedAddresses: nextDerivedAddresses,
              content: presentation.content,
            };
          }),
        }));

        return changed ? nextChats : prevChats;
      });
    };

    const pollConsensus = async () => {
      await Promise.all(consensusPollTargets.map(async (target) => {
        try {
          const result = await getConsensusStatus(
            target.consensusTxId,
            connectedWallet,
            target.network,
            target.intent,
            target.txHash,
            target.preparedTransactionId,
            target.intentHash
          );
          if (!cancelled) {
            updateConsensusMessage(target.id, result);
            const notaryOperation = target.intent?.notary_operation;
            const notaryContractAddress = target.intent?.contract_address;
            if (
              notaryOperation
              && notaryOperation !== 'deploy_registry'
              && notaryContractAddress
              && target.intent?.claim_id
              && result.final
              && result.executionStatus === 'FINISHED_WITH_RETURN'
            ) {
              try {
                const notaryResponse = await getNotaryRecord(
                  notaryContractAddress,
                  target.intent.claim_id,
                  connectedWallet,
                  target.network,
                );
                if (!cancelled) {
                  setChats((prevChats) => prevChats.map((chat) => ({
                    ...chat,
                    messages: chat.messages.map((message) => (
                      message.id === target.id
                        ? { ...message, notaryRecord: notaryResponse.record, contractAddress: notaryContractAddress }
                        : message
                    )),
                  })));
                }
              } catch {
                // The finalized transaction remains visible; record reads can be retried from the panel.
              }
            }

            const workflowContractAddress = !notaryOperation && target.intent?.action === 'deploy_contract'
              ? result.contractAddress
              : !notaryOperation && target.intent?.action === 'contract_call'
                ? target.intent.contract_address
                : undefined;
            if (
              workflowContractAddress
              && result.final
              && result.executionStatus === 'FINISHED_WITH_RETURN'
            ) {
              try {
                const workflowState = await getWorkflowState(
                  workflowContractAddress,
                  connectedWallet,
                  target.network,
                );
                setChats((prevChats) => prevChats.map((chat) => ({
                  ...chat,
                  messages: chat.messages.map((message) => (
                    message.contractAddress?.toLowerCase() === workflowContractAddress.toLowerCase()
                      ? { ...message, workflowState }
                      : message
                  )),
                })));
              } catch {
                // Keep lifecycle state visible; contract-state reads retry on demand.
              }
            }
          }
        } catch (error) {
          if (!cancelled) {
            updateConsensusMessage(
              target.id,
              undefined,
              error instanceof Error ? error.message : 'Unable to read consensus status.'
            );
          }
        }
      }));

      if (!cancelled) {
        pollDelay = Math.min(Math.round(pollDelay * 1.6), 15000);
        pollTimer = window.setTimeout(() => {
          void pollConsensus();
        }, pollDelay);
      }
    };

    pollTimer = window.setTimeout(() => {
      void pollConsensus();
    }, 800);

    return () => {
      cancelled = true;
      if (pollTimer !== undefined) {
        window.clearTimeout(pollTimer);
      }
    };
  }, [connectedWallet, consensusPollTargets, isMounted]);

  const handleCreateNewChat = () => {
    const nextChat = createChatSession();
    setChats((prevChats) => [nextChat, ...prevChats]);
    setCurrentChatId(nextChat.id);
    setInput('');
    setUploadError(null);
  };

  const handleSelectChat = (chatId: string) => {
    setCurrentChatId(chatId);
    setUploadError(null);
  };

  const handleDeleteChat = (chatId: string) => {
    setChats((prevChats) => {
      const remainingChats = prevChats.filter((chat) => chat.id !== chatId);
      if (remainingChats.length === 0) {
        const nextChat = createChatSession();
        setCurrentChatId(nextChat.id);
        return [nextChat];
      }

      if (chatId === currentChatId) {
        setCurrentChatId(remainingChats[0].id);
      }

      return remainingChats;
    });
    setUploadError(null);
  };

  const handleNetworkChange = async (nextNetwork: NetworkKey) => {
    setSelectedNetwork(nextNetwork);
    if (!connectedWallet) {
      return;
    }

    try {
      await switchNetwork(NETWORK_CONFIG[nextNetwork].chainId);
    } catch (error) {
      const message = error instanceof Error ? error.message : `Failed to switch wallet to ${NETWORK_CONFIG[nextNetwork].label}.`;
      appendMessagesToCurrentChat({
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: message,
        status: 'error',
      });
    }
  };

  const handleFileUpload = (e: React.ChangeEvent<HTMLInputElement>) => {
    if (!connectedWallet || isNetworkMismatch) return;
    const file = e.target.files?.[0];
    if (!file) return;

    setUploadError(null);

    if (!file.name.endsWith('.py')) {
      const errorMessage = `Only Python contract files are supported. '${file.name}' is not a .py file.`;
      setUploadError(errorMessage);
      appendMessagesToCurrentChat({
        id: Date.now().toString(),
        role: 'bot',
        content: errorMessage,
        status: 'error',
      });
      if (fileInputRef.current) fileInputRef.current.value = '';
      return;
    }

    const reader = new FileReader();
    reader.onload = async (event) => {
      const content = event.target?.result as string;
      if (!content) return;

      // Automatically send the deployment command with the code
      const deployCmd = `Deploy this contract:\n\n${content}`;

      const userMsg: MessageData = {
        id: Date.now().toString(),
        role: 'user',
        content: `Uploaded file: ${file.name}`
      };

      appendMessagesToCurrentChat(userMsg);
      setIsLoading(true);

      try {
        const validation = await validateContractFile(content, file.name, connectedWallet ?? undefined);
        if (!validation.valid) {
          const details = [...validation.errors, ...validation.warnings].join('\n');
          const botMsg: MessageData = {
            id: (Date.now() + 1).toString(),
            role: 'bot',
            content: `${validation.message}${details ? `\n\n${details}` : ''}`,
            status: 'error',
          };
          setUploadError(validation.message);
          appendMessagesToCurrentChat(botMsg);
          return;
        }
        if (
          !validation.source_hash
          || !validation.py_genlayer_dependency
          || !validation.generator_version
          || !validation.validator_version
        ) {
          throw new Error('Contract validation did not return immutable source metadata.');
        }

        const response = await sendMessage(deployCmd, connectedWallet ?? undefined, selectedNetwork);
        const normalizedIntent = response.intent && response.intent.action === 'deploy_contract'
          ? normalizeDeployIntentForUi({
              ...(response.intent as Intent),
              code: content,
              source_hash: validation.source_hash,
              source_origin: 'uploaded',
              py_genlayer_dependency: validation.py_genlayer_dependency,
              genlayer_sdk_version: validation.genlayer_sdk_version,
              generator_version: validation.generator_version,
              validator_version: validation.validator_version,
              compiler_version: validation.compiler_version,
              artifact_version: validation.artifact_version,
            }, file.name)
          : {
              action: 'deploy_contract',
              code: content,
              contract_name: file.name.replace(/\.py$/i, ''),
              source_file_name: file.name,
              constructor_args_text: '[]',
              constructor_kwargs_text: '{}',
              deploy_value_text: '0',
              gas_limit_text: '',
              consensus_max_rotations_text: '',
              leader_only: false,
              source_hash: validation.source_hash,
              source_origin: 'uploaded',
              py_genlayer_dependency: validation.py_genlayer_dependency,
              genlayer_sdk_version: validation.genlayer_sdk_version,
              generator_version: validation.generator_version,
              validator_version: validation.validator_version,
              compiler_version: validation.compiler_version,
              artifact_version: validation.artifact_version,
            } satisfies Intent;
        const botMsg: MessageData = {
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: [
            response.content || `Contract file '${file.name}' is ready for Studionet deployment. Review the parameters below and confirm when you are ready.`,
            ...validation.warnings,
          ].join('\n\n'),
          intent: normalizedIntent,
          simulation: response.simulation,
          status: response.status === 'error' ? 'error' : 'awaiting_confirmation'
        };
        appendMessagesToCurrentChat(botMsg);
      } catch (error) {
        console.error(error);
        const message = error instanceof Error ? error.message : 'Unable to validate the uploaded contract.';
        setUploadError(message);
        appendMessagesToCurrentChat({
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: message,
          status: 'error',
        });
      } finally {
        setIsLoading(false);
        if (fileInputRef.current) fileInputRef.current.value = '';
      }
    };
    reader.readAsText(file);
  };

  const handleSubmit = async (e: React.FormEvent) => {
    e.preventDefault();
    await executeCommand(input);
  };

  const executeCommand = async (command: string) => {
    if (!connectedWallet || !command.trim() || isLoading || isNetworkMismatch) return;

    const trimmedInput = command.trim();
    const latestMessage = messages[messages.length - 1];
    const pendingNotarySpec = (
      latestMessage?.role === 'bot'
      && latestMessage.status === 'awaiting_input'
      && latestMessage.intent?.action === 'notarize_claim'
    )
      ? latestMessage.intent.notary_spec
      : undefined;
    const userMsg: MessageData = {
      id: Date.now().toString(),
      role: 'user',
      content: trimmedInput
    };

    // Add to recent commands
    setRecentCommands(prev => [trimmedInput, ...prev].slice(0, 5));

    appendMessagesToCurrentChat(userMsg);
    setInput('');

    if (isHelpCommand(trimmedInput)) {
      appendMessagesToCurrentChat(createHelpMessage());
      return;
    }

    if (isGenerateContractCommand(trimmedInput)) {
      const onlyCommand = trimmedInput === '/generate-contract' || trimmedInput === '/generate-contract advanced';
      if (onlyCommand) {
        appendMessagesToCurrentChat(createGenerateContractPrompt(trimmedInput.toLowerCase().includes('advanced')));
        return;
      }

      setIsLoading(true);
      try {
        const response = await sendMessage(trimmedInput, connectedWallet ?? undefined, selectedNetwork);
        const parsedIntent = (response.intent ?? {}) as Partial<Intent>;
        const generated = await generateContract(
          {
            contract_type: parsedIntent.contract_type as string | undefined,
            logic_description: (parsedIntent.logic_description as string | undefined) || trimmedInput,
            contract_name: parsedIntent.contract_name as string | undefined,
            amount: parsedIntent.amount as number | undefined,
            recipient: parsedIntent.recipient as string | undefined,
            condition: parsedIntent.condition as string | undefined,
            advanced: Boolean(parsedIntent.advanced),
          },
          connectedWallet
        );
        if (!generated.valid) {
          appendMessagesToCurrentChat({
            id: (Date.now() + 1).toString(),
            role: 'bot',
            content: `The AI generated invalid contract code: ${generated.errors.join(', ')}`,
            status: 'error',
          });
          return;
        }
        const fileName = `${generated.contract_name}.py`;
        const normalizedIntent = normalizeDeployIntentForUi(
          {
            action: 'deploy_contract',
            code: generated.code,
            contract_name: generated.contract_name,
            source_file_name: fileName,
            constructor_args_text: '[]',
            constructor_kwargs_text: '{}',
            deploy_value_text: '0',
            gas_limit_text: '',
            consensus_max_rotations_text: '',
            leader_only: false,
            source_hash: generated.source_hash,
            source_origin: generated.source_origin,
            py_genlayer_dependency: generated.py_genlayer_dependency,
            genlayer_sdk_version: generated.genlayer_sdk_version,
            generator_version: generated.generator_version,
            validator_version: generated.validator_version,
            compiler_version: generated.compiler_version,
            artifact_version: generated.artifact_version,
          },
          fileName
        );
        appendMessagesToCurrentChat({
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: [
            `I generated a ${generated.contract_name} contract. Review the parameters below and confirm to deploy.`,
            generated.warnings.length ? `Warnings:\n${generated.warnings.join('\n')}` : '',
          ].filter(Boolean).join('\n\n'),
          intent: normalizedIntent,
          generatedContract: {
            contractName: generated.contract_name,
            contractType: (parsedIntent.contract_type as string | undefined) || 'custom',
            explanation: generated.message,
            code: generated.code,
            fileName,
            validation: {
              valid: generated.valid,
              message: generated.message,
              errors: generated.errors,
              warnings: generated.warnings,
              contract_names: [generated.contract_name],
            },
            sourceHash: generated.source_hash,
            sourceOrigin: generated.source_origin,
            pyGenlayerDependency: generated.py_genlayer_dependency,
            genlayerSdkVersion: generated.genlayer_sdk_version,
            generatorVersion: generated.generator_version,
            validatorVersion: generated.validator_version,
            compilerVersion: generated.compiler_version,
            artifactVersion: generated.artifact_version,
          },
          status: 'awaiting_confirmation',
        });
      } catch (err) {
        appendMessagesToCurrentChat({
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: err instanceof Error ? err.message : 'Failed to generate contract.',
          status: 'error',
        });
      } finally {
        setIsLoading(false);
      }
      return;
    }

    if (isDeployContractCommand(trimmedInput)) {
      appendMessagesToCurrentChat(createDeployUploadPrompt());
      setUploadError(null);
      return;
    }

    const workflowParse = WorkflowEngine.parseNaturalLanguage(trimmedInput, connectedWallet);
    if (workflowParse.config && workflowParse.intent) {
      if (workflowParse.errors.length > 0) {
        appendMessagesToCurrentChat({
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: `I detected a ${workflowParse.config.workflowType.replace(/_/g, ' ')} workflow, but it needs a little cleanup before deployment:\n\n${workflowParse.errors.join('\n')}`,
          intent: workflowParse.intent,
          workflowConfig: workflowParse.config,
          status: 'error',
        });
        return;
      }

      setIsLoading(true);
      try {
        const artifact = await reviewWorkflowContract(workflowParse.config, connectedWallet);
        const reviewedIntent: Intent = {
          ...workflowParse.intent,
          ...getWorkflowFundingFields(artifact.workflow_config),
          source_hash: artifact.source_hash,
          source_origin: artifact.source_origin,
          py_genlayer_dependency: artifact.py_genlayer_dependency,
          genlayer_sdk_version: artifact.genlayer_sdk_version,
          generator_version: artifact.generator_version,
          validator_version: artifact.validator_version,
          compiler_version: artifact.compiler_version,
          artifact_version: artifact.artifact_version,
        };
        const summary = WorkflowEngine.getWorkflowSummary(artifact.workflow_config);
        appendMessagesToCurrentChat({
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: `Workflow ready for deployment.\n\n${summary}\n\nReview the canonical backend-generated ${artifact.contract_name} source and confirm to deploy it through your wallet.`,
          intent: reviewedIntent,
          workflowConfig: artifact.workflow_config,
          generatedContract: buildWorkflowGeneratedContract(artifact.workflow_config, artifact),
          status: 'awaiting_confirmation',
        });
      } catch (error) {
        appendMessagesToCurrentChat({
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: error instanceof Error ? error.message : 'Failed to review canonical workflow source.',
          status: 'error',
        });
      } finally {
        setIsLoading(false);
      }
      return;
    }

    setIsLoading(true);

    try {
      const response = await sendMessage(
        userMsg.content,
        connectedWallet ?? undefined,
        selectedNetwork,
        pendingNotarySpec,
      );

      if (response.intent?.action === 'notarize_claim') {
        if (response.status !== 'awaiting_confirmation') {
          appendMessagesToCurrentChat({
            id: (Date.now() + 1).toString(),
            role: 'bot',
            content: response.content || 'The AI Notary blueprint needs a claim and one to three public HTTPS sources.',
            intent: response.intent,
            status: response.status || 'awaiting_input',
          });
          return;
        }
        if (!response.intent.notary_spec) {
          throw new Error('The AI Notary request did not include a reviewable evidence specification.');
        }
        const artifact = await reviewNotaryBlueprint(response.intent.notary_spec, connectedWallet);
        const notaryIntent = buildNotaryDeployIntent(artifact, connectedWallet);
        appendMessagesToCurrentChat({
          id: (Date.now() + 1).toString(),
          role: 'bot',
          content: response.content || 'AI Notary blueprint ready for review.',
          intent: notaryIntent,
          notaryBlueprint: artifact,
          status: 'awaiting_confirmation',
        });
        return;
      }
      
      // Check if this is a workflow intent
      const isWorkflowIntent = response.intent && WorkflowEngine.detectWorkflow(response.intent);
      const workflowStatus = isWorkflowIntent ? 'awaiting_confirmation' : response.status;
      
      // If it's a workflow intent, build and validate the configuration
      let workflowContent = response.content || 'An error occurred.';
      let workflowConfig: MessageData['workflowConfig'] | undefined = undefined;
      let workflowArtifact: WorkflowContractArtifact | undefined;
      let reviewedIntent = response.intent;
      if (isWorkflowIntent && response.intent) {
        workflowConfig = WorkflowEngine.buildWorkflowConfig(response.intent) || undefined;
        if (workflowConfig) {
          const validation = WorkflowEngine.validateConfig(workflowConfig);
          if (validation.valid) {
            workflowArtifact = await reviewWorkflowContract(workflowConfig, connectedWallet);
            workflowConfig = workflowArtifact.workflow_config;
            reviewedIntent = {
              ...response.intent,
              ...getWorkflowFundingFields(workflowArtifact.workflow_config),
              source_hash: workflowArtifact.source_hash,
              source_origin: workflowArtifact.source_origin,
              py_genlayer_dependency: workflowArtifact.py_genlayer_dependency,
              genlayer_sdk_version: workflowArtifact.genlayer_sdk_version,
              generator_version: workflowArtifact.generator_version,
              validator_version: workflowArtifact.validator_version,
              compiler_version: workflowArtifact.compiler_version,
              artifact_version: workflowArtifact.artifact_version,
            };
            const summary = WorkflowEngine.getWorkflowSummary(workflowArtifact.workflow_config);
            workflowContent = `${response.content || 'Workflow ready for deployment'}\n\n${summary}`;
          } else {
            workflowContent = `Configuration error: ${validation.errors.join(', ')}`;
          }
        }
      }
      
      const botMsg: MessageData = {
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: workflowContent,
        intent: reviewedIntent,
        workflowConfig: workflowConfig || undefined,
        generatedContract: workflowArtifact
          ? buildWorkflowGeneratedContract(workflowArtifact.workflow_config, workflowArtifact)
          : response.generatedContract,
        contractReview: response.contractReview,
        simulation: response.simulation,
        status: workflowStatus
      };
      appendMessagesToCurrentChat(botMsg);
    } catch (error) {
      const message =
        error instanceof Error
          ? error.message
          : 'Failed to reach the server. Please try again.';
      appendMessagesToCurrentChat({
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: message,
        status: 'error',
      });
    } finally {
      setIsLoading(false);
    }
  };

  const assertConsensusReady = async () => {
    if (selectedNetwork !== 'studionet' || !connectedWallet) return;
    const readiness = await getConsensusReadiness(connectedWallet, selectedNetwork);
    if (!readiness.ready) {
      const retry = readiness.retryAfterSeconds ? ' Retry after about ' + Math.ceil(readiness.retryAfterSeconds / 60) + ' minutes.' : '';
      throw new Error((readiness.message || 'Studionet is not ready for a consensus transaction.') + retry);
    }
  };

  const handleConfirm = async (msgId: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg || !msg.intent) return;

    if (!connectedWallet) {
      replaceMessageInCurrentChat(msgId, (message) => ({ ...message, status: 'error', content: 'Wallet not connected' }));
      return;
    }

    // Update status to executing
    replaceMessageInCurrentChat(msgId, (message) => ({ ...message, status: 'executing' }));

    try {
      const intent = msg.intent;
      if (
        selectedNetwork === 'studionet'
        && !['transfer', 'appeal_transaction', 'check_balance'].includes(intent.action)
      ) {
        await assertConsensusReady();
      }
      let intentForConfirmation = intent;
      let txHash: string | undefined = undefined;
      let preparedTransactionId: string | undefined;
      let intentHash: string | undefined;

      // A wallet broadcast can succeed before backend verification completes.
      // Reconcile the reviewed transaction hash instead of broadcasting again.
      if (msg.txHash && msg.preparedTransactionId && msg.intentHash) {
        const result = await confirmAction(
          intent,
          connectedWallet,
          undefined,
          msg.txHash,
          selectedNetwork,
          msg.preparedTransactionId,
          msg.intentHash,
        );
        if (!result.error) {
          refreshBalance();
        }
        replaceMessageInCurrentChat(msgId, (message) => ({
          ...message,
          status: result.error ? 'error' : 'success',
          txHash: result.txHash || msg.txHash,
          consensusTxId: intent.action === 'transfer' ? undefined : message.consensusTxId,
          consensusStatus: intent.action === 'transfer' ? undefined : message.consensusStatus,
          consensusTerminal: intent.action === 'transfer' ? true : message.consensusTerminal,
          zeroRoundNoMajority: intent.action === 'transfer' ? false : message.zeroRoundNoMajority,
          preparedTransactionId: result.preparedTransactionId || msg.preparedTransactionId,
          intentHash: result.intentHash || msg.intentHash,
          transactionDiagnostics: result.transactionDiagnostics,
          content: result.error
            ? 'Execution verification failed: ' + result.error
            : result.content || 'Transaction successfully verified on GenLayer.',
        }));
        return;
      }

      const workflowType = WorkflowEngine.detectWorkflow(intent);
      if (intent.notary_operation === 'deploy_registry') {
        const artifact = msg.notaryBlueprint;
        if (!artifact || !intent.notary_spec) {
          throw new Error('AI Notary blueprint must be reviewed again before deployment.');
        }
        if (
          intent.source_origin !== 'notary'
          || !intent.source_hash
          || !intent.py_genlayer_dependency
          || !intent.generator_version
          || !intent.validator_version
        ) {
          throw new Error('AI Notary source metadata is incomplete. Review the blueprint again.');
        }
        const txData = await buildNotaryDeployTx(
          {
            notary_spec: artifact.notary_spec,
            intent,
            gas_limit: intent.gas_limit as number | null,
            consensus_max_rotations: intent.consensus_max_rotations as number | null,
            leader_only: Boolean(intent.leader_only),
            source_hash: intent.source_hash,
            py_genlayer_dependency: intent.py_genlayer_dependency,
            generator_version: intent.generator_version,
            validator_version: intent.validator_version,
          },
          connectedWallet,
          selectedNetwork,
        );
        if (txData.sourceHash !== artifact.source_hash || txData.code !== artifact.code) {
          throw new Error('Backend AI Notary source changed after review. Review the current blueprint before deploying.');
        }
        if (txData.value !== BigInt(0)) {
          throw new Error('AI Notary registry deployment must have zero attached value.');
        }
        txHash = await sendTransaction({
          to: txData.to,
          data: txData.data,
          value: txData.value,
          chainId: txData.chainId,
          nonce: txData.nonce,
          gas: txData.gas,
          gasPrice: txData.gasPrice,
          maxFeePerGas: txData.maxFeePerGas,
          maxPriorityFeePerGas: txData.maxPriorityFeePerGas,
        });
        intentForConfirmation = txData.preparedIntent;
        preparedTransactionId = txData.preparedTransactionId;
        intentHash = txData.intentHash;
      } else if (workflowType) {
        const workflowConfig = msg.workflowConfig || WorkflowEngine.buildWorkflowConfig(intent);
        if (!workflowConfig) {
          throw new Error(`Failed to build workflow configuration for ${workflowType}`);
        }
        if (
          !intent.source_hash
          || intent.source_origin !== 'workflow'
          || !intent.py_genlayer_dependency
          || !intent.generator_version
          || !intent.validator_version
        ) {
          throw new Error('Workflow source must be reviewed again before deployment.');
        }

        const validation = WorkflowEngine.validateConfig(workflowConfig);
        if (!validation.valid) {
          throw new Error(`Workflow validation failed: ${validation.errors.join(', ')}`);
        }

        const txData = await buildWorkflowDeployTx(
          {
            workflow_config: workflowConfig,
            intent,
            deploy_value_wei: '0',
            gas_limit: null,
            consensus_max_rotations: null,
            leader_only: false,
            source_hash: intent.source_hash,
            py_genlayer_dependency: intent.py_genlayer_dependency,
            generator_version: intent.generator_version,
            validator_version: intent.validator_version,
          },
          connectedWallet as string,
          selectedNetwork
        );
        if (txData.sourceHash !== intent.source_hash) {
          throw new Error('Backend workflow source changed after review. Review the current source before deploying.');
        }

        const deployIntent: Intent = {
          action: 'deploy_contract',
          code: txData.code,
          contract_name: txData.contractName,
          contract_type: txData.workflowConfig.workflowType,
          constructor_args: txData.constructorArgs,
          constructor_kwargs: txData.constructorKwargs,
          ...getWorkflowFundingFields(txData.workflowConfig),
          constructor_args_text: JSON.stringify(txData.constructorArgs, null, 2),
          constructor_kwargs_text: '{}',
          source_file_name: `${txData.contractName}.py`,
          gas_limit: null,
          gas_limit_text: '',
          consensus_max_rotations: null,
          consensus_max_rotations_text: '',
          leader_only: false,
          workflow_config: txData.workflowConfig,
          source_hash: txData.sourceHash,
          source_origin: txData.sourceOrigin,
          py_genlayer_dependency: txData.pyGenlayerDependency,
          genlayer_sdk_version: txData.genlayerSdkVersion,
          generator_version: txData.generatorVersion,
          validator_version: txData.validatorVersion,
          compiler_version: txData.compilerVersion,
          artifact_version: txData.artifactVersion,
        };

        txHash = await sendTransaction({
          to: txData.to,
          data: txData.data,
          value: txData.value,
          chainId: txData.chainId,
          nonce: txData.nonce,
          gas: txData.gas,
          gasPrice: txData.gasPrice,
          maxFeePerGas: txData.maxFeePerGas,
          maxPriorityFeePerGas: txData.maxPriorityFeePerGas,
        });

        intentForConfirmation = deployIntent;
        preparedTransactionId = txData.preparedTransactionId;
        intentHash = txData.intentHash;
      } else if (intent.action === 'appeal_transaction') {
        throw new Error(
          'Appeal submission is unavailable until a real appeal round and post-window finality are proven on Studionet.',
        );
      } else if (intent.action === 'transfer') {
        // For transfers and deployments, let the user's wallet broadcast the transaction.
        if (!intent.recipient || typeof intent.amount !== 'number') {
          throw new Error('Transfer intent is missing recipient or amount.');
        }
        const txData = await buildTransferTx(
          intent.recipient,
          intent.amount,
          connectedWallet as string,
          selectedNetwork,
          intent
        );
        txHash = await sendTransaction({
          to: txData.to,
          value: txData.value,
          data: txData.data,
          chainId: txData.chainId,
          nonce: txData.nonce,
          gas: txData.gas,
          gasPrice: txData.gasPrice,
          maxFeePerGas: txData.maxFeePerGas,
          maxPriorityFeePerGas: txData.maxPriorityFeePerGas,
        });
        preparedTransactionId = txData.preparedTransactionId;
        intentHash = txData.intentHash;
      } else if (intent.action === 'deploy_contract') {
        if (!intent.code) {
          throw new Error('Deployment intent is missing contract code.');
        }
        if (
          !intent.source_hash
          || !intent.source_origin
          || !intent.py_genlayer_dependency
          || !intent.generator_version
          || !intent.validator_version
        ) {
          throw new Error('Contract source must be generated or validated again before deployment.');
        }
        const deployIntent = parseDeployIntent(intent);
        intentForConfirmation = deployIntent;
        const txData = await buildDeployTx(
          {
            code: deployIntent.code as string,
            intent: deployIntent,
            constructor_args: deployIntent.constructor_args,
            constructor_kwargs: deployIntent.constructor_kwargs as Record<string, unknown>,
            deploy_value_wei: deployIntent.deploy_value_wei as string,
            gas_limit: deployIntent.gas_limit as number | null,
            consensus_max_rotations: deployIntent.consensus_max_rotations as number | null,
            leader_only: deployIntent.leader_only as boolean,
            source_hash: deployIntent.source_hash as string,
            source_origin: deployIntent.source_origin as 'generated' | 'uploaded',
            py_genlayer_dependency: deployIntent.py_genlayer_dependency as string,
            generator_version: deployIntent.generator_version as string,
            validator_version: deployIntent.validator_version as string,
          },
          connectedWallet as string,
          selectedNetwork
        );
        if (txData.sourceHash !== deployIntent.source_hash) {
          throw new Error('Backend deployment source does not match the reviewed source hash.');
        }
        txHash = await sendTransaction({
          to: txData.to,
          data: txData.data,
          value: txData.value,
          chainId: txData.chainId,
          nonce: txData.nonce,
          gas: txData.gas,
          gasPrice: txData.gasPrice,
          maxFeePerGas: txData.maxFeePerGas,
          maxPriorityFeePerGas: txData.maxPriorityFeePerGas,
        });
        preparedTransactionId = txData.preparedTransactionId;
        intentHash = txData.intentHash;
      }

      const result = await confirmAction(
        intentForConfirmation,
        connectedWallet,
        undefined,
        txHash,
        selectedNetwork,
        preparedTransactionId,
        intentHash
      );
      if (!result.error) {
        refreshBalance();
      }
      replaceMessageInCurrentChat(msgId, (message) => ({
          ...message,
          status: result.error
            ? 'error'
            : ['deploy_contract', 'contract_call'].includes(intentForConfirmation.action)
              ? 'submitted'
              : 'success',
          intent: intentForConfirmation,
          txHash: result.txHash || txHash,
          transactionDiagnostics: result.transactionDiagnostics,
          consensusTxId: result.consensusTxId || result.txHash || txHash,
          consensusStatus: result.consensusStatus,
          executionStatus: result.executionStatus,
          lifecycleStatus: result.lifecycleStatus,
          evmStatus: result.evmStatus,
          consensusNetwork: selectedNetwork,
          preparedTransactionId: result.preparedTransactionId || preparedTransactionId,
          intentHash: result.intentHash || intentHash,
          contractAddress: result.contractAddress,
          derivedAddresses: result.derivedAddresses,
          content: result.error
            ? `Execution failed: ${result.error}`
            : result.balance !== undefined
              ? `Your wallet balance is ${result.balance} GEN.`
              : result.content || 'Transaction successfully executed on GenLayer.'
      }));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Network error during execution.';
      replaceMessageInCurrentChat(msgId, (message) => ({ ...message, status: 'error', content: errorMessage }));
    }
  };

  const handleNotaryAction = async (
    msgId: string,
    action: 'submit_claim' | 'evaluate_claim' | 'refresh',
  ) => {
    const msg = messages.find((message) => message.id === msgId);
    if (!msg?.notaryBlueprint || !msg.intent) {
      return;
    }
    if (!connectedWallet) {
      replaceMessageInCurrentChat(msgId, (message) => ({
        ...message,
        status: 'error',
        content: 'Wallet not connected',
      }));
      return;
    }

    const contractAddress = msg.contractAddress || msg.intent.contract_address;
    const claimId = msg.notaryBlueprint.notary_spec.claim_id;
    if (!contractAddress) {
      replaceMessageInCurrentChat(msgId, (message) => ({
        ...message,
        status: 'error',
        content: 'The AI Notary registry must finalize before a claim can be submitted.',
      }));
      return;
    }

    if (action === 'refresh') {
      try {
        const response = await getNotaryRecord(
          contractAddress,
          claimId,
          connectedWallet,
          selectedNetwork,
        );
        replaceMessageInCurrentChat(msgId, (message) => ({
          ...message,
          notaryRecord: response.record,
          contractAddress,
        }));
      } catch (error) {
        appendMessagesToCurrentChat({
          id: Date.now().toString(),
          role: 'bot',
          content: error instanceof Error ? error.message : 'Unable to refresh the finalized AI Notary record.',
          status: 'error',
        });
      }
      return;
    }

    const actionIntent: Intent = {
      action: 'contract_call',
      contract_address: contractAddress,
      method: action,
      args: [claimId],
      kwargs: {},
      notary_operation: action,
      notary_spec: msg.notaryBlueprint.notary_spec,
      claim_id: claimId,
      claimant_address: connectedWallet,
    };

    replaceMessageInCurrentChat(msgId, (message) => ({
      ...message,
      status: 'executing',
      intent: actionIntent,
      txHash: undefined,
      consensusTxId: undefined,
      consensusStatus: undefined,
      consensusStatusCode: undefined,
      executionStatus: undefined,
      consensusFinal: undefined,
      consensusAppealable: undefined,
      consensusTerminal: undefined,
      consensusError: undefined,
      preparedTransactionId: undefined,
      intentHash: undefined,
    }));

    try {
      const txData = await buildNotaryCallTx(
        {
          contract_address: contractAddress,
          notary_action: action,
          claim_id: claimId,
          notary_spec: action === 'submit_claim' ? msg.notaryBlueprint.notary_spec : undefined,
          intent: actionIntent,
        },
        connectedWallet,
        selectedNetwork,
      );
      if (txData.value !== BigInt(0)) {
        throw new Error('AI Notary actions must have zero attached value.');
      }
      await assertConsensusReady();
      const txHash = await sendTransaction({
        to: txData.to,
        data: txData.data,
        value: txData.value,
        chainId: txData.chainId,
        nonce: txData.nonce,
        gas: txData.gas,
        gasPrice: txData.gasPrice,
        maxFeePerGas: txData.maxFeePerGas,
        maxPriorityFeePerGas: txData.maxPriorityFeePerGas,
      });
      const result = await confirmAction(
        txData.preparedIntent,
        connectedWallet,
        undefined,
        txHash,
        selectedNetwork,
        txData.preparedTransactionId,
        txData.intentHash,
      );
      if (!result.error) {
        refreshBalance();
      }
      replaceMessageInCurrentChat(msgId, (message) => ({
        ...message,
        status: result.error ? 'error' : 'submitted',
        intent: txData.preparedIntent,
        txHash: result.txHash || txHash,
        transactionDiagnostics: result.transactionDiagnostics,
        consensusTxId: result.consensusTxId || result.txHash || txHash,
        consensusStatus: result.consensusStatus,
        consensusNetwork: selectedNetwork,
        preparedTransactionId: result.preparedTransactionId || txData.preparedTransactionId,
        intentHash: result.intentHash || txData.intentHash,
        contractAddress,
        content: result.error
          ? `AI Notary action failed: ${result.error}`
          : result.content || (action === 'submit_claim'
            ? 'AI Notary claim submitted to GenLayer consensus.'
            : 'AI Notary evidence evaluation submitted to GenLayer consensus.'),
      }));
    } catch (error) {
      replaceMessageInCurrentChat(msgId, (message) => ({
        ...message,
        status: 'error',
        content: error instanceof Error ? error.message : 'AI Notary action failed.',
      }));
    }
  };

  const handleWorkflowAction = async (msgId: string, action: string) => {
    const msg = messages.find(m => m.id === msgId);
    if (!msg?.workflowConfig || !msg.contractAddress) {
      return;
    }

    if (!connectedWallet) {
      appendMessagesToCurrentChat({
        id: Date.now().toString(),
        role: 'bot',
        content: 'Wallet not connected',
        status: 'error',
      });
      return;
    }

    const methodMap: Record<string, { method: string; promptLabel?: string }> = {
      fund: { method: 'fund' },
      request_evaluation: { method: 'request_evaluation' },
      settle_release: { method: 'settle_release' },
      settle_refund: { method: 'settle_refund' },
      view_details: { method: 'status' },
      approve_release: { method: 'approve_release' },
      raise_dispute: { method: 'raise_dispute' },
      cancel_escrow: { method: 'cancel_escrow' },
      pause: { method: 'pause' },
      resume: { method: 'resume' },
      cancel_subscription: { method: 'cancel' },
      record_payment: { method: 'record_payment', promptLabel: 'Payment reference' },
      review_submission: { method: 'review_submission', promptLabel: 'Submitter wallet address' },
      select_winner: { method: 'select_winner', promptLabel: 'Winner wallet address' },
      close_bounty: { method: 'close_bounty' },
    };
    const actionConfig = methodMap[action];
    if (!actionConfig) {
      appendMessagesToCurrentChat({
        id: Date.now().toString(),
        role: 'bot',
        content: `Unsupported workflow action: ${action}`,
        status: 'error',
      });
      return;
    }

    if (actionConfig.method === 'status') {
      try {
        const workflowState = await getWorkflowState(msg.contractAddress, connectedWallet, selectedNetwork);
        replaceMessageInCurrentChat(msgId, (message) => ({ ...message, workflowState }));
      } catch (error) {
        appendMessagesToCurrentChat({
          id: Date.now().toString(),
          role: 'bot',
          content: error instanceof Error ? error.message : 'Unable to read finalized workflow state.',
          status: 'error',
        });
      }
      return;
    }

    const args: unknown[] = [];
    if (actionConfig.promptLabel) {
      const value = window.prompt(actionConfig.promptLabel);
      if (!value) {
        return;
      }
      args.push(value.trim());
    }

    const intent: Intent = {
      action: 'contract_call',
      contract_address: msg.contractAddress,
      method: actionConfig.method,
      args,
      kwargs: {},
      workflow_type: msg.workflowConfig.workflowType,
    };
    const actionMessageId = Date.now().toString();
    appendMessagesToCurrentChat({
      id: actionMessageId,
      role: 'bot',
      content: `Preparing workflow action '${actionConfig.method}' for wallet signature.`,
      intent,
      status: 'executing',
    });

    try {
      const txData = await buildContractCallTx(
        {
          contract_address: msg.contractAddress,
          method: actionConfig.method,
          intent,
          args,
          kwargs: {},
          value_wei: '0',
          workflow_type: msg.workflowConfig.workflowType,
        },
        connectedWallet as string,
        selectedNetwork
      );
      await assertConsensusReady();
      const txHash = await sendTransaction({
        to: txData.to,
        data: txData.data,
        value: txData.value,
        chainId: txData.chainId,
        nonce: txData.nonce,
        gas: txData.gas,
        gasPrice: txData.gasPrice,
        maxFeePerGas: txData.maxFeePerGas,
        maxPriorityFeePerGas: txData.maxPriorityFeePerGas,
      });

      const result = await confirmAction(
        intent,
        connectedWallet,
        undefined,
        txHash,
        selectedNetwork,
        txData.preparedTransactionId,
        txData.intentHash
      );
      if (!result.error) {
        refreshBalance();
      }
      replaceMessageInCurrentChat(actionMessageId, (message) => ({
        ...message,
        status: result.error ? 'error' : 'submitted',
        intent,
        txHash: result.txHash || txHash,
        transactionDiagnostics: result.transactionDiagnostics,
        consensusTxId: result.consensusTxId || result.txHash || txHash,
        consensusStatus: result.consensusStatus,
        consensusNetwork: selectedNetwork,
        preparedTransactionId: result.preparedTransactionId || txData.preparedTransactionId,
        intentHash: result.intentHash || txData.intentHash,
        content: result.error
          ? `Workflow action failed: ${result.error}`
          : result.content || `Workflow action '${actionConfig.method}' submitted to GenLayer.`,
      }));
    } catch (err) {
      const errorMessage = err instanceof Error ? err.message : 'Workflow action failed.';
      replaceMessageInCurrentChat(actionMessageId, (message) => ({
        ...message,
        status: 'error',
        content: errorMessage,
      }));
    }
  };

  const handleCancel = (msgId: string) => {
    replaceMessageInCurrentChat(msgId, (message) => ({ ...message, status: undefined, content: 'Transaction cancelled by user.' }));
  };

  const handleQuickAction = (command: string) => {
    if (command === '__new_chat__') {
      handleCreateNewChat();
      return;
    }

    if (command === '__switch_network__') {
      appendMessagesToCurrentChat({
        id: Date.now().toString(),
        role: 'bot',
        content: 'Use the Network selector in the top bar to switch between Studionet and Bradbury. If your wallet supports it, I will also ask the wallet to switch automatically.',
      });
      return;
    }

    if (isHelpCommand(command)) {
      appendMessagesToCurrentChat(
        {
          id: Date.now().toString(),
          role: 'user',
          content: command,
        },
        createHelpMessage()
      );
      setRecentCommands(prev => [command, ...prev.filter((item) => item !== command)].slice(0, 5));
      return;
    }

    if (command.trim().toLowerCase().startsWith('what is my balance')) {
      void executeCommand(command);
      return;
    }

    if (isDeployContractCommand(command)) {
      appendMessagesToCurrentChat(
        {
          id: Date.now().toString(),
          role: 'user',
          content: command,
        },
        createDeployUploadPrompt()
      );
      setRecentCommands(prev => [command, ...prev.filter((item) => item !== command)].slice(0, 5));
      setUploadError(null);
      return;
    }

    if (isGenerateContractCommand(command)) {
      const onlyCommand = command.trim().toLowerCase() === '/generate-contract' || command.trim().toLowerCase() === '/generate-contract advanced';
      if (onlyCommand) {
        appendMessagesToCurrentChat(
          {
            id: Date.now().toString(),
            role: 'user',
            content: command,
          },
          createGenerateContractPrompt(command.toLowerCase().includes('advanced'))
        );
        setRecentCommands(prev => [command, ...prev.filter((item) => item !== command)].slice(0, 5));
        return;
      }
    }

    setInput(command);
    setRecentCommands(prev => [command, ...prev.filter((item) => item !== command)].slice(0, 5));
  };

  const handleIntentUpdate = (msgId: string, patch: Partial<Intent>) => {
    replaceMessageInCurrentChat(msgId, (message) => {
      if (!message.intent) {
        return message;
      }
      return {
        ...message,
        intent: {
          ...message.intent,
          ...patch,
        },
      };
    });
  };

  if (!isMounted) return null;

  const historyPanel = (
    <ChatSidebar
      chats={chats}
      currentChatId={currentChatId}
      connectedWallet={connectedWallet}
      selectedNetwork={selectedNetwork}
      isLoading={isLoading}
      onSelectChat={handleSelectChat}
      onDeleteChat={handleDeleteChat}
      onCreateNewChat={handleCreateNewChat}
      onSetActivePanel={setActivePanel}
    />
  );

  const chatPanel = (
    <div className="flex h-full min-h-0 flex-col">
      <ChatHeader
        selectedNetwork={selectedNetwork}
        connectedWallet={connectedWallet}
        handleNetworkChange={handleNetworkChange}
        setActivePanel={setActivePanel}
        handleQuickAction={handleQuickAction}
      />

      <div className="min-h-0 flex-1 space-y-6 overflow-y-auto overscroll-contain px-4 py-5 scroll-smooth sm:px-6 sm:py-6 xl:px-8">
        {!connectedWallet && (
          <motion.div
            initial={{ opacity: 0, y: 10 }}
            animate={{ opacity: 1, y: 0 }}
            className="panel-soft rounded-[10px] p-4"
          >
            <p className="text-[12px] font-medium text-accent-warning">
              Please connect your wallet to get started.
            </p>
          </motion.div>
        )}

        {connectedWallet && isNetworkMismatch && (
          <div className="rounded-[10px] border border-accent-warning/60 bg-accent-warning/10 px-4 py-3 font-mono text-[10px] leading-relaxed text-accent-warning">
            Wallet is connected to the wrong chain. Please switch your wallet to {NETWORK_CONFIG[selectedNetwork].label} or use the wallet prompt to switch networks.
          </div>
        )}

        <AnimatePresence initial={false}>
          {messages.map(msg => (
            <MessageComponent
              key={msg.id}
              msg={msg}
              onConfirm={handleConfirm}
              onCancel={handleCancel}
              onUpdateIntent={handleIntentUpdate}
              onWorkflowAction={handleWorkflowAction}
              onNotaryAction={handleNotaryAction}
              onRunCommand={handleQuickAction}
              walletAddress={connectedWallet ?? undefined}
            />
          ))}
          {isLoading && (
            <motion.div
              initial={{ opacity: 0, y: 10 }}
              animate={{ opacity: 1, y: 0 }}
              className="flex max-w-3xl gap-3"
            >
              <div className="flex h-8 w-8 shrink-0 items-center justify-center rounded-[8px] border border-border-strong bg-bg-elevated text-text-secondary shadow-sm">
                <Bot size={14} />
              </div>
              <div className="flex flex-col items-start gap-1">
                <span className="micro-label">GenLayer AI</span>
                <div className="message-card flex items-center gap-2 px-4 py-3">
                  <div className="flex gap-1">
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-primary/60 delay-0" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-primary/60 delay-150" />
                    <span className="h-1.5 w-1.5 animate-bounce rounded-full bg-accent-primary/60 delay-300" />
                  </div>
                </div>
              </div>
            </motion.div>
          )}
        </AnimatePresence>
        <div ref={messagesEndRef} className="h-3" />
      </div>

      <ChatInput
        input={input}
        setInput={setInput}
        handleSubmit={handleSubmit}
        setCommandPaletteOpen={setCommandPaletteOpen}
        connectedWallet={connectedWallet}
        isLoading={isLoading}
        isNetworkMismatch={isNetworkMismatch}
        selectedNetwork={selectedNetwork}
        messages={messages}
        fileInputRef={fileInputRef}
        handleFileUpload={handleFileUpload}
        uploadError={uploadError}
      />
    </div>
  );

  const logsPanel = <LiveLogsPanel compact />;

  return (
    <div className="relative mx-auto flex h-full min-h-0 w-full max-w-[1640px] overflow-hidden bg-bg-base p-0 md:p-2 xl:p-3">
      <div className="surface-shell grid h-full min-h-0 w-full grid-cols-1 overflow-hidden rounded-none border-x-0 md:rounded-[14px] lg:grid-cols-[236px_minmax(0,1fr)_300px] xl:grid-cols-[260px_minmax(0,1fr)_320px]">
        <aside className="hidden min-h-0 border-r border-border-default bg-bg-elevated/88 lg:block">
          {historyPanel}
        </aside>

        <section className={`${activePanel === 'chat' ? 'flex' : 'hidden'} min-h-0 min-w-0 flex-col bg-bg-base lg:flex`}>
          {chatPanel}
        </section>

        <aside className="hidden min-h-0 border-l border-border-default bg-bg-elevated/88 p-3 lg:flex">
          {logsPanel}
        </aside>

        <section className={`${activePanel === 'history' ? 'flex' : 'hidden'} min-h-0 bg-bg-elevated lg:hidden`}>
          {historyPanel}
        </section>

        <section className={`${activePanel === 'logs' ? 'flex' : 'hidden'} min-h-0 bg-bg-elevated p-3 lg:hidden`}>
          <div className="flex h-full min-h-0 w-full flex-col">
            <div className="mb-3 flex shrink-0 items-center justify-between px-1">
              <div>
                <h2 className="font-display text-[14px] font-semibold text-text-primary">Activity Monitor</h2>
                <div className="micro-label mt-1">Live validation and deploy logs</div>
              </div>
              <button
                type="button"
                onClick={() => setActivePanel('chat')}
                className="control-button flex h-8 w-8 items-center justify-center rounded-[8px]"
                title="Close logs"
              >
                <X size={13} />
              </button>
            </div>
            {logsPanel}
          </div>
        </section>

        <nav className="absolute inset-x-2 bottom-2 z-20 grid h-11 grid-cols-3 gap-1 rounded-[10px] border border-border-default bg-bg-elevated/95 p-1 shadow-card backdrop-blur lg:hidden">
          {[
            { id: 'history' as const, label: 'History' },
            { id: 'chat' as const, label: 'Chat' },
            { id: 'logs' as const, label: 'Logs' },
          ].map((item) => (
            <button
              key={item.id}
              type="button"
              onClick={() => setActivePanel(item.id)}
              className={`rounded-[8px] font-mono text-[10px] font-bold transition-colors ${
                activePanel === item.id
                  ? 'bg-accent-primary text-[var(--color-ink)]'
                  : 'text-text-secondary hover:bg-bg-base hover:text-text-primary'
              }`}
            >
              {item.label}
            </button>
          ))}
        </nav>

        <CommandPalette
          isOpen={commandPaletteOpen}
          onClose={() => setCommandPaletteOpen(false)}
          onSelectCommand={(cmd) => {
            handleQuickAction(cmd);
            setCommandPaletteOpen(false);
          }}
          recentCommands={recentCommands}
        />
      </div>
    </div>
  );
}
