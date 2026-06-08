// Provider presets for the settings page. Selecting a provider fills base_url +
// a model candidate list + whether an api_key is required. Almost everything is
// OpenAI-compatible (one base_url away); Anthropic is the one native chat adapter.
// Embedders exclude Anthropic — it has no embeddings API (use Voyage/OpenAI).

export type Preset = {
	id: string;
	label: string;
	base_url: string;
	models: string[];
	needs_key: boolean;
};

export const CHAT_PROVIDERS: Preset[] = [
	{ id: 'openai', label: 'OpenAI', base_url: 'https://api.openai.com/v1', models: ['gpt-4o-mini', 'gpt-4o', 'gpt-4.1', 'o4-mini'], needs_key: true },
	{ id: 'anthropic', label: 'Anthropic (native)', base_url: 'https://api.anthropic.com', models: ['claude-sonnet-4-6', 'claude-opus-4-8', 'claude-haiku-4-5'], needs_key: true },
	{ id: 'groq', label: 'Groq', base_url: 'https://api.groq.com/openai/v1', models: ['llama-3.3-70b-versatile', 'llama-3.1-8b-instant'], needs_key: true },
	{ id: 'deepseek', label: 'DeepSeek', base_url: 'https://api.deepseek.com/v1', models: ['deepseek-chat', 'deepseek-reasoner'], needs_key: true },
	{ id: 'openrouter', label: 'OpenRouter', base_url: 'https://openrouter.ai/api/v1', models: ['anthropic/claude-sonnet-4.5', 'openai/gpt-4o-mini'], needs_key: true },
	{ id: 'ollama', label: 'Ollama (本地)', base_url: 'http://localhost:11434/v1', models: ['llama3.2', 'qwen2.5', 'mistral'], needs_key: false },
	{ id: 'vllm', label: 'vLLM (本地)', base_url: 'http://localhost:8000/v1', models: [], needs_key: false },
	{ id: 'lmstudio', label: 'LM Studio (本地)', base_url: 'http://localhost:1234/v1', models: [], needs_key: false },
	{ id: 'azure', label: 'Azure OpenAI', base_url: '', models: [], needs_key: true },
	{ id: 'custom', label: '自定义 (OpenAI 兼容)', base_url: '', models: [], needs_key: false }
];

export const EMBED_PROVIDERS: Preset[] = [
	{ id: 'openai', label: 'OpenAI', base_url: 'https://api.openai.com/v1', models: ['text-embedding-3-small', 'text-embedding-3-large'], needs_key: true },
	{ id: 'ollama', label: 'Ollama (本地)', base_url: 'http://localhost:11434/v1', models: ['nomic-embed-text', 'mxbai-embed-large'], needs_key: false },
	{ id: 'voyage', label: 'Voyage', base_url: 'https://api.voyageai.com/v1', models: ['voyage-3', 'voyage-3-lite'], needs_key: true },
	{ id: 'azure', label: 'Azure OpenAI', base_url: '', models: [], needs_key: true },
	{ id: 'custom', label: '自定义 (OpenAI 兼容)', base_url: '', models: [], needs_key: false }
];

export const chatPreset = (id: string | undefined): Preset | undefined =>
	CHAT_PROVIDERS.find((p) => p.id === id);
export const embedPreset = (id: string | undefined): Preset | undefined =>
	EMBED_PROVIDERS.find((p) => p.id === id);
