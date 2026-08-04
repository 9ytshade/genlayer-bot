'use client';

import React, { useState, useRef, useEffect, useMemo } from 'react';
import MessageComponent from './Message';
import CommandPalette from './CommandPalette';
import LiveLogsPanel from './LiveLogsPanel';
import { WorkflowEngine } from '@/services/WorkflowEngine';
import type { Intent } from '../lib/api';
import {
  MessageData,
  sendMessage,
  confirmAction,
  buildTransferTx,
  buildDeployTx,
  buildWorkflowDeployTx,
  buildContractCallTx,
  validateContractFile,
  getChatHistory,
  saveChatHistory,
  getStoredAuthToken,
  generateContract,
} from '../lib/api';
import { Bot, X } from 'lucide-react';
import ChatHeader from './ChatHeader';
import ChatInput from './ChatInput';
import { motion, AnimatePresence } from 'framer-motion';
import { useWallet } from '@/context/WalletContext';
import { useChainId } from 'wagmi';
import { DEFAULT_NETWORK, NETWORK_CONFIG, type NetworkKey } from '@/config';
import { parseEther } from 'viem';

import ChatSidebar, { type ChatSession } from './ChatSidebar';

const STORAGE_KEY_PREFIX = 'genlayer-chat-history';
const WELCOME_MESSAGE = "Hi! I'm your GenLayer AI assistant. You can check balances, send tokens, deploy contracts, or launch workflow contracts for conditional payments, escrow, subscriptions, and bounties. What would you like to do?";
const HELP_MESSAGE = `Available commands:

help - Show this command list.
check balance - Check the connected wallet balance on the selected GenLayer network.
send tokens - Prepare a wallet-side GEN transfer. Example: Send 10 GEN to 0x...
deploy contract - Start contract deployment. I will ask you to upload a .py GenLayer Intelligent Contract file.
generate contract - Describe a contract in plain English and the AI will write and deploy it for you.

WORKFLOW COMMANDS (require wallet addresses, not names):
conditional payment - Pay when a condition is met. Example: "Pay 100 GEN to 0x... if ETH reaches 10000"
escrow - Secure payment between two parties. Example: "Create escrow for 500 GEN between 0x... and 0x..."
subscription - Recurring payments. Example: "Send 50 GEN weekly to 0x..."
bounty - Reward for work. Example: "Create 1000 GEN bounty for landing page"

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
    label: 'Conditional Payment',
    command: 'Pay 100 GEN to 0x',
    description: 'Send payment when a specified condition is met. Requires recipient wallet address.',
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
    label: 'Bounty',
    command: 'Create 1000 GEN bounty for ',
    description: 'Offer a reward for completing a task or challenge.',
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

function buildWorkflowGeneratedContract(workflowConfig: NonNullable<MessageData['workflowConfig']>): NonNullable<MessageData['generatedContract']> {
  const contractName = WorkflowEngine.getContractName(workflowConfig);
  const code = WorkflowEngine.generateContractCode(workflowConfig);
  return {
    contractName,
    contractType: workflowConfig.workflowType,
    explanation: `Predefined ${workflowConfig.workflowType.replace(/_/g, ' ')} template configured from your request. You can copy/download this Python contract or deploy it directly.`,
    code,
    fileName: `${contractName}.py`,
    specification: workflowConfig as unknown as Record<string, unknown>,
    validation: {
      valid: true,
      message: 'Workflow contract template selected and configured.',
      errors: [],
      warnings: [],
      contract_names: [contractName],
    },
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
        const validation = await validateContractFile(content, file.name);
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

        const response = await sendMessage(deployCmd, connectedWallet ?? undefined, selectedNetwork);
        const normalizedIntent = response.intent && response.intent.action === 'deploy_contract'
          ? normalizeDeployIntentForUi({ ...(response.intent as Intent), code: content }, file.name)
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

      const summary = WorkflowEngine.getWorkflowSummary(workflowParse.config);
      appendMessagesToCurrentChat({
        id: (Date.now() + 1).toString(),
        role: 'bot',
        content: `Workflow ready for deployment.\n\n${summary}\n\nI selected the predefined ${WorkflowEngine.getContractName(workflowParse.config)} template and configured it from your request. Confirm to deploy it through your wallet.`,
        intent: workflowParse.intent,
        workflowConfig: workflowParse.config,
        generatedContract: buildWorkflowGeneratedContract(workflowParse.config),
        status: 'awaiting_confirmation',
      });
      return;
    }

    setIsLoading(true);

    try {
      const response = await sendMessage(userMsg.content, connectedWallet ?? undefined, selectedNetwork);
      
      // Check if this is a workflow intent
      const isWorkflowIntent = response.intent && WorkflowEngine.detectWorkflow(response.intent);
      const workflowStatus = isWorkflowIntent ? 'awaiting_confirmation' : response.status;
      
      // If it's a workflow intent, build and validate the configuration
      let workflowContent = response.content || 'An error occurred.';
      let workflowConfig: MessageData['workflowConfig'] | undefined = undefined;
      if (isWorkflowIntent && response.intent) {
        workflowConfig = WorkflowEngine.buildWorkflowConfig(response.intent) || undefined;
        if (workflowConfig) {
          const validation = WorkflowEngine.validateConfig(workflowConfig);
          if (validation.valid) {
            const summary = WorkflowEngine.getWorkflowSummary(workflowConfig);
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
        intent: response.intent,
        workflowConfig: workflowConfig || undefined,
        generatedContract: workflowConfig ? buildWorkflowGeneratedContract(workflowConfig) : response.generatedContract,
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
      let intentForConfirmation = intent;
      let txHash: string | undefined = undefined;

      const workflowType = WorkflowEngine.detectWorkflow(intent);
      if (workflowType) {
        const workflowConfig = msg.workflowConfig || WorkflowEngine.buildWorkflowConfig(intent);
        if (!workflowConfig) {
          throw new Error(`Failed to build workflow configuration for ${workflowType}`);
        }

        const validation = WorkflowEngine.validateConfig(workflowConfig);
        if (!validation.valid) {
          throw new Error(`Workflow validation failed: ${validation.errors.join(', ')}`);
        }

        const txData = await buildWorkflowDeployTx(
          {
            workflow_config: workflowConfig,
            deploy_value_wei: '0',
            gas_limit: null,
            consensus_max_rotations: null,
            leader_only: false,
          },
          connectedWallet as string,
          selectedNetwork
        );

        const deployIntent: Intent = {
          action: 'deploy_contract',
          code: txData.code,
          contract_name: txData.contractName,
          contract_type: txData.workflowConfig.workflowType,
          constructor_args: txData.constructorArgs,
          constructor_kwargs: txData.constructorKwargs,
          deploy_value: 0,
          constructor_args_text: JSON.stringify(txData.constructorArgs, null, 2),
          constructor_kwargs_text: '{}',
          deploy_value_text: '0',
          source_file_name: `${txData.contractName}.py`,
          gas_limit: null,
          gas_limit_text: '',
          consensus_max_rotations: null,
          consensus_max_rotations_text: '',
          leader_only: false,
          workflow_config: txData.workflowConfig,
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
      } else if (intent.action === 'transfer') {
        // For transfers and deployments, let the user's wallet broadcast the transaction.
        if (!intent.recipient || typeof intent.amount !== 'number') {
          throw new Error('Transfer intent is missing recipient or amount.');
        }
        const txData = await buildTransferTx(intent.recipient, intent.amount, connectedWallet as string, selectedNetwork);
        txHash = await sendTransaction({
          to: txData.to,
          value: txData.value,
          data: txData.data,
          chainId: txData.chainId,
          nonce: txData.nonce,
          gas: txData.gas,
          gasPrice: txData.gasPrice,
        });
      } else if (intent.action === 'deploy_contract') {
        if (!intent.code) {
          throw new Error('Deployment intent is missing contract code.');
        }
        const deployIntent = parseDeployIntent(intent);
        intentForConfirmation = deployIntent;
        const txData = await buildDeployTx(
          {
            code: deployIntent.code as string,
            constructor_args: deployIntent.constructor_args,
            constructor_kwargs: deployIntent.constructor_kwargs as Record<string, unknown>,
            deploy_value_wei: deployIntent.deploy_value_wei as string,
            gas_limit: deployIntent.gas_limit as number | null,
            consensus_max_rotations: deployIntent.consensus_max_rotations as number | null,
            leader_only: deployIntent.leader_only as boolean,
          },
          connectedWallet as string,
          selectedNetwork
        );
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
      }

      const result = await confirmAction(intentForConfirmation, connectedWallet, undefined, txHash, selectedNetwork);
      if (!result.error) {
        refreshBalance();
      }
      replaceMessageInCurrentChat(msgId, (message) => ({
          ...message,
          status: result.error ? 'error' : 'success',
          intent: intentForConfirmation,
          txHash: result.txHash,
          consensusTxId: result.consensusTxId,
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

    const methodMap: Record<string, { method: string; nextStatus?: string; promptLabel?: string }> = {
      cancel_contract: { method: 'cancel_contract', nextStatus: 'cancelled' },
      view_details: { method: 'status' },
      approve_release: { method: 'approve_release', nextStatus: 'completed' },
      raise_dispute: { method: 'raise_dispute', nextStatus: 'disputed' },
      cancel_escrow: { method: 'cancel_escrow', nextStatus: 'cancelled' },
      pause: { method: 'pause', nextStatus: 'paused' },
      resume: { method: 'resume', nextStatus: 'active' },
      cancel_subscription: { method: 'cancel', nextStatus: 'cancelled' },
      record_payment: { method: 'record_payment', nextStatus: 'active' },
      review_submission: { method: 'review_submission', promptLabel: 'Submitter wallet address' },
      select_winner: { method: 'select_winner', nextStatus: 'completed', promptLabel: 'Winner wallet address' },
      close_bounty: { method: 'close_bounty', nextStatus: 'completed' },
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
      appendMessagesToCurrentChat({
        id: Date.now().toString(),
        role: 'bot',
        content: `Workflow contract: ${msg.contractAddress}`,
        status: 'success',
      });
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

    const actionMessageId = Date.now().toString();
    appendMessagesToCurrentChat({
      id: actionMessageId,
      role: 'bot',
      content: `Preparing workflow action '${actionConfig.method}' for wallet signature.`,
      intent: {
        action: 'contract_call',
        contract_address: msg.contractAddress,
        method: actionConfig.method,
        args,
        kwargs: {},
        workflow_type: msg.workflowConfig.workflowType,
        next_status: actionConfig.nextStatus,
      },
      status: 'executing',
    });

    try {
      const txData = await buildContractCallTx(
        {
          contract_address: msg.contractAddress,
          method: actionConfig.method,
          args,
          kwargs: {},
          value_wei: '0',
          workflow_type: msg.workflowConfig.workflowType,
        },
        connectedWallet as string,
        selectedNetwork
      );
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

      const intent: Intent = {
        action: 'contract_call',
        contract_address: msg.contractAddress,
        method: actionConfig.method,
        args,
        kwargs: {},
        workflow_type: msg.workflowConfig.workflowType,
        next_status: actionConfig.nextStatus,
      };
      const result = await confirmAction(intent, connectedWallet, undefined, txHash, selectedNetwork);
      if (!result.error) {
        refreshBalance();
      }
      replaceMessageInCurrentChat(actionMessageId, (message) => ({
        ...message,
        status: result.error ? 'error' : 'success',
        intent,
        txHash: result.txHash,
        consensusTxId: result.consensusTxId,
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
              onRunCommand={handleQuickAction}
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
